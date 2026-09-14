from datetime import date, datetime, timedelta
from typing import List, Optional
from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_gamification import Badge, PointTransaction, StudentStreak, UserBadge
from src.db.users import User
from src.schemas.sms_gamification import (
    BadgeCreate,
    BadgeRead,
    LeaderboardEntry,
    StudentGamificationProfile,
)


class GamificationService:
    @staticmethod
    async def create_badge(
        db: AsyncSession,
        payload: BadgeCreate,
        org_id: Optional[int],
    ) -> Badge:
        badge = Badge(
            org_id=org_id,
            name=payload.name,
            description=payload.description,
            icon_name=payload.icon_name,
            points_reward=payload.points_reward,
            category=payload.category,
        )
        db.add(badge)
        await db.commit()
        await db.refresh(badge)
        return badge

    @staticmethod
    async def list_badges(db: AsyncSession, org_id: Optional[int]) -> List[Badge]:
        query = select(Badge)
        if org_id is not None:
            query = query.where(Badge.org_id == org_id)
        result = await db.exec(query)
        return list(result.all())

    @staticmethod
    async def add_points(
        db: AsyncSession,
        user_id: int,
        points: int,
        reason: str,
        org_id: Optional[int],
    ) -> StudentStreak:
        tx = PointTransaction(
            org_id=org_id,
            user_id=user_id,
            points=points,
            reason=reason,
        )
        db.add(tx)

        # Update or create streak
        query = select(StudentStreak).where(StudentStreak.user_id == user_id)
        result = await db.exec(query)
        streak = result.first()
        today = date.today().isoformat()

        if not streak:
            streak = StudentStreak(
                org_id=org_id,
                user_id=user_id,
                total_xp=max(0, points),
                level=max(1, (max(0, points) // 100) + 1),
                current_streak_days=1,
                longest_streak_days=1,
                last_activity_date=today,
            )
            db.add(streak)
        else:
            streak.total_xp = max(0, streak.total_xp + points)
            streak.level = max(1, (streak.total_xp // 100) + 1)
            # Check streak days
            last_date = date.fromisoformat(streak.last_activity_date) if streak.last_activity_date else None
            today_date = date.today()
            if last_date == today_date - timedelta(days=1):
                streak.current_streak_days += 1
                streak.longest_streak_days = max(streak.longest_streak_days, streak.current_streak_days)
            elif last_date and last_date < today_date - timedelta(days=1):
                streak.current_streak_days = 1
            streak.last_activity_date = today

        await db.commit()
        await db.refresh(streak)
        return streak

    @staticmethod
    async def award_badge(
        db: AsyncSession,
        user_id: int,
        badge_id: int,
        org_id: Optional[int],
    ) -> UserBadge:
        badge = await db.get(Badge, badge_id)
        if not badge:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Badge not found")

        existing = await db.exec(
            select(UserBadge).where(UserBadge.user_id == user_id, UserBadge.badge_id == badge_id)
        )
        if existing.first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already earned this badge")

        ub = UserBadge(
            org_id=org_id,
            user_id=user_id,
            badge_id=badge_id,
        )
        db.add(ub)
        # Award bonus XP for badge
        await GamificationService.add_points(
            db=db,
            user_id=user_id,
            points=badge.points_reward,
            reason=f"Unlocked Badge: {badge.name}",
            org_id=org_id,
        )
        await db.commit()
        await db.refresh(ub)
        return ub

    @staticmethod
    async def get_profile(db: AsyncSession, user_id: int) -> StudentGamificationProfile:
        query = select(StudentStreak).where(StudentStreak.user_id == user_id)
        result = await db.exec(query)
        streak = result.first()

        user_badges_res = await db.exec(
            select(UserBadge, Badge).join(Badge, UserBadge.badge_id == Badge.id).where(UserBadge.user_id == user_id)
        )
        badges = [
            BadgeRead(
                id=b.id,
                org_id=b.org_id,
                name=b.name,
                description=b.description,
                icon_name=b.icon_name,
                points_reward=b.points_reward,
                category=b.category,
                created_at=b.created_at,
            )
            for ub, b in user_badges_res.all()
        ]

        return StudentGamificationProfile(
            user_id=user_id,
            total_xp=streak.total_xp if streak else 0,
            level=streak.level if streak else 1,
            current_streak_days=streak.current_streak_days if streak else 0,
            longest_streak_days=streak.longest_streak_days if streak else 0,
            badges=badges,
        )

    @staticmethod
    async def get_leaderboard(db: AsyncSession, org_id: Optional[int], limit: int = 50) -> List[LeaderboardEntry]:
        query = select(StudentStreak).order_by(StudentStreak.total_xp.desc()).limit(limit)
        if org_id is not None:
            query = query.where(StudentStreak.org_id == org_id)
        results = (await db.exec(query)).all()

        leaderboard = []
        for idx, s in enumerate(results, 1):
            user = await db.get(User, s.user_id)
            name = " ".join(filter(None, [user.first_name, user.last_name])) if user else f"Student #{s.user_id}"
            badge_count = len((await db.exec(select(UserBadge).where(UserBadge.user_id == s.user_id))).all())
            leaderboard.append(
                LeaderboardEntry(
                    rank=idx,
                    user_id=s.user_id,
                    name=name,
                    total_xp=s.total_xp,
                    level=s.level,
                    current_streak_days=s.current_streak_days,
                    badges_count=badge_count,
                )
            )
        return leaderboard
