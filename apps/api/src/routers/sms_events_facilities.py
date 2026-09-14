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
from src.schemas.sms_events_facilities import (
    CampusFacilityCreate,
    CampusFacilityRead,
    FacilityBookingCreate,
    FacilityBookingRead,
)
from src.security.school_ownership import resolve_scoped_campus_id
from src.services.sms.events_facilities import FacilityBookingService

router = APIRouter(prefix="/sms/events-facilities", tags=["sms-events-facilities"])


@router.post("/facilities", response_model=CampusFacilityRead, status_code=status.HTTP_201_CREATED)
async def create_facility(
    payload: CampusFacilityCreate,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, STAFF])),
):
    return await FacilityBookingService.create_facility(
        db=db, payload=payload, org_id=principal.org_id, campus_id=principal.campus_id
    )


@router.get("/facilities", response_model=List[CampusFacilityRead])
async def list_facilities(
    campus_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    # campus_id arrives from the CLIENT. org_id alone is not enough tenancy:
    # without this, a campus-bound admin at campus A could list campus B's
    # facilities simply by passing campus_id=B. resolve_scoped_campus_id pins a
    # campus-bound caller to their own campus whether they ask for another or
    # ask for none; only a caller with no campus of their own sees org-wide.
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)
    return await FacilityBookingService.list_facilities(
        db=db, org_id=principal.org_id, campus_id=scoped_campus
    )


@router.post("/bookings", response_model=FacilityBookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: FacilityBookingCreate,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF])),
):
    user_id = principal.raw_claims.get("lh_user_id", 0)
    return await FacilityBookingService.create_booking(
        db=db,
        payload=payload,
        booked_by_id=user_id,
        org_id=principal.org_id,
        campus_id=principal.campus_id,
    )


@router.get("/bookings", response_model=List[FacilityBookingRead])
async def list_bookings(
    facility_id: Optional[int] = Query(None),
    booking_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    return await FacilityBookingService.list_bookings(
        db=db, org_id=principal.org_id, facility_id=facility_id, booking_date=booking_date
    )
