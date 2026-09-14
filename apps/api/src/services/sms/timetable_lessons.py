"""Lesson logs: what was actually taught, and the handover to whoever is next.

The substitute teacher's problem this exists to solve: you are covering a class
you have never taught, and nothing in the system can tell you what they did
last lesson or what homework is due. `LessonPlan` does not answer it -- a plan
is written before a lesson and may never have been followed.
"""

import datetime
import logging
from typing import List, Optional

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_timetable import TimetableLessonLog, TimetableSchedule

logger = logging.getLogger(__name__)


async def record_lesson_log(
    session: AsyncSession,
    schedule_id: int,
    lesson_date: str,
    topic_covered: str,
    taught_by_user_id: Optional[int],
    recorded_by_user_id: Optional[int],
    homework_set: Optional[str] = None,
    notes_for_next_teacher: Optional[str] = None,
    lesson_plan_id: Optional[int] = None,
) -> TimetableLessonLog:
    """Create or correct the log for one slot on one date.

    Upserts rather than always inserting: a teacher who realises they wrote the
    wrong topic should be able to fix it, and two logs for the same lesson would
    leave a substitute reading whichever the query happened to return first.

    Raises ValueError with a readable message; the router maps it to 404/400.
    """
    schedule = (
        await session.execute(
            select(TimetableSchedule).where(TimetableSchedule.id == schedule_id)
        )
    ).scalar_one_or_none()
    if schedule is None:
        raise ValueError(f"Timetable slot {schedule_id} does not exist.")

    topic = (topic_covered or "").strip()
    if not topic:
        # A blank log is worse than none: it tells the next teacher the lesson
        # was recorded while telling them nothing about it.
        raise ValueError("A lesson log needs a topic; an empty record helps nobody.")

    existing = (
        await session.execute(
            select(TimetableLessonLog).where(
                TimetableLessonLog.schedule_id == schedule_id,
                TimetableLessonLog.lesson_date == lesson_date,
            )
        )
    ).scalars().first()

    if existing is not None:
        existing.topic_covered = topic
        existing.homework_set = homework_set
        existing.notes_for_next_teacher = notes_for_next_teacher
        existing.lesson_plan_id = lesson_plan_id
        # `taught_by_user_id` is NOT reassigned on correction. Who stood in
        # front of the class is a fact about that day; a head of department
        # fixing a typo later must not become the person who taught it.
        existing.updated_at = datetime.datetime.now(datetime.timezone.utc)
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return existing

    log = TimetableLessonLog(
        schedule_id=schedule_id,
        section_id=schedule.section_id,
        lesson_date=lesson_date,
        taught_by_user_id=taught_by_user_id,
        topic_covered=topic,
        homework_set=homework_set,
        notes_for_next_teacher=notes_for_next_teacher,
        lesson_plan_id=lesson_plan_id,
        recorded_by_user_id=recorded_by_user_id,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def list_lesson_logs(
    session: AsyncSession,
    section_id: Optional[int] = None,
    schedule_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
) -> List[TimetableLessonLog]:
    """Lesson logs, most recent first."""
    stmt = select(TimetableLessonLog)
    if section_id is not None:
        stmt = stmt.where(TimetableLessonLog.section_id == section_id)
    if schedule_id is not None:
        stmt = stmt.where(TimetableLessonLog.schedule_id == schedule_id)
    if date_from is not None:
        stmt = stmt.where(TimetableLessonLog.lesson_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(TimetableLessonLog.lesson_date <= date_to)
    stmt = stmt.order_by(
        TimetableLessonLog.lesson_date.desc(),
        TimetableLessonLog.id.desc(),
    ).limit(max(1, min(limit, 200)))
    return list((await session.execute(stmt)).scalars().all())


async def get_previous_lesson(
    session: AsyncSession,
    section_id: int,
    before_date: str,
    course_id: Optional[int] = None,
) -> Optional[TimetableLessonLog]:
    """The last logged lesson for a section before a given date.

    This is the substitute's question, so it is scoped by SECTION rather than by
    slot: someone covering 9A on Tuesday needs what 9A last did, which may have
    been a different slot with a different teacher.

    `course_id` narrows it to one subject, which is what a subject specialist
    covering only their own lesson wants. Without it the answer spans the
    section's whole timetable, which is what a form tutor wants.

    Returns None when there is no log. The caller must say "no record" -- an
    empty answer here means nobody wrote one down, NOT that nothing was taught.
    """
    stmt = select(TimetableLessonLog).where(
        TimetableLessonLog.section_id == section_id,
        TimetableLessonLog.lesson_date < before_date,
    )
    if course_id is not None:
        stmt = stmt.join(
            TimetableSchedule,
            TimetableSchedule.id == TimetableLessonLog.schedule_id,
        ).where(TimetableSchedule.course_id == course_id)
    stmt = stmt.order_by(
        TimetableLessonLog.lesson_date.desc(),
        TimetableLessonLog.id.desc(),
    ).limit(1)
    return (await session.execute(stmt)).scalars().first()
