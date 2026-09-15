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


@pytest.mark.asyncio
async def test_another_schools_profile_is_indistinguishable_from_a_missing_one(
    db: AsyncSession,
):
    """A milestone write must not reveal that another school's profile exists.

    This previously answered 404 for "no such profile" and 403 "Access denied"
    for "belongs to another school". Walking alumni_id values and reading the
    status told an authenticated user at school A exactly which profile ids
    exist at school B, and by counting them, roughly how large another
    school's alumni register is.

    Both cases must now be identical in STATUS and in DETAIL -- a differing
    message leaks exactly what the shared status is there to hide.
    """
    from fastapi import HTTPException

    other_school = await AlumniService.create_profile(
        db=db,
        payload=AlumniProfileCreate(
            user_id=9101,
            graduation_year=2019,
            degree_or_diploma="Diploma",
        ),
        org_id=77,
        campus_id=None,
    )

    def _attempt(alumni_id: int) -> HTTPException:
        return AlumniService.add_milestone(
            db=db,
            payload=AlumniMilestoneCreate(
                alumni_id=alumni_id,
                title="Probe",
                milestone_date="2026-01-01",
            ),
            org_id=1,
        )

    with pytest.raises(HTTPException) as foreign:
        await _attempt(other_school.id)

    # An id that exists nowhere at all.
    with pytest.raises(HTTPException) as absent:
        await _attempt(98765432)

    assert foreign.value.status_code == absent.value.status_code == 404
    assert foreign.value.detail == absent.value.detail, (
        "The two answers differ in wording, which re-opens the existence "
        "oracle the matching status code was meant to close."
    )
