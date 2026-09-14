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
from src.schemas.sms_alumni import (
    AlumniMilestoneCreate,
    AlumniMilestoneRead,
    AlumniProfileCreate,
    AlumniProfileRead,
    AlumniProfileUpdate,
)
from src.services.sms.alumni import AlumniService

router = APIRouter(prefix="/sms/alumni", tags=["sms-alumni"])


@router.post("/profiles", response_model=AlumniProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: AlumniProfileCreate,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, STAFF])),
):
    profile = await AlumniService.create_profile(
        db=db,
        payload=payload,
        org_id=principal.org_id,
        campus_id=principal.campus_id,
    )
    return AlumniProfileRead(
        id=profile.id,
        org_id=profile.org_id,
        campus_id=profile.campus_id,
        user_id=profile.user_id,
        graduation_year=profile.graduation_year,
        degree_or_diploma=profile.degree_or_diploma,
        current_company=profile.current_company,
        job_title=profile.job_title,
        industry=profile.industry,
        higher_ed_institution=profile.higher_ed_institution,
        higher_ed_major=profile.higher_ed_major,
        linkedin_url=profile.linkedin_url,
        location_city=profile.location_city,
        location_country=profile.location_country,
        willing_to_mentor=profile.willing_to_mentor,
        mentorship_topics=profile.mentorship_topics,
        created_at=profile.created_at,
        milestones=[],
    )


@router.get("/profiles", response_model=List[AlumniProfileRead])
async def list_profiles(
    graduation_year: Optional[int] = Query(None),
    industry: Optional[str] = Query(None),
    willing_to_mentor: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    return await AlumniService.list_profiles(
        db=db,
        org_id=principal.org_id,
        graduation_year=graduation_year,
        industry=industry,
        willing_to_mentor=willing_to_mentor,
    )


@router.post("/milestones", response_model=AlumniMilestoneRead, status_code=status.HTTP_201_CREATED)
async def add_milestone(
    payload: AlumniMilestoneCreate,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, STAFF])),
):
    return await AlumniService.add_milestone(
        db=db,
        payload=payload,
        org_id=principal.org_id,
    )
