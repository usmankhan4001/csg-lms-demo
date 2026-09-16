"""
CSG-SMS Facilities: Classrooms & Rooms (Domain 1: Campuses & Classrooms).

Why this table exists at all
----------------------------
Before this, a "room" was only ever a free-text `room_number` string on
`ClassSection`, `sms_exam` and `sms_timetable` -- and none of those carried a
capacity. A timetable constraint solver cannot enforce "this section of 38
children must not be timetabled into a room that seats 24" against a string,
so room capacity had to become a first-class row.

Relationship to `sms_events_facilities.CampusFacility`
------------------------------------------------------
`CampusFacility` (table `sms_campus_facilities`) already models a bookable
venue and does carry a capacity. It is deliberately NOT reused here:

  * its `org_id` / `campus_id` are nullable, which is the tenant-column defect
    this table is required not to add to;
  * it has no `code`, and `create_all` never ALTERs an existing table, so
    adding one would need a migration this change is not allowed to write;
  * it is owned by the booking module (`FacilityBooking` FKs it), so making it
    the timetable's room entity would couple room allocation to venue booking.

`FacilityTypeEnum` there and `ClassroomType` here overlap on purpose: they
answer different questions -- "what can be reserved for an event" versus "what
can hold a class" -- and are expected to drift apart.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import Column, Enum as SAEnum, ForeignKey, Index, Integer
from sqlmodel import Field, SQLModel


def get_utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


class ClassroomType(str, Enum):
    """What a room is used for.

    The solver needs this to reject nonsense allocations (a chemistry
    practical cannot be timetabled into a library) before it ever looks at
    capacity.
    """
    CLASSROOM = "classroom"
    LAB = "lab"
    LIBRARY = "library"
    HALL = "hall"
    AUDITORIUM = "auditorium"
    SPORTS_GROUND = "sports_ground"
    OTHER = "other"


# ---------------------------------------------------------
# Classroom / Room Models
# ---------------------------------------------------------

class ClassroomBase(SQLModel):
    """Base schema for Classroom (a physical room on a campus)."""
    name: str = Field(..., max_length=255, description="Human-readable room name (e.g. 'Room 204', 'Chemistry Lab 1')")
    code: str = Field(..., max_length=50, description="Short unique room code within the org (e.g. 'A-204', 'CHEM-1')")
    room_type: ClassroomType = Field(default=ClassroomType.CLASSROOM, description="What the room is used for")
    # Required, not defaulted: a defaulted capacity would render "seats 30"
    # for a room nobody measured, and the timetable solver would happily
    # allocate 30 children into a cupboard. Absence of data is never a value.
    capacity: int = Field(..., ge=1, le=2000, description="Number of students the room can seat")
    is_active: bool = Field(default=True, description="Whether the room is available for timetabling")


class Classroom(ClassroomBase, table=True):
    """Database model for a Classroom with multi-tenant org + campus isolation.

    Both tenant columns are NOT NULL. `org_id` is the tenant boundary and
    `campus_id` the sub-boundary; a room belongs to exactly one of each, so
    neither may be left to be inferred at query time.

    NOTE on the index names: `org_id` and `campus_id` carry `index=True`, which
    SQLAlchemy auto-names `ix_classroom_org_id` / `ix_classroom_campus_id`. The
    composite indexes below are deliberately named differently. Declaring a
    custom Index whose name collides with an auto-generated one makes
    `create_all` emit CREATE INDEX twice, which has already taken this API down
    once (see the note on `ClassSection`).
    """
    __tablename__ = "sms_classroom"
    __table_args__ = (
        Index("ix_classroom_org_code", "org_id", "code", unique=True),
        Index("ix_classroom_campus_type", "campus_id", "room_type"),
        Index("ix_classroom_campus_active", "campus_id", "is_active"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    # native_enum=False, matching sms_inventory / sms_hostel: the column is a
    # VARCHAR rather than a Postgres ENUM type, so adding a room type later is
    # a Python-side change instead of an ALTER TYPE.
    room_type: ClassroomType = Field(
        default=ClassroomType.CLASSROOM,
        sa_column=Column(
            SAEnum(ClassroomType, name="sms_classroom_type", native_enum=False),
            nullable=False,
            default=ClassroomType.CLASSROOM,
        ),
    )
    org_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("organization.id", ondelete="CASCADE"),
            index=True,
            nullable=False
        )
    )
    campus_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("campus.id", ondelete="CASCADE"),
            index=True,
            nullable=False
        )
    )
    created_at: str = Field(default_factory=get_utc_now_iso)
    updated_at: str = Field(default_factory=get_utc_now_iso)


class ClassroomCreate(ClassroomBase):
    """Schema for creating a Classroom.

    `org_id` is deliberately absent: it is taken from the caller's principal,
    never from the request body. `campus_id` is required -- a room with no
    campus is a room no campus-scoped query can ever find.
    """
    campus_id: int


class ClassroomUpdate(SQLModel):
    """Schema for updating an existing Classroom."""
    name: Optional[str] = None
    code: Optional[str] = None
    room_type: Optional[ClassroomType] = None
    capacity: Optional[int] = None
    is_active: Optional[bool] = None


class ClassroomRead(ClassroomBase):
    """Schema for reading Classroom entity."""
    id: int
    org_id: int
    campus_id: int
    created_at: str
    updated_at: str
