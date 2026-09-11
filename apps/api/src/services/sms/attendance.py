"""
Example usage of the in-process event bus (src/core/event_bus.py).

Computes a student's current consecutive-absence streak from their
attendance history and, once it reaches ABSENCE_STREAK_THRESHOLD, emits
`student.absence_streak` via the shared `bus` singleton — proving the
emit-side pattern. No subscriber is registered for this event yet; that is
intentionally out of scope here.

Wiring note: the actual batch roll-call persistence lives in
`src/routers/sms_attendance.py` (`submit_batch_roll_call`), not in a
separate service module — this codebase's SMS routers hold their own
business logic. That file is a router file, and this task's scope
explicitly excludes router edits (other agents are working on router files
in parallel, to avoid merge conflicts). So `check_and_emit_absence_streak`
below is implemented and ready to use, but not yet called from the roll-call
endpoint. The intended call site, once a router edit is safe to make, is
right after a student is persisted as ABSENT in `submit_batch_roll_call`:

    if entry.status == AttendanceStatus.ABSENT:
        await check_and_emit_absence_streak(session, entry.student_id, payload.section_id)
"""

from typing import List

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.event_bus import bus
from src.db.sms_attendance import AttendanceStatus, StudentAttendance

ABSENCE_STREAK_THRESHOLD = 3


async def get_consecutive_absence_streak(
    session: AsyncSession,
    student_id: int,
    section_id: int,
) -> int:
    """
    Count the student's most recent consecutive ABSENT records in this
    section, most-recent-first, stopping at the first non-ABSENT record.
    """
    stmt = (
        select(StudentAttendance)
        .where(
            StudentAttendance.student_id == student_id,
            StudentAttendance.section_id == section_id,
        )
        .order_by(StudentAttendance.date.desc())
    )
    result = await session.execute(stmt)
    records: List[StudentAttendance] = result.scalars().all()

    streak = 0
    for record in records:
        if record.status != AttendanceStatus.ABSENT:
            break
        streak += 1
    return streak


async def check_and_emit_absence_streak(
    session: AsyncSession,
    student_id: int,
    section_id: int,
) -> int:
    """
    Compute the student's current consecutive-absence streak and, once it
    meets ABSENCE_STREAK_THRESHOLD, emit "student.absence_streak" on the
    shared event bus. Returns the streak regardless of whether it emitted.
    """
    streak = await get_consecutive_absence_streak(session, student_id, section_id)
    if streak >= ABSENCE_STREAK_THRESHOLD:
        await bus.emit(
            "student.absence_streak",
            {"student_id": student_id, "streak": streak},
        )
    return streak
