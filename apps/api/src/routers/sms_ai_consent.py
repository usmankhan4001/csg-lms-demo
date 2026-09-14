"""
Parental consent for a minor's AI use (M47) -- read and write surfaces.

Schools collect consent on paper and by phone as often as through a portal, so
staff must be able to record a guardian's decision on their behalf. The
guardian is always resolved server-side through `StudentGuardian`: the
recorded decision names a real guardian of that child, never whoever the
request claimed.
"""

import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    PSYCHOLOGIST,
    SCHOOL_ADMIN,
    STAFF,
    SUPER_ADMIN,
    TEACHER,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_ai_consent import (
    AIConsentDecision,
    AIConsentEnforcement,
    AIConsentType,
)
from src.security.school_ownership import (
    assert_campus_allowed,
    get_own_children_ids,
    resolve_scoped_campus_id,
)
from src.services.sms.ai_consent import (
    consent_history,
    consent_summary,
    get_org_policy,
    record_decision,
    students_missing_consent,
)

router = APIRouter()

# Who may see and record consent. PSYCHOLOGIST is included because wellbeing
# monitoring consent is directly their concern. TEACHER may READ status (they
# need to know why a pupil cannot use the tutor) but not record a decision --
# accepting a guardian's decision is an office function with a paper trail.
_CONSENT_READERS = [SUPER_ADMIN, SCHOOL_ADMIN, STAFF, PSYCHOLOGIST, TEACHER]
_CONSENT_RECORDERS = [SUPER_ADMIN, SCHOOL_ADMIN, STAFF, PSYCHOLOGIST]


class ConsentStatusRead(BaseModel):
    consent_type: AIConsentType
    decision: AIConsentDecision
    allowed: bool
    reason: Optional[str] = None


class ConsentEventRead(BaseModel):
    id: int
    student_id: int
    consent_type: AIConsentType
    decision: AIConsentDecision
    guardian_user_id: int
    recorded_by_user_id: int
    source: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime.datetime


class RecordConsentRequest(BaseModel):
    consent_type: AIConsentType
    decision: AIConsentDecision
    guardian_user_id: int
    source: Optional[str] = None
    note: Optional[str] = None


class ConsentPolicyRead(BaseModel):
    org_id: int
    enforcement: AIConsentEnforcement
    crisis_override_enabled: bool


async def _assert_may_view_student(
    principal: KeycloakUserPrincipal, student_id: int, db_session: AsyncSession
) -> None:
    """Staff may view any student in their org; a guardian only their own child."""
    if principal.is_superadmin or principal.has_any_role(_CONSENT_READERS):
        return
    caller_id = (principal.raw_claims or {}).get("lh_user_id")
    if caller_id is not None:
        if caller_id == student_id:
            return
        if student_id in await get_own_children_ids(caller_id, db_session):
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You may only view consent for your own children.",
    )


@router.get(
    "/students/{student_id}",
    response_model=List[ConsentStatusRead],
    summary="Current AI Consent Status For A Student",
)
async def api_get_consent_status(
    student_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ConsentStatusRead]:
    await _assert_may_view_student(principal, student_id, db_session)
    statuses = await consent_summary(db_session, student_id, principal.org_id)
    return [
        ConsentStatusRead(
            consent_type=s.consent_type,
            decision=s.decision,
            allowed=s.allowed,
            reason=s.reason,
        )
        for s in statuses
    ]


@router.get(
    "/students/{student_id}/history",
    response_model=List[ConsentEventRead],
    summary="Full AI Consent History For A Student",
    description=(
        "Append-only history. A withdrawal never erases the fact consent was "
        "previously given -- a school asked 'was this child covered last March?' "
        "needs a truthful answer."
    ),
)
async def api_get_consent_history(
    student_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ConsentEventRead]:
    await _assert_may_view_student(principal, student_id, db_session)
    events = await consent_history(db_session, student_id)
    return [ConsentEventRead.model_validate(e, from_attributes=True) for e in events]


@router.post(
    "/students/{student_id}",
    response_model=ConsentEventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record A Guardian's AI Consent Decision",
    description=(
        "Appends a decision. The guardian is verified against StudentGuardian "
        "server-side: a caller cannot record a decision naming someone who is "
        "not that child's guardian."
    ),
    responses={403: {"description": "Not a recorded guardian of this student"}},
)
async def api_record_consent(
    student_id: int,
    payload: RecordConsentRequest,
    campus_id: Optional[int] = Query(None),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CONSENT_RECORDERS)),
) -> ConsentEventRead:
    if principal.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your session is not scoped to a school organisation.",
        )
    assert_campus_allowed(principal, campus_id)
    recorded_by = (principal.raw_claims or {}).get("lh_user_id")
    if not isinstance(recorded_by, int):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve your user account; cannot attribute this decision.",
        )

    event = await record_decision(
        db_session,
        student_id=student_id,
        consent_type=payload.consent_type,
        decision=payload.decision,
        guardian_user_id=payload.guardian_user_id,
        recorded_by_user_id=recorded_by,
        org_id=principal.org_id,
        campus_id=resolve_scoped_campus_id(principal, campus_id),
        source=payload.source,
        note=payload.note,
    )
    return ConsentEventRead.model_validate(event, from_attributes=True)


@router.get(
    "/missing",
    response_model=List[int],
    summary="Students With No Recorded Consent Decision",
    description=(
        "The chase list. This is what makes ADVISORY enforcement defensible "
        "rather than merely permissive: a school can see exactly who it still "
        "has to ask before switching to STRICT."
    ),
)
async def api_students_missing_consent(
    consent_type: AIConsentType = Query(AIConsentType.AI_TUTOR),
    campus_id: Optional[int] = Query(None),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CONSENT_RECORDERS)),
) -> List[int]:
    if principal.org_id is None:
        return []
    return await students_missing_consent(
        db_session,
        org_id=principal.org_id,
        consent_type=consent_type,
        campus_id=resolve_scoped_campus_id(principal, campus_id),
    )


@router.get(
    "/policy",
    response_model=ConsentPolicyRead,
    summary="This Organisation's AI Consent Enforcement Policy",
)
async def api_get_policy(
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CONSENT_READERS)),
) -> ConsentPolicyRead:
    policy = await get_org_policy(db_session, principal.org_id)
    return ConsentPolicyRead(
        org_id=policy.org_id,
        enforcement=AIConsentEnforcement(policy.enforcement),
        crisis_override_enabled=bool(policy.crisis_override_enabled),
    )
