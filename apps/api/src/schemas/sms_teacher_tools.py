import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Lesson-plan authoring (AI-assisted, structured output)
# ---------------------------------------------------------------------------

class LessonPlanActivity(BaseModel):
    name: str
    duration_minutes: int = Field(..., ge=0)
    description: str


class LessonPlanTimingBlock(BaseModel):
    label: str
    minutes: int = Field(..., ge=0)


class GeneratedLessonPlan(BaseModel):
    """The strict structured output the LLM must produce (a Pydantic model,
    not freeform chat) -- see src/services/sms/teacher_tools.py."""
    subject: str
    topic: str
    grade_level: str
    duration_minutes: int
    objectives: List[str] = Field(default_factory=list)
    activities: List[LessonPlanActivity] = Field(default_factory=list)
    timing_breakdown: List[LessonPlanTimingBlock] = Field(default_factory=list)
    materials: List[str] = Field(default_factory=list)
    assessment_ideas: List[str] = Field(default_factory=list)


class LessonPlanGenerateRequest(BaseModel):
    subject: str
    topic: str
    grade_level: str
    duration_minutes: int = Field(..., gt=0, le=480)
    course_id: Optional[int] = None
    extra_instructions: Optional[str] = None


class LessonPlanRead(BaseModel):
    id: int
    teacher_id: Optional[str] = None
    course_id: Optional[int] = None
    subject: str
    topic: str
    grade_level: str
    duration_minutes: int
    objectives: List[str] = Field(default_factory=list)
    activities: List[LessonPlanActivity] = Field(default_factory=list)
    timing_breakdown: List[LessonPlanTimingBlock] = Field(default_factory=list)
    materials: List[str] = Field(default_factory=list)
    assessment_ideas: List[str] = Field(default_factory=list)
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Coursework-hour allocation (plain CRUD, no AI)
# ---------------------------------------------------------------------------

class CourseworkHourAllocationCreate(BaseModel):
    course_id: int
    unit_name: str
    planned_hours: float = Field(..., gt=0)
    order_index: int = 0
    notes: Optional[str] = None


class CourseworkHourAllocationUpdate(BaseModel):
    unit_name: Optional[str] = None
    planned_hours: Optional[float] = Field(default=None, gt=0)
    order_index: Optional[int] = None
    notes: Optional[str] = None


class CourseworkHourAllocationRead(BaseModel):
    id: int
    course_id: int
    unit_name: str
    planned_hours: float
    order_index: int
    notes: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
