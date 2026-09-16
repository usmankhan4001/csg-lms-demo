import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from src.db.sms_transport import RouteDirectionEnum, VehicleTypeEnum


# ── Vehicle Schemas ──

class TransportVehicleCreate(BaseModel):
    campus_id: Optional[int] = Field(None, description="Campus ID")
    registration_no: str = Field(..., min_length=1, max_length=50, description="Plate / registration number")
    vehicle_type: VehicleTypeEnum = Field(default=VehicleTypeEnum.BUS)
    capacity: int = Field(default=0, ge=0, description="Seated capacity")
    make: Optional[str] = Field(None, max_length=80)
    model: Optional[str] = Field(None, max_length=80)
    manufacture_year: Optional[int] = Field(None, ge=1900, le=2100)
    insurance_expiry: Optional[datetime.date] = None
    road_tax_expiry: Optional[datetime.date] = None
    driver_user_id: Optional[int] = None
    driver_name: Optional[str] = Field(None, max_length=150)
    driver_contact: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class TransportVehicleUpdate(BaseModel):
    campus_id: Optional[int] = None
    registration_no: Optional[str] = Field(None, min_length=1, max_length=50)
    vehicle_type: Optional[VehicleTypeEnum] = None
    capacity: Optional[int] = Field(None, ge=0)
    make: Optional[str] = Field(None, max_length=80)
    model: Optional[str] = Field(None, max_length=80)
    manufacture_year: Optional[int] = Field(None, ge=1900, le=2100)
    insurance_expiry: Optional[datetime.date] = None
    road_tax_expiry: Optional[datetime.date] = None
    driver_user_id: Optional[int] = None
    driver_name: Optional[str] = Field(None, max_length=150)
    driver_contact: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class TransportVehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    campus_id: Optional[int] = None
    registration_no: str
    vehicle_type: VehicleTypeEnum
    capacity: int
    make: Optional[str] = None
    model: Optional[str] = None
    manufacture_year: Optional[int] = None
    insurance_expiry: Optional[datetime.date] = None
    road_tax_expiry: Optional[datetime.date] = None
    driver_user_id: Optional[int] = None
    driver_name: Optional[str] = None
    driver_contact: Optional[str] = None
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── Route Schemas ──

class TransportRouteCreate(BaseModel):
    campus_id: Optional[int] = Field(None, description="Campus ID")
    name: str = Field(..., min_length=1, max_length=150, description="Route name (e.g. North Loop)")
    code: str = Field(..., min_length=1, max_length=50, description="Short route code (e.g. R-NORTH)")
    direction: RouteDirectionEnum = Field(default=RouteDirectionEnum.PICKUP, description="Which leg of the day this route runs")
    vehicle_id: Optional[int] = Field(None, description="Assigned vehicle ID")
    description: Optional[str] = None


class TransportRouteUpdate(BaseModel):
    campus_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    direction: Optional[RouteDirectionEnum] = None
    vehicle_id: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class TransportRouteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    campus_id: Optional[int] = None
    name: str
    code: str
    direction: RouteDirectionEnum
    vehicle_id: Optional[int] = None
    vehicle_registration_no: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── Route Stop Schemas ──

class TransportRouteStopCreate(BaseModel):
    route_id: int = Field(..., description="Route this stop belongs to")
    name: str = Field(..., min_length=1, max_length=150, description="Stop name (e.g. Market Square)")
    sequence_no: Optional[int] = Field(None, ge=1, description="Order on the route; appended last when omitted")
    pickup_time: Optional[str] = Field(None, max_length=10, description="Local wall-clock, e.g. 07:15")
    drop_time: Optional[str] = Field(None, max_length=10, description="Local wall-clock, e.g. 15:30")
    address: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="WGS84 latitude; omit when unsurveyed")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="WGS84 longitude; omit when unsurveyed")
    notes: Optional[str] = None


class TransportRouteStopUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    sequence_no: Optional[int] = Field(None, ge=1)
    pickup_time: Optional[str] = Field(None, max_length=10)
    drop_time: Optional[str] = Field(None, max_length=10)
    address: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class TransportRouteStopRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    campus_id: Optional[int] = None
    route_id: int
    route_name: Optional[str] = None
    name: str
    sequence_no: int
    pickup_time: Optional[str] = None
    drop_time: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ── Student Assignment Schemas ──

class StudentTransportAssignmentCreate(BaseModel):
    route_id: int = Field(..., description="Route the student is assigned to")
    student_id: int = Field(..., description="Student user ID")
    stop_id: Optional[int] = Field(None, description="Boarding stop; must belong to the route")
    effective_from: datetime.date = Field(default_factory=datetime.date.today)
    effective_to: Optional[datetime.date] = None
    notes: Optional[str] = None


class StudentTransportAssignmentEnd(BaseModel):
    end_date: datetime.date = Field(default_factory=datetime.date.today)
    notes: Optional[str] = None


class StudentTransportAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    campus_id: Optional[int] = None
    student_id: int
    route_id: int
    route_name: Optional[str] = None
    stop_id: Optional[int] = None
    stop_name: Optional[str] = None
    is_active: bool
    effective_from: datetime.date
    effective_to: Optional[datetime.date] = None
    assigned_by_user_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
