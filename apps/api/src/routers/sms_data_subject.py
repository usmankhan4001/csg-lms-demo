"""
Data-subject access and erasure endpoints (school record).

Authority model, and why it is split three ways:

* **Export** — SUPER_ADMIN / SCHOOL_ADMIN, or a PARENT for their own child via
  the `StudentGuardian` link. A parent self-serving is the whole point of a
  subject-access right; making them file a ticket with the office to see their
  own child's record is the thing the right exists to prevent.
* **Erasure** — SUPER_ADMIN / SCHOOL_ADMIN only. Deliberately NOT parents.
  Erasure is irreversible and has statutory consequences for what the school
  may still hold, so it needs school authority and a recorded decision, not a
  tap in a parent app.
* **Confidential content** — two separate tiers that mirror the gates already
  enforced elsewhere, rather than one "admin sees all" flag:
  counselling is PSYCHOLOGIST-only (`routers/sms_counseling.py` returns 404 to
  everyone else), while AI safety incidents allow school leadership
  (`routers/ai_oversight.py`). A SCHOOL_ADMIN exporting a child therefore gets
  safety incidents but **not** counselling notes, exactly as they would
  through those modules.

Every call is logged to `sms_data_subject_request` before returning.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    PSYCHOLOGIST,
    SCHOOL_ADMIN,
    SUPER_ADMIN,
    KeycloakUserPrincipal,
    get_current_user_principal,
)
from src.db.sms_identity import StudentGuardian
from src.db.users import User
from src.services.sms.data_subject import (
    collect_parent_visible_counselling,
    collect_school_record,
    erase_school_record,
    log_data_subject_request,
)

router = APIRouter()

_SCHOOL_AUTHORITY = (SUPER_ADMIN, SCHOOL_ADMIN)


def _caller_user_id(principal: KeycloakUserPrincipal) -> Optional[int]:
    return (principal.raw_claims or {}).get("lh_user_id")


async def _is_guardian_of(
    session: AsyncSession, caller_user_id: Optional[int], subject_user_id: int
) -> bool:
    if caller_user_id is None:
        return False
    row = (
        await session.execute(
            select(StudentGuardian).where(
                StudentGuardian.guardian_user_id == caller_user_id,
                StudentGuardian.student_id == subject_user_id,
            )
        )
    ).scalars().first()
    return row is not None


async def _load_subject(session: AsyncSession, user_id: int) -> User:
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found"
        )
    return user


async def _authorise(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    subject_user_id: int,
    *,
    allow_guardian: bool,
) -> tuple[bool, bool, bool]:
    """(is_school_authority, include_clinical, include_safeguarding).

    Raises 403 when the caller has no relationship to the subject at all. A
    caller may always request their OWN record.
    """
    caller_id = _caller_user_id(principal)
    is_authority = principal.is_superadmin or principal.has_any_role(list(_SCHOOL_AUTHORITY))
    is_self = caller_id is not None and caller_id == subject_user_id
    is_guardian = allow_guardian and await _is_guardian_of(session, caller_id, subject_user_id)

    if not (is_authority or is_self or is_guardian):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only request records for yourself or your own child.",
        )

    # Clinical content follows sms_counseling's PSYCHOLOGIST-only rule. Note a
    # SCHOOL_ADMIN does NOT qualify -- they get a 404 from that module today,
    # so an export must not hand them the same rows.
    include_clinical = principal.is_superadmin or principal.has_role(PSYCHOLOGIST)
    # Safety incidents follow ai_oversight's wider safeguarding gate.
    include_safeguarding = principal.is_superadmin or principal.has_any_role(
        [SUPER_ADMIN, SCHOOL_ADMIN, PSYCHOLOGIST]
    )
    return is_authority, include_clinical, include_safeguarding


@router.get(
    "/{user_id}/export",
    summary="Subject Access: export the school record",
    description=(
        "Everything the school holds about this person: enrolment, attendance, "
        "grades, report cards, exam results, fees, library loans, live-class "
        "attendance, tutor transcripts, notifications, messaging, staff and "
        "payroll records where applicable, and admissions history. "
        "Counselling and safety records appear only for a caller already "
        "entitled to see them, and are otherwise indistinguishable from absent."
    ),
    responses={403: {"description": "No relationship to this subject"}},
)
async def export_school_record(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> dict:
    _, include_clinical, include_safeguarding = await _authorise(
        session, principal, user_id, allow_guardian=True
    )
    user = await _load_subject(session, user_id)

    record = await collect_school_record(
        session,
        user,
        include_clinical=include_clinical,
        include_safeguarding=include_safeguarding,
    )

    # A guardian who is not clinically authorised still sees the slice the
    # counselling module explicitly designed for them -- summaries a
    # psychologist chose to share. Non-shared sessions stay invisible.
    caller_id = _caller_user_id(principal)
    if not include_clinical and await _is_guardian_of(session, caller_id, user_id):
        shared = await collect_parent_visible_counselling(session, user_id)
        if shared:
            record["counselling_summaries_shared_with_you"] = shared

    await log_data_subject_request(
        session,
        subject_user_id=user_id,
        requested_by_user_id=caller_id,
        requested_by_role="SUPER_ADMIN" if principal.is_superadmin else None,
        org_id=principal.org_id,
        request_type="ACCESS",
        outcome={"exported": {k: len(v) for k, v in record.items()}},
        included_confidential=include_clinical or include_safeguarding,
    )

    return {
        "subject_user_id": user_id,
        "school_record": record,
        "note": (
            "This covers records held by the school management system. "
            "Learning-platform records (courses, trails, certificates) are "
            "exported separately by the platform admin export."
        ),
    }


@router.post(
    "/{user_id}/erase",
    summary="Erasure: delete what may lawfully be deleted",
    description=(
        "Deletes AI tutor transcripts, notifications and admissions/nurture "
        "history, and scrubs personal details from lead records. Academic, "
        "financial, employment and safeguarding records are RETAINED under "
        "statutory duty; the response itemises exactly what was kept and why. "
        "Restricted to school authority -- erasure is irreversible."
    ),
    responses={403: {"description": "Requires SUPER_ADMIN or SCHOOL_ADMIN"}},
)
async def erase_school_record_endpoint(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> dict:
    is_authority, include_clinical, include_safeguarding = await _authorise(
        session, principal, user_id, allow_guardian=False
    )
    if not is_authority:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Erasure requires school authority. Ask the school office to "
                "process this request."
            ),
        )

    user = await _load_subject(session, user_id)
    outcome = await erase_school_record(
        session,
        user,
        include_clinical=include_clinical,
        include_safeguarding=include_safeguarding,
    )

    await log_data_subject_request(
        session,
        subject_user_id=user_id,
        requested_by_user_id=_caller_user_id(principal),
        requested_by_role="SUPER_ADMIN" if principal.is_superadmin else SCHOOL_ADMIN,
        org_id=principal.org_id,
        request_type="ERASURE",
        outcome=outcome,
        included_confidential=include_clinical or include_safeguarding,
    )

    return {
        "subject_user_id": user_id,
        "erased": outcome["erased"],
        "scrubbed": outcome["scrubbed"],
        "retained": outcome["retained"],
        "note": (
            "Retained records are listed individually with the basis for "
            "keeping each. They were not deleted and this response does not "
            "claim otherwise."
        ),
    }
