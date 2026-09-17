"""
CSG-EMS SMS Demo Seeder API Router
===================================
Provides HTTP endpoints for seeding and clean-reseeding comprehensive demo data
across all SMS-First modules and embedded Learnhouse LMS.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.services.demo.sms_demo_seeder import seed_sms_demo_data, clean_sms_demo_data

router = APIRouter()


class SeedDemoRequest(BaseModel):
    org_slug: Optional[str] = Field(
        default=None,
        description="Slug of target organization to seed (defaults to 'csg-academy').",
    )
    clear_previous: bool = Field(
        default=False,
        description="Whether to cleanly delete prior demo data before seeding.",
    )


class CleanAndReseedDemoRequest(BaseModel):
    org_slug: Optional[str] = Field(
        default=None,
        description="Slug of target organization to clean and reseed (defaults to 'csg-academy').",
    )


class DemoSeedResponse(BaseModel):
    status: str
    organization: str
    org_slug: str
    users_seeded: int
    users_created: int
    users_skipped_existing: list[str] = []
    campus: str
    sections: int
    courses: int
    ami_index: float
    demo_password: Optional[str] = None


@router.post(
    "/seed",
    response_model=DemoSeedResponse,
    summary="Seed CSG-EMS Comprehensive Demo Data",
    description="Seeds 7 personas, 4 class sections, 4 courses, timetable, attendance, gradebook, CBT exams, CRM leads, financials, payroll, and Cognia evidence locker.",
)
async def seed_demo_endpoint(
    payload: Optional[SeedDemoRequest] = None,
    db_session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    org_slug = payload.org_slug if payload else None
    clear_previous = payload.clear_previous if payload else False

    try:
        result = await seed_sms_demo_data(
            db_session=db_session,
            org_slug=org_slug,
            clear_previous=clear_previous,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed demo data: {str(e)}",
        )


@router.post(
    "/clean-and-reseed",
    response_model=DemoSeedResponse,
    summary="Clean and Reseed CSG-EMS Demo Data",
    description="Wipes all existing demo records in FK dependency order before re-seeding a pristine demonstration dataset.",
)
async def clean_and_reseed_demo_endpoint(
    payload: Optional[CleanAndReseedDemoRequest] = None,
    db_session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    org_slug = payload.org_slug if payload else None

    try:
        result = await seed_sms_demo_data(
            db_session=db_session,
            org_slug=org_slug,
            clear_previous=True,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clean and reseed demo data: {str(e)}",
        )
