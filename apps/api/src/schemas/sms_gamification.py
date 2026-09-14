from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class BadgeCreate(BaseModel):
    name: str
    description: str
    icon_name: str = "trophy"
    points_reward: int = 50
    category: str = "academic"


class BadgeRead(BaseModel):
    id: int
    org_id: Optional[int]
    name: str
    description: str
    icon_name: str
    points_reward: int
    category: str
    created_at: datetime


class AwardBadgePayload(BaseModel):
    user_id: int
    badge_id: int


class AddPointsPayload(BaseModel):
    user_id: int
    points: int
    reason: str


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    name: str
    total_xp: int
    level: int
    current_streak_days: int
    badges_count: int


class StudentGamificationProfile(BaseModel):
    user_id: int
    total_xp: int
    level: int
    current_streak_days: int
    longest_streak_days: int
    badges: List[BadgeRead] = []
