import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.schemas.sms_gamification import BadgeCreate
from src.services.sms.gamification import GamificationService


@pytest.mark.asyncio
async def test_gamification_points_streak_and_badges(db: AsyncSession):
    # 1. Create Badge
    badge = await GamificationService.create_badge(
        db=db,
        payload=BadgeCreate(
            name="Math Wizard",
            description="Scored 100% on three consecutive math tests",
            points_reward=75,
        ),
        org_id=1,
    )
    assert badge.id is not None

    # 2. Add points
    streak = await GamificationService.add_points(
        db=db,
        user_id=401,
        points=150,
        reason="Completed Socratic Tutor session",
        org_id=1,
    )
    assert streak.total_xp == 150
    assert streak.level == 2

    # 3. Award Badge
    user_badge = await GamificationService.award_badge(
        db=db,
        user_id=401,
        badge_id=badge.id,
        org_id=1,
    )
    assert user_badge.id is not None

    # 4. Check Gamification Profile
    profile = await GamificationService.get_profile(db=db, user_id=401)
    assert profile.total_xp == 225  # 150 + 75 badge bonus
    assert len(profile.badges) == 1
    assert profile.badges[0].name == "Math Wizard"
