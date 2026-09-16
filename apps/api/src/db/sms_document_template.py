"""
CSG School Branding & Document Template Database Models.
========================================================
Stores institutional branding assets (logos, crests, colors, signatures, seals,
tax/banking configurations) and document template specifications across multi-campus hierarchies.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Boolean, Text
from sqlmodel import Field, SQLModel


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SchoolBrandingSettings(SQLModel, table=True):
    """Institutional branding, official stamps, bank routing, and accreditation settings."""

    __tablename__ = "sms_school_branding_settings"
    __table_args__ = (
        Index("ix_sms_branding_scope", "org_id", "campus_id"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))

    # School & Campus Identity
    school_name: str = Field(default="CSG International Academy", sa_column=Column(String(255), nullable=False))
    school_tagline: Optional[str] = Field(default="Excellence in Global Learning & Innovation", sa_column=Column(String(255), nullable=True))
    campus_name: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    logo_url: Optional[str] = Field(default=None, sa_column=Column(String(1024), nullable=True))
    crest_url: Optional[str] = Field(default=None, sa_column=Column(String(1024), nullable=True))

    # Brand Colors (Hex codes)
    primary_color: str = Field(default="#4F46E5", sa_column=Column(String(32), nullable=False))
    secondary_color: str = Field(default="#0EA5E9", sa_column=Column(String(32), nullable=False))
    accent_color: str = Field(default="#D97706", sa_column=Column(String(32), nullable=False))

    # Official Signatories & Seals
    principal_name: Optional[str] = Field(default="Dr. Eleanor Vance", sa_column=Column(String(255), nullable=True))
    principal_title: Optional[str] = Field(default="Head of School & Principal", sa_column=Column(String(255), nullable=True))
    principal_signature_url: Optional[str] = Field(default=None, sa_column=Column(String(1024), nullable=True))

    controller_name: Optional[str] = Field(default="Marcus Sterling, CPA", sa_column=Column(String(255), nullable=True))
    controller_title: Optional[str] = Field(default="Chief Financial Officer", sa_column=Column(String(255), nullable=True))
    controller_signature_url: Optional[str] = Field(default=None, sa_column=Column(String(1024), nullable=True))

    registrar_name: Optional[str] = Field(default="Patricia Holloway", sa_column=Column(String(255), nullable=True))
    registrar_title: Optional[str] = Field(default="Academic Registrar", sa_column=Column(String(255), nullable=True))
    registrar_signature_url: Optional[str] = Field(default=None, sa_column=Column(String(1024), nullable=True))

    official_stamp_url: Optional[str] = Field(default=None, sa_column=Column(String(1024), nullable=True))

    # Registration & Tax Data
    tax_id: Optional[str] = Field(default="NTN-9842104-7", sa_column=Column(String(100), nullable=True))
    registration_number: Optional[str] = Field(default="EDU-REG-2018-9412", sa_column=Column(String(100), nullable=True))

    # Bank Account & Routing Details (For Fee Vouchers & Payslips)
    bank_name: Optional[str] = Field(default="Habib Bank Limited (HBL)", sa_column=Column(String(255), nullable=True))
    bank_branch: Optional[str] = Field(default="F-7 Blue Area Corporate Branch", sa_column=Column(String(255), nullable=True))
    bank_branch_code: Optional[str] = Field(default="0482", sa_column=Column(String(50), nullable=True))
    bank_account_title: Optional[str] = Field(default="CSG Educational Ventures Trust", sa_column=Column(String(255), nullable=True))
    bank_account_number: Optional[str] = Field(default="0482-7901234503", sa_column=Column(String(100), nullable=True))
    bank_iban: Optional[str] = Field(default="PK36HABB0000482790123450", sa_column=Column(String(100), nullable=True))
    bank_swift_code: Optional[str] = Field(default="HABBPKKA", sa_column=Column(String(50), nullable=True))

    # Accreditation & Quality Assurance Seals
    accreditation_body: Optional[str] = Field(default="Cognia Global Commission", sa_column=Column(String(255), nullable=True))
    accreditation_seal_url: Optional[str] = Field(default=None, sa_column=Column(String(1024), nullable=True))
    accreditation_number: Optional[str] = Field(default="COG-INTL-89104", sa_column=Column(String(100), nullable=True))

    # Contact Details
    contact_email: Optional[str] = Field(default="registrar@csg-academy.edu", sa_column=Column(String(255), nullable=True))
    contact_phone: Optional[str] = Field(default="+1 (555) 019-2834", sa_column=Column(String(100), nullable=True))
    website_url: Optional[str] = Field(default="https://academy.csg.edu", sa_column=Column(String(255), nullable=True))
    physical_address: Optional[str] = Field(default="Campus Boulevard, Academic District, Sector H-8", sa_column=Column(String(500), nullable=True))
    custom_footer_text: Optional[str] = Field(default="This is an official computer-generated document verified via cryptographic digital signature.", sa_column=Column(String(500), nullable=True))

    created_at: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))


class SMSDocumentTemplate(SQLModel, table=True):
    """Document layout specifications and custom header/footer overrides per document type."""

    __tablename__ = "sms_document_templates"
    __table_args__ = (
        Index("ix_sms_doc_templates_type", "org_id", "campus_id", "template_type"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))

    # Document type: 'bank_slip', 'payslip', 'cognia_transcript', 'certificate', 'student_id_card'
    template_type: str = Field(sa_column=Column(String(64), nullable=False))
    title: str = Field(sa_column=Column(String(255), nullable=False))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    layout_config: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    header_text: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    footer_text: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    terms_and_conditions: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False))

    created_at: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
