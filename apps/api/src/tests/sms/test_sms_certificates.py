import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.schemas.sms_certificates import CertificateTemplateCreate, IssueCertificatePayload
from src.services.sms.certificates import CertificateService


@pytest.mark.asyncio
async def test_certificate_issuance_and_verification(db: AsyncSession):
    # 1. Create Template
    tmpl = await CertificateService.create_template(
        db=db,
        payload=CertificateTemplateCreate(
            title="Certificate of Academic Excellence",
            issuer_name="Dr. Asad Ullah Khan",
            issuer_title="Head of School",
        ),
        org_id=1,
    )
    assert tmpl.id is not None

    # 2. Issue Certificate
    issued = await CertificateService.issue_certificate(
        db=db,
        payload=IssueCertificatePayload(
            template_id=tmpl.id,
            student_id=301,
            recipient_name="Zainab Malik",
            title="Dean's High Honors",
            honors="Summa Cum Laude",
            issue_date="2026-06-15",
        ),
        org_id=1,
    )
    assert issued.id is not None
    assert issued.verification_hash is not None
    assert len(issued.verification_hash) == 64

    # 3. Verify via public hash
    verified = await CertificateService.verify_certificate(
        db=db,
        verification_hash=issued.verification_hash,
    )
    assert verified.is_valid is True
    assert verified.recipient_name == "Zainab Malik"
    assert verified.issuer_name == "Dr. Asad Ullah Khan"
