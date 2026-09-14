"""Term-end gradebook operations, and the two live bugs found building them.

Two faults this file pins, both verified against the running code before the
fix:

1. `GET /report-card/student/{id}` UPSERTED on read. A PARENT may call it for
   their own child, so a parent merely OPENING their child's sent report card
   silently overwrote its stored grades with a fresh computation -- a stored
   4.0 became 0.0 after a later mark change and a read. A read must never
   rewrite the document it is reading.

2. `calculate_student_gpa` returned `unweighted_gpa: 4.0`,
   `academic_standing: "Good Standing"` and `honor_roll: True` for a student
   with no grades at all, and raised AttributeError (`entry.score` does not
   exist on GradebookEntry) for any student who HAD grades. The only code path
   that returned anything was the fabricated one.
"""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import KeycloakUserPrincipal
from src.db.sms_campus import StudentEnrollment
from src.db.sms_gradebook import (
    AssessmentPlan,
    GradebookEntry,
    ReportCardStatus,
    TermReportCard,
)
from src.services.sms.gradebook import (
    batch_generate_report_card_drafts,
    batch_send_report_cards,
    calculate_cumulative_gpa,
    generate_student_term_report_card,
    list_report_cards,
    recalculate_report_cards,
    send_report_card,
)

# These tests are about term-end mechanics, not about who may run them; the
# role gating is covered in test_gradebook_authorization.py.
_ADMIN = KeycloakUserPrincipal(
    sub="gradebook-module-fixture",
    org_id=1,
    campus_id=1,
    roles={"SCHOOL_ADMIN"},
    raw_claims={"lh_user_id": 77},
)


async def _plan(db: AsyncSession, *, course_id: int, section_id: int, term_id: int,
                weight: float = 100.0, max_score: float = 100.0) -> AssessmentPlan:
    plan = AssessmentPlan(
        course_id=course_id,
        section_id=section_id,
        academic_term_id=term_id,
        assessment_name="Midterm",
        weight_percentage=weight,
        max_score=max_score,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def _mark(db: AsyncSession, *, student_id: int, plan: AssessmentPlan, raw: float) -> None:
    db.add(GradebookEntry(
        student_id=student_id,
        assessment_plan_id=plan.id,
        raw_score=raw,
        max_score=plan.max_score,
    ))
    await db.commit()


async def _enrol(db: AsyncSession, *, student_id: int, section_id: int,
                 status: str = "active") -> None:
    db.add(StudentEnrollment(
        student_id=student_id,
        section_id=section_id,
        academic_year_id=1,
        status=status,
    ))
    await db.commit()


# --- 1. A sent report card is frozen ----------------------------------------

@pytest.mark.asyncio
async def test_reading_a_sent_report_card_does_not_rewrite_it(db: AsyncSession):
    """The headline bug: a parent opening a sent card silently recomputed it."""
    plan = await _plan(db, course_id=100, section_id=100, term_id=100)
    await _mark(db, student_id=100, plan=plan, raw=90.0)

    first = await generate_student_term_report_card(
        session=db, student_id=100, section_id=100, academic_term_id=100
    )
    sent_gpa = first.cumulative_gpa
    assert sent_gpa is not None
    await send_report_card(session=db, report_card_id=first.report_card_id, sent_by="teacher")

    # The mark is corrected downward AFTER the card went out.
    entry = (await db.execute(
        select(GradebookEntry).where(GradebookEntry.student_id == 100)
    )).scalar_one()
    entry.raw_score = 10.0
    db.add(entry)
    await db.commit()

    # A parent opens the card again.
    second = await generate_student_term_report_card(
        session=db, student_id=100, section_id=100, academic_term_id=100
    )
    stored = await db.get(TermReportCard, first.report_card_id)

    assert second.cumulative_gpa == sent_gpa, "A sent card must read as it was sent."
    assert stored.gpa == sent_gpa, "Reading a sent card must not overwrite its stored grades."
    assert stored.status == ReportCardStatus.SENT


@pytest.mark.asyncio
async def test_a_draft_still_recomputes_on_read(db: AsyncSession):
    """Proof the freeze is scoped to SENT and has not frozen everything."""
    plan = await _plan(db, course_id=101, section_id=101, term_id=101)
    await _mark(db, student_id=101, plan=plan, raw=90.0)
    first = await generate_student_term_report_card(
        session=db, student_id=101, section_id=101, academic_term_id=101
    )

    entry = (await db.execute(
        select(GradebookEntry).where(GradebookEntry.student_id == 101)
    )).scalar_one()
    entry.raw_score = 20.0
    db.add(entry)
    await db.commit()

    second = await generate_student_term_report_card(
        session=db, student_id=101, section_id=101, academic_term_id=101
    )
    assert second.cumulative_gpa != first.cumulative_gpa


# --- 2. GPA fabrication -----------------------------------------------------

@pytest.mark.asyncio
async def test_a_student_with_no_marks_has_no_gpa(db: AsyncSession):
    """Not 4.0, not 0.0, not an honour-roll place. No grade."""
    result = await calculate_cumulative_gpa(session=db, student_id=999_001)

    assert result["unweighted_gpa"] is None
    assert result["academic_standing"] is None
    assert result["honor_roll"] is None
    assert result["total_credits"] == 0.0
    assert result["graded_courses"] == 0


@pytest.mark.asyncio
async def test_gpa_works_for_a_student_who_has_marks(db: AsyncSession):
    """The path that used to raise AttributeError on `entry.score`."""
    plan = await _plan(db, course_id=102, section_id=102, term_id=102)
    await _mark(db, student_id=102, plan=plan, raw=95.0)

    result = await calculate_cumulative_gpa(session=db, student_id=102)

    assert result["unweighted_gpa"] is not None, "A graded student must get a GPA."
    assert result["graded_courses"] == 1
    assert result["total_credits"] > 0
    assert result["honor_roll"] is True  # 95% -> A+ -> 4.0


@pytest.mark.asyncio
async def test_gpa_agrees_with_the_report_card_engine(db: AsyncSession):
    """One grading engine, not two. The old handler carried its own ladder."""
    plan = await _plan(db, course_id=103, section_id=103, term_id=103)
    await _mark(db, student_id=103, plan=plan, raw=72.0)

    gpa = await calculate_cumulative_gpa(session=db, student_id=103)
    card = await generate_student_term_report_card(
        session=db, student_id=103, section_id=103, academic_term_id=103
    )
    assert gpa["unweighted_gpa"] == card.cumulative_gpa


# --- 3. Batch draft ---------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_draft_reports_an_ungraded_student_separately(db: AsyncSession):
    """An ungraded student must not look like a successful draft."""
    plan = await _plan(db, course_id=104, section_id=104, term_id=104)
    await _enrol(db, student_id=1041, section_id=104)
    await _enrol(db, student_id=1042, section_id=104)
    await _mark(db, student_id=1041, plan=plan, raw=88.0)  # 1042 has nothing

    outcomes = await batch_generate_report_card_drafts(
        session=db, section_id=104, academic_term_id=104, generate_narrative=False
    )
    by_student = {o["student_id"]: o for o in outcomes}

    assert by_student[1041]["outcome"] == "drafted"
    assert by_student[1042]["outcome"] == "drafted_ungraded"
    assert "no graded credits" in by_student[1042]["detail"].lower()

    ungraded = await db.get(TermReportCard, by_student[1042]["report_card_id"])
    assert ungraded.letter_grade is None, "An ungraded student must not be given a letter."
    assert ungraded.total_credits == 0


@pytest.mark.asyncio
async def test_batch_draft_skips_a_sent_card(db: AsyncSession):
    plan = await _plan(db, course_id=105, section_id=105, term_id=105)
    await _enrol(db, student_id=1051, section_id=105)
    await _mark(db, student_id=1051, plan=plan, raw=80.0)

    first = await generate_student_term_report_card(
        session=db, student_id=1051, section_id=105, academic_term_id=105
    )
    await send_report_card(session=db, report_card_id=first.report_card_id, sent_by="t")

    outcomes = await batch_generate_report_card_drafts(
        session=db, section_id=105, academic_term_id=105, generate_narrative=False
    )
    assert outcomes[0]["outcome"] == "skipped_sent"


@pytest.mark.asyncio
async def test_batch_draft_ignores_withdrawn_students(db: AsyncSession):
    """A withdrawn student must not acquire a fresh report card."""
    await _plan(db, course_id=106, section_id=106, term_id=106)
    await _enrol(db, student_id=1061, section_id=106)
    await _enrol(db, student_id=1062, section_id=106, status="withdrawn")

    outcomes = await batch_generate_report_card_drafts(
        session=db, section_id=106, academic_term_id=106, generate_narrative=False
    )
    assert {o["student_id"] for o in outcomes} == {1061}


# --- 4. Recalculate ---------------------------------------------------------

@pytest.mark.asyncio
async def test_recalculate_is_idempotent(db: AsyncSession):
    plan = await _plan(db, course_id=107, section_id=107, term_id=107)
    await _enrol(db, student_id=1071, section_id=107)
    await _mark(db, student_id=1071, plan=plan, raw=77.0)
    await batch_generate_report_card_drafts(
        session=db, section_id=107, academic_term_id=107, generate_narrative=False
    )

    once = await recalculate_report_cards(session=db, section_id=107, academic_term_id=107)
    twice = await recalculate_report_cards(session=db, section_id=107, academic_term_id=107)

    assert once[0]["cumulative_gpa"] == twice[0]["cumulative_gpa"]
    assert twice[0]["previous_cumulative_gpa"] == twice[0]["cumulative_gpa"]


@pytest.mark.asyncio
async def test_recalculate_never_touches_a_sent_card(db: AsyncSession):
    plan = await _plan(db, course_id=108, section_id=108, term_id=108)
    await _enrol(db, student_id=1081, section_id=108)
    await _mark(db, student_id=1081, plan=plan, raw=90.0)
    first = await generate_student_term_report_card(
        session=db, student_id=1081, section_id=108, academic_term_id=108
    )
    sent_gpa = first.cumulative_gpa
    await send_report_card(session=db, report_card_id=first.report_card_id, sent_by="t")

    entry = (await db.execute(
        select(GradebookEntry).where(GradebookEntry.student_id == 1081)
    )).scalar_one()
    entry.raw_score = 30.0
    db.add(entry)
    await db.commit()

    outcomes = await recalculate_report_cards(session=db, section_id=108, academic_term_id=108)
    stored = await db.get(TermReportCard, first.report_card_id)

    assert outcomes[0]["outcome"] == "skipped_sent"
    assert stored.gpa == sent_gpa, "A sent card must survive a section recalculation."


@pytest.mark.asyncio
async def test_recalculate_picks_up_a_late_mark(db: AsyncSession):
    """The reason recalculate exists at all."""
    plan = await _plan(db, course_id=109, section_id=109, term_id=109, weight=50.0)
    await _enrol(db, student_id=1091, section_id=109)
    await _mark(db, student_id=1091, plan=plan, raw=50.0)
    await batch_generate_report_card_drafts(
        session=db, section_id=109, academic_term_id=109, generate_narrative=False
    )

    entry = (await db.execute(
        select(GradebookEntry).where(GradebookEntry.student_id == 1091)
    )).scalar_one()
    entry.raw_score = 100.0
    db.add(entry)
    await db.commit()

    outcomes = await recalculate_report_cards(session=db, section_id=109, academic_term_id=109)
    assert outcomes[0]["outcome"] == "recalculated"
    assert outcomes[0]["cumulative_gpa"] != outcomes[0]["previous_cumulative_gpa"]


# --- 5. Batch send ----------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_send_reports_a_bad_id_without_aborting(db: AsyncSession):
    """One bad id must not abort a term-end run half-way through."""
    plan = await _plan(db, course_id=110, section_id=110, term_id=110)
    await _enrol(db, student_id=1101, section_id=110)
    await _mark(db, student_id=1101, plan=plan, raw=85.0)
    drafted = await batch_generate_report_card_drafts(
        session=db, section_id=110, academic_term_id=110, generate_narrative=False
    )
    good_id = drafted[0]["report_card_id"]

    outcomes = await batch_send_report_cards(
        session=db, report_card_ids=[good_id, 999_999], sent_by="teacher"
    )
    by_id = {o["report_card_id"]: o["outcome"] for o in outcomes}

    assert by_id[good_id] == "sent"
    assert by_id[999_999] == "not_found"


@pytest.mark.asyncio
async def test_batch_send_reports_an_already_sent_card(db: AsyncSession):
    plan = await _plan(db, course_id=111, section_id=111, term_id=111)
    await _enrol(db, student_id=1111, section_id=111)
    await _mark(db, student_id=1111, plan=plan, raw=85.0)
    drafted = await batch_generate_report_card_drafts(
        session=db, section_id=111, academic_term_id=111, generate_narrative=False
    )
    card_id = drafted[0]["report_card_id"]

    await batch_send_report_cards(session=db, report_card_ids=[card_id], sent_by="t")
    second = await batch_send_report_cards(session=db, report_card_ids=[card_id], sent_by="t")

    assert second[0]["outcome"] == "already_sent"


# --- 6. Listing -------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_report_cards_filters_by_status(db: AsyncSession):
    plan = await _plan(db, course_id=112, section_id=112, term_id=112)
    await _enrol(db, student_id=1121, section_id=112)
    await _enrol(db, student_id=1122, section_id=112)
    await _mark(db, student_id=1121, plan=plan, raw=85.0)
    await _mark(db, student_id=1122, plan=plan, raw=65.0)
    drafted = await batch_generate_report_card_drafts(
        session=db, section_id=112, academic_term_id=112, generate_narrative=False
    )
    await batch_send_report_cards(
        session=db, report_card_ids=[drafted[0]["report_card_id"]], sent_by="t"
    )

    all_cards = await list_report_cards(session=db, section_id=112, academic_term_id=112)
    sent_only = await list_report_cards(
        session=db, section_id=112, academic_term_id=112, status_filter="sent"
    )
    draft_only = await list_report_cards(
        session=db, section_id=112, academic_term_id=112, status_filter="draft"
    )

    assert len(all_cards) == 2
    assert len(sent_only) == 1
    assert len(draft_only) == 1
