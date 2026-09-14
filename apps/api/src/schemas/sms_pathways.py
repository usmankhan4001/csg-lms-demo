from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class PathwayCourseCreate(BaseModel):
    course_id: int
    credits: int = 3
    is_mandatory: bool = True
    semester_sequence: int = 1
    prerequisite_course_id: Optional[int] = None


class PathwayCourseRead(BaseModel):
    id: int
    pathway_id: int
    course_id: int
    credits: int
    is_mandatory: bool
    semester_sequence: int
    prerequisite_course_id: Optional[int]


class CurricularPathwayCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    required_credits: int = 30
    courses: List[PathwayCourseCreate] = []


class CurricularPathwayRead(BaseModel):
    id: int
    org_id: Optional[int]
    name: str
    code: str
    description: Optional[str]
    required_credits: int
    is_active: bool
    created_at: datetime
    courses: List[PathwayCourseRead] = []


class EnrollPathwayPayload(BaseModel):
    student_id: int
    pathway_id: int


class StudentPathwayProgressRead(BaseModel):
    id: int
    org_id: Optional[int]
    student_id: int
    pathway_id: int
    pathway_name: str
    status: str
    total_required_credits: int
    earned_credits: int
    progress_percentage: float
    enrolled_at: datetime
