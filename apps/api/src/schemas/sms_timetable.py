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


# ── Teacher Substitution ──

class TimetableSubstitutionCreate(BaseModel):
    """Assign a substitute to one recurring slot on one specific date."""
    schedule_id: int
    substitution_date: str = Field(description="ISO date 'YYYY-MM-DD' the substitute covers")
    substitute_teacher_id: int
    reason: Optional[str] = None


class TimetableSubstitutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_id: int
    substitution_date: str
    original_teacher_id: int
    substitute_teacher_id: int
    reason: Optional[str] = None
    created_by: Optional[int] = None
    is_active: bool


# ── Lesson Log Schemas ──

class LessonLogCreate(BaseModel):
    """Recording what was actually taught. `taught_by_user_id` is deliberately
    absent: it is taken from the authenticated caller, never the payload, so a
    lesson cannot be attributed to a colleague who was not there."""
    schedule_id: int
    lesson_date: str = Field(..., description="ISO date 'YYYY-MM-DD'")
    topic_covered: str = Field(..., min_length=1, description="What was actually covered")
    homework_set: Optional[str] = None
    notes_for_next_teacher: Optional[str] = None
    lesson_plan_id: Optional[int] = Field(
        default=None,
        description="Optional link to the sms_lesson_plan this lesson followed",
    )


class LessonLogRead(BaseModel):
    id: int
    schedule_id: int
    section_id: int
    lesson_date: str
    taught_by_user_id: Optional[int] = None
    topic_covered: str
    homework_set: Optional[str] = None
    notes_for_next_teacher: Optional[str] = None
    lesson_plan_id: Optional[int] = None
    recorded_by_user_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# ── Conflict Scan Schemas ──

class TimetableConflictScanResponse(BaseModel):
    """Existing conflicts across a timetable, as opposed to `ClashCheckResponse`
    which answers "would this ONE proposed slot conflict?"."""
    scanned_slots: int
    conflicts: List[ClashDetail]
    message: str


# ── Assisted Generation Schemas ──

class GenerationRequirement(BaseModel):
    """One course that needs N periods a week for this section."""
    course_id: int
    teacher_id: int
    periods_per_week: int = Field(..., ge=1, le=40)
    room_number: Optional[str] = None
    preferred_days: Optional[List[DayOfWeek]] = Field(
        default=None,
        description="Restrict placement to these days. Omit for any teaching day.",
    )


class GenerationRequest(BaseModel):
    section_id: int
    academic_term_id: Optional[int] = None
    requirements: List[GenerationRequirement] = Field(..., min_length=1)
    days: Optional[List[DayOfWeek]] = Field(
        default=None,
        description="The section's teaching days. Defaults to Monday-Friday.",
    )
    period_ids: Optional[List[int]] = Field(
        default=None,
        description="Restrict to these periods. Defaults to every period on the campus.",
    )
    dry_run: bool = Field(
        default=True,
        description="Preview only. Nothing is written unless this is explicitly false.",
    )


class PlacedSlot(BaseModel):
    course_id: int
    teacher_id: int
    day_of_week: str
    period_id: int
    room_number: Optional[str] = None
    schedule_id: Optional[int] = Field(
        default=None,
        description="Null on a dry run -- nothing was written.",
    )


class UnplacedSlot(BaseModel):
    """A period this generator could NOT place, and why.

    Never silently dropped and never placed somewhere arbitrary to make the
    numbers add up: a timetable that looks complete but puts a teacher in two
    rooms is worse than one that says plainly it could not finish.
    """
    course_id: int
    teacher_id: int
    occurrence: int = Field(..., description="Which of the N weekly periods this was")
    reason: str


class GenerationResponse(BaseModel):
    section_id: int
    academic_term_id: Optional[int] = None
    dry_run: bool
    requested_periods: int
    placed: List[PlacedSlot]
    unplaced: List[UnplacedSlot]
    message: str
