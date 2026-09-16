"""
CSG Document Engine & School Branding Service.
=============================================
Manages institutional branding, document template presets, cryptographic hash generation,
rendering data consolidation, and document issuance audit logging.
"""

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlmodel import select, desc
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_document_template import SchoolBrandingSettings, SMSDocumentTemplate
from src.db.sms_audit_log import SMSDocumentAuditLog
from src.schemas.sms_documents import (
    SchoolBrandingSettingsUpdate,
    SMSDocumentTemplateCreate,
    SMSDocumentTemplateUpdate,
    DocumentIssueRequest,
    DocumentVerificationResponse,
)


class DocumentService:
    @staticmethod
    async def get_or_create_branding(
        db: AsyncSession,
        org_id: int,
        campus_id: Optional[int] = None,
    ) -> SchoolBrandingSettings:
        """Fetch branding for a specific campus or fallback to org-level branding."""
        # 1. Try campus-specific branding first if campus_id provided
        if campus_id is not None:
            query = select(SchoolBrandingSettings).where(
                SchoolBrandingSettings.org_id == org_id,
                SchoolBrandingSettings.campus_id == campus_id,
            )
            result = await db.exec(query)
            campus_branding = result.first()
            if campus_branding:
                return campus_branding

        # 2. Try org-level branding (campus_id is None)
        query = select(SchoolBrandingSettings).where(
            SchoolBrandingSettings.org_id == org_id,
            SchoolBrandingSettings.campus_id == None,  # noqa: E711
        )
        result = await db.exec(query)
        org_branding = result.first()
        if org_branding:
            return org_branding

        # 3. Create default branding if none exists
        default_branding = SchoolBrandingSettings(
            org_id=org_id,
            campus_id=campus_id,
            school_name="CSG International Academy",
            school_tagline="Excellence in Global Learning & Innovation",
            primary_color="#4F46E5",
            secondary_color="#0EA5E9",
            accent_color="#D97706",
            principal_name="Dr. Eleanor Vance",
            principal_title="Head of School & Principal",
            controller_name="Marcus Sterling, CPA",
            controller_title="Chief Financial Officer",
            registrar_name="Patricia Holloway",
            registrar_title="Academic Registrar",
            tax_id="NTN-9842104-7",
            registration_number="EDU-REG-2018-9412",
            bank_name="Habib Bank Limited (HBL)",
            bank_branch="F-7 Blue Area Corporate Branch",
            bank_branch_code="0482",
            bank_account_title="CSG Educational Ventures Trust",
            bank_account_number="0482-7901234503",
            bank_iban="PK36HABB0000482790123450",
            bank_swift_code="HABBPKKA",
            accreditation_body="Cognia Global Commission",
            accreditation_number="COG-INTL-89104",
            contact_email="registrar@csg-academy.edu",
            contact_phone="+1 (555) 019-2834",
            website_url="https://academy.csg.edu",
            physical_address="Campus Boulevard, Academic District, Sector H-8",
            custom_footer_text="This is an official computer-generated document verified via cryptographic digital signature.",
        )
        db.add(default_branding)
        await db.commit()
        await db.refresh(default_branding)
        return default_branding

    @staticmethod
    async def update_branding(
        db: AsyncSession,
        org_id: int,
        payload: SchoolBrandingSettingsUpdate,
        campus_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> SchoolBrandingSettings:
        """Create or update branding settings."""
        query = select(SchoolBrandingSettings).where(
            SchoolBrandingSettings.org_id == org_id,
            SchoolBrandingSettings.campus_id == campus_id,
        )
        result = await db.exec(query)
        branding = result.first()

        if not branding:
            branding = SchoolBrandingSettings(
                org_id=org_id,
                campus_id=campus_id,
                **payload.model_dump(exclude_unset=True),
            )
            branding.updated_by_user_id = user_id
            db.add(branding)
        else:
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(branding, key, value)
            branding.updated_at = datetime.now(timezone.utc)
            branding.updated_by_user_id = user_id
            db.add(branding)

        await db.commit()
        await db.refresh(branding)
        return branding

    @staticmethod
    async def list_templates(
        db: AsyncSession,
        org_id: int,
        campus_id: Optional[int] = None,
    ) -> List[SMSDocumentTemplate]:
        query = select(SMSDocumentTemplate).where(SMSDocumentTemplate.org_id == org_id)
        if campus_id is not None:
            query = query.where(
                (SMSDocumentTemplate.campus_id == campus_id) | (SMSDocumentTemplate.campus_id == None) # noqa: E711
            )
        result = await db.exec(query)
        return list(result.all())

    @staticmethod
    async def create_or_update_template(
        db: AsyncSession,
        org_id: int,
        payload: SMSDocumentTemplateCreate,
        campus_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> SMSDocumentTemplate:
        query = select(SMSDocumentTemplate).where(
            SMSDocumentTemplate.org_id == org_id,
            SMSDocumentTemplate.campus_id == campus_id,
            SMSDocumentTemplate.template_type == payload.template_type,
        )
        result = await db.exec(query)
        template = result.first()

        if not template:
            template = SMSDocumentTemplate(
                org_id=org_id,
                campus_id=campus_id,
                template_type=payload.template_type,
                title=payload.title,
                description=payload.description,
                layout_config=payload.layout_config,
                header_text=payload.header_text,
                footer_text=payload.footer_text,
                terms_and_conditions=payload.terms_and_conditions,
                is_active=payload.is_active,
                updated_by_user_id=user_id,
            )
            db.add(template)
        else:
            template.title = payload.title
            template.description = payload.description
            template.layout_config = payload.layout_config
            template.header_text = payload.header_text
            template.footer_text = payload.footer_text
            template.terms_and_conditions = payload.terms_and_conditions
            template.is_active = payload.is_active
            template.updated_at = datetime.now(timezone.utc)
            template.updated_by_user_id = user_id
            db.add(template)

        await db.commit()
        await db.refresh(template)
        return template

    @staticmethod
    def generate_verification_hash(
        org_id: int,
        doc_type: str,
        document_number: str,
        recipient_name: str,
    ) -> str:
        """Create a cryptographic tamper-evident SHA-256 hash."""
        salt = secrets.token_hex(8)
        entropy = f"{org_id}:{doc_type}:{document_number}:{recipient_name}:{datetime.now(timezone.utc).isoformat()}:{salt}"
        return hashlib.sha256(entropy.encode("utf-8")).hexdigest()

    @staticmethod
    async def issue_document(
        db: AsyncSession,
        org_id: int,
        payload: DocumentIssueRequest,
        user_id: Optional[int] = None,
        user_name: Optional[str] = None,
    ) -> SMSDocumentAuditLog:
        """Issue an official document, generate tamper hash & QR verification URL, and record audit log."""
        verification_hash = DocumentService.generate_verification_hash(
            org_id=org_id,
            doc_type=payload.doc_type,
            document_number=payload.document_number,
            recipient_name=payload.recipient_name,
        )

        verification_url = f"/verify-doc/{verification_hash}"

        audit_entry = SMSDocumentAuditLog(
            org_id=org_id,
            campus_id=payload.campus_id,
            doc_type=payload.doc_type,
            document_number=payload.document_number,
            recipient_id=payload.recipient_id,
            recipient_name=payload.recipient_name,
            recipient_identifier=payload.recipient_identifier,
            issued_by_user_id=user_id,
            issued_by_name=user_name,
            verification_hash=verification_hash,
            verification_url=verification_url,
            metadata_payload=payload.document_payload,
        )

        db.add(audit_entry)
        await db.commit()
        await db.refresh(audit_entry)
        return audit_entry

    @staticmethod
    async def verify_document(
        db: AsyncSession,
        verification_hash: str,
    ) -> DocumentVerificationResponse:
        """Public tamper verification endpoint for third-parties / scanners."""
        query = select(SMSDocumentAuditLog).where(
            SMSDocumentAuditLog.verification_hash == verification_hash
        )
        result = await db.exec(query)
        entry = result.first()

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document verification record not found or invalid signature.",
            )

        # Fetch branding for the school name
        branding = await DocumentService.get_or_create_branding(
            db=db,
            org_id=entry.org_id,
            campus_id=entry.campus_id,
        )

        return DocumentVerificationResponse(
            is_valid=not bool(entry.is_revoked),
            is_revoked=bool(entry.is_revoked),
            revocation_reason=entry.revocation_reason,
            doc_type=entry.doc_type,
            document_number=entry.document_number,
            recipient_name=entry.recipient_name,
            recipient_identifier=entry.recipient_identifier,
            school_name=branding.school_name,
            campus_name=branding.campus_name,
            issued_at=entry.created_at,
            issued_by_name=entry.issued_by_name,
            verification_hash=entry.verification_hash,
            metadata_summary={
                "doc_type": entry.doc_type,
                "issued_date": entry.created_at.strftime("%Y-%m-%d"),
                "school": branding.school_name,
            },
        )

    @staticmethod
    async def list_audit_logs(
        db: AsyncSession,
        org_id: int,
        doc_type: Optional[str] = None,
        recipient_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[SMSDocumentAuditLog]:
        query = select(SMSDocumentAuditLog).where(SMSDocumentAuditLog.org_id == org_id)
        if doc_type:
            query = query.where(SMSDocumentAuditLog.doc_type == doc_type)
        if recipient_id:
            query = query.where(SMSDocumentAuditLog.recipient_id == recipient_id)

        query = query.order_by(desc(SMSDocumentAuditLog.created_at)).offset(offset).limit(limit)
        result = await db.exec(query)
        return list(result.all())
