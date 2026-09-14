"""
SMS Curricular Pathways & Course Bundles Database Models (Module M13).

Defines academic pathways (e.g. Pre-Engineering, Pre-Medical, Computer Science Track),
course prerequisite DAG requirements, and student pathway enrollment progress.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class CurricularPathway(SQLModel, table=True):
    __tablename__ = "sms_curricular_pathways"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    name: str = Field(description="e.g. Cambridge IGCSE STEM Track, FBISE Pre-Engineering")
    code: str = Field(description="e.g. STEM-01, PRE-ENG")
    description: Optional[str] = Field(default=None)
    required_credits: int = Field(default=30)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PathwayCourse(SQLModel, table=True):
    __tablename__ = "sms_pathway_courses"

    id: Optional[int] = Field(default=None, primary_key=True)
    pathway_id: int = Field(foreign_key="sms_curricular_pathways.id", index=True)
    course_id: int = Field(index=True, description="Learnhouse Course ID")
    credits: int = Field(default=3)
    is_mandatory: bool = Field(default=True)
    semester_sequence: int = Field(default=1, description="Recommended term sequence (1-8)")
    prerequisite_course_id: Optional[int] = Field(default=None, description="Learnhouse Course ID of prerequisite")


class StudentPathwayEnrollment(SQLModel, table=True):
    __tablename__ = "sms_student_pathway_enrollments"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    student_id: int = Field(index=True, description="Learnhouse user ID")
    pathway_id: int = Field(foreign_key="sms_curricular_pathways.id", index=True)
    status: str = Field(default="in_progress", description="in_progress | completed | on_hold")
    enrolled_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
