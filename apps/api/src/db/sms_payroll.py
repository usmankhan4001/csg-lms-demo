import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import (
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


class SalaryPaymentStatus(str, Enum):
    """Payment status for staff salary slips."""
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class SalaryStructure(SQLModel, table=True):
    """
    Recurring salary structure definition per staff member.
    """
    __tablename__ = "sms_salary_structure"
    __table_args__ = (
        UniqueConstraint("staff_id", name="uq_sms_salary_structure_staff"),
        Index("ix_sms_salary_struct_staff", "staff_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    staff_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_staff_profile.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        )
    )
    basic: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    housing_allowance: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    medical_allowance: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    other_allowances: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    tax_deduction: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    provident_fund: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    other_deductions: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    gross_salary: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    total_deductions: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    net_salary: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
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
        ),
    )


class SalarySlip(SQLModel, table=True):
    """
    Issued monthly salary slip ledger for faculty & staff.
    """
    __tablename__ = "sms_salary_slip"
    __table_args__ = (
        UniqueConstraint("slip_no", name="uq_sms_salary_slip_no"),
        Index("ix_sms_slip_staff_period", "staff_id", "month", "year"),
        Index("ix_sms_slip_status", "payment_status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    slip_no: str = Field(sa_column=Column(String(50), nullable=False, unique=True, index=True))
    staff_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_staff_profile.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    month: int = Field(sa_column=Column(Integer, nullable=False))
    year: int = Field(sa_column=Column(Integer, nullable=False))
    basic: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    housing_allowance: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    medical_allowance: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    other_allowances: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    tax_deduction: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    provident_fund: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    other_deductions: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    gross_salary: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    total_deductions: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    net_salary: float = Field(default=0.0, sa_column=Column(Float, nullable=False, default=0.0))
    payment_status: SalaryPaymentStatus = Field(
        default=SalaryPaymentStatus.PENDING,
        sa_column=Column(
            SAEnum(SalaryPaymentStatus, name="sms_salary_payment_status", native_enum=False),
            nullable=False,
            default=SalaryPaymentStatus.PENDING,
        ),
    )
    payment_date: Optional[datetime.date] = Field(default=None, sa_column=Column(Date, nullable=True))
    payment_method: Optional[str] = Field(default=None, sa_column=Column(String(50), nullable=True))
    remarks: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
