"""
CSG-LMS Teacher Module — Lesson Planning & Coursework-Hour Allocation
======================================================================
Phase 4, Part A.1/A.2. An extension of the SMS teacher/gradebook surface
(shares the `sms_gradebook` admin toggle -- see
src/security/features_utils/dependencies.py -- rather than introducing a new
feature key, since this is additive teacher tooling on the same module, not
a new one).

- LessonPlan: AI-assisted, structured lesson-plan authoring output (see
  src/services/sms/teacher_tools.py, which reuses the existing provider-
  agnostic LLM layer at src.services.ai.llm — the same abstraction the
  Socratic Tutor and AI assignment generator use).
- CourseworkHourAllocation: a plain CRUD record, no AI — planned hours per
  topic/unit within a course.
"""

import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import Column, DateTime, Float, Index, Integer, JSON, String, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class LessonPlan(SQLModel, table=True):
    """A persisted, AI-generated lesson plan (objectives, activities, timing
    breakdown) produced from a teacher's prompt (subject/topic/grade/duration)."""
    __tablename__ = "sms_lesson_plan"
    __table_args__ = (
        Index("ix_sms_lesson_plan_teacher", "teacher_id"),
        Index("ix_sms_lesson_plan_course", "course_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    # Keycloak `sub` of the authoring TEACHER (string identity, matching the
    # principal -- see src/core/keycloak_auth.py).
    teacher_id: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True, index=True))
    course_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    subject: str = Field(sa_column=Column(String(150), nullable=False))
    topic: str = Field(sa_column=Column(String(255), nullable=False))
    grade_level: str = Field(sa_column=Column(String(50), nullable=False))
    duration_minutes: int = Field(sa_column=Column(Integer, nullable=False))
    objectives: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    activities: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    timing_breakdown: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    materials: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    assessment_ideas: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )


class CourseworkHourAllocation(SQLModel, table=True):
    """Planned-hours allocation per topic/unit within a course. Straightforward
    CRUD, no AI involved."""
    __tablename__ = "sms_coursework_hour_allocation"
    __table_args__ = (
        Index("ix_sms_coursework_hours_course", "course_id"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    unit_name: str = Field(sa_column=Column(String(255), nullable=False))
    planned_hours: float = Field(sa_column=Column(Float, nullable=False))
    order_index: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, default=_utcnow),
    )
