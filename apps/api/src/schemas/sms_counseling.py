import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 1. Psychologist activity tracking
# ---------------------------------------------------------------------------

class ActivityLogCreate(BaseModel):
    student_id: int
    signal_type: str = Field(..., description="e.g. attendance_pattern, behavioral_flag, academic_concern")
    description: str
    severity: str = "low"


class ActivityLogRead(BaseModel):
    id: int
    student_id: int
    psychologist_id: str
    signal_type: str
    description: str
    severity: str
    recorded_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# 2. Structured 1:1 session logging + parent involvement
# ---------------------------------------------------------------------------

class CounselingSessionCreate(BaseModel):
    student_id: int
    session_date: datetime.datetime
    duration_minutes: int = Field(..., gt=0, le=480)
    notes: str
    follow_up_plan: Optional[str] = None
    # Parent involvement, kept narrow per spec: a boolean flag plus a
    # parent-visible summary field -- not a messaging system.
    share_summary_with_parent: bool = False
    parent_visible_summary: Optional[str] = None


class CounselingSessionUpdate(BaseModel):
    notes: Optional[str] = None
    follow_up_plan: Optional[str] = None
    share_summary_with_parent: Optional[bool] = None
    parent_visible_summary: Optional[str] = None


class CounselingSessionRead(BaseModel):
    """Full record — PSYCHOLOGIST view only (see router confidentiality rule)."""
    id: int
    student_id: int
    psychologist_id: str
    session_date: datetime.datetime
    duration_minutes: int
    notes: str
    follow_up_plan: Optional[str] = None
    share_summary_with_parent: bool
    parent_visible_summary: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ParentVisibleSessionSummary(BaseModel):
    """Restricted view for PARENT/STUDENT: no clinical notes, no follow-up plan."""
    id: int
    student_id: int
    session_date: datetime.datetime
    parent_visible_summary: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# 3. Career guidance (structured AI plan, not open chat)
# ---------------------------------------------------------------------------

class CareerGuidancePathway(BaseModel):
    pathway: str
    reasoning: str


class CareerGuidancePlanGenerated(BaseModel):
    """The strict structured LLM output — a Pydantic model, not freeform chat."""
    suggested_pathways: List[CareerGuidancePathway] = Field(default_factory=list)
    reasoning: str
    next_steps: List[str] = Field(default_factory=list)


class CareerGuidanceGenerateRequest(BaseModel):
    student_id: int
    interests: Optional[List[str]] = None
    extra_context: Optional[str] = None


class CareerGuidancePlanRead(BaseModel):
    id: int
    student_id: int
    generated_by: Optional[str] = None
    suggested_pathways: List[CareerGuidancePathway] = Field(default_factory=list)
    reasoning: str
    next_steps: List[str] = Field(default_factory=list)
    generated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# 4. Psychological Clinical Desk & Envelope Encryption (Phase 5)
# ---------------------------------------------------------------------------

class EncryptedEnvelope(BaseModel):
    """Client-side AES-256-GCM encryption envelope."""
    ciphertext: str = Field(..., description="Base64-encoded encrypted payload")
    iv: str = Field(..., description="Base64-encoded 12-byte initialization vector / nonce")
    tag: str = Field(..., description="Base64-encoded 16-byte authentication tag")
    key_id: Optional[str] = Field(default=None, description="Key identifier or encrypted DEK reference")
    algorithm: str = Field(default="AES-256-GCM", description="Cryptographic cipher used")
    version: str = Field(default="v1", description="Envelope format version")


class ClinicalCaseNoteCreate(BaseModel):
    student_id: int
    category: str = Field(default="therapeutic_note", description="therapeutic_note | diagnostic_assessment | risk_evaluation")
    risk_level: str = Field(default="low", description="low | medium | high | critical")
    envelope: EncryptedEnvelope


class ClinicalCaseNoteRead(BaseModel):
    id: int
    student_id: int
    psychologist_id: str
    category: str
    risk_level: str
    envelope: EncryptedEnvelope
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class DiagnosticAssessmentCreate(BaseModel):
    student_id: int
    assessment_tool: str = Field(..., description="e.g. PHQ-9, GAD-7, BASC-3, WISC-V, BRIEF-2")
    envelope: EncryptedEnvelope
    risk_level: str = Field(default="low")


class PastoralEscalationCreate(BaseModel):
    """Payload to trigger institutional pastoral escalation.
    DO NOT include clinical case notes or diagnostic narratives."""
    student_id: int
    risk_level: str = Field(..., description="low | medium | high | critical")
    category: str = Field(..., description="attendance_decline | pastoral_risk | crisis_triage | safety_alert")
    action_required: str = Field(..., description="Immediate non-clinical protective action needed")


class PastoralEscalationRead(BaseModel):
    """Anonymized escalation visible to school leadership.
    Zero clinical narratives or diagnosis information included."""
    id: int
    org_id: int
    campus_id: Optional[int] = None
    student_anon_token: str
    risk_level: str
    category: str
    action_required: str
    status: str
    escalated_by_sub: str
    created_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CrisisTriageItemCreate(BaseModel):
    student_id: int
    triage_level: str = Field(default="CRITICAL", description="ELEVATED | HIGH | CRITICAL")
    trigger_reason: str = Field(..., description="Operational non-clinical trigger code/reason")


class CrisisTriageItemRead(BaseModel):
    id: int
    student_id: int
    psychologist_id: str
    triage_level: str
    trigger_reason: str
    status: str
    flagged_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CrisisTriageUpdate(BaseModel):
    status: str = Field(..., description="ACTIVE | RESOLVED | ESCALATED")

