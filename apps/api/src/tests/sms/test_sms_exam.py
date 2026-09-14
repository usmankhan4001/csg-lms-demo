"""
School examination (M04) and homework-hint deduction (M40) tests.

The load-bearing assertions here are the ones about what does NOT happen:

- An unmarked or absent student must never be written to the gradebook as a
  zero. This codebase has twice had to tear out endpoints that defaulted
  missing academic data to a plausible number, and a GradebookEntry with
  raw_score 0.0 is indistinguishable from "sat the exam and scored nothing"
  once the weighted-GPA engine reads it.
- Posting results twice must not double-write, and re-grading must not
  deduct hint penalties twice. Both are proven by running the operation
  twice and asserting the second run changes nothing.
"""

import datetime

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_exam import (
    AssignmentHintUsage,
    Exam,
    ExamAttendanceStatus,
    ExamResult,
    ExamStatus,
)
from src.db.sms_gradebook import GradebookEntry
from src.schemas.sms_gradebook import AssessmentPlanCreate
from src.core.keycloak_auth import KeycloakUserPrincipal
from src.routers.sms_gradebook import create_assessment_plan

# Assessment-plan creation is now role-gated and section-scoped: it was
# previously reachable by ANY authenticated user, so a student could define
# the plans their own marks are computed against. These tests exercise exam
# mechanics, not authorization, so the fixture acts as a school admin.
_ADMIN = KeycloakUserPrincipal(
    sub="exam-fixture-admin", org_id=1, campus_id=1, roles={"SCHOOL_ADMIN"}
)
from src.services.sms.exam import (
    ExamNotGradebookLinkedError,
    ExamResultsAlreadyPostedError,
    apply_hint_deduction,
    compute_hint_deduction_percentage,
    post_exam_results_to_gradebook,
    record_hint_usage,
    summarize_exam_results,
)


async def _make_plan(db: AsyncSession, weight: float = 50.0, max_score: float = 100.0):
    return await create_assessment_plan(
        payload=AssessmentPlanCreate(
            course_id=101,
            section_id=1,
            academic_term_id=1,
            assessment_name="Final Exam",
            weight_percentage=weight,
            max_score=max_score,
        ),
        principal=_ADMIN,
        session=db,
    )


async def _make_exam(db: AsyncSession, plan_id=None, total_marks: float = 50.0) -> Exam:
    exam = Exam(
        campus_id=1,
        academic_term_id=1,
        course_id=101,
        title="Physics Final",
        exam_type="Final",
        exam_date=datetime.date(2026, 11, 20),
        duration_minutes=120,
        total_marks=total_marks,
        pass_marks=20.0,
        assessment_plan_id=plan_id,
    )
    db.add(exam)
    await db.commit()
    await db.refresh(exam)
    return exam


async def _add_result(db: AsyncSession, exam_id: int, student_id: int, marks=None,
                      status=ExamAttendanceStatus.PRESENT) -> ExamResult:
    r = ExamResult(
        exam_id=exam_id,
        student_id=student_id,
        marks_obtained=marks,
        attendance_status=status,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


@pytest.mark.asyncio
async def test_exam_results_become_real_gradebook_entries(db: AsyncSession):
    """The whole point of M04: marks land in the ONE grading engine."""
    plan = await _make_plan(db, weight=50.0, max_score=100.0)
    exam = await _make_exam(db, plan_id=plan.id, total_marks=50.0)
    # 40/50 = 80%, scaled onto a plan scored out of 100 -> raw_score 80.
    await _add_result(db, exam.id, student_id=501, marks=40.0)

    written, skipped, plan_id = await post_exam_results_to_gradebook(db, exam.id, graded_by=99)

    assert (written, skipped, plan_id) == (1, 0, plan.id)

    entry = (
        await db.execute(
            select(GradebookEntry).where(
                GradebookEntry.student_id == 501,
                GradebookEntry.assessment_plan_id == plan.id,
            )
        )
    ).scalar_one()
    assert entry.raw_score == 80.0
    assert entry.max_score == 100.0
    # 80% of a 50%-weighted assessment contributes 40 weighted points.
    assert entry.weighted_score == 40.0
    assert entry.letter_grade == "A"
    assert entry.gpa_point == 3.7

    await db.refresh(exam)
    assert exam.status == ExamStatus.RESULTS_POSTED


@pytest.mark.asyncio
async def test_unmarked_and_absent_students_are_skipped_never_zeroed(db: AsyncSession):
    """A student who did not sit has NO grade -- not a zero on their report card."""
    plan = await _make_plan(db)
    exam = await _make_exam(db, plan_id=plan.id)

    await _add_result(db, exam.id, student_id=601, marks=45.0)                      # marked
    await _add_result(db, exam.id, student_id=602, marks=None)                      # not yet marked
    await _add_result(db, exam.id, student_id=603, marks=None,
                      status=ExamAttendanceStatus.ABSENT)                           # absent
    await _add_result(db, exam.id, student_id=604, marks=0.0,
                      status=ExamAttendanceStatus.EXEMPT)                           # exempt

    written, skipped, _ = await post_exam_results_to_gradebook(db, exam.id)

    assert written == 1
    assert skipped == 3

    entries = (await db.execute(select(GradebookEntry))).scalars().all()
    graded_students = {e.student_id for e in entries}
    assert graded_students == {601}
    # The critical negative: no zero-score rows were invented for the others.
    assert 603 not in graded_students
    assert 604 not in graded_students


@pytest.mark.asyncio
async def test_posting_results_twice_is_refused(db: AsyncSession):
    plan = await _make_plan(db)
    exam = await _make_exam(db, plan_id=plan.id)
    await _add_result(db, exam.id, student_id=701, marks=30.0)

    await post_exam_results_to_gradebook(db, exam.id)

    with pytest.raises(ExamResultsAlreadyPostedError):
        await post_exam_results_to_gradebook(db, exam.id)

    entries = (await db.execute(
        select(GradebookEntry).where(GradebookEntry.student_id == 701)
    )).scalars().all()
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_exam_without_assessment_plan_refuses_rather_than_inventing_a_weight(db: AsyncSession):
    """Guessing what an exam is worth would silently change every student's grade."""
    exam = await _make_exam(db, plan_id=None)
    await _add_result(db, exam.id, student_id=801, marks=40.0)

    with pytest.raises(ExamNotGradebookLinkedError):
        await post_exam_results_to_gradebook(db, exam.id)

    assert (await db.execute(select(GradebookEntry))).scalars().first() is None


@pytest.mark.asyncio
async def test_summary_statistics_ignore_unmarked_students(db: AsyncSession):
    plan = await _make_plan(db)
    exam = await _make_exam(db, plan_id=plan.id, total_marks=50.0)
    await _add_result(db, exam.id, student_id=901, marks=45.0)
    await _add_result(db, exam.id, student_id=902, marks=15.0)
    await _add_result(db, exam.id, student_id=903, marks=None)
    await _add_result(db, exam.id, student_id=904, marks=None,
                      status=ExamAttendanceStatus.ABSENT)

    summary = await summarize_exam_results(db, exam)

    assert summary.total_students == 4
    assert summary.marked == 2
    assert summary.not_yet_marked == 2
    assert summary.absent == 1
    assert summary.average_marks == 30.0     # (45 + 15) / 2, unmarked excluded
    assert summary.highest_marks == 45.0
    assert summary.lowest_marks == 15.0
    assert summary.pass_count == 1           # pass_marks = 20
    assert summary.fail_count == 1


@pytest.mark.asyncio
async def test_summary_reports_absence_not_zero_when_nothing_is_marked(db: AsyncSession):
    """No marks at all must yield None averages, never 0.0."""
    plan = await _make_plan(db)
    exam = await _make_exam(db, plan_id=plan.id)
    await _add_result(db, exam.id, student_id=1001, marks=None)

    summary = await summarize_exam_results(db, exam)

    assert summary.average_marks is None
    assert summary.highest_marks is None
    assert summary.lowest_marks is None


# ---------------------------------------------------------------------------
# M40 -- hint deduction
# ---------------------------------------------------------------------------

def test_hint_deduction_percentage_is_capped():
    assert compute_hint_deduction_percentage(0) == 0.0
    assert compute_hint_deduction_percentage(1) == 5.0
    assert compute_hint_deduction_percentage(4) == 20.0
    # Capped: heavy hint use must not be able to zero real work.
    assert compute_hint_deduction_percentage(20) == 30.0


@pytest.mark.asyncio
async def test_hint_usage_accrues_per_student_per_assignment(db: AsyncSession):
    await record_hint_usage(db, student_id=1101, assignment_ref="hw-1", hint_level=1)
    await record_hint_usage(db, student_id=1101, assignment_ref="hw-1", hint_level=3)
    usage = await record_hint_usage(db, student_id=1101, assignment_ref="hw-1", hint_level=2)

    assert usage.hints_used == 3
    # A level-3 "almost the answer" hint is not equivalent to three nudges.
    assert usage.max_hint_level == 3

    # A different assignment is tracked separately.
    other = await record_hint_usage(db, student_id=1101, assignment_ref="hw-2", hint_level=1)
    assert other.hints_used == 1


@pytest.mark.asyncio
async def test_hint_deduction_is_idempotent_across_regrading(db: AsyncSession):
    """Grade twice, deduct once -- the defining requirement of M40.

    Without this, every re-grade would compound the penalty and a student who
    used two hints would lose 10%, then 19%, then 27.1% of their mark.
    """
    plan = await _make_plan(db)
    entry = GradebookEntry(
        student_id=1201,
        assessment_plan_id=plan.id,
        raw_score=100.0,
        max_score=100.0,
        weighted_score=50.0,
        letter_grade="A+",
        gpa_point=4.0,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    await record_hint_usage(db, student_id=1201, assignment_ref="hw-idem", hint_level=1)
    await record_hint_usage(db, student_id=1201, assignment_ref="hw-idem", hint_level=1)

    first = await apply_hint_deduction(db, 1201, "hw-idem", entry.id)
    await db.refresh(entry)
    score_after_first = entry.raw_score

    assert first == 10.0            # 2 hints x 5%
    assert score_after_first == 90.0

    # Re-grade: recomputes from the original mark rather than compounding.
    second = await apply_hint_deduction(db, 1201, "hw-idem", entry.id)
    await db.refresh(entry)

    assert second == 10.0
    assert entry.raw_score == 90.0, "re-grading compounded the hint penalty"


@pytest.mark.asyncio
async def test_hint_deduction_converges_when_more_hints_are_used_after_grading(db: AsyncSession):
    """A later hint must reprice from the ORIGINAL score, not the reduced one."""
    plan = await _make_plan(db)
    entry = GradebookEntry(
        student_id=1301,
        assessment_plan_id=plan.id,
        raw_score=100.0,
        max_score=100.0,
        weighted_score=50.0,
        letter_grade="A+",
        gpa_point=4.0,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    await record_hint_usage(db, student_id=1301, assignment_ref="hw-more", hint_level=1)
    await apply_hint_deduction(db, 1301, "hw-more", entry.id)
    await db.refresh(entry)
    assert entry.raw_score == 95.0

    # Student takes two more hints, then the work is graded again.
    await record_hint_usage(db, student_id=1301, assignment_ref="hw-more", hint_level=1)
    await record_hint_usage(db, student_id=1301, assignment_ref="hw-more", hint_level=1)
    pct = await apply_hint_deduction(db, 1301, "hw-more", entry.id)
    await db.refresh(entry)

    assert pct == 15.0              # 3 hints total
    assert entry.raw_score == 85.0  # 15% off the ORIGINAL 100, not off 95


@pytest.mark.asyncio
async def test_no_hints_means_no_deduction(db: AsyncSession):
    plan = await _make_plan(db)
    entry = GradebookEntry(
        student_id=1401,
        assessment_plan_id=plan.id,
        raw_score=88.0,
        max_score=100.0,
        weighted_score=44.0,
        letter_grade="A",
        gpa_point=3.7,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    pct = await apply_hint_deduction(db, 1401, "never-asked", entry.id)
    await db.refresh(entry)

    assert pct == 0.0
    assert entry.raw_score == 88.0

    usage = (await db.execute(
        select(AssignmentHintUsage).where(AssignmentHintUsage.student_id == 1401)
    )).scalars().first()
    assert usage is None


# ---------------------------------------------------------------------------
# M40 -- the tutor must actually RECORD hints, or the deduction is dead code
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tutor_records_a_hint_so_the_deduction_can_ever_fire(db: AsyncSession):
    """Regression guard: the deduction machinery existed but nothing called it.

    Every part of M40 can be correct and still never affect a single grade if
    the tutor does not record the hint it just gave. This asserts the wiring,
    not the arithmetic.
    """
    from unittest.mock import patch

    from src.services.ai.socratic_tutor import stream_socratic_guidance

    async def fake_stream(*args, **kwargs):
        yield "What happens if you factor the left-hand side?"

    with patch("src.services.ai.socratic_tutor.generate_stream", side_effect=fake_stream):
        async for _ in stream_socratic_guidance(
            query="How do I solve 2x^2 + 5x + 2 = 0?",
            user_id="1501",
            db_session=db,
            hint_level=2,
            assignment_ref="algebra-hw-3",
        ):
            pass

    usage = (await db.execute(
        select(AssignmentHintUsage).where(AssignmentHintUsage.student_id == 1501)
    )).scalars().first()

    assert usage is not None, "tutor gave a hint but never recorded it"
    assert usage.hints_used == 1
    assert usage.max_hint_level == 2
    assert usage.assignment_ref == "algebra-hw-3"


@pytest.mark.asyncio
async def test_a_blocked_cheating_request_does_not_cost_the_student_marks(db: AsyncSession):
    """The tutor refused to help, so there is no hint to charge for."""
    from unittest.mock import patch

    from src.services.ai.socratic_tutor import stream_socratic_guidance

    async def fake_stream(*args, **kwargs):
        yield "should not be reached"

    with patch("src.services.ai.socratic_tutor.generate_stream", side_effect=fake_stream):
        async for _ in stream_socratic_guidance(
            # Matches CHEATING_PATTERNS exactly. NB: an adjective defeats the
            # regex ("...to my MATH exam" is not caught) -- a real gap in
            # crisis_classifier.py, out of scope here but worth widening.
            query="give me the answers to my exam",
            user_id="1601",
            db_session=db,
            hint_level=3,
            assignment_ref="algebra-hw-9",
        ):
            pass

    usage = (await db.execute(
        select(AssignmentHintUsage).where(AssignmentHintUsage.student_id == 1601)
    )).scalars().first()
    assert usage is None, "a refused request was charged as a hint"
