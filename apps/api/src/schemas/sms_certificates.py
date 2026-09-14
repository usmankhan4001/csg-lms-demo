from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CertificateTemplateCreate(BaseModel):
    title: str
    description: Optional[str] = None
    layout_type: str = "landscape"
    background_url: Optional[str] = None
    border_style: str = "classic_gold"
    issuer_name: str
    issuer_title: str


class CertificateTemplateRead(BaseModel):
    id: int
    org_id: Optional[int]
    title: str
    description: Optional[str]
    layout_type: str
    background_url: Optional[str]
    border_style: str
    issuer_name: str
    issuer_title: str
    is_active: bool
    created_at: datetime


class IssueCertificatePayload(BaseModel):
    template_id: int
    student_id: int
    recipient_name: str
    recipient_email: Optional[str] = None
    title: str
    honors: Optional[str] = None
    issue_date: str
    expiry_date: Optional[str] = None


class IssuedCertificateRead(BaseModel):
    id: int
    org_id: Optional[int]
    template_id: int
    student_id: int
    recipient_name: str
    recipient_email: Optional[str]
    title: str
    honors: Optional[str]
    issue_date: str
    expiry_date: Optional[str]
    verification_hash: str
    qr_code_data_url: Optional[str]
    pdf_storage_url: Optional[str]
    is_revoked: bool
    created_at: datetime


class PublicCertificateVerificationResponse(BaseModel):
    is_valid: bool
    recipient_name: str
    title: str
    honors: Optional[str]
    issue_date: str
    issuer_name: str
    issuer_title: str
    is_revoked: bool
    revocation_reason: Optional[str] = None
