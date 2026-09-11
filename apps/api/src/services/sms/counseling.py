"""
CSG-LMS Counseling / Wellbeing / Career Guidance service layer (Phase 4, Part B).

CONFIDENTIALITY RULE (DESIGN-SYSTEM.md §4, §10 — mandatory, not optional):
for psychologist/confidential records, an unauthorized role must get an
EMPTY result (200 with an empty list, or 404), NEVER a 403 — a 403 itself
would confirm to that role that a counseling record exists for this student.

This mirrors src/routers/integrations/zapier.py's shape ("scope the query to
the requester, generic 404 on no-match"), adapted here to: scope to
PSYCHOLOGIST-authored records (`psychologist_id` bound to the authenticated
principal's Keycloak `sub` at write time — never trusted from the request
body, exactly like zapier scoping to `api_user.org_id` from the token rather
than a client-supplied field), or to the student/parent themselves for the
narrow parent-visible slice of their own record. Every other role
(TEACHER/SCHOOL_ADMIN/...) gets the empty result unconditionally.

This is a DELIBERATE, SCOPED exception to this app's general authorization
idiom, confined to this module only. It is the OPPOSITE of
src/services/users/usergroups.py:301-304, which raises 403 before an
empty-result shortcut specifically to prevent an anonymous-existence-oracle
on usergroup resources — a different, unrelated concern for a different
module. That file is intentionally left untouched.

Career guidance (CareerGuidancePlan) is NOT subject to this masking: it is
academic/advisory data, not a clinical record (see db/sms_counseling.py).
"""

import datetime
import logging
from typing import List, Optional

from sqlalchemy import and_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import KeycloakUserPrincipal, PARENT, PSYCHOLOGIST, STUDENT
from src.db.sms_counseling import CareerGuidancePlan, CounselingActivityLog, CounselingSession
from src.schemas.sms_counseling import (
    ActivityLogCreate,
    CareerGuidanceGenerateRequest,
    CareerGuidancePlanGenerated,
    CounselingSessionCreate,
    CounselingSessionUpdate,
)
from src.services.ai.llm import generate, model_for_tier

logger = logging.getLogger(__name__)


def _is_psychologist(principal: KeycloakUserPrincipal) -> bool:
    return principal.has_role(PSYCHOLOGIST)


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# ---------------------------------------------------------------------------
# 1. Psychologist activity tracking
# ---------------------------------------------------------------------------

async def create_activity_log(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    payload: ActivityLogCreate,
) -> CounselingActivityLog:
    """Caller must already be verified PSYCHOLOGIST by the router. The
    authored-by identity is stamped from the authenticated principal, never
    from the request body."""
    record = CounselingActivityLog(
        student_id=payload.student_id,
        psychologist_id=principal.sub,
        signal_type=payload.signal_type,
        description=payload.description,
        severity=payload.severity,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def list_activity_logs_for_viewer(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    student_id: int,
) -> List[CounselingActivityLog]:
    """Confidentiality-preserving read: a PSYCHOLOGIST sees only the signals
    THEY logged for this student; every other role (and a different
    PSYCHOLOGIST who never logged anything for this student) gets an empty
    list -- never a 403 -- so existence can never be inferred."""
    if not _is_psychologist(principal):
        return []
    stmt = (
        select(CounselingActivityLog)
        .where(
            and_(
                CounselingActivityLog.student_id == student_id,
                CounselingActivityLog.psychologist_id == principal.sub,
            )
        )
        .order_by(CounselingActivityLog.recorded_at.desc())
    )
    return (await session.execute(stmt)).scalars().all()


# ---------------------------------------------------------------------------
# 2. Structured 1:1 session logging + parent involvement
# ---------------------------------------------------------------------------

async def create_session(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    payload: CounselingSessionCreate,
) -> CounselingSession:
    record = CounselingSession(
        student_id=payload.student_id,
        psychologist_id=principal.sub,
        session_date=payload.session_date,
        duration_minutes=payload.duration_minutes,
        notes=payload.notes,
        follow_up_plan=payload.follow_up_plan,
        share_summary_with_parent=payload.share_summary_with_parent,
        parent_visible_summary=payload.parent_visible_summary,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_session_for_psychologist(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    session_id: int,
) -> Optional[CounselingSession]:
    """Returns None (never raises) for anyone but the authoring PSYCHOLOGIST
    -- the router turns None into a plain 404, identical whether the record
    doesn't exist or the caller simply isn't authorized to see it."""
    if not _is_psychologist(principal):
        return None
    record = await session.get(CounselingSession, session_id)
    if record is None or record.psychologist_id != principal.sub:
        return None
    return record


async def list_sessions_for_viewer(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    student_id: int,
) -> List[CounselingSession]:
    if not _is_psychologist(principal):
        return []
    stmt = (
        select(CounselingSession)
        .where(
            and_(
                CounselingSession.student_id == student_id,
                CounselingSession.psychologist_id == principal.sub,
            )
        )
        .order_by(CounselingSession.session_date.desc())
    )
    return (await session.execute(stmt)).scalars().all()


async def update_session(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    session_id: int,
    payload: CounselingSessionUpdate,
) -> Optional[CounselingSession]:
    record = await get_session_for_psychologist(session, principal, session_id)
    if record is None:
        return None
    if payload.notes is not None:
        record.notes = payload.notes
    if payload.follow_up_plan is not None:
        record.follow_up_plan = payload.follow_up_plan
    if payload.share_summary_with_parent is not None:
        record.share_summary_with_parent = payload.share_summary_with_parent
    if payload.parent_visible_summary is not None:
        record.parent_visible_summary = payload.parent_visible_summary
    record.updated_at = _utcnow()
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def list_parent_visible_sessions(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    student_id: int,
) -> List[CounselingSession]:
    """The parent-involvement slice: only sessions explicitly flagged
    `share_summary_with_parent`, visible to the STUDENT/PARENT role. Every
    other role gets an empty list here too (this accessor is not the
    PSYCHOLOGIST's full-record view)."""
    if not principal.has_any_role([PARENT, STUDENT]):
        return []
    stmt = (
        select(CounselingSession)
        .where(
            and_(
                CounselingSession.student_id == student_id,
                CounselingSession.share_summary_with_parent == True,  # noqa: E712
            )
        )
        .order_by(CounselingSession.session_date.desc())
    )
    return (await session.execute(stmt)).scalars().all()


# ---------------------------------------------------------------------------
# 3. Career guidance — structured plan, not open chat
# ---------------------------------------------------------------------------

CAREER_GUIDANCE_SYSTEM_PROMPT = """You are a school career-guidance counselor AI helping plan a student's academic/career pathway.

Given the student's academic profile (grades, and stated interests if provided), produce:
- 2-4 suggested pathways, each with a short reasoning tied to the specific evidence given
  (do not suggest a pathway with no supporting evidence in the profile).
- An overall reasoning summary connecting the profile to the suggestions.
- Concrete, achievable next steps the student can take this term (courses to consider,
  clubs/activities, skills to build).

Stay strictly within academic/career guidance. Do not discuss mental health, do not
diagnose, do not make promises about admissions or outcomes. Return ONLY the structured
plan."""


async def generate_career_guidance_plan(
    *,
    session: AsyncSession,
    principal: Optional[KeycloakUserPrincipal],
    payload: CareerGuidanceGenerateRequest,
    academic_summary: str,
    model_name: Optional[str] = None,
) -> CareerGuidancePlan:
    """Single generate-and-store operation (not a conversational agent).
    Reuses the shared provider-agnostic LLM layer (src.services.ai.llm) --
    the same abstraction the Socratic Tutor and AI assignment generator use."""
    user_prompt = f"Student academic profile:\n{academic_summary}\n"
    if payload.interests:
        user_prompt += f"Stated interests: {', '.join(payload.interests)}\n"
    if payload.extra_context:
        user_prompt += f"Additional context: {payload.extra_context}\n"

    generated: CareerGuidancePlanGenerated = await generate(
        model_name=model_name or model_for_tier("standard"),
        user_prompt=user_prompt,
        system_prompt=CAREER_GUIDANCE_SYSTEM_PROMPT,
        output_type=CareerGuidancePlanGenerated,
    )

    record = CareerGuidancePlan(
        student_id=payload.student_id,
        generated_by=principal.sub if principal else None,
        suggested_pathways=[p.model_dump() for p in generated.suggested_pathways],
        reasoning=generated.reasoning,
        next_steps=list(generated.next_steps),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def list_career_plans(session: AsyncSession, student_id: int) -> List[CareerGuidancePlan]:
    """Not confidentiality-masked (see module docstring) -- a plain scoped
    list, same style as any other SMS read."""
    stmt = (
        select(CareerGuidancePlan)
        .where(CareerGuidancePlan.student_id == student_id)
        .order_by(CareerGuidancePlan.generated_at.desc())
    )
    return (await session.execute(stmt)).scalars().all()
