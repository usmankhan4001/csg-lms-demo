"""
Administrator-driven account provisioning for a school.

Before this, a school could grant a role but could not create the person to
grant it to. `POST /sms/identity/roles` takes a `user_id` that must already
exist, and the only ways to mint a user were the public signup endpoints
(`routers/users.py`), which require the *person themselves* to choose a
password and submit the form. For an online school -- no office to walk into,
no front desk -- that meant a new teacher could not be onboarded at all
without someone opening a psql prompt. That is the gap this closes.

Three rules, each with a specific failure mode behind it:

1. **All-or-nothing.** A person left with an account but no role is worse than
   one never created: they can sign in, see nothing, and the admin's screen
   says it worked. Everything here is staged on the caller's session and
   committed once, by the caller, so any raised error rolls the whole person
   back.

2. **No password ever exists.** `_unusable_password_hash()` -- lifted straight
   from `services/sms/revops_enrollment.py`, which took it from
   `services/demo/sync.py` -- stores an Argon2 hash of a secret generated and
   immediately discarded. There is no plaintext, no default, and nothing to
   return to the administrator. The person gets a real password through the
   normal reset flow. A shared default password across a cohort of 50 student
   accounts is a school-wide compromise, so this path makes one impossible
   rather than merely discouraged.

3. **Idempotent on email.** Re-submitting a row (a retried import, a
   double-clicked form, a family listed twice in a spreadsheet) attaches the
   role to the existing account rather than failing or minting a duplicate.
   The result says which happened; the caller reports it honestly instead of
   always claiming a fresh account.

Deliberately NOT reusing `services/users/users.py::create_user`: it commits
twice mid-way (so it cannot participate in an all-or-nothing transaction),
requires a plaintext password it then complexity-checks, runs an RBAC check
against a `Request`, and sends a self-signup verification email. Every one of
those is wrong for an administrator creating somebody else's account. It does
one thing this must not skip, though -- the `UserOrganization` membership row
-- and that is replicated below.
"""

import logging
import secrets
from dataclasses import dataclass
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
from src.db.sms_identity import (
    PersonProvisioningAction,
    SchoolRole,
    SMSPersonProvisioningEvent,
    SMSUserRole,
    StudentGuardian,
)
from src.db.user_organizations import UserOrganization
from src.db.users import User
from src.security.security import security_hash_password

logger = logging.getLogger(__name__)

# Matches `services/users/users.py::create_user` and `services/demo/sync.py`,
# both of which attach a new member with role_id 4. Not re-derived here: an
# account provisioned with a different platform role would behave differently
# from one that signed itself up, for no reason a school could explain.
LEARNER_ROLE_ID = 4


# ---------------------------------------------------------------------------
# Which roles may be handed out here
# ---------------------------------------------------------------------------
#
# SUPER_ADMIN is absent, permanently and deliberately.
#
# SUPER_ADMIN is cross-organization platform control: `has_role()` returns
# True for it against EVERY role check in the codebase, `require_roles()`
# short-circuits on it before evaluating anything, and
# `resolve_scoped_campus_id` / `assert_campus_allowed` both exempt it from
# campus isolation entirely. A form that mints accounts is the last place that
# should be reachable from.
#
# The concrete escalation this forecloses: a SCHOOL_ADMIN is allowed to
# provision, so without this list they could provision an account holding
# SUPER_ADMIN, sign into it, and hold every other tenant's data. Restricting
# it to "only a superadmin may grant SUPER_ADMIN" would not be enough either
# -- it has no legitimate use on a school-administration screen at all, so it
# is not offered to anyone here. Granting it stays a deliberate act outside
# this surface.
PROVISIONABLE_ROLES = frozenset(
    {
        SchoolRole.SCHOOL_ADMIN,
        SchoolRole.TEACHER,
        SchoolRole.STUDENT,
        SchoolRole.PARENT,
        SchoolRole.STAFF,
        SchoolRole.PSYCHOLOGIST,
    }
)


def _unusable_password_hash() -> str:
    """A valid Argon2 hash of a secret generated and immediately discarded.

    Deliberately not an empty string: `pwdlib` raises `UnknownHashError` on a
    hash it cannot identify and `authenticate_user` does not guard that call,
    so a blank password would turn a login attempt against a newly provisioned
    teacher into a 500 rather than a clean 401. Mirrors
    `services/sms/revops_enrollment.py` and `services/demo/sync.py`.
    """
    return security_hash_password(secrets.token_urlsafe(64))


@dataclass
class PersonSpec:
    """One person to provision. Mirrors the API payload, kept separate from it
    so the service is callable from a script or another service."""

    role: SchoolRole
    email: str
    first_name: str
    last_name: str = ""
    campus_id: Optional[int] = None

    # STUDENT only: enrol in one step. A student with no enrollment is
    # invisible to attendance, gradebook and fees -- a school would create a
    # cohort and find every module empty.
    section_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    roll_number: Optional[str] = None

    # PARENT only: link to a child in one step. A parent account with no
    # child linked can see nothing at all.
    child_student_id: Optional[int] = None
    relationship: Optional[str] = None
    is_primary_contact: bool = False


@dataclass
class ProvisionResult:
    """What provisioning actually did, so the caller reports the truth rather
    than always claiming a new account."""

    user_id: int
    email: str
    role: SchoolRole
    created_user: bool
    created_role: bool
    created_enrollment: bool
    created_guardian_link: bool


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _normalize_email(raw: str) -> str:
    email = (raw or "").strip().lower()
    # Not a full RFC check -- deliberately the same shallow test
    # `revops_enrollment.py` applies, since the real validation is that a
    # human can receive the invite, which only delivery can prove.
    if not email or "@" not in email or email.startswith("@") or email.endswith("@"):
        raise _bad_request(
            f"{raw!r} is not a usable email address. Every account needs a real "
            "address: it is the only way the person can set their password."
        )
    return email


async def _unique_username(session: AsyncSession, email: str) -> str:
    """Derive a username from the email local part, disambiguating on clash.

    `User.username` is unique, so two people at `ali@` on different domains
    would otherwise collide and fail the second import row for a reason the
    administrator could neither see nor act on.
    """
    base = email.split("@")[0][:40] or "member"
    clash = (await session.execute(select(User).where(User.username == base))).scalars().first()
    if clash is None:
        return base
    return f"{base}-{uuid4().hex[:6]}"


async def _validate_student_placement(
    session: AsyncSession, spec: PersonSpec, campus: Campus
) -> None:
    """Reject an enrolment target that does not exist or is at another campus.

    Checked BEFORE anything is created, so a bad section id leaves no orphan
    account behind.
    """
    section = await session.get(ClassSection, spec.section_id)
    if section is None:
        raise _bad_request(
            f"Class section {spec.section_id} does not exist. Create the campus, "
            "academic year and class section under Campus & academic structure "
            "before enrolling students into it."
        )
    year = await session.get(AcademicYear, spec.academic_year_id)
    if year is None:
        raise _bad_request(
            f"Academic year {spec.academic_year_id} does not exist. Create one "
            "for this campus before enrolling students."
        )
    if year.campus_id != section.campus_id:
        raise _bad_request(
            "The academic year and class section belong to different campuses. "
            "A student cannot be enrolled across campuses."
        )
    if section.campus_id != campus.id:
        raise _bad_request(
            f"Class section {spec.section_id} belongs to campus "
            f"{section.campus_id}, not campus {campus.id}. Enrol the student "
            "into a section at their own campus."
        )


async def provision_person(
    session: AsyncSession,
    spec: PersonSpec,
    *,
    org_id: int,
    actor_user_id: Optional[int],
    via_bulk_import: bool = False,
    signup_method: str = "school_provisioning",
) -> ProvisionResult:
    """Create (or reuse) an account, grant its school role, and place it.

    Stages everything on `session` WITHOUT committing, exactly as
    `provision_learner_from_lead` does, so the caller commits once and a later
    failure in the same request unwinds the whole person.

    Raises 4xx with an actionable message -- setup guidance, not a 500 -- when
    the school structure being provisioned into does not exist.
    """
    if spec.role not in PROVISIONABLE_ROLES:
        # Reached only for SUPER_ADMIN today; kept as a set-membership test so
        # a role added to the enum later is refused until somebody decides.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"{spec.role.value} cannot be granted by provisioning an account. "
                "It is not a school role."
            ),
        )

    email = _normalize_email(spec.email)

    first_name = (spec.first_name or "").strip()
    if not first_name:
        raise _bad_request(
            "A first name is required. An account with no name shows as "
            "'Unnamed' on every register, report card and parent screen."
        )
    last_name = (spec.last_name or "").strip()

    # --- Campus: must belong to this org ------------------------------------
    campus: Optional[Campus] = None
    if spec.campus_id is not None:
        campus = await session.get(Campus, spec.campus_id)
        if campus is None:
            raise _bad_request(f"Campus {spec.campus_id} does not exist.")
        if campus.org_id != org_id:
            # Not a 403: the caller's own campus binding was already enforced
            # by the router. This catches a campus id belonging to a different
            # TENANT, which is a malformed request rather than an access
            # decision.
            raise _bad_request(
                f"Campus {spec.campus_id} belongs to another organization."
            )

    # --- Placement validation, before any write -----------------------------
    wants_enrollment = spec.section_id is not None or spec.academic_year_id is not None
    if wants_enrollment:
        if spec.role is not SchoolRole.STUDENT:
            raise _bad_request(
                "Only a STUDENT can be enrolled into a class section. Remove the "
                "section and academic year, or provision this person as a student."
            )
        if spec.section_id is None or spec.academic_year_id is None:
            raise _bad_request(
                "Enrolling a student needs BOTH a class section and an academic "
                "year. One without the other cannot be placed."
            )
        if campus is None:
            raise _bad_request(
                "Enrolling a student needs a campus, so the section can be "
                "checked against it."
            )
        await _validate_student_placement(session, spec, campus)

    child: Optional[User] = None
    if spec.child_student_id is not None:
        if spec.role is not SchoolRole.PARENT:
            raise _bad_request(
                "Only a PARENT can be linked to a child. Remove the child, or "
                "provision this person as a parent."
            )
        child = await session.get(User, spec.child_student_id)
        if child is None:
            raise _bad_request(
                f"Student {spec.child_student_id} does not exist, so there is "
                "nobody to link this parent to."
            )
        # The child must actually be a student in THIS org, or a parent could
        # be linked to -- and then read the records of -- a child at another
        # school.
        child_role = (
            await session.execute(
                select(SMSUserRole).where(
                    SMSUserRole.user_id == spec.child_student_id,
                    SMSUserRole.org_id == org_id,
                    SMSUserRole.role == SchoolRole.STUDENT,
                    SMSUserRole.is_active == True,  # noqa: E712
                )
            )
        ).scalars().first()
        if child_role is None:
            raise _bad_request(
                f"User {spec.child_student_id} is not an active student at this "
                "school, so a guardian cannot be linked to them."
            )

    # --- 1. The account (idempotent on email) -------------------------------
    existing_user = (
        await session.execute(select(User).where(User.email == email))
    ).scalars().first()

    created_user = False
    if existing_user is not None:
        user = existing_user
    else:
        user = User(
            username=await _unique_username(session, email),
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=_unusable_password_hash(),
            user_uuid=f"user_{uuid4()}",
            email_verified=False,
            # Provenance: how this person entered the school. The admissions
            # funnel passes its own value so a learner admitted from a won lead
            # stays distinguishable from one an administrator typed in. Losing
            # that distinction would make the funnel unauditable after the fact.
            signup_method=signup_method,
            creation_date=get_utc_now_iso(),
            update_date=get_utc_now_iso(),
        )
        session.add(user)
        # Flush, not commit: the FKs below need a real id while everything
        # stays inside the caller's transaction.
        await session.flush()
        created_user = True

    # --- 2. Organization membership -----------------------------------------
    # Without this the person is a `User` row belonging to no org. They can
    # authenticate and then find the school does not acknowledge them -- the
    # exact "account exists but sees nothing" state rule 1 is about.
    membership = (
        await session.execute(
            select(UserOrganization).where(
                UserOrganization.user_id == user.id,
                UserOrganization.org_id == org_id,
            )
        )
    ).scalars().first()
    if membership is None:
        session.add(
            UserOrganization(
                user_id=user.id,
                org_id=org_id,
                role_id=LEARNER_ROLE_ID,
                creation_date=get_utc_now_iso(),
                update_date=get_utc_now_iso(),
            )
        )

    # --- 3. The school role grant (idempotent on the unique constraint) ------
    existing_role = (
        await session.execute(
            select(SMSUserRole).where(
                SMSUserRole.user_id == user.id,
                SMSUserRole.org_id == org_id,
                SMSUserRole.role == spec.role,
            )
        )
    ).scalars().first()

    created_role = False
    if existing_role is None:
        session.add(
            SMSUserRole(
                user_id=user.id,
                org_id=org_id,
                campus_id=spec.campus_id,
                role=spec.role,
                is_active=True,
            )
        )
        created_role = True
    elif not existing_role.is_active:
        # Somebody returning after being revoked: reactivate rather than
        # inserting a duplicate the unique constraint would reject anyway.
        existing_role.is_active = True
        existing_role.campus_id = spec.campus_id
        session.add(existing_role)
        created_role = True

    # --- 4. Enrollment (students) -------------------------------------------
    created_enrollment = False
    if wants_enrollment:
        existing_enrollment = (
            await session.execute(
                select(StudentEnrollment).where(
                    StudentEnrollment.student_id == user.id,
                    StudentEnrollment.academic_year_id == spec.academic_year_id,
                )
            )
        ).scalars().first()
        if existing_enrollment is None:
            session.add(
                StudentEnrollment(
                    student_id=user.id,
                    section_id=spec.section_id,
                    academic_year_id=spec.academic_year_id,
                    roll_number=spec.roll_number,
                    status="active",
                    enrolled_at=get_utc_now_iso(),
                )
            )
            created_enrollment = True

    # --- 5. Guardian link (parents) -----------------------------------------
    created_guardian_link = False
    if child is not None:
        existing_link = (
            await session.execute(
                select(StudentGuardian).where(
                    StudentGuardian.guardian_user_id == user.id,
                    StudentGuardian.student_id == child.id,
                )
            )
        ).scalars().first()
        if existing_link is None:
            session.add(
                StudentGuardian(
                    guardian_user_id=user.id,
                    student_id=child.id,
                    relationship=spec.relationship,
                    is_primary_contact=spec.is_primary_contact,
                )
            )
            created_guardian_link = True

    # --- 6. Audit ------------------------------------------------------------
    session.add(
        SMSPersonProvisioningEvent(
            subject_user_id=user.id,
            subject_email=email,
            org_id=org_id,
            campus_id=spec.campus_id,
            role=spec.role.value,
            action=(
                PersonProvisioningAction.CREATED
                if created_user
                else PersonProvisioningAction.REUSED
            ),
            enrolled_section_id=spec.section_id if created_enrollment else None,
            linked_student_id=child.id if created_guardian_link else None,
            actor_user_id=actor_user_id,
            via_bulk_import=via_bulk_import,
        )
    )

    logger.info(
        "Provisioned %s user_id=%s org=%s (new_user=%s new_role=%s enrolled=%s linked=%s)",
        spec.role.value,
        user.id,
        org_id,
        created_user,
        created_role,
        created_enrollment,
        created_guardian_link,
    )

    return ProvisionResult(
        user_id=user.id,
        email=email,
        role=spec.role,
        created_user=created_user,
        created_role=created_role,
        created_enrollment=created_enrollment,
        created_guardian_link=created_guardian_link,
    )
