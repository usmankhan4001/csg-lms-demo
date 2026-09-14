import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_campus import StudentEnrollment
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
        # No assessment plans at all: nothing has been set up to grade, so
        # this course has no grade. has_grades=False keeps it out of the
        # cumulative GPA -- it previously contributed 0.0 quality points over
        # 3.0 credits, which pulled the whole average toward zero.
        return CourseGradeSummary(
            course_id=course_id,
            credits=3.0,
            total_raw_percentage=0.0,
            total_weighted_percentage=0.0,
            letter_grade="N/A",
            gpa_point=0.0,
            has_grades=False,
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

    graded_count = 0
    for plan in plans:
        entry = entries.get(plan.id)
        max_s = plan.max_score or 100.0

        if entry is None:
            # NOT marked yet -- excluded from the weighting entirely rather
            # than scored 0. Counting an unmarked assessment as zero meant a
            # teacher who had entered only the first quiz saw every student
            # failing. The row is still listed so the absence is visible.
            breakdown.append({
                "assessment_plan_id": plan.id,
                "assessment_name": plan.assessment_name,
                "weight_percentage": plan.weight_percentage,
                "raw_score": None,
                "max_score": max_s,
                "percentage": None,
                "weighted_score": None,
                "graded": False,
            })
            continue

        graded_count += 1
        raw = entry.raw_score
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
            "graded": True,
        })

    if graded_count == 0:
        # Plans exist but none are marked: still no grade.
        return CourseGradeSummary(
            course_id=course_id,
            credits=3.0,
            total_raw_percentage=0.0,
            total_weighted_percentage=0.0,
            letter_grade="N/A",
            gpa_point=0.0,
            has_grades=False,
            assessment_breakdown=breakdown,
        )

    # Both averages are over MARKED work only -- total_weights now sums just
    # the graded plans' weights, and the raw average divides by graded_count.
    normalized_final_pct = (total_weighted / total_weights * 100.0) if total_weights > 0 else 0.0
    letter, gpa_pt = resolve_letter_and_gpa(normalized_final_pct)

    return CourseGradeSummary(
        course_id=course_id,
        credits=3.0,
        total_raw_percentage=round(total_raw_accum / graded_count, 2),
        total_weighted_percentage=round(normalized_final_pct, 2),
        letter_grade=letter,
        gpa_point=gpa_pt,
        assessment_breakdown=breakdown,
    )


def _response_from_sent_record(record: TermReportCard) -> StudentTermReportCardResponse:
    """Render a SENT report card from what was actually sent.

    A sent report card is a frozen artefact: it is the document a family was
    shown. Recomputing it on read would mean a parent opening last term's
    report card sees whatever the numbers happen to be today.
    """
    return StudentTermReportCardResponse(
        student_id=record.student_id,
        section_id=record.section_id,
        academic_term_id=record.academic_term_id,
        total_credits=record.total_credits,
        # `gpa` is NOT NULL in the column, so 0.0 with no graded credits is a
        # storage artefact rather than a measured grade -- same rule as
        # _to_record_read in the router.
        cumulative_gpa=record.gpa if record.total_credits > 0 else None,
        overall_letter_grade=record.letter_grade,
        remarks=record.remarks,
        courses=[CourseGradeSummary(**c) for c in (record.course_summaries or [])],
        generated_at=record.calculated_at,
        report_card_id=record.id,
        report_card_status=record.status,
    )


async def generate_student_term_report_card(
    session: AsyncSession,
    student_id: int,
    section_id: int,
    academic_term_id: int,
) -> StudentTermReportCardResponse:
    """
    Weighted GPA calculation engine & report card summary generator.

    A SENT report card is returned AS SENT and never recomputed -- see
    `_response_from_sent_record`. This is load-bearing, not a nicety: this
    function upserts, and it backs `GET /report-card/student/{id}`, which a
    PARENT may call for their own child. Before the guard, a parent simply
    OPENING their child's sent report card silently overwrote its stored
    grades with a fresh computation (verified: a stored 4.0 became 0.0 after a
    later mark change and a read). A read must never rewrite the document it
    is reading.
    """
    frozen = await _get_report_card_record(session, student_id, academic_term_id)
    if frozen is not None and frozen.status == ReportCardStatus.SENT:
        return _response_from_sent_record(frozen)

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
        # Only courses with actual marks count toward the cumulative GPA. An
        # ungraded course used to contribute 0.0 quality points over its full
        # credits, so every unmarked course dragged the average down and a
        # student with nothing marked landed at 0.0 -> "F".
        if summary.has_grades:
            total_quality_points += summary.gpa_point * summary.credits
            total_credits += summary.credits

    # A student with no graded credits has NO grade -- not a zero, and
    # emphatically not an F. Previously `else 0.0` fed the chain below, whose
    # final `else` produced "F", and that was UPSERTED onto the report card:
    # a newly enrolled student with nothing marked yet showed a persisted F to
    # their parents. "No marks recorded" and "failed everything" are opposite
    # claims; this is the same fabrication class as the GPA endpoint that once
    # returned 4.0/honor-roll for a student with zero grades, merely inverted.
    has_graded_credits = total_credits > 0
    if not has_graded_credits:
        cumulative_gpa = None
        overall_letter = None
    else:
        cumulative_gpa = round(total_quality_points / total_credits, 2)
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
            # A real, measured F: the student has graded credits and earned it.
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
            # TermReportCard.gpa is NOT NULL (db/sms_gradebook.py:128), so an
            # ungraded student cannot be stored as a null GPA without a
            # migration. `total_credits == 0` together with a NULL
            # letter_grade is the authoritative "no grade yet" signal on the
            # row; read `gpa` only when total_credits > 0.
            gpa=cumulative_gpa if cumulative_gpa is not None else 0.0,
            letter_grade=overall_letter,
            course_summaries=[c.model_dump() for c in course_summaries],
        )
        session.add(report_record)
    else:
        report_record.section_id = section_id
        report_record.total_credits = total_credits
        # See the NOT NULL note above: 0.0 is a storage artefact here, not a
        # measured grade. letter_grade going back to NULL is what un-does a
        # previously persisted letter if marks were removed.
        report_record.gpa = cumulative_gpa if cumulative_gpa is not None else 0.0
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
        # Surfacing the persisted row's id/status is what lets a caller reach
        # the send and PDF endpoints for a card generated in an earlier
        # session. This function already upserts that row, so the id is free.
        report_card_id=report_record.id,
        report_card_status=report_record.status,
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


# ---------------------------------------------------------------------------
# Whole-section term-end operations.
#
# Report cards are the term-end deliverable and a teacher runs a SECTION, not
# one child at a time -- thirty students one at a time is how a term-end
# actually gets skipped. These operate over the section roster
# (StudentEnrollment) and report a per-student outcome rather than a count, so
# a teacher can see exactly who was drafted, who was skipped and why.
# ---------------------------------------------------------------------------


async def _active_section_student_ids(session: AsyncSession, section_id: int) -> List[int]:
    """Actively enrolled students in a section, oldest enrolment first.

    Only `active` enrolments: a transferred, graduated or withdrawn student
    must not acquire a fresh report card for a term they are no longer in.
    """
    rows = (
        await session.execute(
            select(StudentEnrollment.student_id)
            .where(
                and_(
                    StudentEnrollment.section_id == section_id,
                    StudentEnrollment.status == "active",
                )
            )
            .order_by(StudentEnrollment.id)
        )
    ).scalars().all()
    # De-duplicated preserving order: a student re-enrolled in the same section
    # must be drafted once, not twice.
    seen: List[int] = []
    for sid in rows:
        if sid not in seen:
            seen.append(sid)
    return seen


async def batch_generate_report_card_drafts(
    session: AsyncSession,
    section_id: int,
    academic_term_id: int,
    generate_narrative: bool = True,
) -> List[Dict[str, Any]]:
    """Draft a report card for every actively enrolled student in a section.

    Returns one outcome row per student. Outcomes are deliberately explicit
    rather than a success count:

    * ``drafted``          -- a DRAFT was created or refreshed
    * ``skipped_sent``     -- already sent; left frozen, never regenerated
    * ``drafted_ungraded`` -- drafted, but the student has NO graded credits

    ``drafted_ungraded`` is its own outcome because a student with nothing
    marked has no grade -- not a zero and not an F. Collapsing it into
    ``drafted`` would let a teacher send a whole section believing every card
    carried a grade.
    """
    outcomes: List[Dict[str, Any]] = []

    for student_id in await _active_section_student_ids(session, section_id):
        existing = await _get_report_card_record(session, student_id, academic_term_id)
        if existing is not None and existing.status == ReportCardStatus.SENT:
            outcomes.append({
                "student_id": student_id,
                "report_card_id": existing.id,
                "outcome": "skipped_sent",
                "detail": "Already sent; a sent report card is never regenerated.",
            })
            continue

        record = await generate_report_card_draft(
            session=session,
            student_id=student_id,
            section_id=section_id,
            academic_term_id=academic_term_id,
            generate_narrative=generate_narrative,
        )
        has_grades = record.total_credits > 0
        outcomes.append({
            "student_id": student_id,
            "report_card_id": record.id,
            "outcome": "drafted" if has_grades else "drafted_ungraded",
            "detail": (
                None
                if has_grades
                else "No graded credits: this card carries no GPA or letter grade."
            ),
        })

    return outcomes


async def batch_send_report_cards(
    session: AsyncSession,
    report_card_ids: List[int],
    sent_by: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Send an EXPLICIT list of report cards.

    Deliberately keyed on ids the caller names, NOT on a section: a section is
    a moving target, and "send this section" would fan out to whoever happens
    to be enrolled at the moment the button is pressed, including a student
    added since the teacher last looked. A report card sent to thirty families
    cannot be recalled, so the caller must have seen each card it sends.

    Per-id outcomes; an already-sent or missing id is reported rather than
    raising, so one bad id cannot abort a term-end run half-way through.
    """
    outcomes: List[Dict[str, Any]] = []
    for report_card_id in report_card_ids:
        try:
            record = await send_report_card(
                session=session, report_card_id=report_card_id, sent_by=sent_by
            )
        except ReportCardNotFoundError:
            outcomes.append({
                "report_card_id": report_card_id,
                "outcome": "not_found",
                "detail": "No such report card.",
            })
            continue
        except ReportCardAlreadySentError:
            outcomes.append({
                "report_card_id": report_card_id,
                "outcome": "already_sent",
                "detail": "This report card had already been sent.",
            })
            continue
        outcomes.append({
            "report_card_id": record.id,
            "outcome": "sent",
            "detail": None,
        })
    return outcomes


async def recalculate_report_cards(
    session: AsyncSession,
    section_id: int,
    academic_term_id: int,
) -> List[Dict[str, Any]]:
    """Recompute DRAFT report cards for a section after marks or weightings changed.

    Explicit and idempotent: recomputing twice over unchanged marks yields the
    same numbers, because it re-runs the same calculation engine over the same
    entries rather than accumulating anything.

    SENT cards are SKIPPED and reported, never silently recomputed. A parent
    has already been shown that document; changing it underneath them without
    anybody deciding to is exactly the silent mutation this must not do. To
    correct a sent card a school has to make that a deliberate act.

    The narrative is NOT regenerated -- this recomputes numbers. A teacher's
    hand-edited comment must survive a recalculation.
    """
    outcomes: List[Dict[str, Any]] = []

    for student_id in await _active_section_student_ids(session, section_id):
        existing = await _get_report_card_record(session, student_id, academic_term_id)
        if existing is None:
            outcomes.append({
                "student_id": student_id,
                "report_card_id": None,
                "outcome": "no_report_card",
                "detail": "Nothing to recalculate; no report card has been drafted.",
            })
            continue
        if existing.status == ReportCardStatus.SENT:
            outcomes.append({
                "student_id": student_id,
                "report_card_id": existing.id,
                "outcome": "skipped_sent",
                "detail": "Already sent; a sent report card is never recalculated.",
            })
            continue

        previous_gpa = existing.gpa if existing.total_credits > 0 else None
        refreshed = await generate_student_term_report_card(
            session=session,
            student_id=student_id,
            section_id=section_id,
            academic_term_id=academic_term_id,
        )
        outcomes.append({
            "student_id": student_id,
            "report_card_id": refreshed.report_card_id,
            "outcome": "recalculated",
            "previous_cumulative_gpa": previous_gpa,
            "cumulative_gpa": refreshed.cumulative_gpa,
            "detail": None,
        })

    return outcomes


async def calculate_cumulative_gpa(
    session: AsyncSession,
    student_id: int,
) -> Dict[str, Any]:
    """A student's cumulative GPA across every course they have marks in.

    Replaces a router-local implementation that was both FABRICATING and
    BROKEN, and which backed the transcript endpoint as well:

    * With no gradebook entries it returned ``unweighted_gpa: 4.0``,
      ``weighted_gpa: 4.0``, ``academic_standing: "Good Standing"`` and
      ``honor_roll: True`` -- a perfect record and an honour-roll place for a
      student who has never been marked. This is the fabrication this codebase
      has torn out repeatedly; in this endpoint it was still live.
    * With entries it read ``entry.score``, a field ``GradebookEntry`` does not
      have (it has ``raw_score``), so it raised AttributeError -- a 500. The
      only path that returned anything was therefore the fabricated one.
    * It carried its own inline percentage->GPA ladder, a SECOND grading engine
      that could disagree with ``resolve_letter_and_gpa``, and invented credits
      as ``courses * 3``.

    Now built on the same course-summary engine as report cards, so a
    transcript and a report card cannot disagree about the same student.
    A student with no graded credits gets ``None`` -- no GPA, no standing, no
    honour roll -- because they have not been graded, which is a different
    fact from having been graded badly.
    """
    entries = (
        await session.execute(
            select(GradebookEntry).where(GradebookEntry.student_id == student_id)
        )
    ).scalars().all()

    course_ids: List[int] = []
    if entries:
        plan_ids = {e.assessment_plan_id for e in entries}
        course_ids = list(
            (
                await session.execute(
                    select(AssessmentPlan.course_id)
                    .distinct()
                    .where(AssessmentPlan.id.in_(plan_ids))
                )
            ).scalars().all()
        )

    summaries: List[CourseGradeSummary] = []
    for course_id in course_ids:
        summaries.append(
            await calculate_student_course_summary(
                session=session, student_id=student_id, course_id=course_id
            )
        )

    graded = [s for s in summaries if s.has_grades]
    total_credits = sum(s.credits for s in graded)
    if not graded or total_credits <= 0:
        # No graded credits: report the absence, do not manufacture a grade.
        return {
            "student_id": student_id,
            "total_courses": len(summaries),
            "graded_courses": 0,
            "total_credits": 0.0,
            "unweighted_gpa": None,
            "academic_standing": None,
            "honor_roll": None,
            "detail": "No graded coursework on file; this student has no GPA yet.",
        }

    unweighted = round(
        sum(s.gpa_point * s.credits for s in graded) / total_credits, 2
    )
    standing = (
        "Dean's List / High Honors" if unweighted >= 3.8
        else "Honor Roll" if unweighted >= 3.5
        else "Good Standing" if unweighted >= 2.0
        else "Academic Probation"
    )
    return {
        "student_id": student_id,
        "total_courses": len(summaries),
        "graded_courses": len(graded),
        "total_credits": total_credits,
        "unweighted_gpa": unweighted,
        "academic_standing": standing,
        "honor_roll": unweighted >= 3.5,
        "detail": None,
    }


async def list_report_cards(
    session: AsyncSession,
    section_id: Optional[int] = None,
    academic_term_id: Optional[int] = None,
    student_id: Optional[int] = None,
    status_filter: Optional[str] = None,
) -> List[TermReportCard]:
    """Enumerate persisted report cards.

    Exists because nothing else could answer "which cards in this section are
    still drafts?" -- the term-end question. A single card was reachable by id
    and a single student's by (student, term), but there was no way to see a
    section at a glance.
    """
    conditions = []
    if isinstance(section_id, int):
        conditions.append(TermReportCard.section_id == section_id)
    if isinstance(academic_term_id, int):
        conditions.append(TermReportCard.academic_term_id == academic_term_id)
    if isinstance(student_id, int):
        conditions.append(TermReportCard.student_id == student_id)
    if isinstance(status_filter, str) and status_filter:
        conditions.append(TermReportCard.status == status_filter)

    stmt = select(TermReportCard)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(TermReportCard.student_id, TermReportCard.id)
    return list((await session.execute(stmt)).scalars().all())


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


# ── Report Card PDF Rendering (M05) ──


class ReportCardNotSentError(Exception):
    """Raised when a PDF is requested for a report card that is still a DRAFT.

    A PDF is a detachable artifact: once generated it can be saved, mailed and
    forwarded with no further authorization check. A DRAFT is by definition
    not yet approved by the teacher (see ReportCardStatus), so rendering one
    would let an unapproved grade leave the system in a form nothing can
    retract. Staff may READ a draft in-app (get_report_card_for_viewer allows
    it) but nobody -- staff included -- may export one.
    """


def _pdf_rows_from_record(record: TermReportCard) -> List[List[str]]:
    """Per-course table rows straight off the persisted record.

    Deliberately reads `record.course_summaries` rather than recomputing
    anything: the JSON API (`_to_record_read`) renders the very same stored
    list, so the PDF and the on-screen report card cannot drift apart or
    disagree about a grade.
    """
    rows: List[List[str]] = [["Course", "Weighted %", "Grade", "GPA Point"]]
    for raw in record.course_summaries or []:
        summary = CourseGradeSummary(**raw)
        rows.append([
            summary.course_name or f"Course #{summary.course_id}",
            f"{summary.total_weighted_percentage:.1f}%",
            summary.letter_grade,
            f"{summary.gpa_point:.2f}",
        ])
    return rows


def render_report_card_pdf(record: TermReportCard, *, org_name: str = "CSG-LMS") -> bytes:
    """Render a SENT report card to PDF bytes.

    Raises ReportCardNotSentError for a draft -- see that exception's docstring
    for why export is stricter than read access.

    Scoped out deliberately: no org logo (resolving an org's uploaded asset to
    absolute bytes is a separate media-pipeline concern, see
    services/email/utils.py's get_org_logo_url for how involved that is) and no
    custom fonts (reportlab's built-in Helvetica avoids shipping font files).
    """
    if record.status != ReportCardStatus.SENT:
        raise ReportCardNotSentError(
            "Only a SENT report card can be exported as a PDF."
        )

    # Imported here rather than at module scope so that importing this module
    # (which the whole gradebook router depends on) never costs reportlab's
    # import time for the many callers that never render a PDF.
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"Report Card - Student {record.student_id}",
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    story: List[Any] = [
        Paragraph(org_name, styles["Title"]),
        Paragraph("Student Report Card", styles["Heading2"]),
        Spacer(1, 8 * mm),
    ]

    meta = Table(
        [
            ["Student ID", str(record.student_id)],
            ["Section ID", str(record.section_id)],
            ["Academic Term ID", str(record.academic_term_id)],
            ["Generated", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")],
        ],
        colWidths=[45 * mm, 105 * mm],
    )
    meta.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([meta, Spacer(1, 8 * mm)])

    courses = Table(_pdf_rows_from_record(record), colWidths=[70 * mm, 30 * mm, 25 * mm, 25 * mm])
    courses.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([courses, Spacer(1, 8 * mm)])

    totals = Table(
        [
            ["Cumulative GPA", f"{record.gpa:.2f}"],
            ["Overall Grade", record.letter_grade or "-"],
            ["Total Credits", f"{record.total_credits:.1f}"],
        ],
        colWidths=[45 * mm, 105 * mm],
    )
    totals.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(totals)

    if record.remarks:
        story.extend([
            Spacer(1, 6 * mm),
            Paragraph("<b>Teacher Remarks</b>", styles["Normal"]),
            Paragraph(record.remarks, styles["Normal"]),
        ])
    if record.ai_narrative:
        story.extend([
            Spacer(1, 4 * mm),
            Paragraph("<b>Narrative</b>", styles["Normal"]),
            Paragraph(record.ai_narrative, styles["Normal"]),
        ])

    doc.build(story)
    return buffer.getvalue()
