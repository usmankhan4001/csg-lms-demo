import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.schemas.sms_alumni import AlumniMilestoneCreate, AlumniProfileCreate
from src.services.sms.alumni import AlumniService


@pytest.mark.asyncio
async def test_alumni_profile_and_milestones(db: AsyncSession):
    # 1. Create alumni profile
    payload = AlumniProfileCreate(
        user_id=205,
        graduation_year=2023,
        degree_or_diploma="High School STEM Diploma",
        current_company="Google DeepMind",
        job_title="AI Research Engineer",
        industry="Technology",
        higher_ed_institution="MIT",
        higher_ed_major="Computer Science",
        willing_to_mentor=True,
        mentorship_topics="AI, Software Engineering, MIT Admissions",
    )
    profile = await AlumniService.create_profile(
        db=db,
        payload=payload,
        org_id=1,
        campus_id=1,
    )
    assert profile.id is not None
    assert profile.user_id == 205
    assert profile.willing_to_mentor is True

    # 2. Add career milestone
    milestone = await AlumniService.add_milestone(
        db=db,
        payload=AlumniMilestoneCreate(
            alumni_id=profile.id,
            title="Published NeurIPS Paper",
            description="Paper on multi-agent reinforcement learning",
            milestone_date="2025-12-01",
        ),
        org_id=1,
    )
    assert milestone.id is not None
    assert milestone.title == "Published NeurIPS Paper"

    # 3. List profiles
    profiles = await AlumniService.list_profiles(
        db=db,
        org_id=1,
        graduation_year=2023,
    )
    assert len(profiles) >= 1
    assert profiles[0].user_id == 205
    assert len(profiles[0].milestones) >= 1
