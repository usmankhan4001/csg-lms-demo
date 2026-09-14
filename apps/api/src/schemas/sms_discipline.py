from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from src.db.sms_discipline import IncidentSeverityEnum, IncidentStatusEnum


class IncidentCreate(BaseModel):
    student_id: int
    incident_date: str
    title: str
    description: str
    location: Optional[str] = None
    severity: IncidentSeverityEnum = IncidentSeverityEnum.MINOR
    action_taken: Optional[str] = None
    notes: Optional[str] = None


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    severity: Optional[IncidentSeverityEnum] = None
    status: Optional[IncidentStatusEnum] = None
    action_taken: Optional[str] = None
    parent_notified: Optional[bool] = None
    parent_acknowledgement: Optional[bool] = None
    notes: Optional[str] = None


class IncidentRead(BaseModel):
    id: int
    org_id: Optional[int]
    campus_id: Optional[int]
    student_id: int
    reporter_id: int
    incident_date: str
    title: str
    description: str
    location: Optional[str]
    severity: IncidentSeverityEnum
    status: IncidentStatusEnum
    action_taken: Optional[str]
    parent_notified: bool
    parent_notified_at: Optional[datetime]
    parent_acknowledgement: bool
    notes: Optional[str]
    created_at: datetime


class SuspensionCreate(BaseModel):
    incident_id: int
    student_id: int
    start_date: str
    end_date: str
    is_in_school: bool = False
    academic_work_provided: bool = True
    reinstatement_conditions: Optional[str] = None


class SuspensionRead(BaseModel):
    id: int
    org_id: Optional[int]
    incident_id: int
    student_id: int
    authorized_by_id: int
    start_date: str
    end_date: str
    is_in_school: bool
    academic_work_provided: bool
    reinstatement_date: Optional[str]
    reinstatement_conditions: Optional[str]
    created_at: datetime
