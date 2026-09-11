import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.db.sms_revops import (
    ActivityType,
    LeadIntent,
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
    budget_range: Optional[str] = None
    notes: Optional[str] = None
    assigned_officer_id: Optional[int] = None


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
    stage: LeadStage
    lead_score: int
    intent_level: LeadIntent
    last_contacted_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


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
