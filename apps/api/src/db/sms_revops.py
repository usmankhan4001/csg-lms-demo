import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlmodel import Field, SQLModel


class LeadStage(str, Enum):
    """
    Lifecycle stages in the admissions recruitment funnel.

    The real-world funnel is a loop, not a straight line: leads that stall or
    fail to convert during Nurturing / Data Enrichment / Lead Maturing / Uplift
    are marked STALLED and re-enter the funnel at NEW_INQUIRY (Lead
    Research/Sourcing) for another re-nurturing cycle, rather than being
    dropped permanently like LOST leads.
    """
    NEW_INQUIRY = "NEW_INQUIRY"
    CONTACTED = "CONTACTED"
    TOUR_BOOKED = "TOUR_BOOKED"
    ASSESSMENT_SCHEDULED = "ASSESSMENT_SCHEDULED"
    OFFER_SENT = "OFFER_SENT"
    ENROLLED = "ENROLLED"
    LOST = "LOST"
    STALLED = "STALLED"


class LeadSource(str, Enum):
    """Acquisition attribution channels for admissions inquiries."""
    WEBSITE_FORM = "WEBSITE_FORM"
    WHATSAPP = "WHATSAPP"
    META_ADS = "META_ADS"
    GOOGLE_ADS = "GOOGLE_ADS"
    WALK_IN = "WALK_IN"
    REFERRAL = "REFERRAL"


class LeadOrigin(str, Enum):
    """
    Inbound vs outbound nurture-path tagging, distinct from the acquisition
    `LeadSource` channel. INBOUND leads arrive organically / content-driven
    (website form, referral, walk-in, organic WhatsApp). OUTBOUND leads arrive
    via paid ads / pixel-tracked landing pages and follow a materially
    different nurture path.
    """
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class LeadIntent(str, Enum):
    """AI-scored conversion intent probability."""
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class ActivityType(str, Enum):
    """Types of logged interaction activities with prospective parents/students."""
    NOTE = "NOTE"
    CALL = "CALL"
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    TOUR = "TOUR"
    STAGE_CHANGE = "STAGE_CHANGE"
    CONSENT_UPDATE = "CONSENT_UPDATE"


class OfferStatus(str, Enum):
    """Status of institutional scholarship / enrollment offer letter."""
    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class AdmissionsLead(SQLModel, table=True):
    """
    Prospective student admission lead in the RevOps recruitment pipeline.
    """
    __tablename__ = "sms_admissions_lead"
    __table_args__ = (
        Index("ix_sms_lead_stage_campus", "stage", "campus_id"),
        Index("ix_sms_lead_email_phone", "email", "phone"),
        Index("ix_sms_lead_intent", "intent_level"),
        Index("ix_sms_lead_score", "lead_score"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    parent_name: str = Field(sa_column=Column(String(255), nullable=False))
    student_name: str = Field(sa_column=Column(String(255), nullable=False))
    email: str = Field(sa_column=Column(String(255), nullable=False, index=True))
    phone: str = Field(sa_column=Column(String(50), nullable=False, index=True))
    grade_applying_for: str = Field(sa_column=Column(String(50), nullable=False))
    academic_year_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    source: LeadSource = Field(
        default=LeadSource.WEBSITE_FORM,
        sa_column=Column(
            SAEnum(LeadSource, name="sms_lead_source", native_enum=False),
            nullable=False,
            default=LeadSource.WEBSITE_FORM,
        ),
    )
    origin: LeadOrigin = Field(
        default=LeadOrigin.INBOUND,
        sa_column=Column(
            SAEnum(LeadOrigin, name="sms_lead_origin", native_enum=False),
            nullable=False,
            default=LeadOrigin.INBOUND,
            index=True,
        ),
    )
    stage: LeadStage = Field(
        default=LeadStage.NEW_INQUIRY,
        sa_column=Column(
            SAEnum(LeadStage, name="sms_lead_stage", native_enum=False),
            nullable=False,
            default=LeadStage.NEW_INQUIRY,
            index=True,
        ),
    )
    lead_score: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    intent_level: LeadIntent = Field(
        default=LeadIntent.WARM,
        sa_column=Column(
            SAEnum(LeadIntent, name="sms_lead_intent", native_enum=False),
            nullable=False,
            default=LeadIntent.WARM,
        ),
    )
    budget_range: Optional[str] = Field(default=None, sa_column=Column(String(100), nullable=True))
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    assigned_officer_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    # Consent & Compliance: per-channel opt-in/opt-out tracking that gates whether
    # outbound WhatsApp/Email automation is permitted to fire for this lead.
    whatsapp_consent: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    whatsapp_consent_updated_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    email_consent: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    email_consent_updated_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_contacted_at: Optional[datetime.datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class LeadActivityLog(SQLModel, table=True):
    """
    Activity audit timeline log for admissions lead interactions.
    """
    __tablename__ = "sms_lead_activity_log"
    __table_args__ = (
        Index("ix_sms_activity_lead", "lead_id"),
        Index("ix_sms_activity_type", "activity_type"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_admissions_lead.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    activity_type: ActivityType = Field(
        sa_column=Column(
            SAEnum(ActivityType, name="sms_lead_activity_type", native_enum=False),
            nullable=False,
        )
    )
    summary: str = Field(sa_column=Column(Text, nullable=False))
    metadata_json: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )


class ScholarshipOffer(SQLModel, table=True):
    """
    Dynamic scholarship and tuition pricing offer letter generated for an applicant.
    """
    __tablename__ = "sms_scholarship_offer"
    __table_args__ = (
        Index("ix_sms_offer_lead", "lead_id"),
        Index("ix_sms_offer_status", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sms_admissions_lead.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    tuition_discount_percentage: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    final_tuition_amount: float = Field(default=0.0, sa_column=Column(Float, nullable=False))
    valid_until: datetime.date = Field(sa_column=Column(Date, nullable=False))
    status: OfferStatus = Field(
        default=OfferStatus.DRAFT,
        sa_column=Column(
            SAEnum(OfferStatus, name="sms_offer_status", native_enum=False),
            nullable=False,
            default=OfferStatus.DRAFT,
        ),
    )
    offer_letter_url: Optional[str] = Field(default=None, sa_column=Column(String(500), nullable=True))
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.datetime.now(datetime.timezone.utc),
        ),
    )
