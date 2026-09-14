import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from src.db.sms_hostel import (
    AllocationStatusEnum,
    HostelGenderEnum,
    InspectionStatusEnum,
    RoomTypeEnum,
)


# ── Hostel Building Schemas ──

class HostelBuildingCreate(BaseModel):
    campus_id: Optional[int] = Field(None, description="Campus ID")
    org_id: Optional[int] = Field(None, description="Organization ID")
    name: str = Field(..., min_length=1, max_length=150, description="Building name (e.g. West Wing)")
    building_code: str = Field(..., min_length=1, max_length=50, description="Unique building code")
    gender: HostelGenderEnum = Field(default=HostelGenderEnum.COED, description="MALE, FEMALE, COED")
    warden_name: Optional[str] = Field(None, max_length=150)
    warden_contact: Optional[str] = Field(None, max_length=50)
    warden_email: Optional[str] = Field(None, max_length=150)
    address: Optional[str] = None
    total_floors: int = Field(default=1, ge=1)
    total_capacity: int = Field(default=0, ge=0)


class HostelBuildingUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    building_code: Optional[str] = Field(None, min_length=1, max_length=50)
    gender: Optional[HostelGenderEnum] = None
    warden_name: Optional[str] = None
    warden_contact: Optional[str] = None
    warden_email: Optional[str] = None
    address: Optional[str] = None
    total_floors: Optional[int] = Field(None, ge=1)
    total_capacity: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class HostelBuildingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    org_id: Optional[int] = None
    name: str
    building_code: str
    gender: HostelGenderEnum
    warden_name: Optional[str] = None
    warden_contact: Optional[str] = None
    warden_email: Optional[str] = None
    address: Optional[str] = None
    total_floors: int
    total_capacity: int
    total_rooms: int = 0
    occupied_beds: int = 0
    available_beds: int = 0
    occupancy_rate: float = 0.0
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── Dorm Room Schemas ──

class DormRoomCreate(BaseModel):
    building_id: int = Field(..., description="Hostel building ID")
    room_number: str = Field(..., min_length=1, max_length=50, description="Room number / label")
    floor_number: int = Field(default=1, ge=0)
    room_type: RoomTypeEnum = Field(default=RoomTypeEnum.DOUBLE)
    capacity: int = Field(default=2, ge=1, description="Bed capacity")
    base_fee_per_term: float = Field(default=0.0, ge=0.0)
    is_ac: bool = Field(default=False)
    has_attached_bath: bool = Field(default=False)
    notes: Optional[str] = None


class DormRoomUpdate(BaseModel):
    room_number: Optional[str] = Field(None, min_length=1, max_length=50)
    floor_number: Optional[int] = Field(None, ge=0)
    room_type: Optional[RoomTypeEnum] = None
    capacity: Optional[int] = Field(None, ge=1)
    base_fee_per_term: Optional[float] = Field(None, ge=0.0)
    is_ac: Optional[bool] = None
    has_attached_bath: Optional[bool] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class DormRoomRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    building_id: int
    building_name: Optional[str] = None
    room_number: str
    floor_number: int
    room_type: RoomTypeEnum
    capacity: int
    occupied_beds: int
    available_beds: int = 0
    base_fee_per_term: float
    is_ac: bool
    has_attached_bath: bool
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── Bed Allocation Schemas ──

class BedAllocationCreate(BaseModel):
    room_id: int = Field(..., description="Room ID to allocate")
    student_id: int = Field(..., description="Student user ID")
    bed_number: str = Field(..., min_length=1, max_length=50, description="e.g. Bed-1, B1")
    start_date: datetime.date = Field(default_factory=datetime.date.today)
    end_date: Optional[datetime.date] = None
    fee_charged: float = Field(default=0.0, ge=0.0)
    notes: Optional[str] = None


class BedAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    room_number: Optional[str] = None
    building_id: Optional[int] = None
    building_name: Optional[str] = None
    student_id: int
    student_name: Optional[str] = None
    bed_number: str
    start_date: datetime.date
    end_date: Optional[datetime.date] = None
    status: AllocationStatusEnum
    fee_charged: float
    allocated_by_user_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class BedTransferRequest(BaseModel):
    new_room_id: int = Field(..., description="Destination room ID")
    new_bed_number: str = Field(..., min_length=1, max_length=50, description="Destination bed number")
    effective_date: datetime.date = Field(default_factory=datetime.date.today)
    notes: Optional[str] = None


class BedVacateRequest(BaseModel):
    vacate_date: datetime.date = Field(default_factory=datetime.date.today)
    notes: Optional[str] = None


# ── Curfew Log Schemas ──

class CurfewLogCreate(BaseModel):
    student_id: int = Field(..., description="Student ID")
    building_id: Optional[int] = Field(None, description="Hostel building ID")
    log_date: datetime.date = Field(default_factory=datetime.date.today)
    expected_entry_time: str = Field(default="21:00", max_length=20)
    actual_entry_time: Optional[str] = Field(None, max_length=20)
    is_late: bool = Field(default=False)
    is_absent: bool = Field(default=False)
    late_minutes: int = Field(default=0, ge=0)
    reason: Optional[str] = None
    action_taken: Optional[str] = None


class CurfewLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    student_name: Optional[str] = None
    building_id: Optional[int] = None
    building_name: Optional[str] = None
    log_date: datetime.date
    expected_entry_time: str
    actual_entry_time: Optional[str] = None
    is_late: bool
    is_absent: bool
    late_minutes: int
    reason: Optional[str] = None
    action_taken: Optional[str] = None
    reported_by_user_id: Optional[int] = None
    created_at: datetime.datetime


# ── Room Inspection Schemas ──

class RoomInspectionCreate(BaseModel):
    room_id: int = Field(..., description="Room ID inspected")
    inspection_date: datetime.date = Field(default_factory=datetime.date.today)
    cleanliness_score: int = Field(default=5, ge=1, le=10, description="Cleanliness score (1-10)")
    maintenance_status: InspectionStatusEnum = Field(default=InspectionStatusEnum.PASSED)
    issues_found: Optional[str] = None
    action_required: Optional[str] = None


class RoomInspectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    room_number: Optional[str] = None
    building_id: Optional[int] = None
    building_name: Optional[str] = None
    inspection_date: datetime.date
    cleanliness_score: int
    maintenance_status: InspectionStatusEnum
    issues_found: Optional[str] = None
    action_required: Optional[str] = None
    inspected_by_user_id: Optional[int] = None
    created_at: datetime.datetime


# ── Overview & Analytics Schemas ──

class BuildingOccupancyRead(BaseModel):
    building_id: int
    building_name: str
    building_code: str
    gender: HostelGenderEnum
    total_rooms: int
    total_capacity: int
    occupied_beds: int
    available_beds: int
    occupancy_rate: float


class HostelOverviewRead(BaseModel):
    total_buildings: int
    total_rooms: int
    total_capacity: int
    total_occupied_beds: int
    total_available_beds: int
    overall_occupancy_rate: float
    late_curfew_incidents_30d: int
    pending_repairs_count: int
    buildings: List[BuildingOccupancyRead] = []
