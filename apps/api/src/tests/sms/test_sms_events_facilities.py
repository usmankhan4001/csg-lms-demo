import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.schemas.sms_events_facilities import CampusFacilityCreate, FacilityBookingCreate
from src.services.sms.events_facilities import FacilityBookingService


@pytest.mark.asyncio
async def test_facility_booking_and_conflict_engine(db: AsyncSession):
    # 1. Create Facility
    facility = await FacilityBookingService.create_facility(
        db=db,
        payload=CampusFacilityCreate(
            name="Main Auditorium",
            capacity=250,
            location_details="Building A, Floor 1",
            equipment_available="Full PA & Dual Laser Projectors",
        ),
        org_id=1,
        campus_id=1,
    )
    assert facility.id is not None

    # 2. Create Confirmed Booking
    booking = await FacilityBookingService.create_booking(
        db=db,
        payload=FacilityBookingCreate(
            facility_id=facility.id,
            event_title="Annual Science Exhibition",
            booking_date="2026-10-15",
            start_time="09:00",
            end_time="12:00",
            purpose="Student science fair setup and presentation",
        ),
        booked_by_id=10,
        org_id=1,
        campus_id=1,
    )
    assert booking.id is not None

    # 3. Test Conflict Detection: Attempt overlapping booking
    with pytest.raises(HTTPException) as exc_info:
        await FacilityBookingService.create_booking(
            db=db,
            payload=FacilityBookingCreate(
                facility_id=facility.id,
                event_title="Robotics Seminar",
                booking_date="2026-10-15",
                start_time="10:30",
                end_time="13:00",
            ),
            booked_by_id=11,
            org_id=1,
            campus_id=1,
        )
    assert exc_info.value.status_code == 409
    assert "Time slot conflict" in exc_info.value.detail
