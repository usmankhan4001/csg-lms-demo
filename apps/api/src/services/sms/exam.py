"""
School examination service (M04) and homework-hint deduction (M40).

The whole point of this module is that it does NOT grade. Exam marks are
translated into ordinary `GradebookEntry` rows against an existing
`AssessmentPlan`, after which `src/services/sms/gradebook.py` computes
weighted percentages, letter grades and GPA exactly as it does for any other
assessment. There is one grading engine in this codebase and this is not it.
"""

import datetime
import logging
from typing import List, Optional, Tuple

from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_exam import (
    AssignmentHintUsage,
    Exam,
    ExamAttendanceStatus,
    ExamIncident,
    ExamResult,
    ExamSectionSchedule,
    ExamStatus,
)
from src.db.sms_gradebook import AssessmentPlan, GradebookEntry
from src.schemas.sms_exam import ExamResultSummary
from src.services.sms.gradebook import resolve_letter_and_gpa

logger = logging.getLogger(__name__)


class ExamNotFoundError(Exception):
    """Raised when an exam id doesn't resolve."""


class ExamNotGradebookLinkedError(Exception):
    """Raised when results are posted for an exam with no assessment plan.

    Deliberately an error rather than auto-creating a plan: an assessment
    plan carries a WEIGHT (how much this exam counts toward the course), and
    guessing a weight would silently change every affected student's final
    grade. A human has to say what the exam is worth.
    """


class ExamResultsAlreadyPostedError(Exception):
    """Raised when results would be posted to the gradebook a second time."""


# Percentage of the assignment's marks forfeited per Socratic hint consumed.
# Capped so hint use can never zero a student's work outright -- the tutor is
# meant to be usable, and a student who needed four hints but then produced
# correct work has still demonstrated something.
HINT_DEDUCTION_PER_HINT_PERCENT = 5.0
MAX_HINT_DEDUCTION_PERCENT = 30.0


def compute_hint_deduction_percentage(hints_used: int) -> float:
    """Deduction percentage for a number of hints, capped."""
    if hints_used <= 0:
        return 0.0
    return min(hints_used * HINT_DEDUCTION_PER_HINT_PERCENT, MAX_HINT_DEDUCTION_PERCENT)


# ---------------------------------------------------------------------------
# Exam results -> gradebook
# ---------------------------------------------------------------------------

def _result_percentage(result: ExamResult, total_marks: float) -> Optional[float]:
    """Percentage for a marked result, or None.

    Returns None -- never 0.0 -- when there is no mark. A student who has not
    been marked has no percentage, and callers must render that absence
    rather than a number.
    """
    if result.marks_obtained is None:
        return None
    if total_marks <= 0:
        return None
    return round((result.marks_obtained / total_marks) * 100.0, 2)


async def summarize_exam_results(
    session: AsyncSession, exam: Exam
) -> ExamResultSummary:
    """Cohort statistics computed only over students who actually have marks."""
    stmt = select(ExamResult).where(ExamResult.exam_id == exam.id)
    results = list((await session.execute(stmt)).scalars().all())

    marked = [r for r in results if r.marks_obtained is not None]
    absent = [r for r in results if r.attendance_status == ExamAttendanceStatus.ABSENT]
    scores = [r.marks_obtained for r in marked if r.marks_obtained is not None]

    pass_count = sum(1 for s in scores if s >= exam.pass_marks)

    return ExamResultSummary(
        exam_id=exam.id,
        total_students=len(results),
        marked=len(marked),
        not_yet_marked=len(results) - len(marked),
        absent=len(absent),
        average_marks=round(sum(scores) / len(scores), 2) if scores else None,
        highest_marks=max(scores) if scores else None,
        lowest_marks=min(scores) if scores else None,
        pass_count=pass_count,
        fail_count=len(scores) - pass_count,
    )


async def post_exam_results_to_gradebook(
    session: AsyncSession,
    exam_id: int,
    graded_by: Optional[int] = None,
    force: bool = False,
) -> Tuple[int, int, int]:
    """Translate marked exam results into GradebookEntry rows.

    Returns (written, skipped, assessment_plan_id).

    Idempotent: each ExamResult carries `posted_to_gradebook_at`, and an exam
    already in RESULTS_POSTED refuses a second run unless `force` is set.
    Unmarked and absent students are SKIPPED, never written as zeros -- a
    GradebookEntry with raw_score 0.0 is indistinguishable from a student who
    sat the exam and scored nothing, and the weighted-GPA engine would treat
    it as a real failure on the report card.
    """
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise ExamNotFoundError(f"Exam {exam_id} not found.")

    if exam.assessment_plan_id is None:
        raise ExamNotGradebookLinkedError(
            f"Exam {exam_id} has no assessment_plan_id. Link the exam to an "
            "assessment plan (which defines how much it counts toward the "
            "course grade) before posting results."
        )

    if exam.status == ExamStatus.RESULTS_POSTED and not force:
        raise ExamResultsAlreadyPostedError(
            f"Results for exam {exam_id} have already been posted to the gradebook."
        )

    plan = await session.get(AssessmentPlan, exam.assessment_plan_id)
    if plan is None:
        raise ExamNotGradebookLinkedError(
            f"Assessment plan {exam.assessment_plan_id} referenced by exam "
            f"{exam_id} no longer exists."
        )

    stmt = select(ExamResult).where(ExamResult.exam_id == exam_id)
    results = list((await session.execute(stmt)).scalars().all())

    now = datetime.datetime.now(datetime.timezone.utc)
    written = 0
    skipped = 0

    for result in results:
        if result.marks_obtained is None:
            skipped += 1
            continue
        if result.attendance_status in (
            ExamAttendanceStatus.ABSENT,
            ExamAttendanceStatus.EXEMPT,
        ):
            skipped += 1
            continue
        if result.posted_to_gradebook_at is not None and not force:
            skipped += 1
            continue

        # Scale the exam mark onto the assessment plan's own max_score, so a
        # 50-mark exam posted against a plan scored out of 100 lands correctly.
        plan_max = plan.max_score or 100.0
        scaled = (
            (result.marks_obtained / exam.total_marks) * plan_max
            if exam.total_marks > 0
            else 0.0
        )
        pct = (scaled / plan_max) * 100.0 if plan_max > 0 else 0.0
        letter, gpa_point = resolve_letter_and_gpa(pct)

        existing_stmt = select(GradebookEntry).where(
            and_(
                GradebookEntry.student_id == result.student_id,
                GradebookEntry.assessment_plan_id == plan.id,
            )
        )
        entry = (await session.execute(existing_stmt)).scalar_one_or_none()

        if entry is None:
            entry = GradebookEntry(
                student_id=result.student_id,
                assessment_plan_id=plan.id,
                raw_score=round(scaled, 2),
                max_score=plan_max,
                weighted_score=round((pct * plan.weight_percentage) / 100.0, 2),
                letter_grade=letter,
                gpa_point=gpa_point,
                remarks=f"Exam: {exam.title}",
                graded_by=graded_by,
            )
            session.add(entry)
        else:
            entry.raw_score = round(scaled, 2)
            entry.max_score = plan_max
            entry.weighted_score = round((pct * plan.weight_percentage) / 100.0, 2)
            entry.letter_grade = letter
            entry.gpa_point = gpa_point
            entry.remarks = f"Exam: {exam.title}"
            entry.graded_by = graded_by
            entry.graded_at = now
            session.add(entry)

        result.posted_to_gradebook_at = now
        session.add(result)
        written += 1

    exam.status = ExamStatus.RESULTS_POSTED
    session.add(exam)
    await session.commit()

    logger.info(
        "Posted exam %s results to gradebook: %d written, %d skipped (plan %s)",
        exam_id, written, skipped, plan.id,
    )
    return written, skipped, plan.id


# ---------------------------------------------------------------------------
# M40 -- homework hint deduction
# ---------------------------------------------------------------------------

async def record_hint_usage(
    session: AsyncSession,
    student_id: int,
    assignment_ref: str,
    hint_level: int = 1,
    assessment_plan_id: Optional[int] = None,
) -> AssignmentHintUsage:
    """Increment a student's hint count for one assignment.

    Called by the Socratic tutor when it actually issues a hint. Never raises
    into the tutor's path: the caller wraps this, because failing to record a
    hint must not deny a student the help they asked for.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    stmt = select(AssignmentHintUsage).where(
        and_(
            AssignmentHintUsage.student_id == student_id,
            AssignmentHintUsage.assignment_ref == assignment_ref,
        )
    )
    usage = (await session.execute(stmt)).scalar_one_or_none()

    if usage is None:
        usage = AssignmentHintUsage(
            student_id=student_id,
            assignment_ref=assignment_ref,
            assessment_plan_id=assessment_plan_id,
            hints_used=1,
            max_hint_level=hint_level,
            first_hint_at=now,
            last_hint_at=now,
        )
    else:
        usage.hints_used += 1
        usage.max_hint_level = max(usage.max_hint_level, hint_level)
        usage.last_hint_at = now
        if assessment_plan_id is not None and usage.assessment_plan_id is None:
            usage.assessment_plan_id = assessment_plan_id

    session.add(usage)
    await session.commit()
    await session.refresh(usage)
    return usage


async def get_hint_usage(
    session: AsyncSession, student_id: int, assignment_ref: str
) -> Optional[AssignmentHintUsage]:
    stmt = select(AssignmentHintUsage).where(
        and_(
            AssignmentHintUsage.student_id == student_id,
            AssignmentHintUsage.assignment_ref == assignment_ref,
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def apply_hint_deduction(
    session: AsyncSession,
    student_id: int,
    assignment_ref: str,
    gradebook_entry_id: int,
) -> float:
    """Apply the hint deduction to an already-written GradebookEntry.

    Returns the percentage deducted (0.0 when there is nothing to deduct).

    IDEMPOTENCY -- the reason this is safe to call on every re-grade:
    the deduction is always computed against the entry's CURRENT raw_score by
    reversing any deduction already recorded, rather than subtracting again
    from an already-reduced score. `applied_deduction_percentage` stores what
    was last applied, so re-grading with a new raw score, or with a different
    hint count, converges on the correct number instead of compounding.
    """
    usage = await get_hint_usage(session, student_id, assignment_ref)
    if usage is None or usage.hints_used <= 0:
        return 0.0

    entry = await session.get(GradebookEntry, gradebook_entry_id)
    if entry is None:
        logger.warning(
            "Hint deduction skipped: gradebook entry %s not found", gradebook_entry_id
        )
        return 0.0

    deduction_pct = compute_hint_deduction_percentage(usage.hints_used)

    # Recover the pre-deduction score if this entry was already reduced, so
    # the new deduction is applied to the original mark, never compounded.
    previously_applied = usage.applied_deduction_percentage or 0.0
    base_score = entry.raw_score
    if (
        previously_applied > 0.0
        and usage.applied_to_gradebook_entry_id == gradebook_entry_id
        and previously_applied < 100.0
    ):
        base_score = entry.raw_score / (1.0 - previously_applied / 100.0)

    new_score = round(base_score * (1.0 - deduction_pct / 100.0), 2)
    max_score = entry.max_score or 100.0
    pct = (new_score / max_score) * 100.0 if max_score > 0 else 0.0
    letter, gpa_point = resolve_letter_and_gpa(pct)

    entry.raw_score = new_score
    entry.letter_grade = letter
    entry.gpa_point = gpa_point
    note = f"AI hints used: {usage.hints_used} (-{deduction_pct:.0f}%)"
    entry.remarks = f"{entry.remarks} | {note}" if entry.remarks and note not in (entry.remarks or "") else (entry.remarks or note)
    session.add(entry)

    usage.deduction_applied_at = datetime.datetime.now(datetime.timezone.utc)
    usage.applied_to_gradebook_entry_id = gradebook_entry_id
    usage.applied_deduction_percentage = deduction_pct
    session.add(usage)

    await session.commit()
    return deduction_pct


async def log_exam_incident(
    session: AsyncSession,
    exam_id: int,
    description: str,
    severity: str = "INFO",
    section_id: Optional[int] = None,
    student_id: Optional[int] = None,
    reported_by: Optional[int] = None,
) -> ExamIncident:
    """Append an invigilator's incident note. Append-only by design."""
    incident = ExamIncident(
        exam_id=exam_id,
        section_id=section_id,
        student_id=student_id,
        severity=severity,
        description=description,
        reported_by=reported_by,
    )
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return incident
