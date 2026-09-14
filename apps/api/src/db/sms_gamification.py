"""
SMS Gamification, Badges & Leaderboards Database Models (Module M20).

Tracks student XP points, streaks, badges unlocked, level tiers,
and grade-level leaderboards.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class Badge(SQLModel, table=True):
    __tablename__ = "sms_gamification_badges"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    name: str = Field(description="Badge name, e.g. Math Wizard, Perfect Attendance 30D")
    description: str
    icon_name: str = Field(default="trophy")
    points_reward: int = Field(default=50)
    category: str = Field(default="academic", description="academic | attendance | socratic | community")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserBadge(SQLModel, table=True):
    __tablename__ = "sms_gamification_user_badges"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    user_id: int = Field(index=True, description="Learnhouse user ID")
    badge_id: int = Field(foreign_key="sms_gamification_badges.id", index=True)
    awarded_at: datetime = Field(default_factory=datetime.utcnow)


class PointTransaction(SQLModel, table=True):
    __tablename__ = "sms_gamification_point_transactions"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    user_id: int = Field(index=True)
    points: int = Field(description="Positive or negative points delta")
    reason: str = Field(description="e.g. Socratic Tutor Mastery, Quiz 100%, Assignment On-Time")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StudentStreak(SQLModel, table=True):
    __tablename__ = "sms_gamification_streaks"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    user_id: int = Field(index=True, unique=True)
    current_streak_days: int = Field(default=1)
    longest_streak_days: int = Field(default=1)
    last_activity_date: str = Field(description="ISO Date YYYY-MM-DD")
    total_xp: int = Field(default=0)
    level: int = Field(default=1)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
