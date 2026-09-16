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
from src.services.sms.timetable import (
    cancel_substitution,
    create_substitution,
    detect_timetable_clashes,
    list_substitutions,
)
from src.tests.sms._principals import SUPERADMIN


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
            principal=SUPERADMIN,
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
            principal=SUPERADMIN,
    )
    assert p1.id is not None
    assert p2.id is not None

    periods = await list_class_periods(campus_id=1, session=db,
        principal=SUPERADMIN)
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

    # Attempting to create the clashing schedule raises 409
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


# ── Teacher Substitutions ──

async def _make_slot(db: AsyncSession, *, teacher_id: int, section_id: int, period_id: int,
                     course_id: int = 900, day: str = "MONDAY") -> TimetableSchedule:
    slot = TimetableSchedule(
        section_id=section_id,
        course_id=course_id,
        teacher_id=teacher_id,
        day_of_week=day,
        period_id=period_id,
        academic_term_id=1,
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    return slot


async def _period(db: AsyncSession, number: int) -> ClassPeriod:
    p = ClassPeriod(campus_id=1, period_number=number, start_time="08:00", end_time="08:45")
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest.mark.asyncio
async def test_substitution_leaves_permanent_schedule_untouched(db: AsyncSession):
    """The recurring slot must keep its original teacher — otherwise a one-day
    cover would silently reassign the class for every future week."""
    period = await _period(db, 1)
    slot = await _make_slot(db, teacher_id=701, section_id=10, period_id=period.id)

    sub = await create_substitution(
        session=db,
        schedule_id=slot.id,
        substitution_date="2026-09-14",
        substitute_teacher_id=702,
        reason="Sick leave",
    )

    assert sub.original_teacher_id == 701
    assert sub.substitute_teacher_id == 702
    assert sub.is_active is True

    await db.refresh(slot)
    assert slot.teacher_id == 701, "permanent schedule must not be mutated"


@pytest.mark.asyncio
async def test_substitute_already_teaching_that_period_is_rejected(db: AsyncSession):
    """Reuses the existing collision detector: a substitute who already has
    their own class that period cannot also cover this one."""
    period = await _period(db, 2)
    slot = await _make_slot(db, teacher_id=711, section_id=20, period_id=period.id)
    # Substitute 712 already teaches a different section in the same period.
    await _make_slot(db, teacher_id=712, section_id=21, period_id=period.id, course_id=901)

    with pytest.raises(ValueError, match="already booked"):
        await create_substitution(
            session=db,
            schedule_id=slot.id,
            substitution_date="2026-09-14",
            substitute_teacher_id=712,
        )


@pytest.mark.asyncio
async def test_substitute_double_booked_across_two_covers_same_period(db: AsyncSession):
    """A cover lives only in the substitution table, so it is invisible to the
    permanent-timetable clash check — guard against it separately."""
    period = await _period(db, 3)
    slot_a = await _make_slot(db, teacher_id=721, section_id=30, period_id=period.id)
    slot_b = await _make_slot(db, teacher_id=722, section_id=31, period_id=period.id, course_id=902)

    await create_substitution(
        session=db, schedule_id=slot_a.id, substitution_date="2026-09-14", substitute_teacher_id=799
    )

    with pytest.raises(ValueError, match="already covering"):
        await create_substitution(
            session=db, schedule_id=slot_b.id, substitution_date="2026-09-14", substitute_teacher_id=799
        )


@pytest.mark.asyncio
async def test_duplicate_active_substitution_rejected_then_allowed_after_cancel(db: AsyncSession):
    period = await _period(db, 4)
    slot = await _make_slot(db, teacher_id=731, section_id=40, period_id=period.id)

    first = await create_substitution(
        session=db, schedule_id=slot.id, substitution_date="2026-09-14", substitute_teacher_id=732
    )

    with pytest.raises(ValueError, match="already exists"):
        await create_substitution(
            session=db, schedule_id=slot.id, substitution_date="2026-09-14", substitute_teacher_id=733
        )

    cancelled = await cancel_substitution(session=db, substitution_id=first.id)
    assert cancelled.is_active is False

    # Cancelling frees the slot for a different substitute.
    second = await create_substitution(
        session=db, schedule_id=slot.id, substitution_date="2026-09-14", substitute_teacher_id=733
    )
    assert second.substitute_teacher_id == 733


@pytest.mark.asyncio
async def test_cancel_is_soft_and_not_repeatable(db: AsyncSession):
    period = await _period(db, 5)
    slot = await _make_slot(db, teacher_id=741, section_id=50, period_id=period.id)
    sub = await create_substitution(
        session=db, schedule_id=slot.id, substitution_date="2026-09-15", substitute_teacher_id=742
    )

    await cancel_substitution(session=db, substitution_id=sub.id)
    with pytest.raises(ValueError, match="already been cancelled"):
        await cancel_substitution(session=db, substitution_id=sub.id)

    # Soft-cancelled row is still retrievable for audit.
    all_rows = await list_substitutions(session=db, schedule_id=slot.id, include_cancelled=True)
    active_rows = await list_substitutions(session=db, schedule_id=slot.id)
    assert len(all_rows) == 1
    assert active_rows == []


@pytest.mark.asyncio
async def test_substituting_the_same_teacher_is_rejected(db: AsyncSession):
    period = await _period(db, 6)
    slot = await _make_slot(db, teacher_id=751, section_id=60, period_id=period.id)

    with pytest.raises(ValueError, match="already the teacher"):
        await create_substitution(
            session=db, schedule_id=slot.id, substitution_date="2026-09-16", substitute_teacher_id=751
        )


@pytest.mark.asyncio
async def test_substitution_for_missing_schedule_is_rejected(db: AsyncSession):
    with pytest.raises(ValueError, match="does not exist"):
        await create_substitution(
            session=db, schedule_id=999999, substitution_date="2026-09-16", substitute_teacher_id=761
        )
