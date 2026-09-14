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
    """Request payload for 1-click batch roll-call attendance.

    `period_id` omitted (or null) records a WHOLE-DAY register, which is how a
    primary school works and how this endpoint has always behaved. Supplying
    it records that one period only, so a secondary school can take six
    registers a day without each overwriting the last.
    """
    section_id: int
    date: datetime.date
    entries: List[RollCallStudentEntry]
    marked_by: Optional[int] = None
    period_id: Optional[int] = None
    # Why this register was changed. Optional, and deliberately not required:
    # making it mandatory would tempt a teacher into typing "." to get past the
    # field, which is worse than an honest blank.
    reason: Optional[str] = None


class StudentAttendanceRead(BaseModel):
    """Schema representing an attendance record.

    `period_id` is null for a whole-day register.
    """
    id: int
    student_id: int
    section_id: int
    date: datetime.date
    period_id: Optional[int] = None
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
    period_id: Optional[int] = None
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
    # Optional: None means no roll-call has been taken in the period, which is
    # a different fact from 0% attendance and must stay distinguishable.
    attendance_percentage: Optional[float]


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


# ── Attendance correction history ──


class AttendanceChangeAction(str, Enum):
    """First marking vs a later correction."""

    MARKED = "marked"
    CORRECTED = "corrected"


class AttendanceChangeEventRead(BaseModel):
    """One entry in the append-only attendance trail."""

    id: int
    attendance_id: int
    student_id: int
    section_id: int
    date: datetime.date
    period_id: Optional[int] = None
    action: AttendanceChangeAction
    # None on MARKED: there was no previous status. Distinct from PRESENT.
    previous_status: Optional[AttendanceStatus] = None
    new_status: AttendanceStatus
    changed_by_user_id: Optional[int] = None
    reason: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ── Absence excuses ──


class ExcuseStatus(str, Enum):
    """Lifecycle of a parent's absence note."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AbsenceExcuseCreate(BaseModel):
    """A note explaining an absence that already happened."""

    student_id: int
    section_id: int
    date: datetime.date
    reason: str = Field(min_length=1)


class AbsenceExcuseReview(BaseModel):
    """Approve or reject a note. APPROVED converts that day's ABSENT records."""

    status: ExcuseStatus
    review_note: Optional[str] = None


class AbsenceExcuseRead(BaseModel):
    id: int
    student_id: int
    section_id: int
    date: datetime.date
    reason: str
    submitted_by_user_id: Optional[int] = None
    status: ExcuseStatus
    reviewed_by_user_id: Optional[int] = None
    review_note: Optional[str] = None
    reviewed_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class AbsenceExcuseReviewResponse(BaseModel):
    """The reviewed note, plus how many registers it actually changed.

    `records_converted` is reported rather than assumed: 0 is a legitimate
    outcome (the register may not have been taken, or the child was marked
    present), and a reviewer who approved a note deserves to know it changed
    nothing rather than believing it did.
    """

    excuse: AbsenceExcuseRead
    records_converted: int


# ── Pastoral concerns ──


class PastoralConcernStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"


class PastoralConcernRead(BaseModel):
    id: int
    student_id: int
    section_id: int
    trigger: str
    detail: Optional[str] = None
    # None where the trigger has no natural magnitude -- never 0, which would
    # read as "a streak of zero".
    magnitude: Optional[int] = None
    status: PastoralConcernStatus
    resolved_by_user_id: Optional[int] = None
    resolution_note: Optional[str] = None
    resolved_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class PastoralConcernUpdate(BaseModel):
    status: PastoralConcernStatus
    resolution_note: Optional[str] = None


class PastoralInterventionCreate(BaseModel):
    action: str = Field(min_length=1, max_length=64)
    note: Optional[str] = None
    outcome: Optional[str] = None


class PastoralInterventionRead(BaseModel):
    id: int
    concern_id: int
    action: str
    note: Optional[str] = None
    outcome: Optional[str] = None
    acted_by_user_id: Optional[int] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ── Bulk marking ──


class BulkMarkRangeRequest(BaseModel):
    """Mark a whole section across a date range -- a trip, a closure.

    `overwrite_existing` defaults to False so a bulk action can never silently
    rewrite registers a teacher already took. With it False, dates that already
    hold a differing record are REPORTED as skipped rather than changed, and
    the caller decides.
    """

    section_id: int
    start_date: datetime.date
    end_date: datetime.date
    status: AttendanceStatus
    student_ids: Optional[List[int]] = None
    reason: Optional[str] = None
    overwrite_existing: bool = False


class BulkMarkSkipped(BaseModel):
    """A record left alone, and why -- never silently dropped."""

    student_id: int
    date: datetime.date
    existing_status: AttendanceStatus


class BulkMarkRangeResponse(BaseModel):
    section_id: int
    start_date: datetime.date
    end_date: datetime.date
    dates_covered: int
    records_created: int
    records_updated: int
    skipped: List[BulkMarkSkipped]
