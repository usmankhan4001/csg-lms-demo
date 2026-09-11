from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import KeycloakUserPrincipal, get_current_user_principal
from src.db.sms_timetable import ClassPeriod, DayOfWeek, TimetableSchedule
from src.schemas.sms_timetable import (
    ClassPeriodCreate,
    ClassPeriodRead,
    ClashCheckRequest,
    ClashCheckResponse,
    StudentTimetableResponse,
    TeacherTimetableResponse,
    TimetableScheduleCreate,
    TimetableScheduleRead,
    TimetableSlotDetail,
)
from src.security.features_utils.dependencies import require_sms_timetable_feature
from src.services.sms.timetable import (
    check_schedule_clashes,
    detect_timetable_clashes,
    fetch_timetable_slots,
    get_student_timetable_slots,
    get_teacher_timetable_slots,
)

router = APIRouter(dependencies=[Depends(require_sms_timetable_feature)])


# ── Class Periods ──

@router.post(
    "/periods",
    response_model=ClassPeriodRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Class Period",
    description="Define a bell schedule period with start/end time for a campus.",
)
async def create_class_period(
    payload: ClassPeriodCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> ClassPeriodRead:
    period = ClassPeriod(
        campus_id=payload.campus_id,
        period_number=payload.period_number,
        start_time=payload.start_time,
        end_time=payload.end_time,
        name=payload.name,
    )
    session.add(period)
    await session.commit()
    await session.refresh(period)
    return ClassPeriodRead.model_validate(period)


@router.get(
    "/periods",
    response_model=List[ClassPeriodRead],
    summary="List Class Periods",
    description="Retrieve all configured class periods.",
)
async def list_class_periods(
    campus_id: Optional[int] = Query(None, description="Filter by Campus ID"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ClassPeriodRead]:
    stmt = select(ClassPeriod)
    if isinstance(campus_id, int):
        stmt = stmt.where(ClassPeriod.campus_id == campus_id)
    stmt = stmt.order_by(ClassPeriod.period_number.asc())
    result = await session.execute(stmt)
    periods = result.scalars().all()
    return [ClassPeriodRead.model_validate(p) for p in periods]


# ── Conflict Detection & Scheduling ──

@router.post(
    "/check-clashes",
    response_model=ClashCheckResponse,
    summary="Check Timetable Schedule Clashes",
    description="Inspect if a prospective timetable slot causes teacher or room double-booking collisions.",
)
async def check_clashes_endpoint(
    payload: ClashCheckRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> ClashCheckResponse:
    day_str = payload.day_of_week.value if isinstance(payload.day_of_week, DayOfWeek) else str(payload.day_of_week)
    return await check_schedule_clashes(
        session=session,
        section_id=payload.section_id,
        course_id=payload.course_id,
        teacher_id=payload.teacher_id,
        day_of_week=day_str,
        period_id=payload.period_id,
        room_number=payload.room_number,
        academic_term_id=payload.academic_term_id,
        exclude_schedule_id=payload.exclude_schedule_id,
    )


@router.post(
    "/schedules",
    response_model=TimetableScheduleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Timetable Schedule Slot",
    description="Create a timetable schedule entry after validating against conflicts.",
)
async def create_timetable_schedule(
    payload: TimetableScheduleCreate,
    enforce_no_clash: bool = Query(True, description="Reject creation if clashes exist"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> TimetableScheduleRead:
    day_str = payload.day_of_week.value if isinstance(payload.day_of_week, DayOfWeek) else str(payload.day_of_week)

    # Verify period exists
    period_stmt = select(ClassPeriod).where(ClassPeriod.id == payload.period_id)
    period_res = await session.execute(period_stmt)
    if not period_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class period with ID {payload.period_id} does not exist.",
        )

    # Check clashes
    should_enforce = enforce_no_clash if isinstance(enforce_no_clash, bool) else True
    clashes = await detect_timetable_clashes(
        session=session,
        section_id=payload.section_id,
        course_id=payload.course_id,
        teacher_id=payload.teacher_id,
        day_of_week=day_str,
        period_id=payload.period_id,
        room_number=payload.room_number,
        academic_term_id=payload.academic_term_id,
    )

    if should_enforce and clashes:
        descriptions = "; ".join([c.description for c in clashes])
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot schedule slot due to conflict(s): {descriptions}",
        )

    schedule = TimetableSchedule(
        section_id=payload.section_id,
        course_id=payload.course_id,
        teacher_id=payload.teacher_id,
        day_of_week=day_str.upper(),
        period_id=payload.period_id,
        room_number=payload.room_number,
        academic_term_id=payload.academic_term_id,
    )
    session.add(schedule)
    await session.commit()
    await session.refresh(schedule)
    return TimetableScheduleRead.model_validate(schedule)


@router.get(
    "/schedules",
    response_model=List[TimetableSlotDetail],
    summary="List Timetable Schedules",
    description="Retrieve timetable schedule slots with detailed period time info.",
)
async def list_timetable_schedules(
    section_id: Optional[int] = Query(None, description="Filter by Section ID"),
    teacher_id: Optional[int] = Query(None, description="Filter by Teacher ID"),
    academic_term_id: Optional[int] = Query(None, description="Filter by Academic Term ID"),
    day_of_week: Optional[DayOfWeek] = Query(None, description="Filter by Day of Week"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[TimetableSlotDetail]:
    conditions = []
    if isinstance(section_id, int):
        conditions.append(TimetableSchedule.section_id == section_id)
    if isinstance(teacher_id, int):
        conditions.append(TimetableSchedule.teacher_id == teacher_id)
    if isinstance(academic_term_id, int):
        conditions.append(TimetableSchedule.academic_term_id == academic_term_id)
    if isinstance(day_of_week, (DayOfWeek, str)):
        val = day_of_week.value if isinstance(day_of_week, DayOfWeek) else str(day_of_week).upper()
        conditions.append(TimetableSchedule.day_of_week == val)

    return await fetch_timetable_slots(session, conditions)


# ── Student & Teacher Timetables ──

@router.get(
    "/student/{student_id}",
    response_model=StudentTimetableResponse,
    summary="Get Student Timetable",
    description="Fetch a student's weekly timetable based on their section.",
)
async def get_student_timetable(
    student_id: int,
    section_id: int = Query(..., description="Student's section ID"),
    academic_term_id: Optional[int] = Query(None, description="Filter by Academic Term ID"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> StudentTimetableResponse:
    term_id = academic_term_id if isinstance(academic_term_id, int) else None
    slots = await get_student_timetable_slots(
        session=session,
        section_id=section_id,
        academic_term_id=term_id,
    )
    return StudentTimetableResponse(
        student_id=student_id,
        section_id=section_id,
        academic_term_id=term_id,
        slots=slots,
    )


@router.get(
    "/teacher/{teacher_id}",
    response_model=TeacherTimetableResponse,
    summary="Get Teacher Timetable",
    description="Fetch a teacher's weekly timetable.",
)
async def get_teacher_timetable(
    teacher_id: int,
    academic_term_id: Optional[int] = Query(None, description="Filter by Academic Term ID"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> TeacherTimetableResponse:
    term_id = academic_term_id if isinstance(academic_term_id, int) else None
    slots = await get_teacher_timetable_slots(
        session=session,
        teacher_id=teacher_id,
        academic_term_id=term_id,
    )
    return TeacherTimetableResponse(
        teacher_id=teacher_id,
        academic_term_id=term_id,
        slots=slots,
    )
