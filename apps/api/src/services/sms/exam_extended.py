"""Seating allocation and resits.

Both deliberately refuse rather than guess. A seating clash and a duplicate
resit are data-entry mistakes a school needs told about, not silently
resolved -- an auto-reseated candidate turns up at an exam hall to find
someone in their chair, which is worse than an error at allocation time.
"""

import datetime
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_exam import Exam, ExamResult, ExamSectionSchedule, ExamAttendanceStatus
from src.db.sms_exam_extended import (
    ExamResit,
    ExamSeatAllocation,
    ResitReason,
    ResitStatus,
)


class SeatingError(ValueError):
    """A seat could not be allocated. Carries a reason a human can act on."""


class ResitError(ValueError):
    """A resit could not be approved or scheduled."""


async def allocate_seats(
    *,
    session: AsyncSession,
    schedule_id: int,
    allocations: Sequence[Tuple[int, str, Optional[str]]],
    allocated_by_user_id: Optional[int],
    replace_existing: bool = False,
) -> Tuple[List[ExamSeatAllocation], List[str]]:
    """Allocate seats for one section's sitting.

    `allocations` is a sequence of (student_id, seat_label, notes).

    Returns (written, skipped_reasons). A clash is SKIPPED with a stated
    reason rather than raising, so one bad row in a hall of 200 does not
    abort the whole allocation -- but nothing is silently overwritten unless
    `replace_existing` is set explicitly.
    """
    schedule = (
        await session.execute(
            select(ExamSectionSchedule).where(ExamSectionSchedule.id == schedule_id)
        )
    ).scalar_one_or_none()
    if schedule is None:
        raise SeatingError(f"Exam sitting {schedule_id} not found.")

    existing = (
        (
            await session.execute(
                select(ExamSeatAllocation).where(
                    ExamSeatAllocation.schedule_id == schedule_id
                )
            )
        )
        .scalars()
        .all()
    )
    by_student = {a.student_id: a for a in existing}
    by_label = {a.seat_label: a for a in existing}

    written: List[ExamSeatAllocation] = []
    skipped: List[str] = []
    # Track within-call claims too: two rows in one payload can clash with
    # each other, and only checking the database would let the second
    # silently win.
    claimed_labels = set(by_label)
    claimed_students = set(by_student)

    for student_id, seat_label, notes in allocations:
        label = (seat_label or "").strip()
        if not label:
            skipped.append(f"Student {student_id}: no seat label given.")
            continue

        prior_seat = by_student.get(student_id)
        prior_holder = by_label.get(label)

        if prior_holder is not None and prior_holder.student_id != student_id:
            if not replace_existing:
                skipped.append(
                    f"Seat {label} is already allocated to student "
                    f"{prior_holder.student_id}."
                )
                continue
            await session.delete(prior_holder)
            claimed_labels.discard(label)
            by_label.pop(label, None)
        elif label in claimed_labels and prior_holder is None:
            skipped.append(f"Seat {label} was allocated twice in this request.")
            continue

        if prior_seat is not None:
            if not replace_existing:
                skipped.append(
                    f"Student {student_id} already has seat {prior_seat.seat_label}."
                )
                continue
            prior_seat.seat_label = label
            prior_seat.notes = notes
            prior_seat.allocated_by_user_id = allocated_by_user_id
            session.add(prior_seat)
            written.append(prior_seat)
            claimed_labels.add(label)
            continue

        if student_id in claimed_students and prior_seat is None:
            skipped.append(f"Student {student_id} appears twice in this request.")
            continue

        row = ExamSeatAllocation(
            schedule_id=schedule_id,
            student_id=student_id,
            seat_label=label,
            notes=notes,
            allocated_by_user_id=allocated_by_user_id,
        )
        session.add(row)
        written.append(row)
        claimed_labels.add(label)
        claimed_students.add(student_id)

    await session.commit()
    for row in written:
        await session.refresh(row)
    return written, skipped


async def list_seats(
    *, session: AsyncSession, schedule_id: int
) -> List[ExamSeatAllocation]:
    result = await session.execute(
        select(ExamSeatAllocation)
        .where(ExamSeatAllocation.schedule_id == schedule_id)
        .order_by(ExamSeatAllocation.seat_label)
    )
    return list(result.scalars().all())


async def approve_resit(
    *,
    session: AsyncSession,
    original_exam_id: int,
    student_id: int,
    reason: ResitReason,
    reason_detail: Optional[str],
    approved_by_user_id: Optional[int],
) -> ExamResit:
    """Approve a second sitting. Never edits the original result.

    The original mark and attendance stay exactly as recorded: a school asked
    why a grade changed must be able to show both sittings.
    """
    exam = (
        await session.execute(select(Exam).where(Exam.id == original_exam_id))
    ).scalar_one_or_none()
    if exam is None:
        raise ResitError(f"Exam {original_exam_id} not found.")

    existing = (
        await session.execute(
            select(ExamResit).where(
                ExamResit.original_exam_id == original_exam_id,
                ExamResit.student_id == student_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None and existing.status != ResitStatus.CANCELLED:
        raise ResitError(
            f"Student {student_id} already has a {existing.status} resit for "
            f"this exam."
        )

    if existing is not None:
        # A cancelled resit is reopened rather than duplicated, so the
        # unique constraint holds and the history stays in one row.
        existing.status = ResitStatus.APPROVED
        existing.reason = reason
        existing.reason_detail = reason_detail
        existing.approved_by_user_id = approved_by_user_id
        existing.approved_at = datetime.datetime.now(datetime.timezone.utc)
        existing.resit_exam_id = None
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return existing

    row = ExamResit(
        original_exam_id=original_exam_id,
        student_id=student_id,
        reason=reason,
        reason_detail=reason_detail,
        approved_by_user_id=approved_by_user_id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def schedule_resit(
    *, session: AsyncSession, resit_id: int, resit_exam_id: int
) -> ExamResit:
    """Attach an approved resit to the exam the candidate will actually sit."""
    row = (
        await session.execute(select(ExamResit).where(ExamResit.id == resit_id))
    ).scalar_one_or_none()
    if row is None:
        raise ResitError(f"Resit {resit_id} not found.")
    if row.status == ResitStatus.CANCELLED:
        raise ResitError("This resit was cancelled; approve it again first.")

    target = (
        await session.execute(select(Exam).where(Exam.id == resit_exam_id))
    ).scalar_one_or_none()
    if target is None:
        raise ResitError(f"Exam {resit_exam_id} not found.")
    if resit_exam_id == row.original_exam_id:
        raise ResitError("A resit cannot point at the original exam.")

    row.resit_exam_id = resit_exam_id
    row.status = ResitStatus.SCHEDULED
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_resits(
    *,
    session: AsyncSession,
    original_exam_id: Optional[int] = None,
    student_id: Optional[int] = None,
    status: Optional[ResitStatus] = None,
) -> List[ExamResit]:
    stmt = select(ExamResit)
    if original_exam_id is not None:
        stmt = stmt.where(ExamResit.original_exam_id == original_exam_id)
    if student_id is not None:
        stmt = stmt.where(ExamResit.student_id == student_id)
    if status is not None:
        stmt = stmt.where(ExamResit.status == status)
    result = await session.execute(stmt.order_by(ExamResit.approved_at.desc()))
    return list(result.scalars().all())


async def suggest_resit_candidates(
    *, session: AsyncSession, exam_id: int
) -> List[dict]:
    """Candidates a school may want to offer a resit, with the evidence.

    Deliberately a SUGGESTION with a stated reason, never an automatic
    approval: whether an absent child resits is a judgement about that child,
    not a rule. Returns only what the record actually shows -- a candidate
    with no result row is not listed as "failed", because nobody knows.
    """
    results = (
        (
            await session.execute(
                select(ExamResult).where(ExamResult.exam_id == exam_id)
            )
        )
        .scalars()
        .all()
    )
    already = {
        r.student_id
        for r in await list_resits(session=session, original_exam_id=exam_id)
        if r.status != ResitStatus.CANCELLED
    }

    out: List[dict] = []
    for r in results:
        if r.student_id in already:
            continue
        if r.attendance_status == ExamAttendanceStatus.ABSENT:
            out.append(
                {
                    "student_id": r.student_id,
                    "suggested_reason": ResitReason.ABSENT.value,
                    "evidence": "Recorded absent for this exam.",
                }
            )
        elif (
            r.attendance_status == ExamAttendanceStatus.PRESENT
            and r.marks_obtained is None
        ):
            # Sat the exam but has no mark. That is an unmarked paper, not a
            # fail -- so it is surfaced as a gap to chase, not a resit reason.
            out.append(
                {
                    "student_id": r.student_id,
                    "suggested_reason": None,
                    "evidence": "Sat the exam but has no mark recorded yet.",
                }
            )
    return out
