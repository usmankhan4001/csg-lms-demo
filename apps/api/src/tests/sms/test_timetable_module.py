"""Timetable module: assisted generation, lesson logs, conflict scanning.

The behaviours these pin, and why each matters:

- Generation NEVER invents a placement. A period it cannot place without a
  conflict is reported as unplaced with a reason. A generator that fills every
  gap by lying about availability produces a timetable nobody can run.
- A lesson log answers "what was taught last lesson", which is the single thing
  a substitute covering an unfamiliar class cannot otherwise find out.
- Attribution follows the authenticated caller, not the payload.
"""

import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import ClassSection
from src.db.sms_timetable import ClassPeriod, TimetableSchedule
from src.routers.sms_timetable import (
    generate_timetable_endpoint,
    list_lessons_endpoint,
    previous_lesson_endpoint,
    record_lesson_endpoint,
    scan_conflicts_endpoint,
)
from src.schemas.sms_timetable import (
    ClashType,
    GenerationRequirement,
    GenerationRequest,
    LessonLogCreate,
)
from src.tests.sms._principals import SUPERADMIN, principal


async def _seed_periods(db: AsyncSession, campus_id: int, count: int) -> list[int]:
    ids = []
    for n in range(1, count + 1):
        p = ClassPeriod(
            campus_id=campus_id,
            period_number=n,
            start_time=f"{7 + n:02d}:00",
            end_time=f"{7 + n:02d}:45",
            name=f"Period {n}",
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)
        ids.append(p.id)
    return ids


async def _seed_section(db: AsyncSession, campus_id: int = 1) -> int:
    section = ClassSection(
        campus_id=campus_id,
        grade_level="Grade 9",
        section_name="A",
        max_capacity=30,
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section.id


@pytest.mark.asyncio
async def test_generation_places_a_full_week_and_writes_nothing_on_dry_run(db: AsyncSession):
    section_id = await _seed_section(db)
    await _seed_periods(db, campus_id=1, count=6)

    result = await generate_timetable_endpoint(
        payload=GenerationRequest(
            section_id=section_id,
            requirements=[
                GenerationRequirement(course_id=101, teacher_id=11, periods_per_week=3),
                GenerationRequirement(course_id=102, teacher_id=12, periods_per_week=2),
            ],
            dry_run=True,
        ),
        session=db,
        principal=SUPERADMIN,
    )

    assert result.requested_periods == 5
    assert len(result.placed) == 5
    assert result.unplaced == []
    # A dry run must leave no trace: every placement reports no schedule id,
    # and the table is still empty.
    assert all(p.schedule_id is None for p in result.placed)
    rows = (await db.execute(TimetableSchedule.__table__.select())).all()
    assert rows == []
    assert "nothing was saved" in result.message.lower()


@pytest.mark.asyncio
async def test_generation_does_not_double_book_within_one_run(db: AsyncSession):
    """The subtle one: a dry run writes nothing, so without in-run bookkeeping
    every occurrence would be offered the same first free slot and the preview
    would promise a timetable that cannot exist."""
    section_id = await _seed_section(db)
    await _seed_periods(db, campus_id=1, count=6)

    result = await generate_timetable_endpoint(
        payload=GenerationRequest(
            section_id=section_id,
            requirements=[
                GenerationRequirement(course_id=101, teacher_id=11, periods_per_week=4),
            ],
            dry_run=True,
        ),
        session=db,
        principal=SUPERADMIN,
    )

    slots = {(p.day_of_week, p.period_id) for p in result.placed}
    assert len(slots) == len(result.placed) == 4, "a slot was handed out twice"


@pytest.mark.asyncio
async def test_unplaceable_periods_are_reported_not_invented(db: AsyncSession):
    """Ask for more periods than the week has. The surplus must come back as
    unplaced with a reason -- never squeezed into an occupied slot, and never
    silently dropped so the numbers look right."""
    section_id = await _seed_section(db)
    await _seed_periods(db, campus_id=1, count=1)  # 1 period x 5 days = 5 slots

    result = await generate_timetable_endpoint(
        payload=GenerationRequest(
            section_id=section_id,
            requirements=[
                GenerationRequirement(course_id=101, teacher_id=11, periods_per_week=8),
            ],
            dry_run=True,
        ),
        session=db,
        principal=SUPERADMIN,
    )

    assert len(result.placed) == 5
    assert len(result.unplaced) == 3
    assert len(result.placed) + len(result.unplaced) == result.requested_periods
    for u in result.unplaced:
        assert u.reason, "an unplaced period must say why"
    # And nothing was invented into a conflicting slot.
    slots = {(p.day_of_week, p.period_id) for p in result.placed}
    assert len(slots) == 5


@pytest.mark.asyncio
async def test_generation_with_no_periods_reports_every_slot_unplaced(db: AsyncSession):
    """No bell schedule means nothing to place INTO. Reporting the scale of
    what is blocked is more useful than a bare error."""
    section_id = await _seed_section(db, campus_id=77)

    result = await generate_timetable_endpoint(
        payload=GenerationRequest(
            section_id=section_id,
            requirements=[
                GenerationRequirement(course_id=101, teacher_id=11, periods_per_week=3),
            ],
            dry_run=True,
        ),
        session=db,
        principal=SUPERADMIN,
    )

    assert result.placed == []
    assert len(result.unplaced) == 3
    assert "no class periods" in result.unplaced[0].reason.lower()


@pytest.mark.asyncio
async def test_generation_respects_an_existing_teacher_booking(db: AsyncSession):
    """A teacher already teaching elsewhere at that time must not be placed
    there again -- the clash detection the write path uses is the same one
    generation consults."""
    section_id = await _seed_section(db)
    other_section = await _seed_section(db)
    period_ids = await _seed_periods(db, campus_id=1, count=1)

    # Teacher 11 is already busy every day at the only period, in another section.
    for day in ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"):
        db.add(
            TimetableSchedule(
                section_id=other_section,
                course_id=999,
                teacher_id=11,
                day_of_week=day,
                period_id=period_ids[0],
            )
        )
    await db.commit()

    result = await generate_timetable_endpoint(
        payload=GenerationRequest(
            section_id=section_id,
            requirements=[
                GenerationRequirement(course_id=101, teacher_id=11, periods_per_week=1),
            ],
            dry_run=True,
        ),
        session=db,
        principal=SUPERADMIN,
    )

    assert result.placed == []
    assert len(result.unplaced) == 1
    assert "teacher" in result.unplaced[0].reason.lower()


@pytest.mark.asyncio
async def test_generation_writes_when_dry_run_is_explicitly_false(db: AsyncSession):
    section_id = await _seed_section(db)
    await _seed_periods(db, campus_id=1, count=3)

    result = await generate_timetable_endpoint(
        payload=GenerationRequest(
            section_id=section_id,
            requirements=[
                GenerationRequirement(course_id=101, teacher_id=11, periods_per_week=2),
            ],
            dry_run=False,
        ),
        session=db,
        principal=SUPERADMIN,
    )

    assert len(result.placed) == 2
    assert all(p.schedule_id is not None for p in result.placed)
    rows = (await db.execute(TimetableSchedule.__table__.select())).all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_conflict_scan_finds_an_existing_double_booking(db: AsyncSession):
    """/check-clashes asks about a PROPOSED slot. This asks whether the
    timetable we already have is sound -- which still matters now that the
    unique indexes reject a same-term clash on write: they are scoped by
    whether academic_term_id is set, so a term-less slot booked against a
    term-scoped one is a double-booking the database cannot see."""
    section_a = await _seed_section(db)
    section_b = await _seed_section(db)
    period_ids = await _seed_periods(db, campus_id=1, count=1)

    for section_id, term_id in ((section_a, 1), (section_b, None)):
        db.add(
            TimetableSchedule(
                section_id=section_id,
                course_id=101,
                teacher_id=11,  # same teacher, same slot, two sections
                day_of_week="MONDAY",
                period_id=period_ids[0],
                academic_term_id=term_id,
            )
        )
    await db.commit()

    result = await scan_conflicts_endpoint(
        section_id=None,
        teacher_id=None,
        academic_term_id=None,
        session=db,
        principal=principal("SUPER_ADMIN", campus_id=None),
    )

    assert result.scanned_slots == 2
    kinds = {c.clash_type for c in result.conflicts}
    assert ClashType.TEACHER_DOUBLE_BOOKED in kinds
    # Reported once, not once per direction.
    teacher_clashes = [c for c in result.conflicts if c.clash_type == ClashType.TEACHER_DOUBLE_BOOKED]
    assert len(teacher_clashes) == 1


@pytest.mark.asyncio
async def test_clean_timetable_is_distinguishable_from_an_empty_one(db: AsyncSession):
    """"0 conflicts" and "nothing was checked" are different answers, and a
    scheduler acts differently on each."""
    section_id = await _seed_section(db)
    period_ids = await _seed_periods(db, campus_id=1, count=1)

    empty = await scan_conflicts_endpoint(
        section_id=None, teacher_id=None, academic_term_id=None,
        session=db, principal=principal("SUPER_ADMIN", campus_id=None),
    )
    assert empty.scanned_slots == 0
    assert "nothing was checked" in empty.message.lower()

    db.add(
        TimetableSchedule(
            section_id=section_id, course_id=101, teacher_id=11,
            day_of_week="MONDAY", period_id=period_ids[0],
        )
    )
    await db.commit()

    clean = await scan_conflicts_endpoint(
        section_id=None, teacher_id=None, academic_term_id=None,
        session=db, principal=principal("SUPER_ADMIN", campus_id=None),
    )
    assert clean.scanned_slots == 1
    assert clean.conflicts == []
    assert "no conflicts" in clean.message.lower()


@pytest.mark.asyncio
async def test_lesson_log_attaches_to_the_right_slot_and_section(db: AsyncSession):
    section_id = await _seed_section(db)
    period_ids = await _seed_periods(db, campus_id=1, count=1)
    slot = TimetableSchedule(
        section_id=section_id, course_id=101, teacher_id=11,
        day_of_week="MONDAY", period_id=period_ids[0],
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)

    log = await record_lesson_endpoint(
        payload=LessonLogCreate(
            schedule_id=slot.id,
            lesson_date="2026-09-14",
            topic_covered="Photosynthesis: light-dependent reactions",
            homework_set="Worksheet 4, questions 1-6",
            notes_for_next_teacher="Class found the electron transport chain hard.",
        ),
        session=db,
        principal=SUPERADMIN,
    )

    assert log.schedule_id == slot.id
    # section_id is denormalised from the slot, not taken from the caller.
    assert log.section_id == section_id
    assert log.topic_covered.startswith("Photosynthesis")


@pytest.mark.asyncio
async def test_lesson_attribution_follows_the_caller_not_the_payload(db: AsyncSession):
    """A lesson must not be attributable to a colleague who was not there.
    LessonLogCreate has no taught_by field at all; this pins that the value
    comes from the authenticated principal."""
    section_id = await _seed_section(db)
    period_ids = await _seed_periods(db, campus_id=1, count=1)
    slot = TimetableSchedule(
        section_id=section_id, course_id=101, teacher_id=11,
        day_of_week="MONDAY", period_id=period_ids[0],
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)

    caller = principal("TEACHER", user_id=4242)
    log = await record_lesson_endpoint(
        payload=LessonLogCreate(
            schedule_id=slot.id,
            lesson_date="2026-09-14",
            topic_covered="Trigonometric identities",
        ),
        session=db,
        principal=caller,
    )

    assert log.taught_by_user_id == 4242
    assert "taught_by_user_id" not in LessonLogCreate.model_fields


@pytest.mark.asyncio
async def test_a_substitute_can_read_the_previous_lesson_for_a_covered_section(db: AsyncSession):
    """The substitute's whole problem: covering 9A on Tuesday with no idea what
    they did on Monday."""
    section_id = await _seed_section(db)
    period_ids = await _seed_periods(db, campus_id=1, count=1)
    slot = TimetableSchedule(
        section_id=section_id, course_id=101, teacher_id=11,
        day_of_week="MONDAY", period_id=period_ids[0],
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)

    await record_lesson_endpoint(
        payload=LessonLogCreate(
            schedule_id=slot.id,
            lesson_date="2026-09-14",
            topic_covered="Quadratic equations by factorising",
            homework_set="Exercise 7B",
            notes_for_next_teacher="Start with the completing-the-square method.",
        ),
        session=db,
        principal=principal("TEACHER", user_id=11),
    )

    # A DIFFERENT teacher, covering, who does not teach this section.
    substitute = principal("TEACHER", user_id=99)
    previous = await previous_lesson_endpoint(
        section_id=section_id,
        before_date="2026-09-15",
        course_id=None,
        session=db,
        principal=substitute,
    )

    assert previous is not None
    assert previous.topic_covered == "Quadratic equations by factorising"
    assert previous.notes_for_next_teacher is not None


@pytest.mark.asyncio
async def test_no_lesson_log_returns_none_rather_than_a_blank_lesson(db: AsyncSession):
    """An absent log means nobody wrote one down -- NOT that nothing was
    taught. Returning an empty-topic record would assert the second."""
    section_id = await _seed_section(db)

    previous = await previous_lesson_endpoint(
        section_id=section_id,
        before_date="2026-09-15",
        course_id=None,
        session=db,
        principal=SUPERADMIN,
    )

    assert previous is None


@pytest.mark.asyncio
async def test_recording_the_same_lesson_twice_corrects_rather_than_duplicates(db: AsyncSession):
    section_id = await _seed_section(db)
    period_ids = await _seed_periods(db, campus_id=1, count=1)
    slot = TimetableSchedule(
        section_id=section_id, course_id=101, teacher_id=11,
        day_of_week="MONDAY", period_id=period_ids[0],
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)

    first = await record_lesson_endpoint(
        payload=LessonLogCreate(
            schedule_id=slot.id, lesson_date="2026-09-14",
            topic_covered="Typo: Photosynthsis",
        ),
        session=db, principal=principal("TEACHER", user_id=11),
    )
    corrected = await record_lesson_endpoint(
        payload=LessonLogCreate(
            schedule_id=slot.id, lesson_date="2026-09-14",
            topic_covered="Photosynthesis",
        ),
        session=db, principal=principal("SCHOOL_ADMIN", user_id=7),
    )

    assert corrected.id == first.id, "a correction must not create a second log"
    assert corrected.topic_covered == "Photosynthesis"
    # Who actually TAUGHT it is a fact about that day: an admin fixing a typo
    # later must not become the person who took the lesson.
    assert corrected.taught_by_user_id == 11

    logs = await list_lessons_endpoint(
        section_id=section_id, schedule_id=None, date_from=None, date_to=None,
        limit=50, session=db, principal=SUPERADMIN,
    )
    assert len(logs) == 1


@pytest.mark.asyncio
async def test_a_lesson_log_needs_a_topic(db: AsyncSession):
    """A blank log is worse than none: it tells the next teacher the lesson was
    recorded while telling them nothing about it."""
    section_id = await _seed_section(db)
    period_ids = await _seed_periods(db, campus_id=1, count=1)
    slot = TimetableSchedule(
        section_id=section_id, course_id=101, teacher_id=11,
        day_of_week="MONDAY", period_id=period_ids[0],
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)

    with pytest.raises(HTTPException) as exc:
        await record_lesson_endpoint(
            payload=LessonLogCreate(
                schedule_id=slot.id, lesson_date="2026-09-14", topic_covered="   ",
            ),
            session=db, principal=SUPERADMIN,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_logging_against_a_missing_slot_is_a_404(db: AsyncSession):
    with pytest.raises(HTTPException) as exc:
        await record_lesson_endpoint(
            payload=LessonLogCreate(
                schedule_id=999_999, lesson_date="2026-09-14", topic_covered="Anything",
            ),
            session=db, principal=SUPERADMIN,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_a_teacher_cannot_generate_into_a_section_they_do_not_teach(db: AsyncSession):
    """Generation writes a whole week into a section, so it is section-scoped."""
    section_id = await _seed_section(db)
    await _seed_periods(db, campus_id=1, count=3)

    stranger = principal("TEACHER", user_id=555)
    with pytest.raises(HTTPException) as exc:
        await generate_timetable_endpoint(
            payload=GenerationRequest(
                section_id=section_id,
                requirements=[
                    GenerationRequirement(course_id=101, teacher_id=555, periods_per_week=1),
                ],
                dry_run=True,
            ),
            session=db,
            principal=stranger,
        )
    assert exc.value.status_code in (401, 403)
