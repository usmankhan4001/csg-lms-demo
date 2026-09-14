"""
Admissions -> enrollment provisioning (M21-M28 closing step).

Until this existed, moving a lead to ENROLLED was a bare field update: the
pipeline recorded a win and nothing happened. No learner account, no
`SMSUserRole` grant, no `StudentEnrollment` row -- so a "won" lead never
became a student, and the admissions funnel terminated in a dead end.

This closes that loop. Three design rules, each driven by a real failure mode:

1. **Idempotent.** Re-transitioning a lead to ENROLLED (a double-click, a
   retried request, a lead moved out and back) must never mint a second
   account. Every step checks for its own prior result first and reuses it,
   so the operation converges on one outcome rather than accumulating rows.

2. **All-or-nothing.** A lead left with a user account but no enrollment is
   worse than one left untouched: it is invisible to every school module
   while occupying an email address. Everything below is staged in ONE
   transaction and committed once, at the end, by the caller. On any raised
   error nothing is flushed to disk, so a failure leaves the lead exactly as
   it was.

3. **No fabricated contact data.** `AdmissionsLead.email`/`phone` belong to
   the PARENT (the model carries `parent_name` beside `student_name`); the
   student has no address of their own. The webhook path was previously
   found synthesising `lead_<timestamp>@inquiry.local` addresses, which
   polluted the CRM with unreachable records and defeated de-duplication.
   So the student's email is required explicitly from the caller rather than
   invented here.
"""

import logging
import secrets
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import (
    AcademicYear,
    Campus,
    ClassSection,
    StudentEnrollment,
    get_utc_now_iso,
)
from src.db.sms_identity import SchoolRole, SMSUserRole
from src.db.sms_revops import AdmissionsLead
from src.db.users import User
from src.security.security import security_hash_password

logger = logging.getLogger(__name__)


def _unusable_password_hash() -> str:
    """A valid Argon2 hash of a secret generated and immediately discarded.

    Deliberately not an empty string: `pwdlib` raises `UnknownHashError` on a
    hash it cannot identify and `authenticate_user` does not guard that call,
    so a blank password would turn a login attempt against a newly enrolled
    student into a 500 rather than a clean 401. The student gets a real
    password later through the normal reset/invite flow; no plaintext for
    this one exists anywhere. Mirrors `services/demo/sync.py`.
    """
    return security_hash_password(secrets.token_urlsafe(64))


class EnrollmentProvisioningResult:
    """What provisioning actually did, so the caller can report honestly
    rather than always claiming a fresh enrollment."""

    def __init__(
        self,
        user: User,
        enrollment: StudentEnrollment,
        created_user: bool,
        created_role: bool,
        created_enrollment: bool,
    ) -> None:
        self.user = user
        self.enrollment = enrollment
        self.created_user = created_user
        self.created_role = created_role
        self.created_enrollment = created_enrollment

    @property
    def already_provisioned(self) -> bool:
        return not (self.created_user or self.created_role or self.created_enrollment)


async def provision_learner_from_lead(
    session: AsyncSession,
    lead: AdmissionsLead,
    *,
    section_id: int,
    academic_year_id: int,
    student_email: str,
    roll_number: Optional[str] = None,
) -> EnrollmentProvisioningResult:
    """Turn a won lead into a real student: account -> STUDENT role -> enrollment.

    Stages everything on `session` WITHOUT committing. The caller commits once,
    so a later failure in the same request rolls the whole thing back and the
    lead is never left half-enrolled.

    Raises 4xx with an actionable message when the school structure needed to
    enrol into does not exist yet -- setup guidance, not a 500.
    """
    # --- Validate the target structure before creating anything ------------
    section = await session.get(ClassSection, section_id)
    if section is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Class section {section_id} does not exist. Create a campus, "
                "academic year and class section under Campus & academic "
                "structure before enrolling a lead."
            ),
        )

    year = await session.get(AcademicYear, academic_year_id)
    if year is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Academic year {academic_year_id} does not exist. Create one "
                "for this campus before enrolling a lead."
            ),
        )

    if year.campus_id != section.campus_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The academic year and class section belong to different "
                "campuses. A student cannot be enrolled across campuses."
            ),
        )

    # org_id is required for the role grant and is not on the lead -- it hangs
    # off the campus the section belongs to.
    campus = await session.get(Campus, section.campus_id)
    if campus is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campus {section.campus_id} for this section no longer exists.",
        )

    normalized_email = (student_email or "").strip().lower()
    if not normalized_email or "@" not in normalized_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A student email is required to create the learner account. "
                "The lead's email belongs to the parent, so it is not assumed "
                "to be the student's."
            ),
        )

    # --- 1. The learner account (idempotent on email) ----------------------
    existing_user = (
        await session.execute(select(User).where(User.email == normalized_email))
    ).scalars().first()

    created_user = False
    if existing_user is not None:
        user = existing_user
    else:
        # Username must be unique too; derive from the email local part and
        # disambiguate rather than colliding.
        base_username = normalized_email.split("@")[0][:40] or "student"
        username = base_username
        clash = (
            await session.execute(select(User).where(User.username == username))
        ).scalars().first()
        if clash is not None:
            username = f"{base_username}-{uuid4().hex[:6]}"

        name_parts = (lead.student_name or "").strip().split(" ", 1)
        user = User(
            username=username,
            first_name=name_parts[0] if name_parts and name_parts[0] else "Student",
            last_name=name_parts[1] if len(name_parts) > 1 else "",
            email=normalized_email,
            password=_unusable_password_hash(),
            user_uuid=f"user_{uuid4()}",
            email_verified=False,
            signup_method="admissions_enrollment",
            creation_date=get_utc_now_iso(),
            update_date=get_utc_now_iso(),
        )
        session.add(user)
        # Flush (not commit) so the FKs below have a real user id while the
        # whole thing stays inside the caller's transaction.
        await session.flush()
        created_user = True

    # --- 2. The STUDENT role grant (idempotent on the unique constraint) ---
    existing_role = (
        await session.execute(
            select(SMSUserRole).where(
                SMSUserRole.user_id == user.id,
                SMSUserRole.org_id == campus.org_id,
                SMSUserRole.role == SchoolRole.STUDENT,
            )
        )
    ).scalars().first()

    created_role = False
    if existing_role is None:
        session.add(
            SMSUserRole(
                user_id=user.id,
                org_id=campus.org_id,
                campus_id=campus.id,
                role=SchoolRole.STUDENT,
                is_active=True,
            )
        )
        created_role = True
    elif not existing_role.is_active:
        # A previously revoked student returning: reactivate rather than
        # inserting a duplicate the unique constraint would reject anyway.
        existing_role.is_active = True
        existing_role.campus_id = campus.id
        session.add(existing_role)
        created_role = True

    # --- 3. The enrollment (idempotent per academic year) ------------------
    existing_enrollment = (
        await session.execute(
            select(StudentEnrollment).where(
                StudentEnrollment.student_id == user.id,
                StudentEnrollment.academic_year_id == academic_year_id,
            )
        )
    ).scalars().first()

    created_enrollment = False
    if existing_enrollment is not None:
        enrollment = existing_enrollment
    else:
        enrollment = StudentEnrollment(
            student_id=user.id,
            section_id=section_id,
            academic_year_id=academic_year_id,
            roll_number=roll_number,
            status="active",
            enrolled_at=get_utc_now_iso(),
        )
        session.add(enrollment)
        await session.flush()
        created_enrollment = True

    logger.info(
        "Provisioned learner from lead id=%s user_id=%s (new_user=%s new_role=%s new_enrollment=%s)",
        lead.id,
        user.id,
        created_user,
        created_role,
        created_enrollment,
    )

    return EnrollmentProvisioningResult(
        user=user,
        enrollment=enrollment,
        created_user=created_user,
        created_role=created_role,
        created_enrollment=created_enrollment,
    )
