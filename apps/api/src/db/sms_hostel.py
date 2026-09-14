import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


class HostelGenderEnum(str, Enum):
    """Gender categorization of hostel accommodation."""
    MALE = "MALE"
    FEMALE = "FEMALE"
    COED = "COED"


class RoomTypeEnum(str, Enum):
    """Configuration type of student dorm room."""
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"
    TRIPLE = "TRIPLE"
    QUAD = "QUAD"
    DORMITORY = "DORMITORY"


class AllocationStatusEnum(str, Enum):
    """Lifecycle status of a student bed allocation."""
    ACTIVE = "ACTIVE"
    VACATED = "VACATED"
    TRANSFERRED = "TRANSFERRED"
    CANCELLED = "CANCELLED"


class InspectionStatusEnum(str, Enum):
    """Room condition and maintenance assessment grade."""
    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"
    NEEDS_REPAIR = "NEEDS_REPAIR"


class HostelBuilding(SQLModel, table=True):
    """
    Hostel residential building entity on a campus.
    """
    __tablename__ = "sms_hostel_building"
    __table_args__ = (
        Index("ix_sms_hst_campus_code", "campus_id", "building_code"),
        Index("ix_sms_hst_name", "name"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    org_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    name: str = Field(sa_column=Column(String(150), nullable=False, index=True))
    building_code: str = Field(sa_column=Column(String(50), nullable=False, index=True))
    gender: HostelGenderEnum = Field(
        default=HostelGenderEnum.COED,
        sa_column=Column(
            SAEnum(HostelGenderEnum, name="sms_hst_gender", native_enum=False),
            nullable=False,
            default=HostelGenderEnum.COED,
        ),
    )
    warden_name: Optional[str] = Field(default=None, sa_column=Column(String(150), nullable=True))
    warden_contact: Optional[str] = Field(default=None, sa_column=Column(String(50), nullable=True))
    warden_email: Optional[str] = Field(default=None, sa_column=Column(String(150), nullable=True))
    address: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    total_floors: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    total_capacity: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
            onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class DormRoom(SQLModel, table=True):
    """
    Individual dorm room within a hostel building.
    """
    __tablename__ = "sms_hostel_dorm_room"
    __table_args__ = (
        Index("ix_sms_room_building_num", "building_id", "room_number"),
        Index("ix_sms_room_type", "room_type"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    building_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_hostel_building.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    room_number: str = Field(sa_column=Column(String(50), nullable=False, index=True))
    floor_number: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    room_type: RoomTypeEnum = Field(
        default=RoomTypeEnum.DOUBLE,
        sa_column=Column(
            SAEnum(RoomTypeEnum, name="sms_hst_room_type", native_enum=False),
            nullable=False,
            default=RoomTypeEnum.DOUBLE,
        ),
    )
    capacity: int = Field(default=2, sa_column=Column(Integer, nullable=False, default=2))
    occupied_beds: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    base_fee_per_term: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    is_ac: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    has_attached_bath: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
            onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class BedAllocation(SQLModel, table=True):
    """
    Student assignment record to a specific bed in a dorm room.
    """
    __tablename__ = "sms_hostel_bed_allocation"
    __table_args__ = (
        Index("ix_sms_bed_room_id", "room_id"),
        Index("ix_sms_bed_student_id", "student_id"),
        Index("ix_sms_bed_status", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_hostel_dorm_room.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )
    )
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    bed_number: str = Field(sa_column=Column(String(50), nullable=False))
    start_date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    end_date: Optional[datetime.date] = Field(default=None, sa_column=Column(Date, nullable=True))
    status: AllocationStatusEnum = Field(
        default=AllocationStatusEnum.ACTIVE,
        sa_column=Column(
            SAEnum(AllocationStatusEnum, name="sms_hst_alloc_status", native_enum=False),
            nullable=False,
            default=AllocationStatusEnum.ACTIVE,
            index=True,
        ),
    )
    fee_charged: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    allocated_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
            onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class CurfewLog(SQLModel, table=True):
    """
    Hostel entry/exit curfew tracking log for boarding students.
    """
    __tablename__ = "sms_hostel_curfew_log"
    __table_args__ = (
        Index("ix_sms_curfew_student", "student_id"),
        Index("ix_sms_curfew_building", "building_id"),
        Index("ix_sms_curfew_date", "log_date"),
        Index("ix_sms_curfew_late", "is_late"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    building_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("sms_hostel_building.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    log_date: datetime.date = Field(sa_column=Column(Date, nullable=False, index=True))
    expected_entry_time: str = Field(default="21:00", sa_column=Column(String(20), nullable=False, default="21:00"))
    actual_entry_time: Optional[str] = Field(default=None, sa_column=Column(String(20), nullable=True))
    is_late: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False, index=True))
    is_absent: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False, index=True))
    late_minutes: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    action_taken: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    reported_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class RoomInspection(SQLModel, table=True):
    """
    Hostel room cleanliness, safety, and maintenance inspection record.
    """
    __tablename__ = "sms_hostel_room_inspection"
    __table_args__ = (
        Index("ix_sms_insp_room", "room_id"),
        Index("ix_sms_insp_date", "inspection_date"),
        Index("ix_sms_insp_status", "maintenance_status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    room_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_hostel_dorm_room.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    inspection_date: datetime.date = Field(sa_column=Column(Date, nullable=False, index=True))
    cleanliness_score: int = Field(default=5, sa_column=Column(Integer, nullable=False, default=5))
    maintenance_status: InspectionStatusEnum = Field(
        default=InspectionStatusEnum.PASSED,
        sa_column=Column(
            SAEnum(InspectionStatusEnum, name="sms_hst_insp_status", native_enum=False),
            nullable=False,
            default=InspectionStatusEnum.PASSED,
        ),
    )
    issues_found: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    action_required: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    inspected_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
