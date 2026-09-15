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
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import (
    Campus,
    ClassSection,
    StudentEnrollment,
)
from src.db.sms_identity import SchoolRole
from src.db.sms_revops import AdmissionsLead
from src.db.users import User

logger = logging.getLogger(__name__)


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

    DELEGATES to `people_provisioning.provision_person`. This function used to
    carry its own copy of the create-account-grant-role-enrol sequence, and the
    copy had drifted: it never wrote the `UserOrganization` membership row.

    That omission was not cosmetic. A learner admitted through the admissions
    funnel was:

      * absent from the school's own People directory, which JOINs on
        `UserOrganization` (`routers/sms_identity.py`), so an administrator
        could not find the student they had just admitted; and
      * refused with 403 on private course content, which checks the same
        table (`routers/content_files.py`) -- the student could not open the
        materials for the course they were enrolled in.

    Their `SMSUserRole` grant worked, so the SMS modules behaved, which is
    precisely what made it hard to notice.

    There is now ONE provisioning path. `signup_method` keeps the provenance
    distinction so an admissions-funnel learner is still distinguishable from
    an administrator-created one.

    Stages everything on `session` WITHOUT committing; the caller commits once.
    """
    from src.services.sms.people_provisioning import PersonSpec, provision_person

    # org_id is required for the role grant and membership, and is not on the
    # lead -- it hangs off the campus the section belongs to. Resolved here
    # (rather than inside provision_person, which takes org_id as given)
    # because the admissions funnel identifies a school by its section.
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

    campus = await session.get(Campus, section.campus_id)
    if campus is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campus {section.campus_id} for this section no longer exists.",
        )

    # The lead carries one free-text student name; split it the way this
    # module always has. provision_person requires a first name and refuses
    # an empty one, so fall back rather than letting a nameless lead 400.
    name_parts = (lead.student_name or "").strip().split(" ", 1)
    first_name = name_parts[0] if name_parts and name_parts[0] else "Student"
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    result = await provision_person(
        session,
        PersonSpec(
            role=SchoolRole.STUDENT,
            email=student_email,
            first_name=first_name,
            last_name=last_name,
            campus_id=campus.id,
            section_id=section_id,
            academic_year_id=academic_year_id,
            roll_number=roll_number,
        ),
        org_id=campus.org_id,
        actor_user_id=None,
        signup_method="admissions_enrollment",
    )

    # The caller refreshes these objects after committing, so return the
    # instances rather than ids.
    user = await session.get(User, result.user_id)
    if user is None:  # pragma: no cover - provision_person just flushed it
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Learner account could not be read back after provisioning.",
        )

    enrollment = (
        await session.execute(
            select(StudentEnrollment).where(
                StudentEnrollment.student_id == user.id,
                StudentEnrollment.academic_year_id == academic_year_id,
            )
        )
    ).scalars().first()
    if enrollment is None:  # pragma: no cover - provision_person just flushed it
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Enrollment could not be read back after provisioning.",
        )

    logger.info(
        "Provisioned learner from lead id=%s user_id=%s (new_user=%s new_role=%s new_enrollment=%s)",
        lead.id,
        user.id,
        result.created_user,
        result.created_role,
        result.created_enrollment,
    )

    return EnrollmentProvisioningResult(
        user=user,
        enrollment=enrollment,
        created_user=result.created_user,
        created_role=result.created_role,
        created_enrollment=result.created_enrollment,
    )
