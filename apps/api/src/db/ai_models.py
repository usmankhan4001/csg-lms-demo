"""
AI Safety & Pedagogical Guardrail Models
=======================================
Stores AI Safety Incidents, Crisis Flags, and Student Wellbeing Alerts (M42, M47).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import Column, Index, Integer, Text, String, Boolean
from sqlmodel import Field, SQLModel


class AISafetySeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AISafetyCategory(str, Enum):
    SELF_HARM = "SELF_HARM"
    CRISIS = "CRISIS"
    SEVERE_DISTRESS = "SEVERE_DISTRESS"
    BULLYING = "BULLYING"
    VIOLENCE = "VIOLENCE"
    CHEATING = "CHEATING"
    INAPPROPRIATE_CONTENT = "INAPPROPRIATE_CONTENT"
    OTHER = "OTHER"


class AISafetyIncidentBase(SQLModel):
    student_id: str = Field(sa_column=Column(String(255), index=True, nullable=False))
    severity: str = Field(default=AISafetySeverity.MEDIUM.value, sa_column=Column(String(50), index=True, nullable=False))
    trigger_category: str = Field(default=AISafetyCategory.OTHER.value, sa_column=Column(String(100), index=True, nullable=False))
    prompt_snippet: str = Field(sa_column=Column(Text, nullable=False))
    counselor_notified: bool = Field(default=False, sa_column=Column(Boolean, default=False, nullable=False))
    details: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    course_id: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    org_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))


class AISafetyIncidentCreate(AISafetyIncidentBase):
    pass


class AISafetyIncidentRead(AISafetyIncidentBase):
    id: int
    created_at: str


class AISafetyIncident(AISafetyIncidentBase, table=True):
    __tablename__ = "ai_safety_incidents"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        sa_column=Column(String(64), nullable=False, index=True)
    )
