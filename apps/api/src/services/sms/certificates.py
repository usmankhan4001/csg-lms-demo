import hashlib
import secrets
from datetime import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_certificates import CertificateTemplate, IssuedCertificate
from src.schemas.sms_certificates import (
    CertificateTemplateCreate,
    IssueCertificatePayload,
    PublicCertificateVerificationResponse,
)


class CertificateService:
    @staticmethod
    async def create_template(
        db: AsyncSession,
        payload: CertificateTemplateCreate,
        org_id: Optional[int],
    ) -> CertificateTemplate:
        template = CertificateTemplate(
            org_id=org_id,
            title=payload.title,
            description=payload.description,
            layout_type=payload.layout_type,
            background_url=payload.background_url,
            border_style=payload.border_style,
            issuer_name=payload.issuer_name,
            issuer_title=payload.issuer_title,
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)
        return template

    @staticmethod
    async def list_templates(db: AsyncSession, org_id: Optional[int]) -> List[CertificateTemplate]:
        query = select(CertificateTemplate)
        if org_id is not None:
            query = query.where(CertificateTemplate.org_id == org_id)
        result = await db.exec(query)
        return list(result.all())

    @staticmethod
    async def issue_certificate(
        db: AsyncSession,
        payload: IssueCertificatePayload,
        org_id: Optional[int],
    ) -> IssuedCertificate:
        template = await db.get(CertificateTemplate, payload.template_id)
        if not template:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate template not found")

        # Generate tamper-evident verification hash
        entropy = f"{payload.student_id}:{payload.template_id}:{payload.issue_date}:{secrets.token_hex(16)}"
        verification_hash = hashlib.sha256(entropy.encode("utf-8")).hexdigest()

        issued = IssuedCertificate(
            org_id=org_id,
            template_id=payload.template_id,
            student_id=payload.student_id,
            recipient_name=payload.recipient_name,
            recipient_email=payload.recipient_email,
            title=payload.title,
            honors=payload.honors,
            issue_date=payload.issue_date,
            expiry_date=payload.expiry_date,
            verification_hash=verification_hash,
            qr_code_data_url=f"/sms/certificates/verify/{verification_hash}",
            pdf_storage_url=f"/api/v1/sms/certificates/render/{verification_hash}.pdf",
        )
        db.add(issued)
        await db.commit()
        await db.refresh(issued)
        return issued

    @staticmethod
    async def list_issued_certificates(
        db: AsyncSession,
        org_id: Optional[int],
        student_id: Optional[int] = None,
    ) -> List[IssuedCertificate]:
        query = select(IssuedCertificate)
        if org_id is not None:
            query = query.where(IssuedCertificate.org_id == org_id)
        if student_id is not None:
            query = query.where(IssuedCertificate.student_id == student_id)
        query = query.order_by(IssuedCertificate.issue_date.desc())
        result = await db.exec(query)
        return list(result.all())

    @staticmethod
    async def verify_certificate(
        db: AsyncSession,
        verification_hash: str,
    ) -> PublicCertificateVerificationResponse:
        query = select(IssuedCertificate).where(IssuedCertificate.verification_hash == verification_hash)
        result = await db.exec(query)
        cert = result.first()
        if not cert:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid certificate verification code")

        template = await db.get(CertificateTemplate, cert.template_id)
        issuer_name = template.issuer_name if template else "Official Board"
        issuer_title = template.issuer_title if template else "Authorized Issuer"

        return PublicCertificateVerificationResponse(
            is_valid=not cert.is_revoked,
            recipient_name=cert.recipient_name,
            title=cert.title,
            honors=cert.honors,
            issue_date=cert.issue_date,
            issuer_name=issuer_name,
            issuer_title=issuer_title,
            is_revoked=cert.is_revoked,
            revocation_reason=cert.revocation_reason,
        )
