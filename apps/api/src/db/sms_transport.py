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
)
from sqlmodel import Field, SQLModel


class VehicleTypeEnum(str, Enum):
    """Body/fleet class of a transport vehicle."""
    BUS = "BUS"
    MINIBUS = "MINIBUS"
    VAN = "VAN"
    COACH = "COACH"
    CAR = "CAR"
    OTHER = "OTHER"


class RouteDirectionEnum(str, Enum):
    """Which leg of the day a route runs.

    A school bus run is directional: the same road is served in the opposite
    order in the afternoon, so "the 7am bus" and "the 3pm bus" are two routes
    over the same stops rather than one route with two timetables.
    """
    PICKUP = "PICKUP"
    DROP = "DROP"
    BOTH = "BOTH"


class TransportVehicle(SQLModel, table=True):
    """
    A single vehicle in the school's transport fleet.

    Money is deliberately absent: transport is billed through the fees module
    (fee category TRANSPORT), so this table holds no currency column rather
    than repeating the Float-for-money defect the rest of the schema carries.
    """
    __tablename__ = "sms_transport_vehicle"
    __table_args__ = (
        # A plate number is only unique within one school, not globally.
        Index("ix_sms_tpt_vehicle_org_reg", "org_id", "registration_no"),
        Index("ix_sms_tpt_vehicle_org_campus", "org_id", "campus_id"),
        Index("ix_sms_tpt_vehicle_org_active", "org_id", "is_active"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    campus_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True),
        description="Null for a vehicle shared across the whole organisation.",
    )
    registration_no: str = Field(sa_column=Column(String(50), nullable=False))
    vehicle_type: VehicleTypeEnum = Field(
        default=VehicleTypeEnum.BUS,
        sa_column=Column(
            SAEnum(VehicleTypeEnum, name="sms_tpt_vehicle_type", native_enum=False),
            nullable=False,
            default=VehicleTypeEnum.BUS,
        ),
    )
    capacity: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    make: Optional[str] = Field(default=None, sa_column=Column(String(80), nullable=True))
    model: Optional[str] = Field(default=None, sa_column=Column(String(80), nullable=True))
    manufacture_year: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    # Compliance dates. Nullable and deliberately not enforced on write: a
    # vehicle can be on the road before the office has keyed in the paperwork,
    # and refusing the record would leave the fleet invisible instead of
    # flagged. They are surfaced for reporting, not used as a gate.
    insurance_expiry: Optional[datetime.date] = Field(default=None, sa_column=Column(Date, nullable=True))
    road_tax_expiry: Optional[datetime.date] = Field(default=None, sa_column=Column(Date, nullable=True))
    # Plain integer, no FK, matching BedAllocation.student_id in sms_hostel.py:
    # a driver may be recorded before they have a Learnhouse account, in which
    # case driver_name/driver_contact carry the identity instead.
    driver_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    driver_name: Optional[str] = Field(default=None, sa_column=Column(String(150), nullable=True))
    driver_contact: Optional[str] = Field(default=None, sa_column=Column(String(50), nullable=True))
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


class TransportRoute(SQLModel, table=True):
    """
    A named transport route operated by (at most) one vehicle.
    """
    __tablename__ = "sms_transport_route"
    __table_args__ = (
        Index("ix_sms_tpt_route_org_code", "org_id", "code"),
        Index("ix_sms_tpt_route_org_campus", "org_id", "campus_id"),
        Index("ix_sms_tpt_route_org_active", "org_id", "is_active"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    name: str = Field(sa_column=Column(String(150), nullable=False))
    code: str = Field(sa_column=Column(String(50), nullable=False))
    direction: RouteDirectionEnum = Field(
        default=RouteDirectionEnum.PICKUP,
        sa_column=Column(
            SAEnum(RouteDirectionEnum, name="sms_tpt_route_direction", native_enum=False),
            nullable=False,
            default=RouteDirectionEnum.PICKUP,
        ),
    )
    vehicle_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("sms_transport_vehicle.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
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


class TransportRouteStop(SQLModel, table=True):
    """
    One ordered pickup/drop point on a route.

    Pickup and drop times are stored as local wall-clock strings ("07:15"),
    not timestamps: a stop time is a standing daily schedule, and stamping it
    UTC would silently shift it for every school outside UTC.
    """
    __tablename__ = "sms_transport_route_stop"
    __table_args__ = (
        Index("ix_sms_tpt_stop_route_seq", "route_id", "sequence_no"),
        Index("ix_sms_tpt_stop_org_route", "org_id", "route_id"),
        Index("ix_sms_tpt_stop_org_campus", "org_id", "campus_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    route_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_transport_route.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    name: str = Field(sa_column=Column(String(150), nullable=False))
    sequence_no: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    pickup_time: Optional[str] = Field(default=None, sa_column=Column(String(10), nullable=True))
    drop_time: Optional[str] = Field(default=None, sa_column=Column(String(10), nullable=True))
    address: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    # Optional WGS84 decimal degrees. Nullable because most stops are recorded
    # by name long before anyone surveys them, and 0.0 is a real place (the
    # Gulf of Guinea) -- so "no coordinates" has to stay NULL, never 0.
    latitude: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    longitude: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
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


class StudentTransportAssignment(SQLModel, table=True):
    """
    Which route (and optionally which stop) a student is assigned to.

    `student_id` is a plain integer with no FK, matching
    BedAllocation.student_id in sms_hostel.py.
    """
    __tablename__ = "sms_transport_student_assignment"
    __table_args__ = (
        # Un-prefixed: the duplicate-assignment guard in the service filters on
        # student_id + is_active alone, because a student id is a global user id
        # and can only ever belong to one organisation.
        Index("ix_sms_tpt_asg_student_active", "student_id", "is_active"),
        Index("ix_sms_tpt_asg_org_campus", "org_id", "campus_id"),
        Index("ix_sms_tpt_asg_org_route_active", "org_id", "route_id", "is_active"),
        Index("ix_sms_tpt_asg_org_student_active", "org_id", "student_id", "is_active"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    student_id: int = Field(sa_column=Column(Integer, nullable=False))
    route_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_transport_route.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )
    )
    stop_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("sms_transport_route_stop.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    effective_from: datetime.date = Field(sa_column=Column(Date, nullable=False))
    effective_to: Optional[datetime.date] = Field(default=None, sa_column=Column(Date, nullable=True))
    assigned_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
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
