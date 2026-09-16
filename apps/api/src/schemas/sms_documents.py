"""
CSG Document Engine & School Branding Pydantic Schemas.
======================================================
Defines typed request/response models for School Branding settings, Document Templates,
Document Rendering, Official Issuance, Verification, and Audit Logs.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# School Branding Schemas
# ---------------------------------------------------------------------------

class SchoolBrandingSettingsBase(BaseModel):
    school_name: str = "CSG International Academy"
    school_tagline: Optional[str] = "Excellence in Global Learning & Innovation"
    campus_name: Optional[str] = None
    logo_url: Optional[str] = None
    crest_url: Optional[str] = None
    primary_color: str = "#4F46E5"
    secondary_color: str = "#0EA5E9"
    accent_color: str = "#D97706"
    principal_name: Optional[str] = "Dr. Eleanor Vance"
    principal_title: Optional[str] = "Head of School & Principal"
    principal_signature_url: Optional[str] = None
    controller_name: Optional[str] = "Marcus Sterling, CPA"
    controller_title: Optional[str] = "Chief Financial Officer"
    controller_signature_url: Optional[str] = None
    registrar_name: Optional[str] = "Patricia Holloway"
    registrar_title: Optional[str] = "Academic Registrar"
    registrar_signature_url: Optional[str] = None
    official_stamp_url: Optional[str] = None
    tax_id: Optional[str] = "NTN-9842104-7"
    registration_number: Optional[str] = "EDU-REG-2018-9412"
    bank_name: Optional[str] = "Habib Bank Limited (HBL)"
    bank_branch: Optional[str] = "F-7 Blue Area Corporate Branch"
    bank_branch_code: Optional[str] = "0482"
    bank_account_title: Optional[str] = "CSG Educational Ventures Trust"
    bank_account_number: Optional[str] = "0482-7901234503"
    bank_iban: Optional[str] = "PK36HABB0000482790123450"
    bank_swift_code: Optional[str] = "HABBPKKA"
    accreditation_body: Optional[str] = "Cognia Global Commission"
    accreditation_seal_url: Optional[str] = None
    accreditation_number: Optional[str] = "COG-INTL-89104"
    contact_email: Optional[str] = "registrar@csg-academy.edu"
    contact_phone: Optional[str] = "+1 (555) 019-2834"
    website_url: Optional[str] = "https://academy.csg.edu"
    physical_address: Optional[str] = "Campus Boulevard, Academic District, Sector H-8"
    custom_footer_text: Optional[str] = "This is an official computer-generated document verified via cryptographic digital signature."


class SchoolBrandingSettingsUpdate(BaseModel):
    school_name: Optional[str] = None
    school_tagline: Optional[str] = None
    campus_name: Optional[str] = None
    logo_url: Optional[str] = None
    crest_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    principal_name: Optional[str] = None
    principal_title: Optional[str] = None
    principal_signature_url: Optional[str] = None
    controller_name: Optional[str] = None
    controller_title: Optional[str] = None
    controller_signature_url: Optional[str] = None
    registrar_name: Optional[str] = None
    registrar_title: Optional[str] = None
    registrar_signature_url: Optional[str] = None
    official_stamp_url: Optional[str] = None
    tax_id: Optional[str] = None
    registration_number: Optional[str] = None
    bank_name: Optional[str] = None
    bank_branch: Optional[str] = None
    bank_branch_code: Optional[str] = None
    bank_account_title: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_iban: Optional[str] = None
    bank_swift_code: Optional[str] = None
    accreditation_body: Optional[str] = None
    accreditation_seal_url: Optional[str] = None
    accreditation_number: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    website_url: Optional[str] = None
    physical_address: Optional[str] = None
    custom_footer_text: Optional[str] = None


class SchoolBrandingSettingsRead(SchoolBrandingSettingsBase):
    id: int
    org_id: int
    campus_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    updated_by_user_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Document Template Schemas
# ---------------------------------------------------------------------------

class SMSDocumentTemplateBase(BaseModel):
    template_type: str  # bank_slip, payslip, cognia_transcript, certificate, student_id_card
    title: str
    description: Optional[str] = None
    layout_config: Dict[str, Any] = Field(default_factory=dict)
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    is_active: bool = True


class SMSDocumentTemplateCreate(SMSDocumentTemplateBase):
    pass


class SMSDocumentTemplateUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    layout_config: Optional[Dict[str, Any]] = None
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    is_active: Optional[bool] = None


class SMSDocumentTemplateRead(SMSDocumentTemplateBase):
    id: int
    org_id: int
    campus_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    updated_by_user_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Document Issuance & Verification Schemas
# ---------------------------------------------------------------------------

class DocumentRenderRequest(BaseModel):
    doc_type: str  # bank_slip, payslip, cognia_transcript, certificate, student_id_card
    campus_id: Optional[int] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class DocumentRenderResponse(BaseModel):
    doc_type: str
    branding: Dict[str, Any]
    document_data: Dict[str, Any]
    verification_hash: str
    verification_url: str
    qr_data_url: Optional[str] = None
    rendered_at: str


class DocumentIssueRequest(BaseModel):
    doc_type: str
    campus_id: Optional[int] = None
    recipient_id: Optional[int] = None
    recipient_name: str
    recipient_identifier: Optional[str] = None
    document_number: str
    document_payload: Dict[str, Any] = Field(default_factory=dict)


class DocumentIssueResponse(BaseModel):
    id: int
    org_id: int
    campus_id: Optional[int] = None
    doc_type: str
    document_number: str
    recipient_id: Optional[int] = None
    recipient_name: str
    verification_hash: str
    verification_url: str
    qr_data_url: Optional[str] = None
    created_at: datetime


class DocumentVerificationResponse(BaseModel):
    is_valid: bool
    is_revoked: bool
    revocation_reason: Optional[str] = None
    doc_type: str
    document_number: str
    recipient_name: str
    recipient_identifier: Optional[str] = None
    school_name: str
    campus_name: Optional[str] = None
    issued_at: datetime
    issued_by_name: Optional[str] = None
    verification_hash: str
    metadata_summary: Dict[str, Any] = Field(default_factory=dict)


class DocumentAuditLogRead(BaseModel):
    id: int
    org_id: int
    campus_id: Optional[int] = None
    doc_type: str
    document_number: str
    recipient_id: Optional[int] = None
    recipient_name: str
    recipient_identifier: Optional[str] = None
    issued_by_user_id: Optional[int] = None
    issued_by_name: Optional[str] = None
    verification_hash: str
    verification_url: Optional[str] = None
    is_revoked: bool = False
    revocation_reason: Optional[str] = None
    created_at: datetime
