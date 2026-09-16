"""
CSG Document Issuance & Verification Audit Log Models.
=====================================================
Logs all generated and issued documents (transcripts, fee vouchers, payslips,
certificates, ID cards) for ISO 27001 compliance, anti-fraud audit trails, and verification.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import JSON, Column, DateTime, Index, Integer, String, Text
from sqlmodel import Field, SQLModel


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SMSDocumentAuditLog(SQLModel, table=True):
    """Immutable audit trail of issued official documents."""

    __tablename__ = "sms_document_audit_logs"
    __table_args__ = (
        Index("ix_sms_doc_audit_org_type", "org_id", "doc_type"),
        Index("ix_sms_doc_audit_hash", "verification_hash", unique=True),
        Index("ix_sms_doc_audit_doc_number", "document_number"),
        {"extend_existing": True},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(sa_column=Column(Integer, nullable=False, index=True))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))

    # Document classification: 'bank_slip', 'payslip', 'cognia_transcript', 'certificate', 'student_id_card'
    doc_type: str = Field(sa_column=Column(String(64), nullable=False))
    document_number: str = Field(sa_column=Column(String(128), nullable=False))

    # Recipient / Subject Information
    recipient_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True, index=True))
    recipient_name: str = Field(sa_column=Column(String(255), nullable=False))
    recipient_identifier: Optional[str] = Field(default=None, sa_column=Column(String(100), nullable=True)) # Roll no / Staff Code

    # Issuer Information
    issued_by_user_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))
    issued_by_name: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))

    # Cryptographic & Verification Data
    verification_hash: str = Field(sa_column=Column(String(128), nullable=False))
    verification_url: Optional[str] = Field(default=None, sa_column=Column(String(1024), nullable=True))
    qr_data_url: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    # Snapshot of rendered data or parameters for reconstruction
    metadata_payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))

    is_revoked: bool = Field(default=False, sa_column=Column(Integer, default=0, nullable=False))
    revocation_reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(
        default_factory=get_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
