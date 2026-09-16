"""DB-level uniqueness for timetable slots.

`detect_timetable_clashes` is a read-then-write check, so two concurrent
creates both see an empty slot and both insert -- and the old
`?enforce_no_clash=false` query parameter let a client skip even that. The
partial unique indexes on `sms_timetable_schedule` are the real guard; these
tests pin that they reject a clash the service layer never saw.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_timetable import ClassPeriod, DayOfWeek, TimetableSchedule
from src.routers.sms_timetable import (
    create_timetable_schedule,
    update_timetable_schedule,
)
from src.schemas.sms_timetable import (
    TimetableScheduleCreate,
    TimetableScheduleUpdate,
)
from src.tests.sms._principals import SUPERADMIN


async def _period(db: AsyncSession, number: int = 1) -> ClassPeriod:
    p = ClassPeriod(campus_id=1, period_number=number, start_time="08:00", end_time="08:45")
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


def _slot(*, teacher_id: int, section_id: int, period_id: int,
          course_id: int = 900, day: str = "MONDAY",
          academic_term_id: int | None = 1,
          room_number: str | None = None) -> TimetableSchedule:
    return TimetableSchedule(
        section_id=section_id,
        course_id=course_id,
        teacher_id=teacher_id,
        day_of_week=day,
        period_id=period_id,
        academic_term_id=academic_term_id,
        room_number=room_number,
    )


async def _count(db: AsyncSession) -> int:
    rows = await db.execute(select(TimetableSchedule.id))
    return len(rows.all())


async def _reload(db: AsyncSession, schedule_id: int) -> TimetableSchedule:
    """Read a slot back from the database.

    A `refresh` would do, except after a rollback the instance is expired and
    re-touching it outside the async greenlet raises MissingGreenlet; a fresh
    SELECT is unambiguous about reading committed state.
    """
    row = await db.execute(
        select(TimetableSchedule).where(TimetableSchedule.id == schedule_id)
    )
    return row.scalar_one()


@pytest.mark.asyncio
async def test_same_teacher_same_slot_is_rejected(db: AsyncSession):
    """The core clash: one teacher, two sections, one period."""
    period = await _period(db)
    db.add(_slot(teacher_id=5, section_id=10, period_id=period.id, course_id=101))
    await db.commit()

    db.add(_slot(teacher_id=5, section_id=11, period_id=period.id, course_id=102))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()

    assert await _count(db) == 1


@pytest.mark.asyncio
async def test_same_section_same_slot_is_rejected(db: AsyncSession):
    """A section cannot attend two lessons at once, whoever teaches them."""
    period = await _period(db)
    db.add(_slot(teacher_id=5, section_id=10, period_id=period.id, course_id=101))
    await db.commit()

    db.add(_slot(teacher_id=6, section_id=10, period_id=period.id, course_id=102))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()

    assert await _count(db) == 1


@pytest.mark.asyncio
async def test_term_less_slots_are_still_unique(db: AsyncSession):
    """The nullable-uniqueness trap: NULL != NULL in SQL, so a plain unique
    index over academic_term_id would let unlimited duplicates through for
    every school that does not run terms."""
    period = await _period(db)
    db.add(_slot(teacher_id=5, section_id=10, period_id=period.id,
                 academic_term_id=None))
    await db.commit()

    db.add(_slot(teacher_id=5, section_id=11, period_id=period.id,
                 academic_term_id=None))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()

    assert await _count(db) == 1


@pytest.mark.asyncio
async def test_non_conflicting_slots_are_allowed(db: AsyncSession):
    """The constraint must not be broader than the clash it prevents: a
    different period, a different day and a different term are all free."""
    p1 = await _period(db, 1)
    p2 = await _period(db, 2)

    db.add(_slot(teacher_id=5, section_id=10, period_id=p1.id))
    await db.commit()
    # Same teacher, different period.
    db.add(_slot(teacher_id=5, section_id=11, period_id=p2.id))
    await db.commit()
    # Same teacher and period, different day.
    db.add(_slot(teacher_id=5, section_id=12, period_id=p1.id, day="TUESDAY"))
    await db.commit()
    # Same teacher, period and day, different term.
    db.add(_slot(teacher_id=5, section_id=13, period_id=p1.id, academic_term_id=2))
    await db.commit()

    assert await _count(db) == 4


@pytest.mark.asyncio
async def test_two_writers_that_both_saw_a_free_slot_do_not_both_land(
    db: AsyncSession, engine
):
    """The race the service pre-check cannot close.

    Both writers read the slot as free before either writes -- exactly what two
    concurrent POSTs do -- so only the database can decide the winner.
    """
    period = await _period(db)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as writer_a, factory() as writer_b:
        # Both read: nothing scheduled yet.
        assert await _count(writer_a) == 0
        assert await _count(writer_b) == 0

        writer_a.add(_slot(teacher_id=5, section_id=10, period_id=period.id))
        await writer_a.commit()

        writer_b.add(_slot(teacher_id=5, section_id=11, period_id=period.id))
        with pytest.raises(IntegrityError):
            await writer_b.commit()
        await writer_b.rollback()

    assert await _count(db) == 1


@pytest.mark.asyncio
async def test_router_returns_409_when_the_database_rejects_the_insert(
    db: AsyncSession, monkeypatch
):
    """A clash the pre-check did not see must still surface as a clean 409.

    The pre-check is stubbed to report "no clash", which is precisely the state
    a racing request is in: it read the slot before the winner committed.
    """
    import src.routers.sms_timetable as router_mod

    period = await _period(db)
    db.add(_slot(teacher_id=5, section_id=10, period_id=period.id))
    await db.commit()

    real_detect = router_mod.detect_timetable_clashes
    reads = {"n": 0}

    async def _sees_nothing_on_the_first_read(**kwargs):
        # The pre-check read is the one that lost the race; the re-read after
        # the rollback must see the winner so the message can name it.
        reads["n"] += 1
        if reads["n"] == 1:
            return []
        return await real_detect(**kwargs)

    monkeypatch.setattr(
        router_mod, "detect_timetable_clashes", _sees_nothing_on_the_first_read
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_timetable_schedule(
            payload=TimetableScheduleCreate(
                section_id=11,
                course_id=102,
                teacher_id=5,
                day_of_week=DayOfWeek.MONDAY,
                period_id=period.id,
                academic_term_id=1,
            ),
            session=db,
            principal=SUPERADMIN,
        )

    assert exc_info.value.status_code == 409
    assert "Teacher (ID: 5)" in exc_info.value.detail
    # The rejected slot was rolled back, not left half-written.
    assert await _count(db) == 1


@pytest.mark.asyncio
def test_there_is_no_enforce_no_clash_bypass():
    """The old `?enforce_no_clash=false` let a client write a clash anyway.
    The parameter is gone, so the handler no longer accepts it."""
    import inspect

    params = inspect.signature(create_timetable_schedule).parameters
    assert "enforce_no_clash" not in params

    # Not merely absent from the signature: a caller that still sends it is
    # rejected, rather than being silently ignored and written anyway.
    with pytest.raises(TypeError):
        inspect.signature(create_timetable_schedule).bind(
            payload=None,
            session=None,
            principal=SUPERADMIN,
            enforce_no_clash=False,
        )


# ── Update paths ──
#
# A slot can be moved after the fact, and a move is a write like any other:
# without a check here the unique indexes on create could be undone one edit
# at a time.


async def _two_periods(db: AsyncSession):
    return await _period(db, 1), await _period(db, 2)


@pytest.mark.asyncio
async def test_update_onto_an_occupied_slot_is_rejected(db: AsyncSession):
    """Moving a slot onto a teacher who is already teaching that period."""
    p1, p2 = await _two_periods(db)
    db.add(_slot(teacher_id=5, section_id=10, period_id=p1.id, course_id=101))
    mover = _slot(teacher_id=6, section_id=11, period_id=p2.id, course_id=102)
    db.add(mover)
    await db.commit()
    mover_id = mover.id

    with pytest.raises(HTTPException) as exc_info:
        await update_timetable_schedule(
            schedule_id=mover_id,
            payload=TimetableScheduleUpdate(teacher_id=5, period_id=p1.id),
            session=db,
            principal=SUPERADMIN,
        )

    assert exc_info.value.status_code == 409
    assert "Teacher (ID: 5)" in exc_info.value.detail

    # Rejected before anything was written: the slot is where it was.
    stored = await _reload(db, mover_id)
    assert stored.period_id == p2.id
    assert stored.teacher_id == 6


@pytest.mark.asyncio
async def test_update_onto_an_occupied_room_is_rejected(db: AsyncSession):
    """Room clashes stay a service-level check -- see the module docstring --
    but they must apply to an edit just as they do to a create."""
    p1, p2 = await _two_periods(db)
    db.add(
        _slot(
            teacher_id=5,
            section_id=10,
            period_id=p1.id,
            course_id=101,
            room_number="B12",
        )
    )
    mover = _slot(teacher_id=6, section_id=11, period_id=p2.id, course_id=102)
    db.add(mover)
    await db.commit()

    with pytest.raises(HTTPException) as exc_info:
        await update_timetable_schedule(
            schedule_id=mover.id,
            payload=TimetableScheduleUpdate(period_id=p1.id, room_number="b12 "),
            session=db,
            principal=SUPERADMIN,
        )

    assert exc_info.value.status_code == 409
    assert "Room" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_that_does_not_clash_is_saved(db: AsyncSession):
    """The check must not be broader than the clash: changing a slot's room
    and course leaves its teacher and period alone, so it is free."""
    p1, _p2 = await _two_periods(db)
    slot = _slot(teacher_id=5, section_id=10, period_id=p1.id, course_id=101)
    db.add(slot)
    await db.commit()

    updated = await update_timetable_schedule(
        schedule_id=slot.id,
        payload=TimetableScheduleUpdate(room_number="B12", course_id=777),
        session=db,
        principal=SUPERADMIN,
    )

    assert updated.room_number == "B12"
    assert updated.course_id == 777
    # Untouched fields survive a partial update.
    assert updated.teacher_id == 5
    assert updated.period_id == p1.id
    assert updated.section_id == 10


@pytest.mark.asyncio
async def test_update_is_rejected_by_the_database_when_the_pre_check_misses_it(
    db: AsyncSession, monkeypatch
):
    """The update-path race, same shape as the create-path one: the pre-check
    read the slot as free, so only the constraint can stop the edit."""
    import src.routers.sms_timetable as router_mod

    p1, p2 = await _two_periods(db)
    # Read the ids out now: the rollback inside the handler expires every
    # instance in the session, including these periods.
    p1_id, p2_id = p1.id, p2.id
    db.add(_slot(teacher_id=5, section_id=10, period_id=p1_id, course_id=101))
    mover = _slot(teacher_id=6, section_id=11, period_id=p2_id, course_id=102)
    db.add(mover)
    await db.commit()
    mover_id = mover.id

    real_detect = router_mod.detect_timetable_clashes
    reads = {"n": 0}

    async def _sees_nothing_on_the_first_read(**kwargs):
        reads["n"] += 1
        if reads["n"] == 1:
            return []
        return await real_detect(**kwargs)

    monkeypatch.setattr(
        router_mod, "detect_timetable_clashes", _sees_nothing_on_the_first_read
    )

    with pytest.raises(HTTPException) as exc_info:
        await update_timetable_schedule(
            schedule_id=mover_id,
            payload=TimetableScheduleUpdate(teacher_id=5, period_id=p1_id),
            session=db,
            principal=SUPERADMIN,
        )

    assert exc_info.value.status_code == 409
    # Rolled back, so the slot kept its old period rather than landing on top
    # of the one it clashes with.
    stored = await _reload(db, mover_id)
    assert stored.period_id == p2_id
    assert stored.teacher_id == 6


@pytest.mark.asyncio
async def test_update_of_a_slot_that_does_not_exist_is_404(db: AsyncSession):
    p1, _p2 = await _two_periods(db)
    with pytest.raises(HTTPException) as exc_info:
        await update_timetable_schedule(
            schedule_id=999_999,
            payload=TimetableScheduleUpdate(period_id=p1.id),
            session=db,
            principal=SUPERADMIN,
        )
    assert exc_info.value.status_code == 404
