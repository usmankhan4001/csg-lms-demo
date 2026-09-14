from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SUPER_ADMIN,
    SCHOOL_ADMIN,
    TEACHER,
    STAFF,
    STUDENT,
    get_current_user_principal,
    require_roles,
)
from src.schemas.sms_gamification import (
    AddPointsPayload,
    AwardBadgePayload,
    BadgeCreate,
    BadgeRead,
    LeaderboardEntry,
    StudentGamificationProfile,
)
from src.services.sms.gamification import GamificationService

router = APIRouter(prefix="/sms/gamification", tags=["sms-gamification"])


@router.post("/badges", response_model=BadgeRead, status_code=status.HTTP_201_CREATED)
async def create_badge(
    payload: BadgeCreate,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER])),
):
    return await GamificationService.create_badge(db=db, payload=payload, org_id=principal.org_id)


@router.get("/badges", response_model=List[BadgeRead])
async def list_badges(
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    return await GamificationService.list_badges(db=db, org_id=principal.org_id)


@router.post("/badges/award", status_code=status.HTTP_201_CREATED)
async def award_badge(
    payload: AwardBadgePayload,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER])),
):
    return await GamificationService.award_badge(
        db=db, user_id=payload.user_id, badge_id=payload.badge_id, org_id=principal.org_id
    )


@router.post("/points/add", status_code=status.HTTP_200_OK)
async def add_points(
    payload: AddPointsPayload,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER])),
):
    return await GamificationService.add_points(
        db=db,
        user_id=payload.user_id,
        points=payload.points,
        reason=payload.reason,
        org_id=principal.org_id,
    )


@router.get("/profile/{user_id}", response_model=StudentGamificationProfile)
async def get_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    return await GamificationService.get_profile(db=db, user_id=user_id)


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    return await GamificationService.get_leaderboard(db=db, org_id=principal.org_id, limit=limit)
