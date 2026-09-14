from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from src.db.sms_events_facilities import BookingStatusEnum, FacilityTypeEnum


class CampusFacilityCreate(BaseModel):
    name: str
    facility_type: FacilityTypeEnum = FacilityTypeEnum.CLASSROOM
    capacity: int = 30
    location_details: Optional[str] = None
    equipment_available: Optional[str] = None


class CampusFacilityRead(BaseModel):
    id: int
    org_id: Optional[int]
    campus_id: Optional[int]
    name: str
    facility_type: FacilityTypeEnum
    capacity: int
    location_details: Optional[str]
    equipment_available: Optional[str]
    is_active: bool
    created_at: datetime


class FacilityBookingCreate(BaseModel):
    facility_id: int
    event_title: str
    booking_date: str
    start_time: str
    end_time: str
    purpose: Optional[str] = None


class FacilityBookingRead(BaseModel):
    id: int
    org_id: Optional[int]
    campus_id: Optional[int]
    facility_id: int
    booked_by_id: int
    event_title: str
    booking_date: str
    start_time: str
    end_time: str
    status: BookingStatusEnum
    purpose: Optional[str]
    created_at: datetime
