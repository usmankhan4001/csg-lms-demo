from typing import List, Optional
from fastapi import HTTPException, status
from sqlmodel import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_events_facilities import BookingStatusEnum, CampusFacility, FacilityBooking
from src.schemas.sms_events_facilities import CampusFacilityCreate, FacilityBookingCreate


class FacilityBookingService:
    @staticmethod
    async def create_facility(
        db: AsyncSession,
        payload: CampusFacilityCreate,
        org_id: Optional[int],
        campus_id: Optional[int],
    ) -> CampusFacility:
        facility = CampusFacility(
            org_id=org_id,
            campus_id=campus_id,
            name=payload.name,
            facility_type=payload.facility_type,
            capacity=payload.capacity,
            location_details=payload.location_details,
            equipment_available=payload.equipment_available,
        )
        db.add(facility)
        await db.commit()
        await db.refresh(facility)
        return facility

    @staticmethod
    async def list_facilities(
        db: AsyncSession,
        org_id: Optional[int],
        campus_id: Optional[int] = None,
    ) -> List[CampusFacility]:
        query = select(CampusFacility).where(CampusFacility.is_active == True)  # noqa: E712
        if org_id is not None:
            query = query.where(CampusFacility.org_id == org_id)
        if campus_id is not None:
            query = query.where(CampusFacility.campus_id == campus_id)
        result = await db.exec(query)
        return list(result.all())

    @staticmethod
    async def create_booking(
        db: AsyncSession,
        payload: FacilityBookingCreate,
        booked_by_id: int,
        org_id: Optional[int],
        campus_id: Optional[int],
    ) -> FacilityBooking:
        facility = await db.get(CampusFacility, payload.facility_id)
        if not facility or not facility.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found or inactive")

        # Conflict Detection Engine: Check for overlapping bookings
        conflict_query = select(FacilityBooking).where(
            FacilityBooking.facility_id == payload.facility_id,
            FacilityBooking.booking_date == payload.booking_date,
            FacilityBooking.status == BookingStatusEnum.CONFIRMED,
            and_(
                FacilityBooking.start_time < payload.end_time,
                FacilityBooking.end_time > payload.start_time,
            ),
        )
        conflicts = (await db.exec(conflict_query)).all()
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Time slot conflict: Facility is already booked on {payload.booking_date} from {conflicts[0].start_time} to {conflicts[0].end_time}",
            )

        booking = FacilityBooking(
            org_id=org_id,
            campus_id=campus_id,
            facility_id=payload.facility_id,
            booked_by_id=booked_by_id,
            event_title=payload.event_title,
            booking_date=payload.booking_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            purpose=payload.purpose,
            status=BookingStatusEnum.CONFIRMED,
        )
        db.add(booking)
        await db.commit()
        await db.refresh(booking)
        return booking

    @staticmethod
    async def list_bookings(
        db: AsyncSession,
        org_id: Optional[int],
        facility_id: Optional[int] = None,
        booking_date: Optional[str] = None,
    ) -> List[FacilityBooking]:
        query = select(FacilityBooking)
        if org_id is not None:
            query = query.where(FacilityBooking.org_id == org_id)
        if facility_id is not None:
            query = query.where(FacilityBooking.facility_id == facility_id)
        if booking_date is not None:
            query = query.where(FacilityBooking.booking_date == booking_date)
        query = query.order_by(FacilityBooking.booking_date.asc(), FacilityBooking.start_time.asc())
        result = await db.exec(query)
        return list(result.all())
