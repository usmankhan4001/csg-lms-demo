"""
School identity: "who am I" resolution + role/guardian assignment.

`GET /me` replaces the dev Keycloak JWT's client-side-decoded claims
(subject_id/section_id/academic_term_id/children_ids in
apps/web/lib/api/dev-token.ts's `DevSessionClaims`) with a real, server-side
resolution against `SMSUserRole`/`StudentGuardian` (src/db/sms_identity.py)
plus `StudentEnrollment`/`StaffProfile`/`ClassSection`. This becomes the
frontend's session source (useSchoolSession) and the post-login redirect
signal.

The assignment endpoints below are the only way to grant someone a school
role today -- there was previously no way to do this at all outside minting
a throwaway dev JWT.
"""

import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SUPER_ADMIN,
    SCHOOL_ADMIN,
    PARENT,
    PSYCHOLOGIST,
    STAFF,
    STUDENT,
    TEACHER,
    get_current_user_principal,
    require_roles,
)
from src.db.sms_campus import AcademicTerm, AcademicTermRead, AcademicYear, Campus, ClassSection, StudentEnrollment
from src.db.sms_hr import StaffProfile
from src.db.sms_identity import (
    SchoolRole,
    SMSImpersonationEvent,
    SMSUserRole,
    SMSUserRoleCreate,
    SMSUserRoleRead,
    StudentGuardian,
    StudentGuardianCreate,
    StudentGuardianRead,
)
from src.db.user_organizations import UserOrganization
from src.db.users import User
from src.routers.auth import get_cookie_domain_for_request, is_request_secure
from src.security.auth import get_authenticated_user, resolve_acting_user_id
from src.security.school_ownership import (
    assert_campus_allowed,
    require_own_student_or_privileged,
    resolve_scoped_campus_id,
)
from src.services.sms.people_provisioning import PersonSpec, provision_person
from src.db.sms_invite import RESENDABLE, InviteStatus, SMSPersonInvite
from src.services.sms.invites import (
    accept_invite,
    dispatch_invite,
    get_open_invite,
    list_invites,
)
from src.security.school_principal import (
    IMPERSONATION_COOKIE_MAX_AGE_SECONDS,
    IMPERSONATION_COOKIE_NAME,
    create_impersonation_cookie_value,
    decode_impersonation_cookie,
)

router = APIRouter(tags=["sms-identity"])

logger = logging.getLogger(__name__)


class MyIdentityResponse(SQLModel):
    roles: List[str]
    org_id: Optional[int]
    campus_id: Optional[int]
    student_id: Optional[int] = None
    staff_id: Optional[int] = None
    section_id: Optional[int] = None
    academic_term_id: Optional[int] = None
    children_ids: List[int] = []
    name: Optional[str] = None
    email: Optional[str] = None


async def _resolve_student_academic_context(
    db_session: AsyncSession, student_user_id: int
) -> tuple[Optional[int], Optional[int]]:
    """(section_id, academic_term_id) for a student's active enrollment --
    shared by GET /me (the caller's own context) and
    GET /identity/children/{student_id}/context (a specific child's context,
    e.g. for a parent with multiple children in different sections/terms)."""
    result = await db_session.exec(
        select(StudentEnrollment).where(
            StudentEnrollment.student_id == student_user_id, StudentEnrollment.status == "active"
        )
    )
    enrollment = result.first()
    if not enrollment:
        return None, None
    academic_term_id = await _current_academic_term_id(db_session, enrollment.academic_year_id)
    return enrollment.section_id, academic_term_id


async def _current_academic_term_id(db_session: AsyncSession, academic_year_id: int) -> Optional[int]:
    """Best-effort "which term is active right now" for a student's enrolled
    year -- there's no direct enrollment->term FK (enrollment is per academic
    YEAR; a year has multiple terms), so this resolves by today's date falling
    inside a term's [start_date, end_date] range (both stored as 'YYYY-MM-DD'
    strings, which sort/compare correctly as ISO dates)."""
    today = date.today().isoformat()
    result = await db_session.exec(
        select(AcademicTerm).where(
            AcademicTerm.academic_year_id == academic_year_id,
            AcademicTerm.start_date <= today,
            AcademicTerm.end_date >= today,
        )
    )
    term = result.first()
    return term.id if term else None


@router.get(
    "/me",
    response_model=MyIdentityResponse,
    summary="Get My School Identity",
    description="Resolves the caller's school role(s), campus, and linked student/staff/children records from their real Learnhouse session.",
)
async def get_my_identity(
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> MyIdentityResponse:
    user_id = principal.raw_claims.get("lh_user_id")

    student_id: Optional[int] = None
    section_id: Optional[int] = None
    academic_term_id: Optional[int] = None
    staff_id: Optional[int] = None
    children_ids: List[int] = []

    if principal.has_role(STUDENT) and user_id:
        section_id, academic_term_id = await _resolve_student_academic_context(db_session, user_id)
        if section_id is not None or academic_term_id is not None:
            student_id = user_id

    if principal.has_any_role([TEACHER, STAFF, PSYCHOLOGIST]) and user_id:
        result = await db_session.exec(select(StaffProfile).where(StaffProfile.user_id == user_id))
        staff = result.first()
        if staff:
            # Deliberately the Learnhouse user_id, NOT StaffProfile.id: every
            # SMS table that references "the teacher" (ClassSection.class_teacher_id,
            # TimetableSchedule.teacher_id) is an FK/int matching user.id directly,
            # matching StudentEnrollment.student_id's same convention for students.
            # The frontend's `teacherId` (modules/sms/timetable/api.ts) is compared
            # against those columns, so returning StaffProfile.id here would silently
            # return empty results for every "my timetable"/"my section" query.
            staff_id = user_id
            if section_id is None:
                section_result = await db_session.exec(
                    select(ClassSection).where(ClassSection.class_teacher_id == user_id)
                )
                own_section = section_result.first()
                if own_section:
                    section_id = own_section.id

    if principal.has_role(PARENT) and user_id:
        result = await db_session.exec(select(StudentGuardian).where(StudentGuardian.guardian_user_id == user_id))
        children_ids = [g.student_id for g in result.all()]

    return MyIdentityResponse(
        roles=sorted(principal.roles),
        org_id=principal.org_id,
        campus_id=principal.campus_id,
        student_id=student_id,
        staff_id=staff_id,
        section_id=section_id,
        academic_term_id=academic_term_id,
        children_ids=children_ids,
        name=principal.name,
        email=principal.email,
    )


class ChildContextResponse(SQLModel):
    student_id: int
    name: Optional[str] = None
    section_id: Optional[int] = None
    academic_term_id: Optional[int] = None


@router.get(
    "/identity/children/{student_id}/context",
    response_model=ChildContextResponse,
    summary="Get a Child's Academic Context",
    description=(
        "A specific student's own current section/term -- for a PARENT with "
        "multiple children, GET /me only ever returns the PARENT's own "
        "(always-empty) section_id/academic_term_id, since those are per-role "
        "claims, not per-child. This resolves one named child's own active "
        "enrollment instead, so the frontend can fetch that child's report "
        "card/attendance with the correct section/term. Access is gated by "
        "require_own_student_or_privileged: the student themselves, one of "
        "their guardians, SCHOOL_ADMIN, or SUPER_ADMIN."
    ),
)
async def get_child_context(
    student_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_own_student_or_privileged(student_id_param="student_id")),
) -> ChildContextResponse:
    student = await db_session.get(User, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    section_id, academic_term_id = await _resolve_student_academic_context(db_session, student_id)

    return ChildContextResponse(
        student_id=student_id,
        name=" ".join(filter(None, [student.first_name, student.last_name])) or None,
        section_id=section_id,
        academic_term_id=academic_term_id,
    )


# ---------------------------------------------------------
# Role assignment (superadmin / school-admin only)
# ---------------------------------------------------------

@router.post(
    "/identity/roles",
    response_model=SMSUserRoleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a School Role",
)
async def assign_role(
    payload: SMSUserRoleCreate,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> SMSUserRole:
    # A SCHOOL_ADMIN reaches this endpoint, and `role` and `org_id` both come
    # straight from the request body. Without the two checks below a school
    # admin could POST {"role": "SUPER_ADMIN"} for themselves and hold every
    # other tenant's data, or grant a role inside an org they have nothing to
    # do with. Both were possible until now; the frontend even offered
    # "Super Admin" in its role dropdown.
    _assert_may_grant(principal, payload.role, payload.org_id)
    assert_campus_allowed(principal, payload.campus_id)

    existing = await db_session.exec(
        select(SMSUserRole).where(
            SMSUserRole.user_id == payload.user_id,
            SMSUserRole.org_id == payload.org_id,
            SMSUserRole.role == payload.role,
        )
    )
    row = existing.first()
    if row:
        row.campus_id = payload.campus_id
        row.is_active = True
    else:
        row = SMSUserRole(**payload.model_dump())
        db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


@router.get(
    "/identity/roles",
    response_model=List[SMSUserRoleRead],
    summary="List School Role Grants",
)
async def list_roles(
    user_id: Optional[int] = Query(None),
    org_id: Optional[int] = Query(None),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> List[SMSUserRole]:
    query = select(SMSUserRole)
    if user_id is not None:
        query = query.where(SMSUserRole.user_id == user_id)
    if org_id is not None:
        query = query.where(SMSUserRole.org_id == org_id)
    result = await db_session.exec(query)
    return list(result.all())


@router.delete(
    "/identity/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a School Role",
)
async def revoke_role(
    role_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> None:
    row = await db_session.get(SMSUserRole, role_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role grant not found")
    row.is_active = False
    await db_session.commit()


# ---------------------------------------------------------
# Guardian linkage (superadmin / school-admin only)
# ---------------------------------------------------------

@router.post(
    "/identity/guardians",
    response_model=StudentGuardianRead,
    status_code=status.HTTP_201_CREATED,
    summary="Link a Guardian to a Student",
)
async def link_guardian(
    payload: StudentGuardianCreate,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> StudentGuardian:
    existing = await db_session.exec(
        select(StudentGuardian).where(
            StudentGuardian.guardian_user_id == payload.guardian_user_id,
            StudentGuardian.student_id == payload.student_id,
        )
    )
    if existing.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This guardian is already linked to this student")
    row = StudentGuardian(**payload.model_dump())
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


@router.get(
    "/identity/guardians",
    response_model=List[StudentGuardianRead],
    summary="List Guardian Links",
)
async def list_guardians(
    student_id: Optional[int] = Query(None),
    guardian_user_id: Optional[int] = Query(None),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> List[StudentGuardian]:
    query = select(StudentGuardian)
    if student_id is not None:
        query = query.where(StudentGuardian.student_id == student_id)
    if guardian_user_id is not None:
        query = query.where(StudentGuardian.guardian_user_id == guardian_user_id)
    result = await db_session.exec(query)
    return list(result.all())


@router.delete(
    "/identity/guardians/{guardian_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink a Guardian from a Student",
)
async def unlink_guardian(
    guardian_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> None:
    row = await db_session.get(StudentGuardian, guardian_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guardian link not found")
    await db_session.delete(row)
    await db_session.commit()


class SchoolPersonRead(SQLModel):
    """A person holding a school role, WITH their name.

    `SMSUserRoleRead` returns a bare `user_id`, which is why every screen
    built on it renders "User #42" -- unusable for picking a student to
    enrol or a guardian to link. This joins `User` so the caller gets
    something a human can choose from, without a separate lookup per row.
    """

    user_id: int
    name: Optional[str] = None
    email: Optional[str] = None
    role: str
    campus_id: Optional[int] = None


@router.get(
    "/identity/people",
    response_model=List[SchoolPersonRead],
    summary="List People by School Role",
    description=(
        "Users holding a given school role in the caller's org, with names "
        "attached -- the picker source for enrolling a student or assigning "
        "a class teacher."
    ),
)
async def list_school_people(
    role: SchoolRole = Query(..., description="School role to filter by"),
    campus_id: Optional[int] = Query(None),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, STAFF, TEACHER])),
) -> List[SchoolPersonRead]:
    query = (
        select(SMSUserRole, User)
        .join(User, SMSUserRole.user_id == User.id)
        .where(SMSUserRole.role == role, SMSUserRole.is_active == True)  # noqa: E712
    )
    # Org scoping: a non-superadmin never sees another tenant's people.
    if principal.org_id and not principal.is_superadmin:
        query = query.where(SMSUserRole.org_id == principal.org_id)
    if campus_id is not None:
        query = query.where(SMSUserRole.campus_id == campus_id)

    result = await db_session.exec(query)
    people: List[SchoolPersonRead] = []
    for grant, user in result.all():
        people.append(
            SchoolPersonRead(
                user_id=user.id,
                name=" ".join(filter(None, [user.first_name, user.last_name])) or user.username,
                email=user.email,
                role=grant.role.value if hasattr(grant.role, "value") else str(grant.role),
                campus_id=grant.campus_id,
            )
        )
    return people


def _assert_may_grant(
    principal: KeycloakUserPrincipal,
    role: SchoolRole,
    target_org_id: Optional[int],
) -> None:
    """Refuse a grant that would widen the caller's own reach.

    Two rules:

    * **SUPER_ADMIN is never grantable by a school administrator.** It is
      cross-organization platform control -- `has_role()` returns True for it
      against every role check in the codebase and campus isolation exempts it
      entirely -- so a SCHOOL_ADMIN granting it to themselves is a complete
      escape from their own tenant. Only an existing SUPER_ADMIN may hand it
      on, and never through the provisioning surface (see
      `PROVISIONABLE_ROLES`, which omits it for everyone).

    * **A grant lands in the caller's own org.** `org_id` arrives in the
      request body and was previously used verbatim, so a school admin at org
      1 could mint a SCHOOL_ADMIN at org 2.
    """
    if principal.is_superadmin:
        return

    if role == SchoolRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a super admin can grant the SUPER_ADMIN role.",
        )

    if (
        target_org_id is not None
        and principal.org_id is not None
        and target_org_id != principal.org_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: you can only assign roles within your own organization.",
        )


# ---------------------------------------------------------
# Account provisioning (superadmin / school-admin only)
# ---------------------------------------------------------
#
# `POST /identity/roles` above grants a role to a user who must ALREADY exist,
# and nothing in this codebase let an administrator create that user: the only
# account-creation paths are the public signup endpoints in routers/users.py,
# which require the person themselves to choose a password. So onboarding a
# teacher meant a psql prompt. These endpoints are the fix.
#
# No password is set, generated, or returned anywhere below -- see
# `services/sms/people_provisioning.py`.

# An import is one HTTP request holding one transaction open, and every row
# costs an Argon2 hash (deliberately slow). A whole school arrives as several
# batches rather than one request that ties up a worker for minutes.
MAX_BULK_PROVISION_ROWS = 500


class ProvisionPersonRequest(SQLModel):
    role: SchoolRole
    email: str
    first_name: str
    last_name: str = ""
    campus_id: Optional[int] = None

    # STUDENT only.
    section_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    roll_number: Optional[str] = None

    # PARENT only.
    child_student_id: Optional[int] = None
    relationship: Optional[str] = None
    is_primary_contact: bool = False

    # Whether to email the invitation now. Defaults to true, because an account
    # nobody can reach is the defect this endpoint exists to fix. A school
    # preparing a cohort before term starts can set it false and chase everyone
    # later with POST /identity/invites/resend-pending.
    send_invite: bool = True


class ProvisionPersonResponse(SQLModel):
    user_id: int
    email: str
    role: SchoolRole
    # Reported separately rather than as one "success" flag: "we created this
    # account" and "this email already existed and we attached a role to it"
    # are different facts, and an administrator importing a cohort needs to
    # know which happened.
    created_user: bool
    created_role: bool
    created_enrollment: bool
    created_guardian_link: bool
    # What happened to the invitation, separately from what happened to the
    # account. An account created whose invite bounced is NOT a success: the
    # person cannot sign in and nobody would know to chase them.
    invite_status: Optional[str] = None
    invite_error: Optional[str] = None


class BulkProvisionRequest(SQLModel):
    people: List[ProvisionPersonRequest]


class BulkProvisionRowResult(SQLModel):
    """One row's outcome. `row` is the caller's own 0-based index into the
    submitted list, so a spreadsheet line can be found again."""

    row: int
    email: Optional[str] = None
    status: str  # "created" | "reused" | "failed"
    user_id: Optional[int] = None
    created_enrollment: bool = False
    created_guardian_link: bool = False
    error: Optional[str] = None
    # Delivery is reported per row and separately from account creation. A row
    # whose account was created but whose invite bounced reads differently from
    # one that fully succeeded -- otherwise the importer says "50 created" and
    # three families are never heard from again.
    invite_status: Optional[str] = None
    invite_error: Optional[str] = None


class BulkProvisionResponse(SQLModel):
    created: int
    reused: int
    failed: int
    results: List[BulkProvisionRowResult]
    # Accounts created and invites delivered are counted separately and both
    # are reported. "50 created" while three invites bounced is not 50
    # successes -- three families are stranded and an administrator needs the
    # number to be visibly different.
    invites_sent: int = 0
    invites_failed: int = 0


def _resolve_provisioning_campus(
    principal: KeycloakUserPrincipal, requested: Optional[int]
) -> Optional[int]:
    """The campus a provisioned person is placed at.

    `assert_campus_allowed` first, so naming somebody else's campus fails
    loudly rather than silently landing the account elsewhere -- creating a
    person is a write, and a write that quietly goes to the wrong campus is
    the worse outcome. `resolve_scoped_campus_id` then pins a campus-bound
    admin who named no campus at all to their own, rather than leaving the
    grant org-wide.
    """
    assert_campus_allowed(principal, requested)
    return resolve_scoped_campus_id(principal, requested)


def _require_org(principal: KeycloakUserPrincipal) -> int:
    org_id = principal.org_id
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Your session is not attached to a school, so there is no "
                "organization to create this account in."
            ),
        )
    return org_id


def _spec_from_request(
    payload: ProvisionPersonRequest, principal: KeycloakUserPrincipal
) -> PersonSpec:
    return PersonSpec(
        role=payload.role,
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        campus_id=_resolve_provisioning_campus(principal, payload.campus_id),
        section_id=payload.section_id,
        academic_year_id=payload.academic_year_id,
        roll_number=payload.roll_number,
        child_student_id=payload.child_student_id,
        relationship=payload.relationship,
        is_primary_contact=payload.is_primary_contact,
    )


async def _send_invite_for(
    db_session: AsyncSession,
    *,
    request: Request,
    user_id: int,
    org_id: int,
    role: str,
    actor_user_id: Optional[int],
    existing: Optional[SMSPersonInvite] = None,
) -> Optional[SMSPersonInvite]:
    """Load the account and org, then dispatch. Never raises.

    An invite failure must never surface as a provisioning failure: the account
    has already been committed, and telling an administrator the import failed
    when forty-nine of fifty rows are fine would be worse than the missing
    email it is reporting.
    """
    try:
        from src.db.organizations import Organization
        from src.db.users import User

        user = (
            await db_session.execute(select(User).where(User.id == user_id))
        ).scalars().first()
        org = (
            await db_session.execute(
                select(Organization).where(Organization.id == org_id)
            )
        ).scalars().first()
        if user is None or org is None:
            logger.error(
                "Cannot dispatch invite: user %s or org %s not found", user_id, org_id
            )
            return None

        return await dispatch_invite(
            db_session,
            user=user,
            org=org,
            role=role,
            request=request,
            actor_user_id=actor_user_id,
            existing=existing,
        )
    except Exception:
        logger.exception("Invite dispatch failed for user %s", user_id)
        return None


@router.post(
    "/identity/provision",
    response_model=ProvisionPersonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a School Account",
    description=(
        "Creates a school account AND grants its role in one transaction, "
        "optionally enrolling a student into a section or linking a parent to "
        "a child at the same time. No password is set: the person receives one "
        "through the normal reset flow, so none is generated or returned here. "
        "SUPER_ADMIN cannot be provisioned."
    ),
    responses={
        400: {"description": "Invalid email, missing name, or a campus/section that does not exist"},
        403: {"description": "School-admin access required, cross-campus request, or a non-school role"},
    },
)
async def provision_school_person(
    payload: ProvisionPersonRequest,
    # FastAPI injects Request by type annotation, so the default never applies
    # over HTTP. It exists so the handler stays directly callable from a script
    # or a test without fabricating a request object.
    request: Request = None,  # type: ignore[assignment]
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> ProvisionPersonResponse:
    org_id = _require_org(principal)
    result = await provision_person(
        db_session,
        _spec_from_request(payload, principal),
        org_id=org_id,
        actor_user_id=principal.raw_claims.get("lh_user_id"),
    )
    # One commit, at the end: everything the service staged lands together or
    # not at all, so a failure can never leave an account without its role.
    await db_session.commit()

    # Invite dispatch is deliberately AFTER the commit. The account must
    # durably exist before anyone is told it does, and `dispatch_invite`
    # commits its own row -- which would have torn the provisioning
    # transaction in half had it run inside it.
    invite = None
    if payload.send_invite:
        invite = await _send_invite_for(
            db_session,
            request=request,
            user_id=result.user_id,
            org_id=org_id,
            role=getattr(result.role, "value", str(result.role)),
            actor_user_id=principal.raw_claims.get("lh_user_id"),
        )

    if not payload.send_invite:
        # Explicitly withheld, which is NOT the same as failed. Saying "sent"
        # here, or leaving it blank, would both mislead.
        invite_status, invite_error = "NOT_SENT", None
    elif invite is not None:
        invite_status, invite_error = invite.status, invite.delivery_error
    else:
        invite_status = InviteStatus.DELIVERY_FAILED.value
        invite_error = "Invite was not dispatched."

    return ProvisionPersonResponse(
        user_id=result.user_id,
        email=result.email,
        role=result.role,
        created_user=result.created_user,
        created_role=result.created_role,
        created_enrollment=result.created_enrollment,
        created_guardian_link=result.created_guardian_link,
        invite_status=invite_status,
        invite_error=invite_error,
    )


@router.post(
    "/identity/provision/bulk",
    response_model=BulkProvisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk Provision School Accounts",
    description=(
        "Provisions a list of people, reporting EVERY row's outcome "
        "individually. A school onboards a cohort, not one person, and a "
        "result that said only '47 created, 3 failed' would leave nobody able "
        "to tell which three families to chase -- so each failure carries its "
        "row index, its email and its reason. One bad row does not discard the "
        "good ones: each row is applied inside its own savepoint."
    ),
    responses={
        400: {"description": "Empty or oversized list"},
        403: {"description": "School-admin access required"},
    },
)
async def bulk_provision_school_people(
    payload: BulkProvisionRequest,
    request: Request = None,  # type: ignore[assignment]
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> BulkProvisionResponse:
    org_id = _require_org(principal)
    actor_user_id = principal.raw_claims.get("lh_user_id")

    if not payload.people:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No people to import.",
        )
    if len(payload.people) > MAX_BULK_PROVISION_ROWS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{len(payload.people)} rows is more than one import can take. "
                f"Split the file into batches of {MAX_BULK_PROVISION_ROWS} or fewer."
            ),
        )

    results: List[BulkProvisionRowResult] = []
    created = reused = failed = 0

    for index, person in enumerate(payload.people):
        # A SAVEPOINT per row. Without it a single bad row poisons the whole
        # session -- SQLAlchemy refuses further work on a transaction that has
        # raised -- so 49 good rows would be lost to one typo. With it, the
        # failed row is rolled back to its savepoint and the rest carry on.
        try:
            async with db_session.begin_nested():
                result = await provision_person(
                    db_session,
                    _spec_from_request(person, principal),
                    org_id=org_id,
                    actor_user_id=actor_user_id,
                    via_bulk_import=True,
                )
        except HTTPException as exc:
            failed += 1
            results.append(
                BulkProvisionRowResult(
                    row=index,
                    email=(person.email or "").strip().lower() or None,
                    status="failed",
                    error=str(exc.detail),
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001
            # An unexpected failure is still THIS row's failure. Reported with
            # the row rather than turned into a 500 that would hide which 47
            # of the 50 had already succeeded.
            logger.exception("Bulk provisioning row %s failed", index)
            failed += 1
            results.append(
                BulkProvisionRowResult(
                    row=index,
                    email=(person.email or "").strip().lower() or None,
                    status="failed",
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        if result.created_user:
            created += 1
            row_status = "created"
        else:
            reused += 1
            row_status = "reused"
        results.append(
            BulkProvisionRowResult(
                row=index,
                email=result.email,
                status=row_status,
                user_id=result.user_id,
                created_enrollment=result.created_enrollment,
                created_guardian_link=result.created_guardian_link,
            )
        )

    await db_session.commit()

    # Invites go out only once every row has durably landed. Dispatching inside
    # the loop would have committed mid-import (dispatch_invite commits its own
    # row), destroying the savepoint isolation that stops one bad row taking
    # the other forty-nine with it.
    for row in results:
        if row.user_id is None or row.status == "failed":
            continue
        if not payload.people[row.row].send_invite:
            row.invite_status = "NOT_SENT"
            continue
        invite = await _send_invite_for(
            db_session,
            request=request,
            user_id=row.user_id,
            org_id=org_id,
            role=getattr(
                payload.people[row.row].role,
                "value",
                str(payload.people[row.row].role),
            ),
            actor_user_id=actor_user_id,
        )
        row.invite_status = (
            invite.status if invite else InviteStatus.DELIVERY_FAILED.value
        )
        row.invite_error = (
            invite.delivery_error if invite else "Invite was not dispatched."
        )

    return BulkProvisionResponse(
        created=created,
        reused=reused,
        failed=failed,
        results=results,
        invites_sent=sum(
            1 for r in results if r.invite_status == InviteStatus.PENDING.value
        ),
        invites_failed=sum(
            1
            for r in results
            if r.invite_status
            in (InviteStatus.DELIVERY_FAILED.value, InviteStatus.UNKNOWN.value)
        ),
    )


# ---------------------------------------------------------
# Invitations
# ---------------------------------------------------------
#
# Provisioning creates an account nobody can sign into by design. These
# endpoints are the other half: issuing the single-use link that lets the owner
# set their own password, showing an administrator who has not used it yet, and
# resending when it is lost.


class InviteRead(SQLModel):
    id: int
    subject_user_id: int
    subject_email: str
    subject_role: str
    status: str
    delivery_error: Optional[str] = None
    sent_count: int = 0
    last_sent_at: Optional[str] = None
    expires_at: Optional[str] = None
    accepted_at: Optional[str] = None


def _invite_read(invite: SMSPersonInvite) -> InviteRead:
    return InviteRead(
        id=invite.id or 0,
        subject_user_id=invite.subject_user_id,
        subject_email=invite.subject_email,
        subject_role=invite.subject_role,
        status=invite.status,
        delivery_error=invite.delivery_error,
        sent_count=invite.sent_count or 0,
        last_sent_at=invite.last_sent_at.isoformat() if invite.last_sent_at else None,
        expires_at=invite.expires_at.isoformat() if invite.expires_at else None,
        accepted_at=invite.accepted_at.isoformat() if invite.accepted_at else None,
    )


@router.get(
    "/identity/invites",
    response_model=List[InviteRead],
    summary="List Invitations",
    description=(
        "Every invitation issued for the caller's organization, with what "
        "genuinely happened to it. PENDING means the provider accepted the "
        "message; DELIVERY_FAILED means it refused; UNKNOWN means the outcome "
        "could not be determined and is reported as such rather than assumed "
        "to be a success."
    ),
)
async def list_school_invites(
    status_filter: Optional[str] = Query(None, alias="status"),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> List[InviteRead]:
    org_id = _require_org(principal)
    rows = await list_invites(db_session, org_id, status=status_filter)
    return [_invite_read(r) for r in rows]


@router.post(
    "/identity/invites/{user_id}/resend",
    response_model=InviteRead,
    summary="Resend One Invitation",
    description=(
        "Issues a FRESH single-use link and revokes the previous one, so an "
        "invite forwarded to the wrong address stops working. Refuses for "
        "somebody who has already accepted -- that would hand out a new "
        "password-setting token for a live account."
    ),
    responses={
        404: {"description": "No open invitation for that person"},
        409: {"description": "That person has already accepted"},
    },
)
async def resend_school_invite(
    user_id: int,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> InviteRead:
    org_id = _require_org(principal)

    invite = await get_open_invite(db_session, user_id, org_id)
    if invite is None:
        # Scoped to the caller's own org, so this cannot be used to probe
        # whether a user exists in another tenant.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No open invitation for that person.",
        )
    if InviteStatus(invite.status) not in RESENDABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That person has already accepted their invitation.",
        )

    refreshed = await _send_invite_for(
        db_session,
        request=request,
        user_id=user_id,
        org_id=org_id,
        role=invite.subject_role,
        actor_user_id=principal.raw_claims.get("lh_user_id"),
        existing=invite,
    )
    return _invite_read(refreshed or invite)


class ResendPendingResponse(SQLModel):
    attempted: int
    sent: int
    failed: int
    results: List[InviteRead]


@router.post(
    "/identity/invites/resend-pending",
    response_model=ResendPendingResponse,
    summary="Resend Every Outstanding Invitation",
    description=(
        "Chases the whole cohort at once. Only invitations that have not been "
        "accepted are touched, and every outcome is reported individually so "
        "an address that keeps bouncing is visible rather than averaged away."
    ),
)
async def resend_pending_invites(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> ResendPendingResponse:
    org_id = _require_org(principal)
    actor_user_id = principal.raw_claims.get("lh_user_id")

    outstanding = [
        i
        for i in await list_invites(db_session, org_id)
        if InviteStatus(i.status) in RESENDABLE
    ]

    results: List[InviteRead] = []
    sent = failed = 0
    for invite in outstanding:
        refreshed = await _send_invite_for(
            db_session,
            request=request,
            user_id=invite.subject_user_id,
            org_id=org_id,
            role=invite.subject_role,
            actor_user_id=actor_user_id,
            existing=invite,
        )
        target = refreshed or invite
        if target.status == InviteStatus.PENDING.value:
            sent += 1
        else:
            failed += 1
        results.append(_invite_read(target))

    return ResendPendingResponse(
        attempted=len(outstanding), sent=sent, failed=failed, results=results
    )


class AcceptInviteRequest(SQLModel):
    org_id: int
    email: str
    code: str
    new_password: str


@router.post(
    "/identity/invites/accept",
    status_code=status.HTTP_200_OK,
    summary="Accept an Invitation",
    description=(
        "Redeems a single-use invitation link and sets the chosen password. "
        "DELIBERATELY UNAUTHENTICATED: the whole point of an invitation is "
        "that its recipient cannot sign in yet. Every failure returns the same "
        "message so this cannot be used to discover which addresses have "
        "accounts, and attempts are rate limited per address."
    ),
    responses={
        400: {"description": "Invalid or expired invitation, or a weak password"},
        429: {"description": "Too many attempts for this address"},
    },
)
async def accept_school_invite(
    payload: AcceptInviteRequest,
    db_session: AsyncSession = Depends(get_db_session),
):
    # Same limiter the password-reset path uses: 5 attempts per 5 minutes per
    # address. Without it this endpoint is an offline-speed oracle for guessing
    # invitation codes.
    from src.services.security.rate_limiting import check_password_reset_rate_limit

    is_allowed, retry_after = check_password_reset_rate_limit(payload.email)
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many attempts. Please try again in "
                f"{max(retry_after // 60, 1)} minutes."
            ),
        )

    await accept_invite(
        db_session,
        org_id=payload.org_id,
        email=payload.email,
        code=payload.code,
        new_password=payload.new_password,
    )
    return {"detail": "Your password has been set. You can now sign in."}


class DirectoryEntry(SQLModel):
    user_id: int
    name: Optional[str] = None
    email: Optional[str] = None
    # An empty list means exactly that: this person is a member of the school
    # with no school role yet. It is NOT defaulted to STUDENT -- guessing here
    # would silently hand someone a learner's view of the school.
    roles: List[str] = []
    campus_id: Optional[int] = None


@router.get(
    "/identity/directory",
    response_model=List[DirectoryEntry],
    summary="List Everyone at the School",
    description=(
        "Every member of the caller's organization with the school roles they "
        "hold. Unlike GET /identity/people, which filters to ONE role and so "
        "can never show somebody who has none, this includes members with no "
        "school role yet -- the accounts that exist but cannot do anything, "
        "which is exactly what an administrator needs to find."
    ),
)
async def list_school_directory(
    campus_id: Optional[int] = Query(None),
    unassigned_only: bool = Query(
        False, description="Only members holding no active school role."
    ),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> List[DirectoryEntry]:
    org_id = _require_org(principal)
    scoped_campus_id = resolve_scoped_campus_id(principal, campus_id)

    members = (
        await db_session.exec(
            select(User)
            .join(UserOrganization, UserOrganization.user_id == User.id)
            .where(UserOrganization.org_id == org_id)
        )
    ).all()

    grants = (
        await db_session.exec(
            select(SMSUserRole).where(
                SMSUserRole.org_id == org_id,
                SMSUserRole.is_active == True,  # noqa: E712
            )
        )
    ).all()

    by_user: dict[int, List[SMSUserRole]] = {}
    for grant in grants:
        by_user.setdefault(grant.user_id, []).append(grant)

    entries: List[DirectoryEntry] = []
    for user in members:
        user_grants = by_user.get(user.id, [])
        if scoped_campus_id is not None and user_grants:
            # A campus-bound admin sees the people at their campus. A grant
            # with campus_id None is org-wide and stays visible: it is not
            # somebody else's campus, it is nobody's.
            if not any(g.campus_id in (None, scoped_campus_id) for g in user_grants):
                continue
        if unassigned_only and user_grants:
            continue
        entries.append(
            DirectoryEntry(
                user_id=user.id,
                name=" ".join(filter(None, [user.first_name, user.last_name])) or user.username,
                email=user.email,
                roles=sorted(
                    g.role.value if hasattr(g.role, "value") else str(g.role)
                    for g in user_grants
                ),
                campus_id=next((g.campus_id for g in user_grants if g.campus_id is not None), None),
            )
        )
    return entries


# ---------------------------------------------------------
# Academic terms (replaces the frontend's hardcoded ACADEMIC_TERMS mock)
# ---------------------------------------------------------

@router.get(
    "/academic-terms",
    response_model=List[AcademicTermRead],
    summary="List Academic Terms",
    description="Terms across the caller's org (or a specific campus/year), joined Campus -> AcademicYear -> AcademicTerm. Same org/campus scoping rules as GET /sms/campuses.",
)
async def list_academic_terms(
    campus_id: Optional[int] = Query(None, description="Optional campus filter"),
    academic_year_id: Optional[int] = Query(None, description="Optional academic year filter"),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[AcademicTerm]:
    query = select(AcademicTerm).join(AcademicYear, AcademicTerm.academic_year_id == AcademicYear.id).join(
        Campus, AcademicYear.campus_id == Campus.id
    )

    if academic_year_id is not None:
        query = query.where(AcademicTerm.academic_year_id == academic_year_id)
    if campus_id is not None:
        query = query.where(Campus.id == campus_id)

    target_org_id = principal.org_id
    if target_org_id and not principal.is_superadmin:
        query = query.where(Campus.org_id == target_org_id)
    if principal.campus_id and not principal.is_superadmin and not principal.has_role(SCHOOL_ADMIN):
        query = query.where(Campus.id == principal.campus_id)

    result = await db_session.exec(query)
    return list(result.all())


# ---------------------------------------------------------
# Superadmin impersonation (QA/demo tool)
# ---------------------------------------------------------
#
# Permanent, audited replacement for the now-deleted dev-only Keycloak-shaped
# JWT minting endpoint that used to live in this router. A real superadmin --
# already authenticated via their own real Learnhouse
# session, checked here via `get_authenticated_user` rather than
# `get_current_user_principal` since no principal/impersonation exists yet at
# this point -- can temporarily view the app as another user for QA/demo/
# support. This does not mint a new token type: it sets a signed, httpOnly,
# short-lived cookie that `resolve_school_principal()` (src/security/
# school_principal.py) consults to resolve the principal as the TARGET user's
# own SMSUserRole grants, not the superadmin's. Every start/stop is written to
# the durable `SMSImpersonationEvent` audit trail (src/db/sms_identity.py),
# kept deliberately separate from `UserAuditEvent`, which is scoped to
# learner activity only.


class ImpersonateRequest(SQLModel):
    target_user_id: int


class ImpersonateResponse(SQLModel):
    id: int
    name: Optional[str] = None
    email: str


@router.post(
    "/identity/impersonate",
    response_model=ImpersonateResponse,
    status_code=status.HTTP_200_OK,
    summary="Start Impersonating a User (Superadmin QA/Demo Tool)",
    description=(
        "Superadmin-only. Sets a signed, httpOnly, ~2-hour `sms_impersonation` "
        "cookie so subsequent requests resolve the caller's SMS principal as "
        "the target user instead of the superadmin. Writes an audited "
        "SMSImpersonationEvent(action='start') row."
    ),
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Superadmin access required"},
        404: {"description": "Target user not found"},
    },
)
async def start_impersonation(
    payload: ImpersonateRequest,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_authenticated_user),
) -> ImpersonateResponse:
    if not getattr(current_user, "is_superadmin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")

    target = await db_session.get(User, payload.target_user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")

    actor_user_id = resolve_acting_user_id(current_user)

    db_session.add(
        SMSImpersonationEvent(
            actor_user_id=actor_user_id,
            target_user_id=target.id,
            action="start",
        )
    )
    await db_session.commit()

    cookie_value = create_impersonation_cookie_value(actor_user_id=actor_user_id, target_user_id=target.id)
    response.set_cookie(
        key=IMPERSONATION_COOKIE_NAME,
        value=cookie_value,
        httponly=True,
        secure=is_request_secure(request),
        samesite="lax",
        domain=get_cookie_domain_for_request(request),
        max_age=IMPERSONATION_COOKIE_MAX_AGE_SECONDS,
    )

    return ImpersonateResponse(
        id=target.id,
        name=" ".join(filter(None, [target.first_name, target.last_name])) or None,
        email=target.email,
    )


@router.post(
    "/identity/impersonate/stop",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Stop Impersonating",
    description=(
        "Clears the `sms_impersonation` cookie and reverts the caller to their "
        "own real session. No role gate -- anyone can stop their own "
        "impersonation. Best-effort: a missing or already-invalid cookie is a "
        "silent no-op (the audit write is skipped, not a 500)."
    ),
)
async def stop_impersonation(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_authenticated_user),
) -> None:
    payload = decode_impersonation_cookie(request.cookies.get(IMPERSONATION_COOKIE_NAME))
    if payload is not None:
        target_user_id = payload.get("target_user_id")
        if target_user_id is not None:
            db_session.add(
                SMSImpersonationEvent(
                    actor_user_id=resolve_acting_user_id(current_user),
                    target_user_id=target_user_id,
                    action="stop",
                )
            )
            await db_session.commit()

    response.delete_cookie(
        key=IMPERSONATION_COOKIE_NAME,
        domain=get_cookie_domain_for_request(request),
    )
