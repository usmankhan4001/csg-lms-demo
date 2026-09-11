import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_timetable import ClassPeriod, DayOfWeek, TimetableSchedule
from src.schemas.sms_timetable import (
    ClashCheckRequest,
    ClashType,
    ClassPeriodCreate,
    TimetableScheduleCreate,
)
from src.routers.sms_timetable import (
    check_clashes_endpoint,
    create_class_period,
    create_timetable_schedule,
    get_student_timetable,
    get_teacher_timetable,
    list_class_periods,
)
from src.services.sms.timetable import detect_timetable_clashes


@pytest.mark.asyncio
async def test_class_period_and_schedule_creation(db: AsyncSession):
    """Test creating class periods and clean non-conflicting timetable schedules."""
    # 1. Create class periods
    p1 = await create_class_period(
        payload=ClassPeriodCreate(
            campus_id=1,
            period_number=1,
            start_time="08:30",
            end_time="09:15",
            name="Period 1",
        ),
        session=db,
    )
    p2 = await create_class_period(
        payload=ClassPeriodCreate(
            campus_id=1,
            period_number=2,
            start_time="09:20",
            end_time="10:05",
            name="Period 2",
        ),
        session=db,
    )
    assert p1.id is not None
    assert p2.id is not None

    periods = await list_class_periods(campus_id=1, session=db)
    assert len(periods) == 2

    # 2. Create valid schedule slot
    sched_payload = TimetableScheduleCreate(
        section_id=10,
        course_id=101,
        teacher_id=5,
        day_of_week=DayOfWeek.MONDAY,
        period_id=p1.id,
        room_number="Room 101",
        academic_term_id=1,
    )
    sched = await create_timetable_schedule(payload=sched_payload, session=db)
    assert sched.id is not None
    assert sched.teacher_id == 5
    assert sched.room_number == "Room 101"


@pytest.mark.asyncio
async def test_timetable_conflict_solver_teacher_clash(db: AsyncSession):
    """Test conflict solver detects teacher double-booking."""
    # Setup period
    period = ClassPeriod(period_number=1, start_time="08:00", end_time="08:45")
    db.add(period)
    await db.commit()
    await db.refresh(period)

    # Existing schedule for Teacher 5 with Section A in Room 101
    existing = TimetableSchedule(
        section_id=1,
        course_id=101,
        teacher_id=5,
        day_of_week="MONDAY",
        period_id=period.id,
        room_number="Room 101",
        academic_term_id=1,
    )
    db.add(existing)
    await db.commit()

    # Try assigning Teacher 5 to Section B on the same day/period in Room 102
    clash_req = ClashCheckRequest(
        section_id=2,
        course_id=102,
        teacher_id=5,
        day_of_week=DayOfWeek.MONDAY,
        period_id=period.id,
        room_number="Room 102",
        academic_term_id=1,
    )
    check_res = await check_clashes_endpoint(payload=clash_req, session=db)
    assert check_res.has_clash is True
    assert any(c.clash_type == ClashType.TEACHER_DOUBLE_BOOKED for c in check_res.clashes)

    # Attempting to create schedule with enforce_no_clash=True raises 409
    with pytest.raises(HTTPException) as exc_info:
        await create_timetable_schedule(
            payload=TimetableScheduleCreate(
                section_id=2,
                course_id=102,
                teacher_id=5,
                day_of_week=DayOfWeek.MONDAY,
                period_id=period.id,
                room_number="Room 102",
                academic_term_id=1,
            ),
            enforce_no_clash=True,
            session=db,
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_timetable_conflict_solver_room_clash(db: AsyncSession):
    """Test conflict solver detects room double-booking."""
    period = ClassPeriod(period_number=1, start_time="08:00", end_time="08:45")
    db.add(period)
    await db.commit()
    await db.refresh(period)

    # Schedule Room 101 for Teacher 1 / Section 1
    existing = TimetableSchedule(
        section_id=1,
        course_id=101,
        teacher_id=1,
        day_of_week="TUESDAY",
        period_id=period.id,
        room_number="Lab-A",
        academic_term_id=1,
    )
    db.add(existing)
    await db.commit()

    # Different Teacher (2) and Section (2) trying to use same Room "Lab-A" at the same time
    clashes = await detect_timetable_clashes(
        session=db,
        section_id=2,
        course_id=102,
        teacher_id=2,
        day_of_week="TUESDAY",
        period_id=period.id,
        room_number="Lab-A",
        academic_term_id=1,
    )
    assert len(clashes) == 1
    assert clashes[0].clash_type == ClashType.ROOM_DOUBLE_BOOKED


@pytest.mark.asyncio
async def test_student_and_teacher_timetable_views(db: AsyncSession):
    """Test querying structured timetable slots for student and teacher."""
    period1 = ClassPeriod(period_number=1, start_time="09:00", end_time="09:45")
    period2 = ClassPeriod(period_number=2, start_time="10:00", end_time="10:45")
    db.add(period1)
    db.add(period2)
    await db.commit()
    await db.refresh(period1)
    await db.refresh(period2)

    # Schedule slots
    s1 = TimetableSchedule(
        section_id=10,
        course_id=101,
        teacher_id=5,
        day_of_week="MONDAY",
        period_id=period1.id,
        room_number="Room 1",
        academic_term_id=1,
    )
    s2 = TimetableSchedule(
        section_id=10,
        course_id=102,
        teacher_id=6,
        day_of_week="MONDAY",
        period_id=period2.id,
        room_number="Room 2",
        academic_term_id=1,
    )
    db.add(s1)
    db.add(s2)
    await db.commit()

    # Student timetable (by section)
    student_tt = await get_student_timetable(
        student_id=999,
        section_id=10,
        academic_term_id=1,
        session=db,
    )
    assert len(student_tt.slots) == 2
    assert student_tt.slots[0].start_time == "09:00"
    assert student_tt.slots[1].start_time == "10:00"

    # Teacher timetable
    teacher_tt = await get_teacher_timetable(
        teacher_id=5,
        academic_term_id=1,
        session=db,
    )
    assert len(teacher_tt.slots) == 1
    assert teacher_tt.slots[0].teacher_id == 5
    assert teacher_tt.slots[0].period_number == 1
