from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    KeycloakUserPrincipal,
    SUPER_ADMIN,
    SCHOOL_ADMIN,
    TEACHER,
    STAFF,
    STUDENT,
    get_current_user_principal,
    require_roles,
)
from src.schemas.sms_certificates import (
    CertificateTemplateCreate,
    CertificateTemplateRead,
    IssueCertificatePayload,
    IssuedCertificateRead,
    PublicCertificateVerificationResponse,
)
from src.services.sms.certificates import CertificateService

router = APIRouter(prefix="/sms/certificates", tags=["sms-certificates"])


@router.post("/templates", response_model=CertificateTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: CertificateTemplateCreate,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
):
    return await CertificateService.create_template(db=db, payload=payload, org_id=principal.org_id)


@router.get("/templates", response_model=List[CertificateTemplateRead])
async def list_templates(
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    return await CertificateService.list_templates(db=db, org_id=principal.org_id)


@router.post("/issue", response_model=IssuedCertificateRead, status_code=status.HTTP_201_CREATED)
async def issue_certificate(
    payload: IssueCertificatePayload,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER])),
):
    return await CertificateService.issue_certificate(db=db, payload=payload, org_id=principal.org_id)


@router.get("/issued", response_model=List[IssuedCertificateRead])
async def list_issued_certificates(
    student_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    return await CertificateService.list_issued_certificates(
        db=db, org_id=principal.org_id, student_id=student_id
    )


@router.get("/verify/{verification_hash}", response_model=PublicCertificateVerificationResponse)
async def verify_certificate(
    verification_hash: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Public tamper-evident certificate verification endpoint."""
    return await CertificateService.verify_certificate(db=db, verification_hash=verification_hash)
