import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.schemas.sms_pathways import CurricularPathwayCreate, PathwayCourseCreate
from src.services.sms.pathways import CurricularPathwayService


@pytest.mark.asyncio
async def test_curricular_pathways_and_enrollment(db: AsyncSession):
    # 1. Create Pathway with Course Sequence
    pathway = await CurricularPathwayService.create_pathway(
        db=db,
        payload=CurricularPathwayCreate(
            name="Cambridge STEM Distinction Track",
            code="CAM-STEM",
            required_credits=18,
            courses=[
                PathwayCourseCreate(course_id=1001, credits=4, semester_sequence=1),
                PathwayCourseCreate(course_id=1002, credits=4, semester_sequence=1),
                PathwayCourseCreate(course_id=1003, credits=5, semester_sequence=2, prerequisite_course_id=1001),
                PathwayCourseCreate(course_id=1004, credits=5, semester_sequence=2),
            ],
        ),
        org_id=1,
    )
    assert pathway.id is not None

    # 2. List Pathways
    pathways = await CurricularPathwayService.list_pathways(db=db, org_id=1)
    assert len(pathways) >= 1
    assert pathways[0].code == "CAM-STEM"
    assert len(pathways[0].courses) == 4

    # 3. Enroll Student
    enrollment = await CurricularPathwayService.enroll_student(
        db=db,
        student_id=501,
        pathway_id=pathway.id,
        org_id=1,
    )
    assert enrollment.id is not None
    assert enrollment.status == "in_progress"

    # 4. Get Student Progress
    progress = await CurricularPathwayService.get_student_progress(db=db, student_id=501)
    assert len(progress) == 1
    assert progress[0].pathway_name == "Cambridge STEM Distinction Track"

    # A student who has just enrolled has completed NOTHING. Credit progress is
    # not tracked anywhere -- StudentPathwayEnrollment records who enrolled and
    # when, with no link to completed work -- so it must report no figure.
    #
    # This previously computed earned credits as
    # `min(required_credits, len(pathway_courses) * 3)`, counting the pathway's
    # OWN syllabus as the student's completed work. This pathway has 4 courses,
    # so it credited 12 and clamped to the requirement: a student who had done
    # nothing was shown at 100% of their graduation requirements.
    assert progress[0].earned_credits is None, (
        "Earned credits must not be inferred from the pathway's own course list."
    )
    assert progress[0].progress_percentage is None, (
        "A student who has completed nothing must not be shown a completion "
        "percentage -- least of all against graduation requirements."
    )
    assert progress[0].detail is not None
    # The requirement itself is real configuration and is still reported.
    assert progress[0].total_required_credits == pathway.required_credits
    assert progress[0].status == "in_progress"
