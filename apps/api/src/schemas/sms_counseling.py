import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 1. Psychologist activity tracking
# ---------------------------------------------------------------------------

class ActivityLogCreate(BaseModel):
    student_id: int
    signal_type: str = Field(..., description="e.g. attendance_pattern, behavioral_flag, academic_concern")
    description: str
    severity: str = "low"


class ActivityLogRead(BaseModel):
    id: int
    student_id: int
    psychologist_id: str
    signal_type: str
    description: str
    severity: str
    recorded_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# 2. Structured 1:1 session logging + parent involvement
# ---------------------------------------------------------------------------

class CounselingSessionCreate(BaseModel):
    student_id: int
    session_date: datetime.datetime
    duration_minutes: int = Field(..., gt=0, le=480)
    notes: str
    follow_up_plan: Optional[str] = None
    # Parent involvement, kept narrow per spec: a boolean flag plus a
    # parent-visible summary field -- not a messaging system.
    share_summary_with_parent: bool = False
    parent_visible_summary: Optional[str] = None


class CounselingSessionUpdate(BaseModel):
    notes: Optional[str] = None
    follow_up_plan: Optional[str] = None
    share_summary_with_parent: Optional[bool] = None
    parent_visible_summary: Optional[str] = None


class CounselingSessionRead(BaseModel):
    """Full record — PSYCHOLOGIST view only (see router confidentiality rule)."""
    id: int
    student_id: int
    psychologist_id: str
    session_date: datetime.datetime
    duration_minutes: int
    notes: str
    follow_up_plan: Optional[str] = None
    share_summary_with_parent: bool
    parent_visible_summary: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ParentVisibleSessionSummary(BaseModel):
    """Restricted view for PARENT/STUDENT: no clinical notes, no follow-up plan."""
    id: int
    student_id: int
    session_date: datetime.datetime
    parent_visible_summary: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# 3. Career guidance (structured AI plan, not open chat)
# ---------------------------------------------------------------------------

class CareerGuidancePathway(BaseModel):
    pathway: str
    reasoning: str


class CareerGuidancePlanGenerated(BaseModel):
    """The strict structured LLM output — a Pydantic model, not freeform chat."""
    suggested_pathways: List[CareerGuidancePathway] = Field(default_factory=list)
    reasoning: str
    next_steps: List[str] = Field(default_factory=list)


class CareerGuidanceGenerateRequest(BaseModel):
    student_id: int
    interests: Optional[List[str]] = None
    extra_context: Optional[str] = None


class CareerGuidancePlanRead(BaseModel):
    id: int
    student_id: int
    generated_by: Optional[str] = None
    suggested_pathways: List[CareerGuidancePathway] = Field(default_factory=list)
    reasoning: str
    next_steps: List[str] = Field(default_factory=list)
    generated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
