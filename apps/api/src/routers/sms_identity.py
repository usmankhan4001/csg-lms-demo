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
from src.db.users import User
from src.routers.auth import get_cookie_domain_for_request, is_request_secure
from src.security.auth import get_authenticated_user, resolve_acting_user_id
from src.security.school_ownership import require_own_student_or_privileged
from src.security.school_principal import (
    IMPERSONATION_COOKIE_MAX_AGE_SECONDS,
    IMPERSONATION_COOKIE_NAME,
    create_impersonation_cookie_value,
    decode_impersonation_cookie,
)

router = APIRouter(tags=["sms-identity"])


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
