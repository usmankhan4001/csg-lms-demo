import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class GradeInterval(BaseModel):
    grade: str
    min_percentage: float
    max_percentage: float
    gpa_point: float


class GradingScaleBase(BaseModel):
    name: str
    description: Optional[str] = None
    intervals: List[GradeInterval] = Field(default_factory=list)
    is_default: bool = False


class GradingScaleCreate(GradingScaleBase):
    pass


class GradingScaleRead(GradingScaleBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class AssessmentPlanBase(BaseModel):
    course_id: int
    section_id: Optional[int] = None
    academic_term_id: Optional[int] = None
    assessment_name: str
    weight_percentage: float = Field(..., ge=0.0, le=100.0)
    max_score: float = Field(default=100.0, gt=0.0)


class AssessmentPlanCreate(AssessmentPlanBase):
    pass


class AssessmentPlanRead(AssessmentPlanBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class GradebookEntryInput(BaseModel):
    student_id: int
    raw_score: float = Field(..., ge=0.0)
    remarks: Optional[str] = None


class BatchGradebookEntryRequest(BaseModel):
    assessment_plan_id: int
    entries: List[GradebookEntryInput]
    graded_by: Optional[int] = None


class GradebookEntryRead(BaseModel):
    id: int
    student_id: int
    assessment_plan_id: int
    raw_score: float
    max_score: float
    weighted_score: Optional[float] = None
    letter_grade: Optional[str] = None
    gpa_point: Optional[float] = None
    remarks: Optional[str] = None
    graded_by: Optional[int] = None
    graded_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class CourseGradeSummary(BaseModel):
    course_id: int
    course_name: Optional[str] = None
    credits: float = 3.0
    total_raw_percentage: float
    total_weighted_percentage: float
    letter_grade: str
    gpa_point: float
    assessment_breakdown: List[Dict[str, Any]] = Field(default_factory=list)


class StudentTermReportCardResponse(BaseModel):
    student_id: int
    section_id: int
    academic_term_id: int
    total_credits: float
    cumulative_gpa: float
    overall_letter_grade: str
    remarks: Optional[str] = None
    courses: List[CourseGradeSummary]
    generated_at: datetime.datetime
