import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.db.sms_revops import (
    ActivityType,
    LeadIntent,
    LeadOrigin,
    LeadSource,
    LeadStage,
    OfferStatus,
)


class LeadBase(BaseModel):
    """Core attributes for an admissions lead."""
    parent_name: str = Field(..., max_length=255)
    student_name: str = Field(..., max_length=255)
    email: str = Field(..., max_length=255)
    phone: str = Field(..., max_length=50)
    grade_applying_for: str = Field(..., max_length=50)
    campus_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    source: LeadSource = LeadSource.WEBSITE_FORM
    # Inbound (organic/content-driven) vs Outbound (paid ads/pixel-tracked) nurture
    # path, distinct from `source`. Left unset to allow server-side inference from
    # `source` when the caller doesn't know / doesn't care to specify it.
    origin: Optional[LeadOrigin] = None
    budget_range: Optional[str] = None
    notes: Optional[str] = None
    assigned_officer_id: Optional[int] = None
    # Consent & Compliance: explicit per-channel opt-in captured at intake. Defaults
    # to False (no consent assumed) until the prospect explicitly opts in.
    whatsapp_consent: bool = False
    email_consent: bool = False


class LeadCreate(LeadBase):
    """Schema for registering a new admissions lead."""
    intent_level: Optional[LeadIntent] = None


class LeadUpdate(BaseModel):
    """Schema for updating an existing admissions lead."""
    parent_name: Optional[str] = None
    student_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    grade_applying_for: Optional[str] = None
    campus_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    source: Optional[LeadSource] = None
    origin: Optional[LeadOrigin] = None
    stage: Optional[LeadStage] = None
    lead_score: Optional[int] = Field(default=None, ge=0, le=100)
    intent_level: Optional[LeadIntent] = None
    budget_range: Optional[str] = None
    notes: Optional[str] = None
    assigned_officer_id: Optional[int] = None
    last_contacted_at: Optional[datetime.datetime] = None


class LeadRead(LeadBase):
    """Schema for reading an admissions lead."""
    id: int
    origin: LeadOrigin
    stage: LeadStage
    lead_score: int
    intent_level: LeadIntent
    whatsapp_consent_updated_at: Optional[datetime.datetime] = None
    email_consent_updated_at: Optional[datetime.datetime] = None
    last_contacted_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class LeadConsentUpdate(BaseModel):
    """
    Schema for recording an opt-in/opt-out consent change for a lead's outbound
    communication channels. At least one channel must be supplied.
    """
    whatsapp_consent: Optional[bool] = None
    email_consent: Optional[bool] = None
    reason: Optional[str] = None


class LeadStageUpdate(BaseModel):
    """Schema for progressing or moving a lead across pipeline stages."""
    stage: LeadStage
    reason: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class LeadActivityCreate(BaseModel):
    """Schema for logging an outreach or engagement activity."""
    activity_type: ActivityType
    summary: str
    metadata_json: Optional[Dict[str, Any]] = None


class LeadActivityRead(BaseModel):
    """Schema for reading a lead activity record."""
    id: int
    lead_id: int
    activity_type: ActivityType
    summary: str
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ScholarshipOfferCreate(BaseModel):
    """Schema for creating a dynamic scholarship / pricing offer."""
    lead_id: int
    campus_id: Optional[int] = None
    base_tuition_amount: float = Field(..., gt=0.0)
    tuition_discount_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    valid_until: datetime.date
    status: Optional[OfferStatus] = OfferStatus.SENT
    remarks: Optional[str] = None


class OfferDecision(str, Enum):
    """What the family said about the offer."""

    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class OfferResponseRequest(BaseModel):
    """A family's answer to an offer, recorded by the admissions office.

    `decided_by` names the person at the school who took the call/visit, which
    is set from the authenticated principal -- never from this payload. The
    family member's name goes in `responded_by`, as a record of who the school
    spoke to, not as an authorisation.
    """

    decision: OfferDecision
    responded_by: Optional[str] = Field(
        default=None,
        description="Name of the parent/guardian who gave the answer, as told to the office.",
        max_length=255,
    )
    note: Optional[str] = Field(
        default=None,
        description="Anything the family said that the office should keep.",
        max_length=2000,
    )


class ScholarshipOfferRead(BaseModel):
    """Schema for reading a generated scholarship offer."""
    id: int
    lead_id: int
    campus_id: Optional[int] = None
    tuition_discount_percentage: float
    final_tuition_amount: float
    valid_until: datetime.date
    status: OfferStatus
    offer_letter_url: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class PipelineStageGroup(BaseModel):
    """Grouped leads for a specific Kanban stage."""
    stage: LeadStage
    stage_name: str
    count: int
    leads: List[LeadRead]


class PipelineResponse(BaseModel):
    """Full Kanban pipeline response with stage categorization."""
    stages: List[PipelineStageGroup]
    total_leads: int


class BatchScoringRequest(BaseModel):
    """Request payload for running AI lead scoring engine across leads."""
    lead_ids: Optional[List[int]] = None
    campus_id: Optional[int] = None


class LeadScoringResult(BaseModel):
    """Individual lead AI scoring outcome."""
    lead_id: int
    score: int
    intent_level: LeadIntent
    breakdown: Dict[str, Any]


class BatchScoringResponse(BaseModel):
    """Response summarizing batch lead scoring results."""
    processed_count: int
    results: List[LeadScoringResult]


class LeadDetailResponse(LeadRead):
    """Complete detail view of a lead with interaction audit trail and offers."""
    activities: List[LeadActivityRead] = []
    offers: List[ScholarshipOfferRead] = []


class EnrollLeadRequest(BaseModel):
    """Provision a won lead into a real student.

    `student_email` is required rather than derived: `AdmissionsLead.email`
    is the PARENT's address (the model carries `parent_name` beside
    `student_name`), so reusing it would either mis-attribute the account or
    collide for a second sibling. Synthesising one was previously found and
    removed from the webhook path, so it is not done here either.
    """
    section_id: int
    academic_year_id: int
    student_email: str
    roll_number: Optional[str] = None


class EnrollLeadResponse(BaseModel):
    """What provisioning actually did -- distinguishes a fresh enrollment from
    a repeat call, so the UI can say 'already enrolled' instead of implying a
    duplicate was created."""
    lead: LeadRead
    student_id: int
    enrollment_id: int
    created_user: bool
    created_role: bool
    created_enrollment: bool
    already_provisioned: bool
