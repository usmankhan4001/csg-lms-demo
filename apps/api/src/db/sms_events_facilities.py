"""
SMS Campus Events & Facility Booking Database Models (Module M38).

Tracks school auditoriums, sports grounds, science labs, reservations with conflict engine,
and campus-wide calendar events.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel


class FacilityTypeEnum(str, Enum):
    AUDITORIUM = "auditorium"
    SPORTS_GROUND = "sports_ground"
    SCIENCE_LAB = "science_lab"
    COMPUTER_LAB = "computer_lab"
    LIBRARY_HALL = "library_hall"
    CONFERENCE_ROOM = "conference_room"
    CLASSROOM = "classroom"


class BookingStatusEnum(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class CampusFacility(SQLModel, table=True):
    __tablename__ = "sms_campus_facilities"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    campus_id: Optional[int] = Field(default=None, index=True)
    name: str = Field(description="e.g. Main Auditorium, Chemistry Lab 2")
    facility_type: FacilityTypeEnum = Field(default=FacilityTypeEnum.CLASSROOM)
    capacity: int = Field(default=30)
    location_details: Optional[str] = Field(default=None)
    equipment_available: Optional[str] = Field(default=None, description="Projector, PA System, Lab Benches")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FacilityBooking(SQLModel, table=True):
    __tablename__ = "sms_facility_bookings"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    campus_id: Optional[int] = Field(default=None, index=True)
    facility_id: int = Field(foreign_key="sms_campus_facilities.id", index=True)
    booked_by_id: int = Field(index=True, description="Learnhouse user ID")
    event_title: str
    booking_date: str = Field(description="ISO Date YYYY-MM-DD")
    start_time: str = Field(description="HH:MM (24h format)")
    end_time: str = Field(description="HH:MM (24h format)")
    status: BookingStatusEnum = Field(default=BookingStatusEnum.CONFIRMED)
    purpose: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
