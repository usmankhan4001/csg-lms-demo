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

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from src.db.sms_campus import AcademicTerm, ClassSection, StudentEnrollment
from src.db.sms_hr import StaffProfile
from src.db.sms_identity import (
    SMSUserRole,
    SMSUserRoleCreate,
    SMSUserRoleRead,
    StudentGuardian,
    StudentGuardianCreate,
    StudentGuardianRead,
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
        result = await db_session.exec(
            select(StudentEnrollment).where(StudentEnrollment.student_id == user_id, StudentEnrollment.status == "active")
        )
        enrollment = result.first()
        if enrollment:
            student_id = user_id
            section_id = enrollment.section_id
            academic_term_id = await _current_academic_term_id(db_session, enrollment.academic_year_id)

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
