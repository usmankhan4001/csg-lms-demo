"""Exam seating/resits and library reservations.

The tests that matter here are the refusals. Seating clashes and duplicate
holds are data-entry mistakes a school must be TOLD about: an auto-reseated
candidate finds someone in their chair on the day, and a silently reordered
queue means telling a child they are next when they are not.
"""

import datetime

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_exam import (
    Exam,
    ExamAttendanceStatus,
    ExamResult,
    ExamSectionSchedule,
)
from src.db.sms_exam_extended import ResitReason, ResitStatus

# `sms_exam.assessment_plan_id` is a foreign key to `sms_assessment_plan`, so
# that table must be registered in the metadata before the fixture creates
# tables -- otherwise SQLAlchemy raises NoReferencedTableError. Production
# never hits this because `import_all_models()` registers everything; a test
# module that imports only what it names does not.
from src.db.sms_gradebook import AssessmentPlan  # noqa: F401
from src.db.sms_library import LibraryBook
from src.db.sms_library_extended import ReservationStatus
from src.services.sms.exam_extended import (
    ResitError,
    SeatingError,
    allocate_seats,
    approve_resit,
    list_seats,
    schedule_resit,
    suggest_resit_candidates,
)
from src.services.sms.library_extended import (
    ReservationError,
    close_reservation,
    expire_stale_holds,
    mark_ready,
    next_in_queue,
    queue_position,
    reserve_book,
)


async def _make_exam(db: AsyncSession, title: str = "Physics Final") -> Exam:
    exam = Exam(
        campus_id=1,
        academic_term_id=1,
        course_id=101,
        title=title,
        exam_type="Final",
        exam_date=datetime.date(2026, 11, 20),
        duration_minutes=120,
        total_marks=50.0,
        pass_marks=20.0,
    )
    db.add(exam)
    await db.commit()
    await db.refresh(exam)
    return exam


async def _make_sitting(db: AsyncSession, exam_id: int, section_id: int = 1):
    row = ExamSectionSchedule(exam_id=exam_id, section_id=section_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _make_book(db: AsyncSession, copies: int = 1, available: int = 0):
    book = LibraryBook(
        campus_id=1,
        title="A Wrinkle in Time",
        author="Madeleine L'Engle",
        total_copies=copies,
        available_copies=available,
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


# ---------------------------------------------------------------------------
# Seating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_seat_clash_is_reported_not_silently_reassigned(db: AsyncSession):
    exam = await _make_exam(db)
    sitting = await _make_sitting(db, exam.id)

    await allocate_seats(
        session=db,
        schedule_id=sitting.id,
        allocations=[(1, "A1", None)],
        allocated_by_user_id=99,
    )
    written, skipped = await allocate_seats(
        session=db,
        schedule_id=sitting.id,
        allocations=[(2, "A1", None)],
        allocated_by_user_id=99,
    )

    assert written == []
    assert len(skipped) == 1
    assert "A1" in skipped[0]
    seats = await list_seats(session=db, schedule_id=sitting.id)
    assert len(seats) == 1
    assert seats[0].student_id == 1, "the original candidate must keep their seat"


@pytest.mark.asyncio
async def test_the_same_seat_twice_in_one_request_is_caught(db: AsyncSession):
    """Only checking the database would let the second row silently win."""
    exam = await _make_exam(db)
    sitting = await _make_sitting(db, exam.id)

    written, skipped = await allocate_seats(
        session=db,
        schedule_id=sitting.id,
        allocations=[(1, "B2", None), (2, "B2", None)],
        allocated_by_user_id=99,
    )
    assert len(written) == 1
    assert any("twice" in s for s in skipped)


@pytest.mark.asyncio
async def test_replace_existing_reseats_deliberately(db: AsyncSession):
    exam = await _make_exam(db)
    sitting = await _make_sitting(db, exam.id)

    await allocate_seats(
        session=db,
        schedule_id=sitting.id,
        allocations=[(1, "C3", None)],
        allocated_by_user_id=99,
    )
    written, skipped = await allocate_seats(
        session=db,
        schedule_id=sitting.id,
        allocations=[(1, "D4", "extra time")],
        allocated_by_user_id=99,
        replace_existing=True,
    )
    assert skipped == []
    assert written[0].seat_label == "D4"
    assert written[0].notes == "extra time"


@pytest.mark.asyncio
async def test_seating_an_unknown_sitting_refuses(db: AsyncSession):
    with pytest.raises(SeatingError):
        await allocate_seats(
            session=db,
            schedule_id=999_999,
            allocations=[(1, "A1", None)],
            allocated_by_user_id=99,
        )


# ---------------------------------------------------------------------------
# Resits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_resit_never_edits_the_original_result(db: AsyncSession):
    exam = await _make_exam(db)
    original = ExamResult(
        exam_id=exam.id,
        student_id=7,
        marks_obtained=12.0,
        attendance_status=ExamAttendanceStatus.PRESENT,
    )
    db.add(original)
    await db.commit()
    await db.refresh(original)

    await approve_resit(
        session=db,
        original_exam_id=exam.id,
        student_id=7,
        reason=ResitReason.FAILED,
        reason_detail="Below pass mark",
        approved_by_user_id=99,
    )

    await db.refresh(original)
    assert original.marks_obtained == 12.0, "the first sitting must stay readable"
    assert original.attendance_status == ExamAttendanceStatus.PRESENT


@pytest.mark.asyncio
async def test_a_duplicate_live_resit_is_refused(db: AsyncSession):
    exam = await _make_exam(db)
    await approve_resit(
        session=db,
        original_exam_id=exam.id,
        student_id=8,
        reason=ResitReason.ILLNESS,
        reason_detail=None,
        approved_by_user_id=99,
    )
    with pytest.raises(ResitError):
        await approve_resit(
            session=db,
            original_exam_id=exam.id,
            student_id=8,
            reason=ResitReason.ABSENT,
            reason_detail=None,
            approved_by_user_id=99,
        )


@pytest.mark.asyncio
async def test_a_resit_cannot_point_at_the_original_exam(db: AsyncSession):
    exam = await _make_exam(db)
    resit = await approve_resit(
        session=db,
        original_exam_id=exam.id,
        student_id=9,
        reason=ResitReason.ABSENT,
        reason_detail=None,
        approved_by_user_id=99,
    )
    with pytest.raises(ResitError):
        await schedule_resit(session=db, resit_id=resit.id, resit_exam_id=exam.id)


@pytest.mark.asyncio
async def test_scheduling_a_resit_links_the_second_sitting(db: AsyncSession):
    exam = await _make_exam(db)
    makeup = await _make_exam(db, title="Physics Final (Resit)")
    resit = await approve_resit(
        session=db,
        original_exam_id=exam.id,
        student_id=10,
        reason=ResitReason.TIMETABLE_CLASH,
        reason_detail=None,
        approved_by_user_id=99,
    )
    updated = await schedule_resit(
        session=db, resit_id=resit.id, resit_exam_id=makeup.id
    )
    assert updated.status == ResitStatus.SCHEDULED
    assert updated.resit_exam_id == makeup.id


@pytest.mark.asyncio
async def test_an_unmarked_paper_is_not_suggested_as_a_failure(db: AsyncSession):
    """Sat the exam with no mark is an unmarked paper, not grounds for a resit.

    Suggesting FAILED here would invent an outcome nobody recorded -- the same
    fabrication class this codebase has torn out repeatedly.
    """
    exam = await _make_exam(db)
    db.add(
        ExamResult(
            exam_id=exam.id,
            student_id=11,
            marks_obtained=None,
            attendance_status=ExamAttendanceStatus.PRESENT,
        )
    )
    db.add(
        ExamResult(
            exam_id=exam.id,
            student_id=12,
            marks_obtained=None,
            attendance_status=ExamAttendanceStatus.ABSENT,
        )
    )
    await db.commit()

    out = await suggest_resit_candidates(session=db, exam_id=exam.id)
    by_student = {c["student_id"]: c for c in out}

    assert by_student[11]["suggested_reason"] is None
    assert "no mark" in by_student[11]["evidence"].lower()
    assert by_student[12]["suggested_reason"] == ResitReason.ABSENT.value


@pytest.mark.asyncio
async def test_a_candidate_with_an_approved_resit_is_not_suggested_again(
    db: AsyncSession,
):
    exam = await _make_exam(db)
    db.add(
        ExamResult(
            exam_id=exam.id,
            student_id=13,
            marks_obtained=None,
            attendance_status=ExamAttendanceStatus.ABSENT,
        )
    )
    await db.commit()

    assert len(await suggest_resit_candidates(session=db, exam_id=exam.id)) == 1
    await approve_resit(
        session=db,
        original_exam_id=exam.id,
        student_id=13,
        reason=ResitReason.ABSENT,
        reason_detail=None,
        approved_by_user_id=99,
    )
    assert await suggest_resit_candidates(session=db, exam_id=exam.id) == []


# ---------------------------------------------------------------------------
# Library reservations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_hold_is_kept_for_the_right_borrower_in_order(db: AsyncSession):
    book = await _make_book(db, copies=1, available=0)
    first, pos_first = await reserve_book(session=db, book_id=book.id, user_id=101)
    _, pos_second = await reserve_book(session=db, book_id=book.id, user_id=102)

    assert pos_first == 1
    assert pos_second == 2

    nxt = await next_in_queue(session=db, book_id=book.id)
    assert nxt is not None
    assert nxt.user_id == 101, "the reader who waited longest must be next"
    assert nxt.id == first.id


@pytest.mark.asyncio
async def test_a_second_live_hold_by_the_same_reader_is_refused(db: AsyncSession):
    book = await _make_book(db)
    await reserve_book(session=db, book_id=book.id, user_id=201)
    with pytest.raises(ReservationError):
        await reserve_book(session=db, book_id=book.id, user_id=201)


@pytest.mark.asyncio
async def test_cancelling_moves_the_queue_up_without_stored_positions(
    db: AsyncSession,
):
    book = await _make_book(db)
    first, _ = await reserve_book(session=db, book_id=book.id, user_id=301)
    second, _ = await reserve_book(session=db, book_id=book.id, user_id=302)

    await close_reservation(
        session=db, reservation_id=first.id, status=ReservationStatus.CANCELLED
    )

    await db.refresh(second)
    assert await queue_position(session=db, reservation=second) == 1


@pytest.mark.asyncio
async def test_a_copy_cannot_be_held_when_none_is_available(db: AsyncSession):
    """Otherwise the desk tells a child their book is waiting when it is not."""
    book = await _make_book(db, copies=1, available=0)
    row, _ = await reserve_book(session=db, book_id=book.id, user_id=401)
    with pytest.raises(ReservationError):
        await mark_ready(session=db, reservation_id=row.id)


@pytest.mark.asyncio
async def test_a_ready_hold_expires_and_releases_the_queue(db: AsyncSession):
    book = await _make_book(db, copies=1, available=1)
    row, _ = await reserve_book(session=db, book_id=book.id, user_id=501)
    ready = await mark_ready(session=db, reservation_id=row.id, hold_days=1)
    assert ready.status == ReservationStatus.READY
    assert await queue_position(session=db, reservation=ready) == 0

    ready.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=1
    )
    db.add(ready)
    await db.commit()

    expired = await expire_stale_holds(session=db)
    assert [e.id for e in expired] == [ready.id]
    await db.refresh(ready)
    assert ready.status == ReservationStatus.EXPIRED


@pytest.mark.asyncio
async def test_closing_with_a_live_status_is_refused(db: AsyncSession):
    book = await _make_book(db)
    row, _ = await reserve_book(session=db, book_id=book.id, user_id=601)
    with pytest.raises(ReservationError):
        await close_reservation(
            session=db, reservation_id=row.id, status=ReservationStatus.WAITING
        )


@pytest.mark.asyncio
async def test_reservations_carry_the_books_campus_for_scoping(db: AsyncSession):
    book = await _make_book(db)
    row, _ = await reserve_book(session=db, book_id=book.id, user_id=701)
    assert row.campus_id == book.campus_id
