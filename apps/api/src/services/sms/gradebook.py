import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_gradebook import (
    AssessmentPlan,
    GradebookEntry,
    GradingScale,
    ReportCardStatus,
    TermReportCard,
)
from src.schemas.sms_gradebook import (
    CourseGradeSummary,
    GradeInterval,
    StudentTermReportCardResponse,
)
from src.services.ai.llm import generate, model_for_tier

logger = logging.getLogger(__name__)


class ReportCardAlreadySentError(Exception):
    """Raised when an action would mutate a report card that has already
    been sent -- a sent report card is frozen (visible to the PARENT role)
    and must not be silently regenerated/edited out from under them."""


class ReportCardNotFoundError(Exception):
    """Raised when a report-card id doesn't resolve to a persisted record."""

DEFAULT_INTERVALS = [
    {"grade": "A+", "min_percentage": 90.0, "max_percentage": 100.0, "gpa_point": 4.0},
    {"grade": "A", "min_percentage": 80.0, "max_percentage": 89.99, "gpa_point": 3.7},
    {"grade": "B+", "min_percentage": 75.0, "max_percentage": 79.99, "gpa_point": 3.3},
    {"grade": "B", "min_percentage": 70.0, "max_percentage": 74.99, "gpa_point": 3.0},
    {"grade": "C+", "min_percentage": 65.0, "max_percentage": 69.99, "gpa_point": 2.7},
    {"grade": "C", "min_percentage": 60.0, "max_percentage": 64.99, "gpa_point": 2.0},
    {"grade": "D", "min_percentage": 50.0, "max_percentage": 59.99, "gpa_point": 1.0},
    {"grade": "F", "min_percentage": 0.0, "max_percentage": 49.99, "gpa_point": 0.0},
]


def resolve_letter_and_gpa(
    percentage: float,
    intervals: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, float]:
    """Resolves percentage score to letter grade and GPA points."""
    scale = intervals or DEFAULT_INTERVALS
    for band in scale:
        min_p = float(band.get("min_percentage", 0.0))
        max_p = float(band.get("max_percentage", 100.0))
        if min_p <= percentage <= (max_p + 0.001):
            return band.get("grade", "F"), float(band.get("gpa_point", 0.0))
    if percentage > 100.0:
        return scale[0].get("grade", "A+"), float(scale[0].get("gpa_point", 4.0))
    return "F", 0.0


async def calculate_student_course_summary(
    session: AsyncSession,
    student_id: int,
    course_id: int,
    academic_term_id: Optional[int] = None,
) -> CourseGradeSummary:
    """
    Calculates weighted performance for a single course based on assessment plans and entered grades.
    """
    plan_stmt = select(AssessmentPlan).where(AssessmentPlan.course_id == course_id)
    if academic_term_id is not None:
        plan_stmt = plan_stmt.where(
            (AssessmentPlan.academic_term_id == academic_term_id)
            | (AssessmentPlan.academic_term_id.is_(None))
        )
    plans = (await session.execute(plan_stmt)).scalars().all()

    if not plans:
        return CourseGradeSummary(
            course_id=course_id,
            credits=3.0,
            total_raw_percentage=0.0,
            total_weighted_percentage=0.0,
            letter_grade="N/A",
            gpa_point=0.0,
            assessment_breakdown=[],
        )

    plan_ids = [p.id for p in plans if p.id is not None]
    grade_stmt = select(GradebookEntry).where(
        and_(
            GradebookEntry.student_id == student_id,
            GradebookEntry.assessment_plan_id.in_(plan_ids),
        )
    )
    entries = {g.assessment_plan_id: g for g in (await session.execute(grade_stmt)).scalars().all()}

    breakdown = []
    total_weighted = 0.0
    total_weights = 0.0
    total_raw_accum = 0.0

    for plan in plans:
        entry = entries.get(plan.id)
        raw = entry.raw_score if entry else 0.0
        max_s = plan.max_score or 100.0
        pct = (raw / max_s) * 100.0 if max_s > 0 else 0.0
        weighted_contrib = (pct * plan.weight_percentage) / 100.0

        total_weighted += weighted_contrib
        total_weights += plan.weight_percentage
        total_raw_accum += pct

        breakdown.append({
            "assessment_plan_id": plan.id,
            "assessment_name": plan.assessment_name,
            "weight_percentage": plan.weight_percentage,
            "raw_score": raw,
            "max_score": max_s,
            "percentage": round(pct, 2),
            "weighted_score": round(weighted_contrib, 2),
        })

    normalized_final_pct = (total_weighted / total_weights * 100.0) if total_weights > 0 else 0.0
    letter, gpa_pt = resolve_letter_and_gpa(normalized_final_pct)

    return CourseGradeSummary(
        course_id=course_id,
        credits=3.0,
        total_raw_percentage=round(total_raw_accum / len(plans) if plans else 0.0, 2),
        total_weighted_percentage=round(normalized_final_pct, 2),
        letter_grade=letter,
        gpa_point=gpa_pt,
        assessment_breakdown=breakdown,
    )


async def generate_student_term_report_card(
    session: AsyncSession,
    student_id: int,
    section_id: int,
    academic_term_id: int,
) -> StudentTermReportCardResponse:
    """
    Weighted GPA calculation engine & report card summary generator.
    """
    # Fetch all assessment plans relevant to this section / term
    stmt = select(AssessmentPlan.course_id).distinct()
    if academic_term_id is not None:
        stmt = stmt.where(
            (AssessmentPlan.academic_term_id == academic_term_id)
            | (AssessmentPlan.academic_term_id.is_(None))
        )
    course_ids = (await session.execute(stmt)).scalars().all()

    course_summaries: List[CourseGradeSummary] = []
    total_quality_points = 0.0
    total_credits = 0.0

    for c_id in course_ids:
        summary = await calculate_student_course_summary(
            session=session,
            student_id=student_id,
            course_id=c_id,
            academic_term_id=academic_term_id,
        )
        course_summaries.append(summary)
        total_quality_points += summary.gpa_point * summary.credits
        total_credits += summary.credits

    cumulative_gpa = round(total_quality_points / total_credits, 2) if total_credits > 0 else 0.0
    # Map GPA back to overall letter grade
    if cumulative_gpa >= 3.8:
        overall_letter = "A+"
    elif cumulative_gpa >= 3.5:
        overall_letter = "A"
    elif cumulative_gpa >= 3.0:
        overall_letter = "B"
    elif cumulative_gpa >= 2.0:
        overall_letter = "C"
    elif cumulative_gpa >= 1.0:
        overall_letter = "D"
    else:
        overall_letter = "F"

    # Upsert TermReportCard in database
    existing_stmt = select(TermReportCard).where(
        and_(
            TermReportCard.student_id == student_id,
            TermReportCard.academic_term_id == academic_term_id,
        )
    )
    report_record = (await session.execute(existing_stmt)).scalar_one_or_none()

    if not report_record:
        report_record = TermReportCard(
            student_id=student_id,
            section_id=section_id,
            academic_term_id=academic_term_id,
            total_credits=total_credits,
            gpa=cumulative_gpa,
            letter_grade=overall_letter,
            course_summaries=[c.model_dump() for c in course_summaries],
        )
        session.add(report_record)
    else:
        report_record.section_id = section_id
        report_record.total_credits = total_credits
        report_record.gpa = cumulative_gpa
        report_record.letter_grade = overall_letter
        report_record.course_summaries = [c.model_dump() for c in course_summaries]
        report_record.calculated_at = datetime.datetime.now(datetime.timezone.utc)
        session.add(report_record)

    await session.commit()
    await session.refresh(report_record)

    return StudentTermReportCardResponse(
        student_id=student_id,
        section_id=section_id,
        academic_term_id=academic_term_id,
        total_credits=total_credits,
        cumulative_gpa=cumulative_gpa,
        overall_letter_grade=overall_letter,
        courses=course_summaries,
        generated_at=report_record.calculated_at,
    )


# ---------------------------------------------------------------------------
# Report-card draft -> sent distribution lifecycle (Phase 4, Part A.4)
#
# TEACHER approves, then explicitly sends -- there is no auto-send and no
# separate SCHOOL_ADMIN approval gate (product decision). Modeled as an
# explicit `status` column on TermReportCard rather than an implicit side
# effect of some other action. A SENT report card is frozen: regenerating or
# editing it raises ReportCardAlreadySentError so a teacher can't silently
# rewrite grade data a parent has already been shown.
# ---------------------------------------------------------------------------

REPORT_CARD_NARRATIVE_SYSTEM_PROMPT = """You are an experienced, warm classroom teacher writing the short narrative comment section of a student's term report card.

Write 2-4 sentences, in plain language a parent will read:
- Ground every statement strictly in the GPA/grade data provided. Do not invent facts, incidents, or behavior not implied by the data.
- Note genuine strengths first, then any course(s) that need attention, framed constructively.
- Keep it encouraging and specific -- avoid generic filler ("doing great!") with nothing tied to the actual grades.
- Return ONLY the narrative text, no headings, no markdown."""


async def _generate_report_card_narrative(
    course_summaries: List[Dict[str, Any]],
    gpa: float,
    letter_grade: Optional[str],
    model_name: Optional[str] = None,
) -> str:
    """Best-effort AI-assisted narrative. Reuses the shared provider-agnostic
    LLM layer (src.services.ai.llm) -- same abstraction as the Socratic
    Tutor / assignment generator -- rather than a new client. Fails soft
    (returns an empty string) so a provider outage never blocks generating
    the draft's GPA/grade data, which is the part that matters most."""
    course_lines = "\n".join(
        f"- {c.get('course_name') or c.get('course_id')}: {c.get('letter_grade')} "
        f"({c.get('total_weighted_percentage')}%)"
        for c in (course_summaries or [])
    ) or "(no course grades on file yet)"
    user_prompt = (
        f"Cumulative GPA: {gpa}\nOverall grade: {letter_grade or 'N/A'}\n"
        f"Per-course results:\n{course_lines}"
    )
    try:
        narrative = await generate(
            model_name=model_name or model_for_tier("fast"),
            user_prompt=user_prompt,
            system_prompt=REPORT_CARD_NARRATIVE_SYSTEM_PROMPT,
            output_type=str,
        )
        return (narrative or "").strip()
    except Exception as e:
        logger.warning("Report card narrative generation failed, leaving blank: %s", e)
        return ""


async def _get_report_card_record(
    session: AsyncSession, student_id: int, academic_term_id: int
) -> Optional[TermReportCard]:
    stmt = select(TermReportCard).where(
        and_(
            TermReportCard.student_id == student_id,
            TermReportCard.academic_term_id == academic_term_id,
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def generate_report_card_draft(
    session: AsyncSession,
    student_id: int,
    section_id: int,
    academic_term_id: int,
    generate_narrative: bool = True,
    model_name: Optional[str] = None,
) -> TermReportCard:
    """Generate (or refresh) a DRAFT report card: reuses the existing GPA/grade
    calculation engine (generate_student_term_report_card) for the numeric
    data, then layers an AI-assisted narrative comment on top. Raises
    ReportCardAlreadySentError instead of touching a record that has already
    been sent to the parent.
    """
    existing = await _get_report_card_record(session, student_id, academic_term_id)
    if existing is not None and existing.status == ReportCardStatus.SENT:
        raise ReportCardAlreadySentError(
            f"Report card for student {student_id}, term {academic_term_id} "
            "has already been sent and cannot be regenerated."
        )

    # Reuses the existing weighted-GPA calculation engine -- it upserts the
    # TermReportCard row's numeric fields but never touches status/
    # ai_narrative/sent_at/sent_by, so a DRAFT stays a DRAFT here.
    await generate_student_term_report_card(
        session=session,
        student_id=student_id,
        section_id=section_id,
        academic_term_id=academic_term_id,
    )

    record = await _get_report_card_record(session, student_id, academic_term_id)
    assert record is not None  # just upserted above

    if generate_narrative:
        record.ai_narrative = await _generate_report_card_narrative(
            record.course_summaries, record.gpa, record.letter_grade, model_name
        )
    record.status = ReportCardStatus.DRAFT
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def update_report_card_draft(
    session: AsyncSession,
    report_card_id: int,
    ai_narrative: Optional[str] = None,
    remarks: Optional[str] = None,
) -> TermReportCard:
    """Teacher edits to a still-DRAFT report card (e.g. hand-editing the
    AI-generated narrative before sending)."""
    record = await session.get(TermReportCard, report_card_id)
    if record is None:
        raise ReportCardNotFoundError(f"Report card {report_card_id} not found.")
    if record.status == ReportCardStatus.SENT:
        raise ReportCardAlreadySentError(
            f"Report card {report_card_id} has already been sent and cannot be edited."
        )

    if ai_narrative is not None:
        record.ai_narrative = ai_narrative
    if remarks is not None:
        record.remarks = remarks

    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def send_report_card(
    session: AsyncSession,
    report_card_id: int,
    sent_by: Optional[str] = None,
) -> TermReportCard:
    """Explicit TEACHER-initiated send action -- the only thing that makes a
    report card visible to the PARENT role. Never called automatically."""
    record = await session.get(TermReportCard, report_card_id)
    if record is None:
        raise ReportCardNotFoundError(f"Report card {report_card_id} not found.")
    if record.status == ReportCardStatus.SENT:
        raise ReportCardAlreadySentError(f"Report card {report_card_id} has already been sent.")

    record.status = ReportCardStatus.SENT
    record.sent_at = datetime.datetime.now(datetime.timezone.utc)
    record.sent_by = sent_by

    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def get_report_card_for_viewer(
    session: AsyncSession,
    report_card_id: int,
    is_staff_viewer: bool,
) -> Optional[TermReportCard]:
    """Fetch a single persisted report card, honoring the draft/sent
    visibility rule: TEACHER/SCHOOL_ADMIN/SUPER_ADMIN (``is_staff_viewer``)
    may see it in any status; every other caller (PARENT, STUDENT, ...) only
    once it has been SENT. Returns None rather than raising so the router can
    turn a mismatch into a plain 404 (no special existence-masking is
    mandated for gradebook -- that rule is scoped to the counseling module).
    """
    record = await session.get(TermReportCard, report_card_id)
    if record is None:
        return None
    if is_staff_viewer or record.status == ReportCardStatus.SENT:
        return record
    return None
