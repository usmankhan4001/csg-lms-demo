"""
Schemas for Automated Matriculation Handshake, BANT Scoring & Curriculum RAG
=============================================================================
Phase 3 RevOps & Matriculation API models.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.services.ai.bant_scoring import BANTScoreBreakdown, BANTTier


class MatriculationHandshakeRequest(BaseModel):
    """Payload for triggering the Automated Matriculation Handshake."""
    lead_id: int = Field(..., description="Admissions lead ID to matriculate")
    section_id: int = Field(..., description="Target Class Section ID for enrollment")
    tuition_plan_id: Optional[int] = Field(default=None, description="Optional specific fee structure ID")
    academic_year_id: Optional[int] = Field(default=None, description="Optional Academic Year ID (defaults to section year)")
    student_email: Optional[str] = Field(default=None, description="Permanent email address for student learner account")
    parent_email: Optional[str] = Field(default=None, description="Permanent email address for parent account")
    roll_number: Optional[str] = Field(default=None, description="Assigned student roll or registration number")
    installment_count: int = Field(default=4, ge=1, le=12, description="Quarterly/installment count for fee plan (default 4)")
    relationship: str = Field(default="parent", description="Guardian relationship: 'mother', 'father', 'guardian'")
    discount_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Optional manual scholarship discount override")


class StudentProfileSummary(BaseModel):
    id: int
    name: str
    email: str
    created: bool


class ParentProfileSummary(BaseModel):
    id: int
    name: str
    email: str
    created: bool


class EnrollmentSummary(BaseModel):
    id: int
    section_id: int
    academic_year_id: int
    status: str
    created: bool


class FeeScheduleSummary(BaseModel):
    installment_plan_id: int
    installment_count: int
    vouchers_count: int
    total_invoiced: float
    voucher_numbers: List[str]


class MatriculationHandshakeResponse(BaseModel):
    """Response returned upon successful execution of matriculation handshake."""
    lead_id: int
    status: str
    student: StudentProfileSummary
    parent: ParentProfileSummary
    enrollment: EnrollmentSummary
    fee_schedule: FeeScheduleSummary
    already_matriculated: bool


class CounselorQueryRequest(BaseModel):
    """Conversational admissions query payload for Curriculum RAG."""
    query: str = Field(..., min_length=2, description="Parent or prospective student inquiry text")
    campus_id: Optional[int] = Field(default=None, description="Optional campus scoping filter")
    grade_level: Optional[str] = Field(default=None, description="Optional grade level context (e.g. 'Grade 9', 'IB')")
    category: Optional[str] = Field(default=None, description="Optional topic filter: 'curriculum', 'tuition', 'policy', 'admissions'")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of top grounded citations to retrieve")


class CitationItem(BaseModel):
    doc_id: str
    title: str
    category: str
    campus_id: Optional[int] = None
    grade_levels: List[str] = []
    snippet: str
    relevance_score: float


class CounselorQueryResponse(BaseModel):
    """Grounded RAG admissions response with source citations."""
    query: str
    answer: str
    confidence: float
    citations: List[CitationItem]
    grounded_facts: List[str]
    suggested_followups: List[str]
    campus_id: Optional[int] = None
    grade_level: Optional[str] = None


class BANTQualifyRequest(BaseModel):
    """Optional lead data overrides for running BANT qualification."""
    stated_budget: Optional[float] = None
    budget_range: Optional[str] = None
    start_timeline: Optional[str] = None
    curriculum_preference: Optional[str] = None
    fee_concern: Optional[bool] = False
    relationship: Optional[str] = None


class BANTQualifyResponse(BaseModel):
    """5-Factor BANT Lead Qualification result."""
    lead_id: Optional[int] = None
    total_score: float
    tier: BANTTier
    breakdown: BANTScoreBreakdown
    conversion_signals: List[str]
    risk_factors: List[str]
    recommended_next_action: str
    qualification_summary: str


class MatriculationStatusResponse(BaseModel):
    """Live matriculation and enrollment status for an admissions lead."""
    lead_id: int
    student_name: str
    parent_name: str
    stage: str
    is_matriculated: bool
    student_user_id: Optional[int] = None
    parent_user_id: Optional[int] = None
    section_id: Optional[int] = None
    academic_year_id: Optional[int] = None
    vouchers_count: int = 0
    total_balance: float = 0.0
