"""
Live-class attendance: percentage, threshold, and the bridge into the register.

WHAT THIS CLOSES. `LiveClassAttendanceLog` (db/sms_live_class.py) already
records, server-side and unforgeably, when each student joined and left a
LiveKit room and how long they were in it -- written by the LiveKit webhook
(routers/live_class_webhooks.py), which verifies the media server's own
signature before trusting anything. Nothing consumed it. `StudentAttendance`
-- the register a school actually reports on -- was never written from a live
class at all, so a child who sat through forty minutes of online maths stayed
unmarked until somebody remembered to mark them by hand.

This module is the missing middle: active minutes -> percentage -> status ->
register row.

THE RULE THAT SHAPES EVERYTHING BELOW: absence of data is never rendered as a
value. Concretely:

  * a session whose length cannot be established produces NO result at all --
    not 0% (which would mark every child absent) and not 100% (which would
    mark them all present);
  * a student with no telemetry gets NO row, not a 0% and not an automatic
    ABSENT;
  * a student whose telemetry is incomplete (a join with no leave) is skipped
    with a reason rather than counted as zero minutes.

Every "we cannot know" path returns a skip carrying the reason, so the gap is
visible and answerable instead of being filled in.
"""

import datetime
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_attendance import (
    AttendanceChangeAction,
    AttendanceStatus,
    StudentAttendance,
)
from src.db.sms_live_class import LiveClassAttendanceLog, LiveClassSession
from src.services.sms.attendance import get_active_roster
from src.services.sms.attendance_pastoral import record_attendance_change

logger = logging.getLogger(__name__)


# ── The threshold ────────────────────────────────────────────────────────────

# A student is PRESENT at or above this share of the session's minutes.
# PROJECT_DOCS/09_EXPANDED_SYSTEM_ARCHITECTURE_AND_LIVE_CLASSES.md, §4 step 5
# and §8 advantage 3 both specify 80%.
PRESENT_THRESHOLD_PERCENT = 80.0

# A student who was measurably in the room but fell short of the threshold is
# LATE (partial attendance), not ABSENT: "they were there for twelve minutes"
# and "they never came" are different facts, and a register that collapses them
# cannot be defended to a parent. Only a measured ZERO minutes is ABSENT.
#
# Raise this to PRESENT_THRESHOLD_PERCENT for a strict two-way
# Present/Absent register -- that is the only line that has to change.
PARTIAL_ATTENDANCE_FLOOR_PERCENT = 0.0

_NO_SESSION_MINUTES_NOTE = (
    "Session length cannot be established: end_time is missing, or is not "
    "after start_time. No percentage is computed and nothing is written -- an "
    "unknown session length is not 0% and not 100%."
)


# ── Results ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StudentAttendanceComputation:
    """One student's measured share of one session."""

    student_id: int
    active_minutes: float
    session_minutes: float
    attended_percentage: float
    status: AttendanceStatus


@dataclass(frozen=True)
class SkippedStudent:
    """A student deliberately NOT given a status, and why.

    Never a guess dressed up as a number: this is how "we do not know" is
    reported.
    """

    student_id: int
    reason: str


@dataclass
class SessionAttendancePlan:
    """What WOULD be written for a session. Read-only; writes nothing."""

    session_id: int
    section_id: Optional[int]
    date: Optional[datetime.date]
    session_minutes: Optional[float]
    session_minutes_note: Optional[str]
    computed: List[StudentAttendanceComputation] = field(default_factory=list)
    skipped: List[SkippedStudent] = field(default_factory=list)


@dataclass(frozen=True)
class PreservedRegisterRow:
    """An existing register row this bridge refused to touch."""

    student_id: int
    status: AttendanceStatus
    reason: str


@dataclass
class BridgeResult:
    """What WAS written, what was left alone, and what was skipped."""

    session_id: int
    section_id: Optional[int]
    date: Optional[datetime.date]
    session_minutes: Optional[float]
    session_minutes_note: Optional[str]
    # What was measured, alongside what was written: the register row carries
    # only a status, and the percentage behind it is what a teacher will be
    # asked about.
    computed: List[StudentAttendanceComputation] = field(default_factory=list)
    records: List[StudentAttendance] = field(default_factory=list)
    preserved: List[PreservedRegisterRow] = field(default_factory=list)
    skipped: List[SkippedStudent] = field(default_factory=list)


# ── Session length ───────────────────────────────────────────────────────────


def _aware(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """SQLite (tests) hands back naive datetimes where Postgres gives aware
    ones; comparing the two raises. Normalise before any arithmetic."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


def scheduled_session_minutes(live: LiveClassSession) -> Optional[float]:
    """The denominator: SCHEDULED minutes, `end_time - start_time`.

    WHY SCHEDULED AND NOT ACTUAL. The alternative -- first join to last leave
    across the room's logs -- is rejected for two reasons:

      1. It is circular. The denominator would be derived from the same
         telemetry it grades, so a room with one student in it would define
         its own length and that student would be 100% present by
         construction. A student who joined late would shorten the session
         for everybody and so raise their own percentage.
      2. It is undefined exactly when it matters. A session nobody attended
         has no first join and no last leave, so the one case a school most
         needs reported -- nobody turned up -- is the case that cannot be
         computed.

    The scheduled window is fixed independently of what is being measured, it
    is what the timetable promised the child, and it is what "attend 80% of
    the class" means to a teacher.

    Returns None -- never 0 -- when the length cannot be established: no
    `end_time` (a class still running, or an ad-hoc room never closed), or an
    `end_time` not after `start_time`. None means "unknown", and callers must
    treat it as no result at all.
    """
    start = _aware(live.start_time)
    end = _aware(live.end_time)
    if start is None or end is None:
        return None
    minutes = (end - start).total_seconds() / 60.0
    if minutes <= 0:
        return None
    return minutes


def status_for_percentage(attended_percentage: float) -> AttendanceStatus:
    """The register status for a measured share of the session.

    Uses the existing `AttendanceStatus` values -- PRESENT / LATE / ABSENT --
    rather than inventing a PARTIAL the rest of the register does not
    understand. EXCUSED is deliberately never produced here: excusing an
    absence is a human decision about a note from home, not something a
    percentage can conclude.
    """
    if attended_percentage >= PRESENT_THRESHOLD_PERCENT:
        return AttendanceStatus.PRESENT
    if attended_percentage > PARTIAL_ATTENDANCE_FLOOR_PERCENT:
        return AttendanceStatus.LATE
    return AttendanceStatus.ABSENT


# ── Compute ──────────────────────────────────────────────────────────────────


async def compute_session_attendance(
    session: AsyncSession,
    live: LiveClassSession,
) -> SessionAttendancePlan:
    """Per-student attendance for one live class. Writes nothing.

    Safe to call as often as a teacher likes: it is the preview behind the
    read endpoint, so what a teacher is shown is exactly what the write will
    do.
    """
    start = _aware(live.start_time)
    session_minutes = scheduled_session_minutes(live)
    plan = SessionAttendancePlan(
        session_id=live.id or 0,
        section_id=live.section_id,
        # The register is a DAILY register, so the row is dated by the class's
        # own scheduled start (UTC, which is how start_time is stored).
        date=start.date() if start is not None else None,
        session_minutes=session_minutes,
        session_minutes_note=None if session_minutes else _NO_SESSION_MINUTES_NOTE,
    )
    # No denominator, no result. Not 0%, not 100%, and no rows for anybody.
    if session_minutes is None or plan.section_id is None or plan.date is None:
        return plan

    logs = (
        await session.execute(
            select(LiveClassAttendanceLog).where(
                LiveClassAttendanceLog.session_id == live.id
            )
        )
    ).scalars().all()

    by_student: Dict[int, List[LiveClassAttendanceLog]] = {}
    for log in logs:
        # The teacher is in the room too. Their presence is not a child's
        # attendance, and the webhook already excludes them -- exclude here as
        # well so the client-driven log path cannot reintroduce it.
        if log.student_id == live.teacher_id:
            continue
        by_student.setdefault(log.student_id, []).append(log)

    # Enrolment is the roster. A register is only taken for children actually
    # on it -- see get_active_roster for why "no enrolment rows at all" is
    # None rather than an empty set, and is therefore not a reason to skip.
    roster = await get_active_roster(session, plan.section_id)

    for student_id in sorted(by_student):
        student_logs = by_student[student_id]

        if roster is not None and student_id not in roster:
            plan.skipped.append(
                SkippedStudent(
                    student_id,
                    f"Not actively enrolled in section {plan.section_id}.",
                )
            )
            continue

        # A join with no leave means we do not know how long they stayed.
        # Counting it as zero would mark a child ABSENT on missing data --
        # precisely the fabrication this module exists to avoid.
        open_logs = [log for log in student_logs if log.left_at is None]
        if open_logs:
            plan.skipped.append(
                SkippedStudent(
                    student_id,
                    f"Telemetry incomplete: {len(open_logs)} join(s) with no "
                    "leave recorded, so active minutes are unknown.",
                )
            )
            continue

        # Summed, not averaged: a student who drops and rejoins has several
        # logs and was present for all of them put together.
        active_minutes = sum(float(log.duration_minutes or 0.0) for log in student_logs)
        percentage = min(
            100.0, max(0.0, active_minutes / session_minutes * 100.0)
        )
        plan.computed.append(
            StudentAttendanceComputation(
                student_id=student_id,
                active_minutes=round(active_minutes, 2),
                session_minutes=round(session_minutes, 2),
                attended_percentage=round(percentage, 2),
                status=status_for_percentage(percentage),
            )
        )

    return plan


# ── Bridge ───────────────────────────────────────────────────────────────────


def _marker(session_id: int) -> str:
    """Provenance stamp written into `StudentAttendance.remarks`.

    A marker in an existing column rather than a new one: this project
    creates schema with `SQLModel.metadata.create_all`, which creates missing
    TABLES but never ALTERs an existing one, so a new column on
    `sms_student_attendance` would not exist in any environment that already
    has the table. See db/sms_live_class.py's `LiveClassSessionDetail` for the
    same constraint and the same conclusion.

    It is also the honest place for it: the remark is what a teacher reading
    the register sees, so the row explains itself.
    """
    return f"[live-class {session_id}]"


def _was_written_by_this_bridge(row: StudentAttendance, session_id: int) -> bool:
    return row.remarks is not None and _marker(session_id) in row.remarks


def bridge_remark(session_id: int, computed: StudentAttendanceComputation) -> str:
    return (
        f"{_marker(session_id)} {computed.status.value}: "
        f"{computed.active_minutes:g} of {computed.session_minutes:g} scheduled "
        f"minutes ({computed.attended_percentage:g}%; present at "
        f"{PRESENT_THRESHOLD_PERCENT:g}%)."
    )


def _audit_reason(
    plan: SessionAttendancePlan, computed: StudentAttendanceComputation
) -> str:
    """Why the register changed, in the words a school would have to defend."""
    return (
        f"Live class {plan.session_id}: {computed.attended_percentage:g}% of "
        f"{computed.session_minutes:g} scheduled minutes "
        f"({computed.active_minutes:g} active); present at "
        f"{PRESENT_THRESHOLD_PERCENT:g}%."
    )


async def bridge_session_attendance(
    session: AsyncSession,
    live: LiveClassSession,
    *,
    actor_user_id: Optional[int],
) -> BridgeResult:
    """Write the computed statuses into the daily register.

    THE ALREADY-EXISTS RULE, stated because it is the whole risk of this
    feature. A register row for that student/section/date that this bridge did
    NOT write is NEVER overwritten -- not a teacher's roll-call mark, not an
    approved excuse, not a correction. It is left exactly as it is and
    reported back in `preserved`, so the caller is told rather than silently
    overridden.

    Provenance is the marker in `remarks` (see `_marker`). Two consequences
    fall out of that and both fail safe:

      * a teacher re-marking the row through the normal roll-call endpoint
        overwrites `remarks`, which removes the marker, after which this
        bridge stops touching that row for good;
      * a row this bridge wrote is updated in place on a re-run, so the
        bridge is idempotent rather than duplicating.

    IDEMPOTENCY. Re-running for the same session updates the same rows rather
    than inserting new ones (the lookup is by student/section/date with
    `period_id IS NULL`, because the table's unique constraint does not
    protect the NULL-period case), and an audit event is written only when the
    status actually changes -- the same rule the roll-call endpoint applies,
    so pressing the button twice does not fill the trail with noise that hides
    real corrections.

    Commits once, with the audit trail in the same transaction: a crash cannot
    leave a register changed with no record of who changed it.
    """
    plan = await compute_session_attendance(session, live)
    result = BridgeResult(
        session_id=plan.session_id,
        section_id=plan.section_id,
        date=plan.date,
        session_minutes=plan.session_minutes,
        session_minutes_note=plan.session_minutes_note,
        computed=list(plan.computed),
        skipped=list(plan.skipped),
    )
    if plan.session_minutes is None or plan.section_id is None or plan.date is None:
        return result
    if not plan.computed:
        return result

    student_ids = [c.student_id for c in plan.computed]
    existing_rows = (
        await session.execute(
            select(StudentAttendance)
            .where(
                and_(
                    StudentAttendance.section_id == plan.section_id,
                    StudentAttendance.date == plan.date,
                    StudentAttendance.student_id.in_(student_ids),
                    # `.is_(None)`, not `== None`, so the day-level case emits
                    # `IS NULL` explicitly.
                    StudentAttendance.period_id.is_(None),
                )
            )
            .order_by(StudentAttendance.id.asc())
        )
    ).scalars().all()
    # Ordered by id and last-wins: the unique constraint does not cover a NULL
    # period, so a duplicate day row is possible in principle and the most
    # recently written one is the live one.
    existing = {row.student_id: row for row in existing_rows}

    # (row, action, previous_status, audit reason)
    pending: List[
        Tuple[StudentAttendance, AttendanceChangeAction, Optional[AttendanceStatus], str]
    ] = []

    for computed in plan.computed:
        row = existing.get(computed.student_id)

        if row is None:
            row = StudentAttendance(
                student_id=computed.student_id,
                section_id=plan.section_id,
                date=plan.date,
                # Day-level, deliberately. `LiveClassSession` carries no
                # period, and guessing one would put the row in a period the
                # school never scheduled.
                period_id=None,
                status=computed.status,
                marked_by=actor_user_id,
                remarks=bridge_remark(plan.session_id, computed),
            )
            session.add(row)
            pending.append(
                (row, AttendanceChangeAction.MARKED, None, _audit_reason(plan, computed))
            )
        elif _was_written_by_this_bridge(row, plan.session_id):
            previous_status = row.status
            row.status = computed.status
            row.remarks = bridge_remark(plan.session_id, computed)
            session.add(row)
            if previous_status != computed.status:
                pending.append(
                    (
                        row,
                        AttendanceChangeAction.CORRECTED,
                        previous_status,
                        _audit_reason(plan, computed),
                    )
                )
        else:
            result.preserved.append(
                PreservedRegisterRow(
                    student_id=computed.student_id,
                    status=row.status,
                    reason=(
                        "Already marked for this date by someone other than "
                        "this live class, so it was left untouched."
                    ),
                )
            )
            continue

        result.records.append(row)

    # Flush so newly inserted rows have primary keys before the trail rows
    # reference them.
    await session.flush()
    for row, action, previous_status, reason in pending:
        record_attendance_change(
            session,
            attendance=row,
            action=action,
            previous_status=previous_status,
            changed_by_user_id=actor_user_id,
            reason=reason,
        )

    await session.commit()
    for row in result.records:
        await session.refresh(row)
    return result

