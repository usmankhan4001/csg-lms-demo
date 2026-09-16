"""
Consecutive-absence streak detection, wired to a real parent notification
via the in-process event bus (src/core/event_bus.py).

`check_and_emit_absence_streak` is called from `submit_batch_roll_call`
(src/routers/sms_attendance.py) right after a student is persisted as
ABSENT. Once a student's streak reaches ABSENCE_STREAK_THRESHOLD, it emits
`student.absence_streak`; `_notify_guardians_of_absence_streak` below (the
real subscriber, registered at import time via the `@bus.on` decorator)
looks up the student's guardians (StudentGuardian) and emails each one
using the existing transactional `send_email()` helper
(src/services/email/utils.py) -- the same one used for magic-login/
verification mail, not the separate marketing-nudge system in
src/services/nudges/ (that one is a catalog-driven re-engagement system for
Learnhouse's own course product, the wrong shape for a one-off transactional
alert like this).

The event bus has no persistence/retry (see event_bus.py's own docstring),
so a process crash mid-handler silently drops the notification -- acceptable
here since this is a supplementary alert, not the attendance record of
record (that's StudentAttendance itself, unaffected either way).
"""

import asyncio
import logging
from collections import OrderedDict
from datetime import date
from typing import List, Optional, Set

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.event_bus import bus
from src.db.sms_attendance import AttendanceStatus, StudentAttendance
from src.db.sms_campus import ClassSection, StudentEnrollment
from src.db.sms_identity import StudentGuardian
from src.db.users import User

logger = logging.getLogger(__name__)

ABSENCE_STREAK_THRESHOLD = 3

# StudentEnrollment.status is free text ('active', 'transferred',
# 'graduated', 'withdrawn' -- see db/sms_campus.py). Only 'active' puts a
# child on a section's register; the other three are exactly the children a
# register must not be taken for.
ACTIVE_ENROLLMENT_STATUS = "active"

# How bad a status is, for collapsing several period records into one verdict
# for the day. ABSENT beats LATE beats EXCUSED beats PRESENT.
_STATUS_SEVERITY = {
    AttendanceStatus.PRESENT: 0,
    AttendanceStatus.EXCUSED: 1,
    AttendanceStatus.LATE: 2,
    AttendanceStatus.ABSENT: 3,
}


def collapse_to_daily_status(records) -> "OrderedDict":
    """Reduce attendance records to ONE status per date, worst status winning.

    Attendance may be recorded per period (`period_id` set) or per day
    (`period_id` NULL). Anything that reports in DAYS -- monthly totals, the
    parent digest, absence streaks -- has to collapse first, or a secondary
    school running six periods reports six times the days it actually has.

    Worst-status-wins because the exception is the point: a child who missed
    two periods was not "present" that day, and a summary that says otherwise
    is worse than no summary. For day-level registers there is one record per
    date, so this returns exactly what went in.

    Preserves the input ordering of dates, so a caller that queried
    most-recent-first (like the streak counter) keeps that order.
    """
    worst: "OrderedDict" = OrderedDict()
    for record in records:
        current = worst.get(record.date)
        if current is None or _STATUS_SEVERITY.get(record.status, 0) > _STATUS_SEVERITY.get(current, 0):
            worst[record.date] = record.status
    return worst


async def get_active_roster(session: AsyncSession, section_id: int) -> Optional[Set[int]]:
    """The ids of the students ACTIVELY enrolled in this section.

    Returns None, not an empty set, when the section has NO enrolment rows at
    all. Those are different facts and callers must not collapse them:

      * a set (even an empty one) is an authoritative roster -- anyone absent
        from it is not on the register;
      * None means the school has no enrolment data for this section, so
        "not in the roster" cannot be distinguished from "the roster was never
        loaded". Refusing a register on that basis would stop a school taking
        attendance at all, which is worse than the gap it closes. Absence of
        data is not evidence of non-enrolment -- the same rule that keeps a
        month with no register from being reported as 0%.

    Deliberately reads every enrolment row for the section rather than
    filtering on status in SQL, so that "has a roster" and "is on it" come
    from one query and cannot disagree.
    """
    # ENROLMENT IS PER ACADEMIC YEAR. StudentEnrollment is unique on
    # (student_id, academic_year_id), so a child who stays on the same section
    # across a rollover has one row per year -- and a section that was never
    # re-created carries LAST year's 'active' row next to THIS year's
    # 'withdrawn' one. Filtering on section_id alone would read the stale row
    # and wave through a child who left in August.
    #
    # The section's own year is the authority for which rows are current
    # (ClassSection.academic_year_id, set by services/sms/academic_rollover.py).
    section_year = (
        await session.execute(
            select(ClassSection.academic_year_id).where(ClassSection.id == section_id)
        )
    ).scalar_one_or_none()

    rows = (
        await session.execute(
            select(
                StudentEnrollment.student_id,
                StudentEnrollment.status,
                StudentEnrollment.academic_year_id,
            ).where(StudentEnrollment.section_id == section_id)
        )
    ).all()
    if not rows:
        return None

    if section_year is not None:
        this_year = [row for row in rows if row[2] == section_year]
        # Only fall back to the section's whole enrolment history when its own
        # year has NO rows. A school mid-rollover (section rolled forward,
        # enrolments not yet) would otherwise be handed an empty roster, and an
        # empty set is authoritative -- every register would be refused. That
        # outage is worse than the stale-row gap this fallback reopens.
        if this_year:
            rows = this_year

    return {
        student_id
        for student_id, status, _academic_year_id in rows
        if status == ACTIVE_ENROLLMENT_STATUS
    }


async def get_consecutive_absence_streak(
    session: AsyncSession,
    student_id: int,
    section_id: int,
) -> int:
    """
    Count the student's most recent consecutive absent DAYS in this section,
    most-recent-first, stopping at the first day that is not a full absence.

    THE RULE, and why it is per-day rather than per-record: a day counts as an
    absence only if EVERY attendance record for that student and section on
    that date is ABSENT. This is a stricter test than the worst-status rule
    used for reporting (`collapse_to_daily_status`) -- and deliberately so, see
    the note in the body.

    This matters now that attendance can be recorded per period. Counting rows
    would mean a student absent for six periods of one day scores a streak of
    six and trips the three-day threshold before lunch -- their parents get
    "absent 6 days in a row" on day one, which is both false and exactly the
    kind of fabricated figure this codebase has had to tear out elsewhere.
    Requiring the whole day also means a student who misses period 1 and
    attends the rest is treated as a late arrival, not an absence, which is
    what a school means by "days in a row".

    Day-level registers (period_id NULL) are unaffected: one row per date, so
    "every record that day is ABSENT" is the same test as before.

    The run is also required to be CONTIGUOUS IN CALENDAR DAYS, not merely
    contiguous in the rows returned. See the note in the body.
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

    # NOTE this deliberately does NOT use collapse_to_daily_status. That helper
    # takes the WORST status of the day, which is right for reporting (a parent
    # needs to see the missed period) but wrong here: it would mark a day
    # absent because of one missed period, and a child who attended five of six
    # periods was in school. A streak asks the opposite question, so a date
    # counts only when EVERY record for it is ABSENT.
    fully_absent_by_date: "OrderedDict[date, bool]" = OrderedDict()
    for record in records:
        is_absent = record.status == AttendanceStatus.ABSENT
        if record.date in fully_absent_by_date:
            fully_absent_by_date[record.date] = fully_absent_by_date[record.date] and is_absent
        else:
            fully_absent_by_date[record.date] = is_absent

    # CALENDAR CONTIGUITY. The keys above are only the days a register was
    # actually taken. Walking them as though they were consecutive counted a
    # child absent on Fri 5 Sep and Mon 29 Sep -- nothing in between because
    # of a cover teacher or a school trip -- as "absent 2 days running", and
    # one more isolated absence emailed the family "absent 3 days in a row"
    # for three absences weeks apart. A streak is a run of CALENDAR days, so
    # a gap of more than one day ends it.
    #
    # LIMIT, and it is a real one: there is no school-calendar model in the
    # schema, so a weekend or a holiday still breaks a run (Fri -> Mon is a
    # three-day gap). That errs towards under-reporting rather than inventing
    # a figure, which is the direction this codebase takes, but it does mean a
    # genuine Mon/Tue/Wed absence either side of a closure goes undetected
    # until something exists that says which days were school days.
    streak = 0
    previous_date = None
    for current_date, fully_absent in fully_absent_by_date.items():
        if not fully_absent:
            break
        if previous_date is not None and (previous_date - current_date).days > 1:
            break
        streak += 1
        previous_date = current_date
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

    DEPRECATED -- DO NOT CALL THIS FROM NEW CODE (Lane J).

    Nothing calls it today: `submit_batch_roll_call` now raises the streak
    through the notification fabric (`services/sms/school_events.py`) instead.
    This and its `@bus.on` subscriber below are retained only because the
    subscriber has a direct end-to-end test, and deleting live-tested code was
    outside the notification work.

    Calling it would REGRESS behaviour rather than duplicate it: the bus path
    emails guardians directly, so it bypasses notification preferences (a
    parent could not switch it off), duplicate suppression (re-saving a
    register re-sends), the delivery log (no answer to "were they told?"), and
    it writes no in-app copy. Use `raise_school_event(ABSENCE_STREAK, ...)`.
    """
    streak = await get_consecutive_absence_streak(session, student_id, section_id)
    if streak >= ABSENCE_STREAK_THRESHOLD:
        await bus.emit(
            "student.absence_streak",
            {"student_id": student_id, "streak": streak},
        )
    return streak



@bus.on("student.absence_streak")
async def _notify_guardians_of_absence_streak(payload: dict) -> None:
    """Real subscriber: emails every guardian of the student on their own
    fresh DB session (event handlers run outside the request's session/
    request-scoped dependency injection, so this opens its own via the same
    session factory get_db_session itself uses)."""
    # Imported lazily to avoid a module-import cycle at process startup
    # (database.py imports a broad set of db modules to register them with
    # SQLModel.metadata before the engine/session factory exist).
    from src.core.events.database import _async_session_factory
    from src.services.email.utils import send_email

    student_id = payload.get("student_id")
    streak = payload.get("streak")
    if student_id is None or streak is None:
        return

    async with _async_session_factory() as session:
        student = await session.get(User, student_id)
        student_name = f"Student #{student_id}"
        if student is not None:
            full_name = " ".join(
                filter(None, [getattr(student, "first_name", None), getattr(student, "last_name", None)])
            )
            if full_name:
                student_name = full_name

        result = await session.execute(select(StudentGuardian).where(StudentGuardian.student_id == student_id))
        guardian_links = result.scalars().all()
        if not guardian_links:
            logger.info("Absence streak alert for student %s has no linked guardians to notify", student_id)
            return

        for link in guardian_links:
            guardian = await session.get(User, link.guardian_user_id)
            if guardian is None or not getattr(guardian, "email", None):
                continue
            try:
                # send_email() is synchronous (resend SDK / smtplib) and
                # `bus.emit` AWAITS this handler inline with the roll-call
                # request (see event_bus.py) -- calling it directly would
                # block the event loop for every guardian of every absent
                # student before the teacher's HTTP response returns. Same
                # off-load the crisis-alert path uses.
                await asyncio.to_thread(
                    send_email,
                    guardian.email,
                    f"Attendance alert: {student_name} has been absent {streak} days in a row",
                    (
                        f"<p>{student_name} has now been marked absent for "
                        f"{streak} consecutive school days.</p>"
                        f"<p>Please contact the school if this is unexpected, "
                        f"or submit a leave request if it is planned.</p>"
                    ),
                )
            except Exception:
                # Best-effort per guardian: one bad address (or a transient
                # provider failure beyond send_email's own single retry)
                # should not stop the rest of the guardians from being
                # notified.
                logger.warning(
                    "Failed to send absence-streak email to guardian %s for student %s",
                    link.guardian_user_id,
                    student_id,
                    exc_info=True,
                )
