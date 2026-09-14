"""
SMS Certificates & Tamper-Evident Verification Database Models (Module M16).

Stores certificate design templates, issued certificates, public verification hashes,
and tamper-evident QR verification tokens.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class CertificateTemplate(SQLModel, table=True):
    __tablename__ = "sms_certificate_templates"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    title: str = Field(description="e.g. High School Diploma, Certificate of Excellence")
    description: Optional[str] = Field(default=None)
    layout_type: str = Field(default="landscape", description="landscape | portrait")
    background_url: Optional[str] = Field(default=None)
    border_style: str = Field(default="classic_gold")
    issuer_name: str = Field(description="Principal or Dean signature name")
    issuer_title: str = Field(description="e.g. Head of School")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class IssuedCertificate(SQLModel, table=True):
    __tablename__ = "sms_issued_certificates"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: Optional[int] = Field(default=None, index=True)
    template_id: int = Field(foreign_key="sms_certificate_templates.id", index=True)
    student_id: int = Field(index=True, description="Learnhouse user ID")
    recipient_name: str
    recipient_email: Optional[str] = Field(default=None)
    title: str = Field(description="e.g. Diploma of Secondary Education")
    honors: Optional[str] = Field(default=None, description="e.g. Summa Cum Laude, High Distinction")
    issue_date: str = Field(description="ISO Date YYYY-MM-DD")
    expiry_date: Optional[str] = Field(default=None)
    verification_hash: str = Field(unique=True, index=True, description="Cryptographic tamper-evident verification hash")
    qr_code_data_url: Optional[str] = Field(default=None)
    pdf_storage_url: Optional[str] = Field(default=None)
    is_revoked: bool = Field(default=False)
    revocation_reason: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
