from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DayOfWeek(str, Enum):
    """Day of week enumeration for timetable slots."""
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class ClashType(str, Enum):
    """Types of timetable scheduling conflicts."""
    TEACHER_DOUBLE_BOOKED = "TEACHER_DOUBLE_BOOKED"
    ROOM_DOUBLE_BOOKED = "ROOM_DOUBLE_BOOKED"
    SECTION_DOUBLE_BOOKED = "SECTION_DOUBLE_BOOKED"


# ── Class Period Schemas ──

class ClassPeriodBase(BaseModel):
    campus_id: Optional[int] = None
    period_number: int
    start_time: str = Field(..., description="Start time (e.g. '08:30')")
    end_time: str = Field(..., description="End time (e.g. '09:15')")
    name: Optional[str] = None


class ClassPeriodCreate(ClassPeriodBase):
    pass


class ClassPeriodUpdate(BaseModel):
    campus_id: Optional[int] = None
    period_number: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    name: Optional[str] = None


class ClassPeriodRead(ClassPeriodBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ── Timetable Schedule Schemas ──

class TimetableScheduleBase(BaseModel):
    section_id: int
    course_id: int
    teacher_id: int
    day_of_week: DayOfWeek | str
    period_id: int
    room_number: Optional[str] = None
    academic_term_id: Optional[int] = None


class TimetableScheduleCreate(TimetableScheduleBase):
    pass


class TimetableScheduleUpdate(BaseModel):
    section_id: Optional[int] = None
    course_id: Optional[int] = None
    teacher_id: Optional[int] = None
    day_of_week: Optional[DayOfWeek | str] = None
    period_id: Optional[int] = None
    room_number: Optional[str] = None
    academic_term_id: Optional[int] = None


class TimetableScheduleRead(TimetableScheduleBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class TimetableSlotDetail(BaseModel):
    """Detailed slot in a timetable including period timing."""
    id: int
    section_id: int
    course_id: int
    teacher_id: int
    day_of_week: str
    period_id: int
    period_number: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room_number: Optional[str] = None
    academic_term_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ── Conflict Detection Schemas ──

class ClashDetail(BaseModel):
    """Detailed information about a timetable schedule clash."""
    clash_type: ClashType
    description: str
    conflicting_schedule_id: int
    day_of_week: str
    period_id: int
    academic_term_id: Optional[int] = None
    teacher_id: Optional[int] = None
    room_number: Optional[str] = None
    section_id: Optional[int] = None


class ClashCheckRequest(BaseModel):
    """Request payload to test prospective timetable slots for clashes."""
    section_id: int
    course_id: int
    teacher_id: int
    day_of_week: DayOfWeek | str
    period_id: int
    room_number: Optional[str] = None
    academic_term_id: Optional[int] = None
    exclude_schedule_id: Optional[int] = Field(
        default=None,
        description="Schedule ID to ignore when checking updates to existing slot",
    )


class ClashCheckResponse(BaseModel):
    """Response containing clash results."""
    has_clash: bool
    clashes: List[ClashDetail]
    message: str


# ── Timetable Views ──

class StudentTimetableResponse(BaseModel):
    student_id: Optional[int] = None
    section_id: Optional[int] = None
    academic_term_id: Optional[int] = None
    slots: List[TimetableSlotDetail]


class TeacherTimetableResponse(BaseModel):
    teacher_id: int
    academic_term_id: Optional[int] = None
    slots: List[TimetableSlotDetail]
