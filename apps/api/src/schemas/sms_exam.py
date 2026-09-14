"""Request/response schemas for the school examination module (M04)."""

import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from src.db.sms_exam import ExamAttendanceStatus, ExamStatus


class ExamCreate(BaseModel):
    campus_id: int
    academic_term_id: int
    course_id: int
    title: str = Field(..., max_length=200)
    exam_type: Optional[str] = Field(default=None, max_length=50)
    exam_date: datetime.date
    start_time: Optional[str] = Field(default=None, max_length=5, description="HH:MM")
    duration_minutes: int = Field(default=60, ge=1, le=1440)
    total_marks: float = Field(default=100.0, gt=0)
    pass_marks: float = Field(default=40.0, ge=0)
    assessment_plan_id: Optional[int] = None
    instructions: Optional[str] = None


class ExamUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    exam_type: Optional[str] = Field(default=None, max_length=50)
    exam_date: Optional[datetime.date] = None
    start_time: Optional[str] = Field(default=None, max_length=5)
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    total_marks: Optional[float] = Field(default=None, gt=0)
    pass_marks: Optional[float] = Field(default=None, ge=0)
    assessment_plan_id: Optional[int] = None
    status: Optional[ExamStatus] = None
    instructions: Optional[str] = None


class ExamRead(BaseModel):
    id: int
    campus_id: int
    academic_term_id: int
    course_id: int
    title: str
    exam_type: Optional[str] = None
    exam_date: datetime.date
    start_time: Optional[str] = None
    duration_minutes: int
    total_marks: float
    pass_marks: float
    assessment_plan_id: Optional[int] = None
    status: ExamStatus
    instructions: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime.datetime


class ExamSectionScheduleCreate(BaseModel):
    section_id: int
    room_number: Optional[str] = Field(default=None, max_length=50)
    invigilator_id: Optional[int] = None


class ExamSectionScheduleRead(BaseModel):
    id: int
    exam_id: int
    section_id: int
    room_number: Optional[str] = None
    invigilator_id: Optional[int] = None
    actual_start_at: Optional[datetime.datetime] = None
    actual_end_at: Optional[datetime.datetime] = None


class ExamSittingUpdate(BaseModel):
    """Invigilator recording when the room actually started/finished."""
    actual_start_at: Optional[datetime.datetime] = None
    actual_end_at: Optional[datetime.datetime] = None


class ExamResultEntry(BaseModel):
    student_id: int
    # None is a legitimate, meaningful value: not yet marked, or did not sit.
    # It is never coerced to 0.0 anywhere downstream.
    marks_obtained: Optional[float] = Field(default=None, ge=0)
    attendance_status: ExamAttendanceStatus = ExamAttendanceStatus.PRESENT
    remarks: Optional[str] = None


class BatchExamResultRequest(BaseModel):
    entries: List[ExamResultEntry]


class ExamResultRead(BaseModel):
    id: int
    exam_id: int
    student_id: int
    marks_obtained: Optional[float] = None
    attendance_status: ExamAttendanceStatus
    percentage: Optional[float] = None
    passed: Optional[bool] = None
    remarks: Optional[str] = None
    marked_by: Optional[int] = None
    marked_at: Optional[datetime.datetime] = None
    posted_to_gradebook_at: Optional[datetime.datetime] = None


class ExamResultSummary(BaseModel):
    """Cohort statistics. Every figure is computed only from students who
    actually have a mark -- `not_yet_marked` and `absent` are reported
    separately rather than being folded in as zeros, which would understate
    the cohort and misrepresent individuals."""
    exam_id: int
    total_students: int
    marked: int
    not_yet_marked: int
    absent: int
    # None when nobody has been marked yet -- there is no average of nothing.
    average_marks: Optional[float] = None
    highest_marks: Optional[float] = None
    lowest_marks: Optional[float] = None
    pass_count: int = 0
    fail_count: int = 0


class PostResultsResponse(BaseModel):
    exam_id: int
    entries_written: int
    entries_skipped: int
    already_posted: bool
    assessment_plan_id: int
    message: str


class ExamIncidentCreate(BaseModel):
    section_id: Optional[int] = None
    student_id: Optional[int] = None
    severity: str = Field(default="INFO", max_length=20)
    description: str


class ExamIncidentRead(BaseModel):
    id: int
    exam_id: int
    section_id: Optional[int] = None
    student_id: Optional[int] = None
    severity: str
    description: str
    reported_by: Optional[int] = None
    reported_at: datetime.datetime


class HintUsageRead(BaseModel):
    student_id: int
    assignment_ref: str
    hints_used: int
    max_hint_level: int
    deduction_percentage: float
    deduction_applied_at: Optional[datetime.datetime] = None
