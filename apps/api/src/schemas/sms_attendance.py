import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AttendanceStatus(str, Enum):
    """Attendance state for daily roll-call."""
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    EXCUSED = "EXCUSED"


class LeaveRequestStatus(str, Enum):
    """Lifecycle status for student leave requests."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RollCallStudentEntry(BaseModel):
    """A single student's roll-call attendance status."""
    student_id: int
    status: AttendanceStatus = AttendanceStatus.PRESENT
    remarks: Optional[str] = None


class BatchRollCallRequest(BaseModel):
    """Request payload for 1-click batch roll-call attendance."""
    section_id: int
    date: datetime.date
    entries: List[RollCallStudentEntry]
    marked_by: Optional[int] = None


class StudentAttendanceRead(BaseModel):
    """Schema representing an attendance record."""
    id: int
    student_id: int
    section_id: int
    date: datetime.date
    status: AttendanceStatus
    marked_by: Optional[int] = None
    remarks: Optional[str] = None
    timestamp: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class BatchRollCallResponse(BaseModel):
    """Response payload after processing a batch roll call."""
    success: bool = True
    section_id: int
    date: datetime.date
    total_submitted: int
    total_recorded: int
    records: List[StudentAttendanceRead]


class MonthlyAttendanceStats(BaseModel):
    """Summary metrics of attendance over a month."""
    total_days: int
    present_days: int
    absent_days: int
    late_days: int
    excused_days: int
    attendance_percentage: float


class MonthlyStudentAttendanceSheet(BaseModel):
    """Student monthly attendance sheet and aggregated stats."""
    student_id: int
    section_id: Optional[int] = None
    year: int
    month: int
    stats: MonthlyAttendanceStats
    daily_records: List[StudentAttendanceRead]


class LeaveRequestCreate(BaseModel):
    """Payload to create a student leave request."""
    student_id: int
    start_date: datetime.date
    end_date: datetime.date
    reason: Optional[str] = None


class LeaveRequestUpdateStatus(BaseModel):
    """Payload to approve or reject a leave request."""
    status: LeaveRequestStatus
    approved_by: Optional[int] = None


class LeaveRequestRead(BaseModel):
    """Schema representing an attendance leave request."""
    id: int
    student_id: int
    start_date: datetime.date
    end_date: datetime.date
    reason: Optional[str] = None
    status: LeaveRequestStatus
    approved_by: Optional[int] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
