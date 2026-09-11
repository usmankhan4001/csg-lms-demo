import datetime
from typing import Optional
from enum import Enum
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel


class AttendanceStatus(str, Enum):
    """Status enumeration for student attendance records."""
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    EXCUSED = "EXCUSED"


class LeaveRequestStatus(str, Enum):
    """Status enumeration for student leave requests."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class StudentAttendance(SQLModel, table=True):
    """
    Records daily roll-call attendance per student for a specific section and date.
    
    Ported from Frappe Education & RosarioSIS student attendance ledger.
    """
    __tablename__ = "sms_student_attendance"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "section_id", "date",
            name="uq_sms_student_section_date"
        ),
        Index("ix_sms_att_section_date", "section_id", "date"),
        Index("ix_sms_att_student_date", "student_id", "date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    section_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    date: datetime.date = Field(
        sa_column=Column(Date, nullable=False, index=True)
    )
    status: AttendanceStatus = Field(
        default=AttendanceStatus.PRESENT,
        sa_column=Column(
            SAEnum(AttendanceStatus, name="sms_attendance_status", native_enum=False),
            nullable=False,
            default=AttendanceStatus.PRESENT,
        ),
    )
    marked_by: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True)
    )
    remarks: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True)
    )
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class AttendanceLeaveRequest(SQLModel, table=True):
    """
    Leave requests submitted by or on behalf of students.
    """
    __tablename__ = "sms_attendance_leave_request"
    __table_args__ = (
        Index("ix_sms_leave_student_dates", "student_id", "start_date", "end_date"),
        Index("ix_sms_leave_status", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    start_date: datetime.date = Field(
        sa_column=Column(Date, nullable=False, index=True)
    )
    end_date: datetime.date = Field(
        sa_column=Column(Date, nullable=False, index=True)
    )
    reason: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True)
    )
    status: LeaveRequestStatus = Field(
        default=LeaveRequestStatus.PENDING,
        sa_column=Column(
            SAEnum(LeaveRequestStatus, name="sms_leave_request_status", native_enum=False),
            nullable=False,
            default=LeaveRequestStatus.PENDING,
        ),
    )
    approved_by: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True, index=True)
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
