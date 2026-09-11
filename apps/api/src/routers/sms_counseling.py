"""
CSG-LMS Counseling / Wellbeing / Career Guidance router (Phase 4, Part B).

Mount pattern matches the other SMS routers exactly (see
src/routers/sms_attendance.py): router-level
`dependencies=[Depends(require_tutor_counseling_feature)]` plus a per-handler
`Depends(get_current_user_principal)`. Mounted in src/router.py WITHOUT any
router-mount-level Learnhouse-native auth dependency, to avoid reintroducing
the double-auth-gate bug fixed for the other 8 SMS routers (see
src/tests/routers/test_sms_router_mount_auth.py).

CONFIDENTIALITY (DESIGN-SYSTEM.md §4/§10 — mandatory): every activity-log and
session endpoint below returns an EMPTY result (200 empty list, or 404) to an
unauthorized caller — NEVER a 403. A 403 would itself confirm to a
TEACHER/SCHOOL_ADMIN that a counseling record exists for this student. This
rule is scoped to THIS module only (see src/services/sms/counseling.py
module docstring for the full rationale and the explicit contrast with
src/services/users/usergroups.py:301-304, which is left untouched).

Career guidance (§3) is NOT a confidential clinical record and uses ordinary
403s for role checks, like the rest of the app.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    PSYCHOLOGIST,
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    TEACHER,
    get_current_user_principal,
)
from src.db.sms_gradebook import TermReportCard
from src.schemas.sms_counseling import (
    ActivityLogCreate,
    ActivityLogRead,
    CareerGuidanceGenerateRequest,
    CareerGuidancePlanRead,
    CounselingSessionCreate,
    CounselingSessionRead,
    CounselingSessionUpdate,
    ParentVisibleSessionSummary,
)
from src.security.features_utils.dependencies import require_tutor_counseling_feature
from src.services.ai.llm import AINotConfiguredError
from src.services.sms import counseling as counseling_service

router = APIRouter(dependencies=[Depends(require_tutor_counseling_feature)])

# Staff roles permitted to generate a (non-confidential) career guidance plan.
CAREER_GUIDANCE_STAFF_ROLES = [SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, PSYCHOLOGIST]

def _confidential_not_found() -> HTTPException:
    """A generic 404, deliberately indistinguishable from 'record does not
    exist' -- never a 403. See module docstring."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


# ---------------------------------------------------------------------------
# 1. Psychologist activity tracking
# ---------------------------------------------------------------------------

@router.post(
    "/activity-logs",
    response_model=ActivityLogRead,
    status_code=status.HTTP_201_CREATED,
    summary="Log a Counseling-Relevant Activity Signal",
    description="PSYCHOLOGIST-only. Any other role gets a generic 404, never a 403.",
)
async def create_activity_log_endpoint(
    payload: ActivityLogCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> ActivityLogRead:
    if not principal.has_role(PSYCHOLOGIST):
        raise _confidential_not_found()
    record = await counseling_service.create_activity_log(session, principal, payload)
    return ActivityLogRead.model_validate(record)


@router.get(
    "/activity-logs/student/{student_id}",
    response_model=List[ActivityLogRead],
    summary="List a Student's Counseling Activity Signals",
    description=(
        "PSYCHOLOGIST-only, scoped to signals THEY logged. Every other role "
        "(TEACHER, SCHOOL_ADMIN, a different PSYCHOLOGIST, ...) gets an "
        "empty list -- never a 403 -- so existence can never be inferred."
    ),
)
async def list_activity_logs_endpoint(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ActivityLogRead]:
    records = await counseling_service.list_activity_logs_for_viewer(session, principal, student_id)
    return [ActivityLogRead.model_validate(r) for r in records]


# ---------------------------------------------------------------------------
# 2. Structured 1:1 session logging + parent involvement
# ---------------------------------------------------------------------------

@router.post(
    "/sessions",
    response_model=CounselingSessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Log a 1:1 Counseling Session",
    description="PSYCHOLOGIST-only. Any other role gets a generic 404, never a 403.",
)
async def create_session_endpoint(
    payload: CounselingSessionCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> CounselingSessionRead:
    if not principal.has_role(PSYCHOLOGIST):
        raise _confidential_not_found()
    record = await counseling_service.create_session(session, principal, payload)
    return CounselingSessionRead.model_validate(record)


@router.get(
    "/sessions/student/{student_id}",
    response_model=List[CounselingSessionRead],
    summary="List a Student's Full Counseling Sessions",
    description=(
        "PSYCHOLOGIST-only full record, scoped to sessions THEY logged. "
        "Every other role gets an empty list -- never a 403. PARENT/STUDENT "
        "use GET .../parent-summary instead for the narrow shared slice."
    ),
)
async def list_sessions_endpoint(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[CounselingSessionRead]:
    records = await counseling_service.list_sessions_for_viewer(session, principal, student_id)
    return [CounselingSessionRead.model_validate(r) for r in records]


@router.get(
    "/sessions/{session_id}",
    response_model=CounselingSessionRead,
    summary="Get a Counseling Session by ID",
    description="PSYCHOLOGIST-only (the author). Every other caller gets a generic 404.",
)
async def get_session_endpoint(
    session_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> CounselingSessionRead:
    record = await counseling_service.get_session_for_psychologist(session, principal, session_id)
    if record is None:
        raise _confidential_not_found()
    return CounselingSessionRead.model_validate(record)


@router.patch(
    "/sessions/{session_id}",
    response_model=CounselingSessionRead,
    summary="Edit a Counseling Session",
    description="PSYCHOLOGIST-only (the author). Every other caller gets a generic 404.",
)
async def update_session_endpoint(
    session_id: int,
    payload: CounselingSessionUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> CounselingSessionRead:
    record = await counseling_service.update_session(session, principal, session_id, payload)
    if record is None:
        raise _confidential_not_found()
    return CounselingSessionRead.model_validate(record)


@router.get(
    "/sessions/student/{student_id}/parent-summary",
    response_model=List[ParentVisibleSessionSummary],
    summary="Parent-Visible Session Summaries",
    description=(
        "The parent-involvement slice: only sessions the psychologist "
        "explicitly flagged share_summary_with_parent. Visible to the "
        "STUDENT/PARENT role; every other role gets an empty list."
    ),
)
async def list_parent_visible_sessions_endpoint(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ParentVisibleSessionSummary]:
    records = await counseling_service.list_parent_visible_sessions(session, principal, student_id)
    return [ParentVisibleSessionSummary.model_validate(r) for r in records]


# ---------------------------------------------------------------------------
# 3. Career guidance -- structured plan, not open chat (not confidential)
# ---------------------------------------------------------------------------

async def _build_academic_summary(session: AsyncSession, student_id: int) -> str:
    """Grounds the career-guidance generation in the student's real academic
    profile by reusing the existing gradebook data (Part A.4's
    TermReportCard) rather than inventing a parallel data source."""
    stmt = (
        select(TermReportCard)
        .where(TermReportCard.student_id == student_id)
        .order_by(TermReportCard.calculated_at.desc())
    )
    record = (await session.execute(stmt)).scalars().first()
    if record is None:
        return "No academic record on file yet."

    lines = [f"Cumulative GPA: {record.gpa}", f"Overall grade: {record.letter_grade or 'N/A'}"]
    for c in record.course_summaries or []:
        lines.append(
            f"- {c.get('course_name') or c.get('course_id')}: "
            f"{c.get('letter_grade')} ({c.get('total_weighted_percentage')}%)"
        )
    return "\n".join(lines)


@router.post(
    "/career-guidance/generate",
    response_model=CareerGuidancePlanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a Structured Career Guidance Plan",
    description=(
        "Generates a structured CareerGuidancePlan (pathways, reasoning, next "
        "steps) grounded in the student's academic profile. A single "
        "generate-and-store operation, not a conversational agent."
    ),
)
async def generate_career_guidance_endpoint(
    payload: CareerGuidanceGenerateRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> CareerGuidancePlanRead:
    if not principal.has_any_role(CAREER_GUIDANCE_STAFF_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only counseling/teaching staff can generate a career guidance plan.",
        )
    academic_summary = await _build_academic_summary(session, payload.student_id)
    try:
        record = await counseling_service.generate_career_guidance_plan(
            session=session,
            principal=principal,
            payload=payload,
            academic_summary=academic_summary,
        )
    except AINotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Career guidance plan generation failed. Please try again.",
        )
    return CareerGuidancePlanRead.model_validate(record)


@router.get(
    "/career-guidance/student/{student_id}",
    response_model=List[CareerGuidancePlanRead],
    summary="List a Student's Career Guidance Plans",
    description="Not confidential -- visible to school staff and to the student/parent themselves.",
)
async def list_career_guidance_endpoint(
    student_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[CareerGuidancePlanRead]:
    records = await counseling_service.list_career_plans(session, student_id)
    return [CareerGuidancePlanRead.model_validate(r) for r in records]
