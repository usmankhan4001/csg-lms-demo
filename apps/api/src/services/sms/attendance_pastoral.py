"""Excuse review, attendance-correction history, and the pastoral queue.

These three are one module because they are one loop: a register is marked, a
parent explains an absence, the school decides, and if a pattern emerges
somebody has to act on it. Splitting them would mean three modules each
importing the other two.

WHAT WAS ALREADY THERE, and why the gap mattered: `check_and_emit_absence_streak`
in attendance.py correctly detects a run of absences and emits an event. Its
only subscriber emails the guardians -- and with mail unconfigured (the
default) that means the detection fires into a void. Nobody is told, nothing
is recorded, and no screen shows which children are at risk. The hard part was
built and had no destination. `raise_absence_concern` below is the destination.
"""

import datetime
import logging
from typing import List, Optional, Sequence

from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_attendance import (
    AbsenceExcuse,
    AttendanceChangeAction,
    AttendanceChangeEvent,
    AttendanceStatus,
    ExcuseStatus,
    PastoralConcern,
    PastoralConcernStatus,
    PastoralIntervention,
    StudentAttendance,
)

logger = logging.getLogger(__name__)

# Raised against this trigger by the absence-streak detector. A plain string so
# a future detector can raise a concern without a schema change.
TRIGGER_ABSENCE_STREAK = "absence_streak"


def record_attendance_change(
    session: AsyncSession,
    *,
    attendance: StudentAttendance,
    action: AttendanceChangeAction,
    previous_status: Optional[AttendanceStatus],
    changed_by_user_id: Optional[int],
    reason: Optional[str] = None,
) -> AttendanceChangeEvent:
    """Append one row to the attendance audit trail.

    Deliberately NOT async and does NOT commit: the caller adds this to the
    same session and the same transaction as the attendance write itself, so a
    crash cannot leave a register changed with no record of the change. Same
    guarantee the gradebook trail gives.

    `attendance.id` may still be None when this is called for a brand-new row;
    the caller flushes first so the PK exists. That mirrors the batch grade
    path in routers/sms_gradebook.py.
    """
    event = AttendanceChangeEvent(
        attendance_id=attendance.id or 0,
        student_id=attendance.student_id,
        section_id=attendance.section_id,
        date=attendance.date,
        period_id=attendance.period_id,
        action=action,
        previous_status=previous_status,
        new_status=attendance.status,
        changed_by_user_id=changed_by_user_id,
        reason=reason,
    )
    session.add(event)
    return event


async def get_attendance_history(
    session: AsyncSession,
    *,
    student_id: int,
    section_id: Optional[int] = None,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
) -> List[AttendanceChangeEvent]:
    """Every recorded change to a student's register, newest first."""
    conditions = [AttendanceChangeEvent.student_id == student_id]
    if section_id is not None:
        conditions.append(AttendanceChangeEvent.section_id == section_id)
    if date_from is not None:
        conditions.append(AttendanceChangeEvent.date >= date_from)
    if date_to is not None:
        conditions.append(AttendanceChangeEvent.date <= date_to)

    result = await session.execute(
        select(AttendanceChangeEvent)
        .where(and_(*conditions))
        .order_by(AttendanceChangeEvent.created_at.desc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Absence excuses
# ---------------------------------------------------------------------------


async def apply_approved_excuse(
    session: AsyncSession,
    *,
    excuse: AbsenceExcuse,
    reviewed_by_user_id: Optional[int],
) -> int:
    """Convert that day's ABSENT records to EXCUSED, and record why.

    THE DECISION, and it is a real one because it moves the attendance
    percentage: an approved excuse CONVERTS the record rather than merely
    annotating it.

    Three reasons.

    1. The percentage formula already treats EXCUSED as present-equivalent
       (`present + 0.5*late + excused` in routers/sms_attendance.py). Leaving
       an approved absence as ABSENT means the child's attendance figure still
       counts against them despite the school having accepted the reason --
       which is precisely the thing the note exists to correct. A school that
       approves a note and then reports the child as absent has not actually
       approved anything.

    2. It keeps ONE source of truth for "what was this child's status that
       day". The alternative -- status stays ABSENT, an excuse row sits
       alongside -- forces every reader (monthly sheet, parent digest, report
       card, streak detector, any future export) to join against excuses and
       apply the rule itself. One of them will forget, and then two screens
       disagree about the same child.

    3. The conversion is auditable and reversible because the original ABSENT
       is preserved in the change trail, attributed to the reviewer, with the
       excuse reason attached. Nothing is destroyed; the history says
       "was ABSENT, now EXCUSED, because <reason>, approved by <user>".

    Only ABSENT records convert. A day already marked PRESENT or LATE is left
    alone: an excuse cannot make a child who attended *more* present, and
    silently upgrading LATE would hide a real punctuality record.

    Returns the number of records converted -- 0 is a legitimate answer (the
    register may not have been taken yet, or the child was marked present).
    """
    result = await session.execute(
        select(StudentAttendance).where(
            and_(
                StudentAttendance.student_id == excuse.student_id,
                StudentAttendance.section_id == excuse.section_id,
                StudentAttendance.date == excuse.date,
                StudentAttendance.status == AttendanceStatus.ABSENT,
            )
        )
    )
    records = list(result.scalars().all())

    for record in records:
        previous = record.status
        record.status = AttendanceStatus.EXCUSED
        session.add(record)
        record_attendance_change(
            session,
            attendance=record,
            action=AttendanceChangeAction.CORRECTED,
            previous_status=previous,
            changed_by_user_id=reviewed_by_user_id,
            reason=f"Absence excuse approved: {excuse.reason}",
        )

    return len(records)


# ---------------------------------------------------------------------------
# Pastoral concerns
# ---------------------------------------------------------------------------


async def raise_absence_concern(
    session: AsyncSession,
    *,
    student_id: int,
    section_id: int,
    streak: int,
) -> Optional[PastoralConcern]:
    """Open a pastoral concern for an absence streak, if one is not already open.

    Idempotent by design: the streak detector runs on every roll-call
    submission, so without this check a child absent for a week would collect a
    fresh concern every morning and the queue would be unusable by Wednesday.
    An existing OPEN or IN_PROGRESS concern for the same trigger is UPDATED
    with the higher magnitude instead, so the queue shows the current severity.

    Returns the concern (new or updated), or None if nothing was recorded.
    """
    existing = (
        await session.execute(
            select(PastoralConcern).where(
                and_(
                    PastoralConcern.student_id == student_id,
                    PastoralConcern.section_id == section_id,
                    PastoralConcern.trigger == TRIGGER_ABSENCE_STREAK,
                    PastoralConcern.status.in_(
                        [PastoralConcernStatus.OPEN, PastoralConcernStatus.IN_PROGRESS]
                    ),
                )
            )
        )
    ).scalars().first()

    detail = f"Absent {streak} consecutive school days"

    if existing is not None:
        # Only ever escalate. A streak that shortens (because an excuse was
        # approved for one day) must not quietly downgrade a concern staff are
        # already working; they close it themselves when it is resolved.
        if existing.magnitude is None or streak > existing.magnitude:
            existing.magnitude = streak
            existing.detail = detail
            session.add(existing)
        return existing

    concern = PastoralConcern(
        student_id=student_id,
        section_id=section_id,
        trigger=TRIGGER_ABSENCE_STREAK,
        detail=detail,
        magnitude=streak,
        status=PastoralConcernStatus.OPEN,
    )
    session.add(concern)
    return concern


async def list_pastoral_concerns(
    session: AsyncSession,
    *,
    section_ids: Optional[Sequence[int]] = None,
    status_filter: Optional[PastoralConcernStatus] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[PastoralConcern]:
    """The at-risk queue.

    `section_ids` is the gate, not a convenience filter: a caller restricted to
    their own sections passes theirs, and an empty sequence means "no sections"
    and must return nothing rather than everything. That distinction is why
    this takes `Optional[Sequence]` and treats None (unrestricted) differently
    from [] (restricted to nothing).
    """
    conditions = []
    if section_ids is not None:
        if not section_ids:
            return []
        conditions.append(PastoralConcern.section_id.in_(list(section_ids)))
    if status_filter is not None:
        conditions.append(PastoralConcern.status == status_filter)

    stmt = select(PastoralConcern)
    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await session.execute(
        stmt.order_by(PastoralConcern.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


async def list_interventions(
    session: AsyncSession, *, concern_id: int
) -> List[PastoralIntervention]:
    result = await session.execute(
        select(PastoralIntervention)
        .where(PastoralIntervention.concern_id == concern_id)
        .order_by(PastoralIntervention.created_at.asc())
    )
    return list(result.scalars().all())
