import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.schemas.sms_gradebook import (
    AssessmentPlanCreate,
    BatchGradebookEntryRequest,
    GradeInterval,
    GradebookEntryInput,
    GradingScaleCreate,
)
from src.routers.sms_gradebook import (
    batch_enter_grades,
    create_assessment_plan,
    create_grading_scale,
    get_student_report_card,
    list_assessment_plans,
    list_grading_scales,
)
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
