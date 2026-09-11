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


class ContractType(str, Enum):
    """Staff contract classification."""
    PERMANENT = "PERMANENT"
    PROBATION = "PROBATION"
    CONTRACT = "CONTRACT"
    PART_TIME = "PART_TIME"
    VISITING = "VISITING"


class LeaveType(str, Enum):
    """Staff leave category."""
    ANNUAL = "ANNUAL"
    SICK = "SICK"
    CASUAL = "CASUAL"
    MATERNITY = "MATERNITY"
    UNPAID = "UNPAID"


class LeaveStatus(str, Enum):
    """Staff leave lifecycle status."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class StaffProfile(SQLModel, table=True):
    """
    Staff Profile and Faculty Directory Model.
    """
    __tablename__ = "sms_staff_profile"
    __table_args__ = (
        UniqueConstraint("employee_code", name="uq_sms_staff_employee_code"),
        Index("ix_sms_staff_campus_dept", "campus_id", "department"),
        Index("ix_sms_staff_user", "user_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    employee_code: str = Field(sa_column=Column(String(50), nullable=False, unique=True, index=True))
    full_name: str = Field(sa_column=Column(String(150), nullable=False))
    designation: str = Field(sa_column=Column(String(100), nullable=False))
    department: str = Field(sa_column=Column(String(100), nullable=False, index=True))
    joining_date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    contract_type: ContractType = Field(
        default=ContractType.PERMANENT,
        sa_column=Column(
            SAEnum(ContractType, name="sms_staff_contract_type", native_enum=False),
            nullable=False,
            default=ContractType.PERMANENT,
        ),
    )
    basic_salary: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    email: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    phone: Optional[str] = Field(default=None, sa_column=Column(String(50), nullable=True))
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class StaffLeave(SQLModel, table=True):
    """
    Staff Leave Application & Ledger Record.
    """
    __tablename__ = "sms_staff_leave"
    __table_args__ = (
        Index("ix_sms_leave_staff_status", "staff_id", "status"),
        Index("ix_sms_leave_dates", "start_date", "end_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    staff_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_staff_profile.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    leave_type: LeaveType = Field(
        sa_column=Column(
            SAEnum(LeaveType, name="sms_staff_leave_type", native_enum=False),
            nullable=False,
        )
    )
    start_date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    end_date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    status: LeaveStatus = Field(
        default=LeaveStatus.PENDING,
        sa_column=Column(
            SAEnum(LeaveStatus, name="sms_staff_leave_status", native_enum=False),
            nullable=False,
            default=LeaveStatus.PENDING,
        ),
    )
    approved_by: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
