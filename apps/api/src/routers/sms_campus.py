"""
Campus, Academic Calendar & Enrollment Router
=============================================
Provides REST endpoints for CSG-LMS multi-campus operations,
academic calendars, class sections, and student enrollments
secured by Keycloak OIDC JWT token verification and RBAC roles.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SUPER_ADMIN,
    CAMPUS_PRINCIPAL,
    TEACHER,
    STUDENT,
    PARENT,
    ACCOUNTANT,
    get_current_user_principal,
    require_roles,
    get_utc_now_iso,
)
from src.db.sms_campus import (
    Campus,
    CampusCreate,
    CampusRead,
    CampusUpdate,
    AcademicYear,
    AcademicYearCreate,
    AcademicYearRead,
    AcademicYearUpdate,
    AcademicTerm,
    AcademicTermCreate,
    AcademicTermRead,
    AcademicTermUpdate,
    ClassSection,
    ClassSectionCreate,
    ClassSectionRead,
    ClassSectionUpdate,
    StudentEnrollment,
    StudentEnrollmentCreate,
    StudentEnrollmentRead,
    StudentEnrollmentUpdate,
)

router = APIRouter(prefix="/campuses", tags=["campuses"])


# ---------------------------------------------------------
# Campus Endpoints
# ---------------------------------------------------------

@router.get(
    "/",
    response_model=List[CampusRead],
    summary="List Campuses",
    description="List all active campuses for the authenticated user's organization.",
)
async def list_campuses(
    org_id: Optional[int] = Query(None, description="Optional organization filter"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[Campus]:
    query = select(Campus)

    # Multi-tenant scoping
    target_org_id = org_id or principal.org_id
    if target_org_id and not principal.is_superadmin:
        query = query.where(Campus.org_id == target_org_id)
    elif target_org_id:
        query = query.where(Campus.org_id == target_org_id)

    # Campus isolation: non-superadmin users with assigned campus can only see their campus
    if principal.campus_id and not principal.is_superadmin and not principal.has_role(CAMPUS_PRINCIPAL):
        query = query.where(Campus.id == principal.campus_id)

    if is_active is not None:
        query = query.where(Campus.is_active == is_active)

    result = await db_session.exec(query)
    return list(result.all())


@router.post(
    "/",
    response_model=CampusRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Campus",
    description="Create a new campus. Restricted to SUPER_ADMIN and CAMPUS_PRINCIPAL.",
)
async def create_campus(
    payload: CampusCreate,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, CAMPUS_PRINCIPAL])),
) -> Campus:
    # Ensure tenant alignment
    if not principal.is_superadmin and principal.org_id and payload.org_id != principal.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create campus in an organization other than your assigned tenant",
        )

    # Check for code collision in org
    existing = await db_session.exec(
        select(Campus).where(Campus.org_id == payload.org_id, Campus.code == payload.code)
    )
    if existing.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Campus code '{payload.code}' already exists in this organization",
        )

    new_campus = Campus(
        org_id=payload.org_id,
        name=payload.name,
        code=payload.code,
        address=payload.address,
        timezone=payload.timezone,
        is_active=payload.is_active,
        created_at=get_utc_now_iso(),
        updated_at=get_utc_now_iso(),
    )
    db_session.add(new_campus)
    await db_session.commit()
    await db_session.refresh(new_campus)
    return new_campus


@router.get(
    "/{campus_id}",
    response_model=CampusRead,
    summary="Get Campus by ID",
)
async def get_campus(
    campus_id: int,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> Campus:
    campus = await db_session.get(Campus, campus_id)
    if not campus:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campus not found")

    if not principal.is_superadmin:
        if principal.org_id and campus.org_id != principal.org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to campus outside organization is denied")
        if principal.campus_id and principal.campus_id != campus.id and not principal.has_role(CAMPUS_PRINCIPAL):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to other campuses is restricted")

    return campus


@router.patch(
    "/{campus_id}",
    response_model=CampusRead,
    summary="Update Campus",
)
async def update_campus(
    campus_id: int,
    payload: CampusUpdate,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, CAMPUS_PRINCIPAL])),
) -> Campus:
    campus = await db_session.get(Campus, campus_id)
    if not campus:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campus not found")

    if not principal.is_superadmin and principal.campus_id and principal.campus_id != campus.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify another campus")

    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(campus, k, v)
    campus.updated_at = get_utc_now_iso()

    db_session.add(campus)
    await db_session.commit()
    await db_session.refresh(campus)
    return campus


# ---------------------------------------------------------
# Academic Year Endpoints
# ---------------------------------------------------------

@router.get(
    "/{campus_id}/academic-years",
    response_model=List[AcademicYearRead],
    summary="List Academic Years for Campus",
)
async def list_academic_years(
    campus_id: int,
    is_active: Optional[bool] = Query(None),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[AcademicYear]:
    query = select(AcademicYear).where(AcademicYear.campus_id == campus_id)
    if is_active is not None:
        query = query.where(AcademicYear.is_active == is_active)
    result = await db_session.exec(query)
    return list(result.all())


@router.post(
    "/{campus_id}/academic-years",
    response_model=AcademicYearRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Academic Year for Campus",
)
async def create_academic_year(
    campus_id: int,
    payload: AcademicYearBase,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, CAMPUS_PRINCIPAL])),
) -> AcademicYear:
    new_year = AcademicYear(
        campus_id=campus_id,
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=payload.is_active,
        created_at=get_utc_now_iso(),
    )
    db_session.add(new_year)
    await db_session.commit()
    await db_session.refresh(new_year)
    return new_year


# ---------------------------------------------------------
# Class Section Endpoints
# ---------------------------------------------------------

@router.get(
    "/{campus_id}/sections",
    response_model=List[ClassSectionRead],
    summary="List Class Sections for Campus",
)
async def list_class_sections(
    campus_id: int,
    grade_level: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ClassSection]:
    query = select(ClassSection).where(ClassSection.campus_id == campus_id)
    if grade_level:
        query = query.where(ClassSection.grade_level == grade_level)
    if is_active is not None:
        query = query.where(ClassSection.is_active == is_active)
    result = await db_session.exec(query)
    return list(result.all())


@router.post(
    "/{campus_id}/sections",
    response_model=ClassSectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Class Section",
)
async def create_class_section(
    campus_id: int,
    payload: ClassSectionBase,
    class_teacher_id: Optional[int] = Query(None),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, CAMPUS_PRINCIPAL])),
) -> ClassSection:
    section = ClassSection(
        campus_id=campus_id,
        grade_level=payload.grade_level,
        section_name=payload.section_name,
        room_number=payload.room_number,
        class_teacher_id=class_teacher_id,
        max_capacity=payload.max_capacity,
        is_active=payload.is_active,
    )
    db_session.add(section)
    await db_session.commit()
    await db_session.refresh(section)
    return section


# ---------------------------------------------------------
# Student Enrollment Endpoints
# ---------------------------------------------------------

@router.get(
    "/sections/{section_id}/enrollments",
    response_model=List[StudentEnrollmentRead],
    summary="List Student Enrollments for Section",
)
async def list_section_enrollments(
    section_id: int,
    status_filter: Optional[str] = Query(None, alias="status"),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, CAMPUS_PRINCIPAL, TEACHER, ACCOUNTANT])),
) -> List[StudentEnrollment]:
    query = select(StudentEnrollment).where(StudentEnrollment.section_id == section_id)
    if status_filter:
        query = query.where(StudentEnrollment.status == status_filter)
    result = await db_session.exec(query)
    return list(result.all())


@router.post(
    "/enrollments",
    response_model=StudentEnrollmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll Student in Section",
)
async def enroll_student(
    payload: StudentEnrollmentCreate,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, CAMPUS_PRINCIPAL, ACCOUNTANT])),
) -> StudentEnrollment:
    # Check if student is already enrolled in this academic year
    existing = await db_session.exec(
        select(StudentEnrollment).where(
            StudentEnrollment.student_id == payload.student_id,
            StudentEnrollment.academic_year_id == payload.academic_year_id,
        )
    )
    if existing.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student is already enrolled in a section for this academic year",
        )

    enrollment = StudentEnrollment(
        student_id=payload.student_id,
        section_id=payload.section_id,
        academic_year_id=payload.academic_year_id,
        roll_number=payload.roll_number,
        status=payload.status,
        enrolled_at=get_utc_now_iso(),
    )
    db_session.add(enrollment)
    await db_session.commit()
    await db_session.refresh(enrollment)
    return enrollment
