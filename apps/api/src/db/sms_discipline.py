"""
SMS Disciplinary Incident Tracking Database Models (Module M32).

Tracks student behavioral incidents, severity levels, actions taken,
parent notification status, and suspension logs.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel


class IncidentSeverityEnum(str, Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class IncidentStatusEnum(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    APPEALED = "appealed"


class DisciplinaryIncident(SQLModel, table=True):
    __tablename__ = "sms_disciplinary_incidents"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    campus_id: Optional[int] = Field(default=None, index=True)
    student_id: int = Field(index=True, description="Learnhouse user ID of the student")
    reporter_id: int = Field(index=True, description="Learnhouse user ID of reporting staff/teacher")
    incident_date: str = Field(description="ISO Date YYYY-MM-DD")
    title: str = Field(description="Brief summary of incident")
    description: str = Field(description="Detailed narrative of behavioral infraction")
    location: Optional[str] = Field(default=None, description="Classroom, playground, hallway, etc.")
    severity: IncidentSeverityEnum = Field(default=IncidentSeverityEnum.MINOR)
    status: IncidentStatusEnum = Field(default=IncidentStatusEnum.OPEN)
    action_taken: Optional[str] = Field(default=None, description="Detention, counseling, suspension, warning")
    parent_notified: bool = Field(default=False)
    parent_notified_at: Optional[datetime] = Field(default=None)
    parent_acknowledgement: bool = Field(default=False)
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SuspensionRecord(SQLModel, table=True):
    __tablename__ = "sms_suspension_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    incident_id: int = Field(foreign_key="sms_disciplinary_incidents.id", index=True)
    student_id: int = Field(index=True)
    authorized_by_id: int = Field(description="School Admin authorizing the suspension")
    start_date: str = Field(description="ISO Date YYYY-MM-DD")
    end_date: str = Field(description="ISO Date YYYY-MM-DD")
    is_in_school: bool = Field(default=False, description="In-school vs Out-of-school suspension")
    academic_work_provided: bool = Field(default=True)
    reinstatement_date: Optional[str] = Field(default=None)
    reinstatement_conditions: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
