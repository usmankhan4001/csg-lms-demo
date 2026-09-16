from typing import Dict, List, Optional, Union
from pydantic import BaseModel
from sqlalchemy import JSON, Column, ForeignKey, Integer, String, Index
from sqlmodel import Field, SQLModel
from src.db.roles import Rights


# ---------------------------------------------------------------------------
# Granular API Token Scope Catalog
# ---------------------------------------------------------------------------

VALID_API_SCOPES: Dict[str, Dict[str, str]] = {
    # ── Academic Structure & Curricular Bridge ──────────────────────────────
    "academic:read": {"category": "Academic", "description": "Read academic years, terms, sections, and enrollments"},
    "academic:write": {"category": "Academic", "description": "Create and update academic years, terms, sections, and enrollments"},
    "campus:read": {"category": "Academic", "description": "Read campuses, buildings, rooms, and facilities"},
    "campus:write": {"category": "Academic", "description": "Create and modify campuses and facility assets"},
    "curriculum:read": {"category": "Academic", "description": "Read LMS course-to-section subject mappings"},
    "curriculum:write": {"category": "Academic", "description": "Assign LMS courses to SMS sections (SectionSubjects)"},
    "timetable:read": {"category": "Academic", "description": "Read bell schedules, period grids, and timetables"},
    "timetable:write": {"category": "Academic", "description": "Generate and edit timetable slots and schedule allocations"},

    # ── Biometric Attendance ────────────────────────────────────────────────
    "attendance:read": {"category": "Attendance", "description": "Query daily and period attendance records"},
    "attendance:write": {"category": "Attendance", "description": "Record and update individual student attendance"},
    "attendance:bulk": {"category": "Attendance", "description": "Batch ingest biometric turnstile / IoT clock-in events"},

    # ── Gradebook, SpeedGrader & CBT Exams ──────────────────────────────────
    "gradebook:read": {"category": "Assessment", "description": "Read gradebook entries, rubric scores, and report cards"},
    "gradebook:write": {"category": "Assessment", "description": "Post SpeedGrader evaluations and publish term report cards"},
    "exams:read": {"category": "Assessment", "description": "Read CBT exam schedules, questions, and student responses"},
    "exams:write": {"category": "Assessment", "description": "Create exams, manage sitting sessions, and grade responses"},
    "exams:psychometrics": {"category": "Assessment", "description": "Calculate and view 2PL IRT item discrimination & Cronbach alpha"},

    # ── Admissions & RevOps CRM ─────────────────────────────────────────────
    "admissions:read": {"category": "Admissions", "description": "Query pipeline inquiries, BANT qualifications, and applications"},
    "admissions:write": {"category": "Admissions", "description": "Create and update leads, stage transitions, and activity logs"},
    "admissions:matriculate": {"category": "Admissions", "description": "Execute 1-Click Matriculation Handshake to enroll students"},

    # ── Financials, Tuition Fees & Payroll ──────────────────────────────────
    "fees:read": {"category": "Financials", "description": "Read tuition fee structures, student vouchers, and payment records"},
    "fees:write": {"category": "Financials", "description": "Create and update fee structures, discounts, and fee vouchers"},
    "fees:collect": {"category": "Financials", "description": "Record online and cash fee payments and issue receipts"},
    "financials:read": {"category": "Financials", "description": "Access Chart of Accounts, Journal Entries, and Trial Balance"},
    "financials:write": {"category": "Financials", "description": "Post double-entry journal vouchers and close fiscal periods"},
    "payroll:read": {"category": "Financials", "description": "Read staff salary structures, progressive payroll runs, and payslips"},
    "payroll:write": {"category": "Financials", "description": "Prepare monthly payroll disbursements and tax calculations"},
    "payroll:approve": {"category": "Financials", "description": "Authorize and finalize monthly payroll batches"},

    # ── Pastoral Care & Crisis Safety ───────────────────────────────────────
    "pastoral:read": {"category": "Pastoral", "description": "Read student commendations and disciplinary logs"},
    "pastoral:write": {"category": "Pastoral", "description": "Record pastoral incidents and behavioral notes"},
    "crisis:alert": {"category": "Pastoral", "description": "Trigger urgent mental health / safety crisis escalation alerts"},

    # ── Accreditation & Compliance ──────────────────────────────────────────
    "cognia:read": {"category": "Compliance", "description": "Read Cognia accreditation evidence and AMI maturity index"},
    "cognia:write": {"category": "Compliance", "description": "Submit accreditation evidence artifacts with SHA-256 digests"},
    "cognia:verify": {"category": "Compliance", "description": "Certify and verify compliance evidence dossiers"},

    # ── Identity & Organization ─────────────────────────────────────────────
    "users:read": {"category": "Identity", "description": "Query user profiles, staff directories, and student roster"},
    "users:write": {"category": "Identity", "description": "Create and update user accounts and roles"},
    "guardians:manage": {"category": "Identity", "description": "Establish and manage Student-Guardian relationships"},

    # ── Isolated Clinical Desk ──────────────────────────────────────────────
    "clinical:restricted": {"category": "Clinical", "description": "Access encrypted psychological notes (clinical specialists only)"},
}


class APITokenBase(SQLModel):
    """Base model for API tokens"""
    name: str = Field(max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    rights: Optional[Union[Rights, dict]] = Field(default=None, sa_column=Column(JSON))
    scopes: Optional[List[str]] = Field(default_factory=list, sa_column=Column(JSON))


class APIToken(APITokenBase, table=True):
    """Database model for API tokens"""
    __tablename__ = "apitoken"
    __table_args__ = (
        Index("ix_apitoken_token_prefix", "token_prefix"),
        Index("ix_apitoken_org_id", "org_id"),
        {"extend_existing": True}
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    token_uuid: str = Field(default="", max_length=100)  # format: apitoken_{uuid4()}
    token_prefix: str = Field(default="", max_length=12)
    token_hash: str = Field(default="", sa_column=Column(String(255)))
    org_id: int = Field(
        sa_column=Column(Integer, ForeignKey("organization.id", ondelete="CASCADE"), nullable=False)
    )
    created_by_user_id: int = Field(
        sa_column=Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    )
    creation_date: str = ""
    update_date: str = ""
    last_used_at: Optional[str] = None
    expires_at: Optional[str] = None  # None = never expires
    is_active: bool = Field(default=True)  # False = revoked


class APITokenCreate(BaseModel):
    """Model for creating a new API token"""
    name: str
    description: Optional[str] = None
    rights: Optional[Union[Rights, dict]] = None
    scopes: Optional[List[str]] = None
    expires_at: Optional[str] = None


class APITokenUpdate(BaseModel):
    """Model for updating an API token"""
    name: Optional[str] = None
    description: Optional[str] = None
    rights: Optional[Union[Rights, dict]] = None
    scopes: Optional[List[str]] = None
    expires_at: Optional[str] = None


class APITokenRead(BaseModel):
    """Model for reading an API token (without sensitive data)"""
    id: int
    token_uuid: str
    name: str
    description: Optional[str] = None
    token_prefix: str
    org_id: int
    rights: Optional[Union[Rights, dict]] = None
    scopes: Optional[List[str]] = None
    created_by_user_id: int
    creation_date: str
    update_date: str
    last_used_at: Optional[str] = None
    expires_at: Optional[str] = None
    is_active: bool


class APITokenCreatedResponse(BaseModel):
    """
    Response model when a new API token is created.
    This is the ONLY time the full token is shown.
    """
    token: str  # The full token (only shown once!)
    token_uuid: str
    name: str
    description: Optional[str] = None
    token_prefix: str
    org_id: int
    rights: Optional[Union[Rights, dict]] = None
    scopes: Optional[List[str]] = None
    created_by_user_id: int
    creation_date: str
    expires_at: Optional[str] = None

