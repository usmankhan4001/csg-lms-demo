"""
Campus, Academic Calendar & Enrollment Router
=============================================
Provides REST endpoints for CSG-LMS multi-campus operations,
academic calendars, class sections, and student enrollments
secured by Keycloak OIDC JWT token verification and RBAC roles.
"""

from typing import List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlmodel import SQLModel, select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SUPER_ADMIN,
    SCHOOL_ADMIN,
    TEACHER,
    STUDENT,
    PARENT,
    STAFF,
    get_current_user_principal,
    require_roles,
)
from src.security.school_ownership import (
    assert_campus_allowed,
    resolve_scoped_campus_id,
)
from src.services.sms.academic_rollover import plan_rollover
from src.db.sms_campus import (
    get_utc_now_iso,
    Campus,
    CampusCreate,
    CampusRead,
    CampusUpdate,
    AcademicYear,
    AcademicYearBase,
    AcademicYearCreate,
    AcademicYearRead,
    AcademicYearUpdate,
    AcademicTerm,
    AcademicTermBase,
    AcademicTermCreate,
    AcademicTermRead,
    AcademicTermUpdate,
    ClassSection,
    ClassSectionBase,
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
    if principal.campus_id and not principal.is_superadmin and not principal.has_role(SCHOOL_ADMIN):
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
    description="Create a new campus. Restricted to SUPER_ADMIN and SCHOOL_ADMIN.",
)
async def create_campus(
    payload: CampusCreate,
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
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
        if principal.campus_id and principal.campus_id != campus.id and not principal.has_role(SCHOOL_ADMIN):
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
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
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
    payload: AcademicYearBase = Body(...),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
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


@router.post(
    "/academic-years/{academic_year_id}/terms",
    response_model=AcademicTermRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Academic Term for an Academic Year",
    description=(
        "Terms are the grading periods a year is divided into. Report cards "
        "and timetables are both keyed on academic_term_id, so a year with no "
        "terms leaves the gradebook unusable."
    ),
    responses={404: {"description": "Academic year not found"}},
)
async def create_academic_term(
    academic_year_id: int,
    payload: AcademicTermBase = Body(...),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> AcademicTerm:
    # Verify the parent year exists rather than letting the FK fail as a 500.
    year = await db_session.get(AcademicYear, academic_year_id)
    if year is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")

    new_term = AcademicTerm(
        academic_year_id=academic_year_id,
        name=payload.name,
        term_code=payload.term_code,
        weight_percentage=payload.weight_percentage,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db_session.add(new_term)
    await db_session.commit()
    await db_session.refresh(new_term)
    return new_term


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
    academic_year_id: Optional[int] = Query(
        None,
        description=(
            "Academic year to list sections for. Defaults to the campus's "
            "ACTIVE year so today's screens show today's sections."
        ),
    ),
    all_years: bool = Query(
        False, description="Include every year's sections, ignoring the year filter."
    ),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ClassSection]:
    # A read narrows to what the caller is entitled to rather than refusing,
    # so an unscoped request from a campus-bound user still works.
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)
    query = select(ClassSection).where(ClassSection.campus_id == (scoped_campus or campus_id))

    if not all_years:
        year_id = academic_year_id
        if year_id is None:
            # Default to the active year. Without this, every caller would have
            # to know the year id, and a school with two years of sections
            # would show both in one list.
            active = (
                await db_session.execute(
                    select(AcademicYear).where(
                        AcademicYear.campus_id == (scoped_campus or campus_id),
                        AcademicYear.is_active == True,  # noqa: E712
                    )
                )
            ).scalars().first()
            year_id = active.id if active else None
        if year_id is not None:
            # Sections predating the academic_year_id column have NULL and are
            # included, otherwise upgrading this schema would make an existing
            # school's sections vanish from its own screens.
            query = query.where(
                (ClassSection.academic_year_id == year_id)
                | (ClassSection.academic_year_id.is_(None))  # type: ignore[union-attr]
            )

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
    payload: ClassSectionBase = Body(...),
    class_teacher_id: Optional[int] = Query(None),
    academic_year_id: Optional[int] = Query(
        None, description="Academic year this section belongs to."
    ),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> ClassSection:
    # This took campus_id straight from the path with NO ownership check, so a
    # campus-bound SCHOOL_ADMIN could create sections in any campus in the org.
    # A write that names a campus fails loudly rather than being narrowed --
    # silently creating the section somewhere other than where it was asked for
    # would be worse than refusing.
    assert_campus_allowed(principal, campus_id)

    # A section's year must belong to the same campus as the section, or the
    # two disagree about which campus the class is in.
    if academic_year_id is not None:
        year = (
            await db_session.execute(
                select(AcademicYear).where(AcademicYear.id == academic_year_id)
            )
        ).scalar_one_or_none()
        if year is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Academic year {academic_year_id} not found",
            )
        if year.campus_id != campus_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Academic year belongs to a different campus than this section",
            )

    section = ClassSection(
        campus_id=campus_id,
        academic_year_id=academic_year_id,
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
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF])),
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
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, STAFF])),
) -> StudentEnrollment:
    # section_id and academic_year_id arrive in the BODY, which
    # `require_campus_access` never inspects -- it reads only path and query
    # params. So this was role-gated but not campus-scoped: STAFF at campus A
    # could enrol any student into any section at campus B.
    #
    # It also never checked that the section and the year agree, so the two
    # could be mismatched and the enrolment would belong to a year from one
    # campus and a section from another.
    section = (
        await db_session.execute(
            select(ClassSection).where(ClassSection.id == payload.section_id)
        )
    ).scalar_one_or_none()
    if section is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class section {payload.section_id} not found",
        )

    year = (
        await db_session.execute(
            select(AcademicYear).where(AcademicYear.id == payload.academic_year_id)
        )
    ).scalar_one_or_none()
    if year is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Academic year {payload.academic_year_id} not found",
        )

    if section.campus_id != year.campus_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Class section and academic year belong to different campuses; "
                "an enrolment cannot span two campuses."
            ),
        )

    assert_campus_allowed(principal, section.campus_id)

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


# ---------------------------------------------------------
# Academic Year Rollover
# ---------------------------------------------------------

class GradeProgressionRequest(SQLModel):
    """Instructions for rolling a cohort into the next academic year.

    `grade_progression` is REQUIRED and explicit: there is no grade ordering
    anywhere in this data model ("KG-1", "Grade 1" and "Year 7" all appear in
    real schools), so inferring that one grade follows another would work
    until it silently promoted a child into a grade that does not exist. Map a
    grade to null to say "this cohort leaves rather than progressing".
    """
    source_year_id: int
    target_year_id: int
    grade_progression: dict
    hold_back_student_ids: Optional[List[int]] = None


@router.post(
    "/rollover",
    summary="Roll Sections and Students into the Next Academic Year",
    description=(
        "Creates next year's sections from this year's and promotes active "
        "students into them. ONLY creates -- never updates or deletes a row "
        "belonging to the outgoing year, so last year stays readable. "
        "Idempotent: re-running creates nothing already present. "
        "Use dry_run=true first; it returns the exact plan the real run acts on."
    ),
    responses={403: {"description": "Cross-campus rollover is not permitted"}},
)
async def rollover_academic_year(
    payload: GradeProgressionRequest,
    dry_run: bool = Query(
        True,
        description="Preview only. Writes nothing. Defaults to TRUE so the "
                    "destructive-looking call is never the accidental one.",
    ),
    db_session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> dict:
    # Authorize BEFORE planning. plan_rollover commits when dry_run is False,
    # so checking afterwards would mean the write had already happened -- the
    # campus is resolved from the source year here precisely so the check can
    # come first.
    source_year = (
        await db_session.execute(
            select(AcademicYear).where(AcademicYear.id == payload.source_year_id)
        )
    ).scalar_one_or_none()
    if source_year is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source academic year {payload.source_year_id} not found",
        )
    assert_campus_allowed(principal, source_year.campus_id)

    plan = await plan_rollover(
        db_session,
        source_year_id=payload.source_year_id,
        target_year_id=payload.target_year_id,
        grade_progression=payload.grade_progression,
        hold_back_student_ids=payload.hold_back_student_ids,
        dry_run=dry_run,
    )

    return {
        "dry_run": plan.dry_run,
        "campus_id": plan.campus_id,
        "source_year_id": plan.source_year_id,
        "target_year_id": plan.target_year_id,
        "summary": plan.summary(),
        "sections": [vars(s) for s in plan.sections],
        "students": [vars(s) for s in plan.students],
        "warnings": plan.warnings,
    }
