"""Request/response shapes for M01 Admissions.

Read models deliberately expose absence as absence: `score`, `outcome`,
`submitted_at` and every verification field are Optional and stay None until
something real fills them. An applicant with no assessment must never read as
having scored zero.
"""

import datetime
from typing import List, Optional

from pydantic import BaseModel, Field as PydanticField

from src.db.sms_admissions import (
    AdmissionDecision,
    ApplicationStatus,
    AssessmentOutcome,
    DocumentType,
    DocumentVerificationStatus,
)


# ── Applications ───────────────────────────────────────────────────────────


class ApplicationCreate(BaseModel):
    """A new application. `lead_id` is optional -- a walk-in family may never
    have been a tracked lead."""

    campus_id: Optional[int] = None
    lead_id: Optional[int] = None
    student_name: str = PydanticField(min_length=1, max_length=255)
    date_of_birth: Optional[datetime.date] = None
    guardian_name: str = PydanticField(min_length=1, max_length=255)
    guardian_email: Optional[str] = None
    guardian_phone: Optional[str] = None
    grade_applying_for: str = PydanticField(min_length=1, max_length=50)
    academic_year_id: Optional[int] = None
    notes: Optional[str] = None


class ApplicationUpdate(BaseModel):
    student_name: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None
    guardian_name: Optional[str] = None
    guardian_email: Optional[str] = None
    guardian_phone: Optional[str] = None
    grade_applying_for: Optional[str] = None
    academic_year_id: Optional[int] = None
    notes: Optional[str] = None


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
    note: Optional[str] = None


class ApplicationRead(BaseModel):
    id: int
    application_number: str
    org_id: int
    campus_id: Optional[int]
    lead_id: Optional[int]
    student_name: str
    date_of_birth: Optional[datetime.date]
    guardian_name: str
    guardian_email: Optional[str]
    guardian_phone: Optional[str]
    grade_applying_for: str
    academic_year_id: Optional[int]
    status: ApplicationStatus
    submitted_at: Optional[datetime.datetime]
    enrolled_student_id: Optional[int]
    notes: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


# ── Documents ──────────────────────────────────────────────────────────────


class DocumentRead(BaseModel):
    """Document metadata. Deliberately carries NO url or path.

    The file is fetched through an authorised endpoint that re-checks the
    caller against the application; exposing a path here would make the
    document reachable by anyone who saw the response.
    """

    id: int
    application_id: int
    document_type: DocumentType
    original_filename: Optional[str]
    verification_status: DocumentVerificationStatus
    verified_by_user_id: Optional[int]
    verified_at: Optional[datetime.datetime]
    rejection_reason: Optional[str]
    uploaded_by_user_id: Optional[int]
    uploaded_at: datetime.datetime

    model_config = {"from_attributes": True}


class DocumentVerifyRequest(BaseModel):
    """Verify or reject. A rejection without a reason tells the family
    nothing, so the service requires one."""

    verification_status: DocumentVerificationStatus
    rejection_reason: Optional[str] = None


# ── Assessments ────────────────────────────────────────────────────────────


class AssessmentScheduleRequest(BaseModel):
    assessment_name: str = PydanticField(min_length=1, max_length=255)
    scheduled_for: Optional[datetime.datetime] = None
    venue: Optional[str] = None


class AssessmentResultRequest(BaseModel):
    """Record a result. `score` stays absent for a NOT_ATTENDED outcome rather
    than being recorded as 0."""

    outcome: AssessmentOutcome
    score: Optional[float] = None
    max_score: Optional[float] = None
    assessor_notes: Optional[str] = None


class AssessmentRead(BaseModel):
    id: int
    application_id: int
    assessment_name: str
    scheduled_for: Optional[datetime.datetime]
    venue: Optional[str]
    score: Optional[float]
    max_score: Optional[float]
    outcome: Optional[AssessmentOutcome]
    assessor_notes: Optional[str]
    assessed_by_user_id: Optional[int]
    assessed_at: Optional[datetime.datetime]
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ── Decisions ──────────────────────────────────────────────────────────────


class DecisionCreate(BaseModel):
    """`reason` is required: a decision with no recorded rationale is exactly
    what the decision trail exists to prevent."""

    decision: AdmissionDecision
    reason: str = PydanticField(min_length=1)


class DecisionRead(BaseModel):
    id: int
    application_id: int
    decision: AdmissionDecision
    reason: str
    decided_by_user_id: int
    decided_at: datetime.datetime

    model_config = {"from_attributes": True}


# ── Composite ──────────────────────────────────────────────────────────────


class ApplicationDetailRead(BaseModel):
    """Everything the office needs on one screen.

    `assessments` and `decisions` are empty lists when nothing has happened --
    an empty list means "none recorded", which is a different and honest
    statement from a zero score or a default outcome.
    """

    application: ApplicationRead
    documents: List[DocumentRead]
    assessments: List[AssessmentRead]
    decisions: List[DecisionRead]
    # True only when every REQUIRED document type is VERIFIED. Computed, never
    # stored, so it cannot drift from the documents themselves.
    documents_complete: bool
    missing_document_types: List[DocumentType]
