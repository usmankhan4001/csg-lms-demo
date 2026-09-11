import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.keycloak_auth import KeycloakUserPrincipal
from src.schemas.sms_gradebook import (
    AssessmentPlanCreate,
    BatchGradebookEntryRequest,
    GenerateReportCardDraftRequest,
    GradeInterval,
    GradebookEntryInput,
    GradingScaleCreate,
    ReportCardDraftUpdate,
)
from src.routers.sms_gradebook import (
    batch_enter_grades,
    create_assessment_plan,
    create_grading_scale,
    generate_report_card_draft_endpoint,
    get_report_card_by_id_endpoint,
    get_student_report_card,
    list_assessment_plans,
    list_grading_scales,
    send_report_card_endpoint,
    update_report_card_draft_endpoint,
)
from src.services.sms import gradebook as gradebook_service
from src.services.sms.gradebook import resolve_letter_and_gpa


def test_resolve_letter_and_gpa():
    """Test standard 4.0 GPA scale resolution."""
    assert resolve_letter_and_gpa(95.0) == ("A+", 4.0)
    assert resolve_letter_and_gpa(85.0) == ("A", 3.7)
    assert resolve_letter_and_gpa(78.0) == ("B+", 3.3)
    assert resolve_letter_and_gpa(72.0) == ("B", 3.0)
    assert resolve_letter_and_gpa(66.0) == ("C+", 2.7)
    assert resolve_letter_and_gpa(62.0) == ("C", 2.0)
    assert resolve_letter_and_gpa(55.0) == ("D", 1.0)
    assert resolve_letter_and_gpa(45.0) == ("F", 0.0)


@pytest.mark.asyncio
async def test_gradebook_and_gpa_calculation_lifecycle(db: AsyncSession):
    """Test full gradebook lifecycle: plans, grading entries, and term report card."""
    # 1. Create custom grading scale
    scale_payload = GradingScaleCreate(
        name="Custom 4.0 Scale",
        description="Standard institutional grading scale",
        intervals=[
            GradeInterval(grade="A+", min_percentage=90.0, max_percentage=100.0, gpa_point=4.0),
            GradeInterval(grade="A", min_percentage=80.0, max_percentage=89.99, gpa_point=3.7),
            GradeInterval(grade="B", min_percentage=70.0, max_percentage=79.99, gpa_point=3.0),
            GradeInterval(grade="C", min_percentage=60.0, max_percentage=69.99, gpa_point=2.0),
            GradeInterval(grade="F", min_percentage=0.0, max_percentage=59.99, gpa_point=0.0),
        ],
        is_default=True,
    )
    scale = await create_grading_scale(payload=scale_payload, session=db)
    assert scale.id is not None

    scales = await list_grading_scales(session=db)
    assert len(scales) == 1

    # 2. Create Assessment Plans for Course 101 (Midterm 40%, Final 60%)
    plan1 = await create_assessment_plan(
        payload=AssessmentPlanCreate(
            course_id=101,
            section_id=1,
            academic_term_id=1,
            assessment_name="Midterm Exam",
            weight_percentage=40.0,
            max_score=100.0,
        ),
        session=db,
    )
    plan2 = await create_assessment_plan(
        payload=AssessmentPlanCreate(
            course_id=101,
            section_id=1,
            academic_term_id=1,
            assessment_name="Final Exam",
            weight_percentage=60.0,
            max_score=100.0,
        ),
        session=db,
    )
    assert plan1.id is not None
    assert plan2.id is not None

    plans = await list_assessment_plans(course_id=101, session=db)
    assert len(plans) == 2

    # 3. Enter grades for Student 501
    # Midterm: 90/100 (weighted = 36)
    # Final: 80/100 (weighted = 48)
    # Course final score = 36 + 48 = 84% -> Grade A, GPA point 3.7
    await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan1.id,
            entries=[GradebookEntryInput(student_id=501, raw_score=90.0, remarks="Excellent")],
            graded_by=10,
        ),
        session=db,
    )
    await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan2.id,
            entries=[GradebookEntryInput(student_id=501, raw_score=80.0, remarks="Good job")],
            graded_by=10,
        ),
        session=db,
    )

    # 4. Generate Student Report Card
    report = await get_student_report_card(
        student_id=501,
        section_id=1,
        academic_term_id=1,
        session=db,
    )
    assert report.student_id == 501
    assert report.total_credits == 3.0
    assert report.cumulative_gpa == 3.7
    assert report.overall_letter_grade == "A"
    assert len(report.courses) == 1
    assert report.courses[0].total_weighted_percentage == 84.0
    assert len(report.courses[0].assessment_breakdown) == 2


@pytest.mark.asyncio
async def test_report_card_draft_to_sent_lifecycle(db: AsyncSession, monkeypatch):
    """Phase 4, Part A.4: TEACHER generates a DRAFT (GPA data + AI narrative),
    edits it, then explicitly sends it. A PARENT can only see it once SENT,
    and a sent report card is frozen against further regeneration/editing."""

    async def _fake_narrative(**kwargs):
        return "Great progress this term, especially in mathematics."

    monkeypatch.setattr(gradebook_service, "generate", _fake_narrative)

    teacher = KeycloakUserPrincipal(sub="teacher-1", org_id=1, campus_id=1, roles={"TEACHER"})
    parent = KeycloakUserPrincipal(sub="parent-1", org_id=1, campus_id=1, roles={"PARENT"})

    plan = await create_assessment_plan(
        payload=AssessmentPlanCreate(
            course_id=201,
            section_id=2,
            academic_term_id=2,
            assessment_name="Final Exam",
            weight_percentage=100.0,
            max_score=100.0,
        ),
        session=db,
    )
    await batch_enter_grades(
        payload=BatchGradebookEntryRequest(
            assessment_plan_id=plan.id,
            entries=[GradebookEntryInput(student_id=601, raw_score=88.0)],
        ),
        session=db,
    )

    # A non-staff caller cannot generate a report card at all.
    with pytest.raises(HTTPException) as excinfo_forbidden:
        await generate_report_card_draft_endpoint(
            student_id=601,
            payload=GenerateReportCardDraftRequest(
                section_id=2, academic_term_id=2, generate_narrative=False
            ),
            session=db,
            principal=parent,
        )
    assert excinfo_forbidden.value.status_code == 403

    # 1. Teacher generates the draft (with AI-assisted narrative).
    draft = await generate_report_card_draft_endpoint(
        student_id=601,
        payload=GenerateReportCardDraftRequest(
            section_id=2, academic_term_id=2, generate_narrative=True
        ),
        session=db,
        principal=teacher,
    )
    assert draft.status.value == "draft"
    assert draft.ai_narrative == "Great progress this term, especially in mathematics."
    assert draft.sent_at is None

    # A PARENT cannot see it yet -- it's still a draft.
    with pytest.raises(HTTPException) as excinfo_draft:
        await get_report_card_by_id_endpoint(
            report_card_id=draft.id, session=db, principal=parent
        )
    assert excinfo_draft.value.status_code == 404

    # 2. Teacher edits the draft before sending.
    edited = await update_report_card_draft_endpoint(
        report_card_id=draft.id,
        payload=ReportCardDraftUpdate(remarks="Reviewed and approved by homeroom teacher."),
        session=db,
        principal=teacher,
    )
    assert edited.remarks == "Reviewed and approved by homeroom teacher."
    assert edited.status.value == "draft"

    # 3. Teacher explicitly sends it -- no auto-send, no separate admin approval.
    sent = await send_report_card_endpoint(
        report_card_id=draft.id, session=db, principal=teacher
    )
    assert sent.status.value == "sent"
    assert sent.sent_by == "teacher-1"
    assert sent.sent_at is not None

    # 4. Now the parent CAN see it.
    parent_view = await get_report_card_by_id_endpoint(
        report_card_id=draft.id, session=db, principal=parent
    )
    assert parent_view.status.value == "sent"
    assert parent_view.ai_narrative == "Great progress this term, especially in mathematics."

    # 5. A sent report card is frozen: sending again conflicts.
    with pytest.raises(HTTPException) as excinfo_resend:
        await send_report_card_endpoint(report_card_id=draft.id, session=db, principal=teacher)
    assert excinfo_resend.value.status_code == 409

    # 6. ...and so does editing it.
    with pytest.raises(HTTPException) as excinfo_edit_sent:
        await update_report_card_draft_endpoint(
            report_card_id=draft.id,
            payload=ReportCardDraftUpdate(remarks="oops"),
            session=db,
            principal=teacher,
        )
    assert excinfo_edit_sent.value.status_code == 409

    # 7. ...and regenerating it.
    with pytest.raises(HTTPException) as excinfo_regen:
        await generate_report_card_draft_endpoint(
            student_id=601,
            payload=GenerateReportCardDraftRequest(
                section_id=2, academic_term_id=2, generate_narrative=False
            ),
            session=db,
            principal=teacher,
        )
    assert excinfo_regen.value.status_code == 409
