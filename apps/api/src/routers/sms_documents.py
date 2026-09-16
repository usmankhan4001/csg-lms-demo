"""
CSG Document Engine & School Branding API Router.
================================================
Endpoints for School Branding management, Document Template configuration,
document rendering previews, official issuance with audit trails, and public verification.
"""

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
from src.schemas.sms_documents import (
    SchoolBrandingSettingsRead,
    SchoolBrandingSettingsUpdate,
    SMSDocumentTemplateRead,
    SMSDocumentTemplateCreate,
    DocumentRenderRequest,
    DocumentRenderResponse,
    DocumentIssueRequest,
    DocumentIssueResponse,
    DocumentVerificationResponse,
    DocumentAuditLogRead,
)
from src.services.sms.documents import DocumentService

router = APIRouter(prefix="/sms/documents", tags=["sms-documents"])


# ---------------------------------------------------------------------------
# School Branding Endpoints
# ---------------------------------------------------------------------------

@router.get("/branding", response_model=SchoolBrandingSettingsRead)
async def get_school_branding(
    campus_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    """Get active school branding configuration for the organization/campus."""
    return await DocumentService.get_or_create_branding(
        db=db,
        org_id=principal.org_id,
        campus_id=campus_id,
    )


@router.put("/branding", response_model=SchoolBrandingSettingsRead)
async def update_school_branding(
    payload: SchoolBrandingSettingsUpdate,
    campus_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
):
    """Update institutional branding, colors, signatories, and banking credentials."""
    return await DocumentService.update_branding(
        db=db,
        org_id=principal.org_id,
        payload=payload,
        campus_id=campus_id,
        user_id=principal.user_id if hasattr(principal, "user_id") else None,
    )


# ---------------------------------------------------------------------------
# Document Templates Endpoints
# ---------------------------------------------------------------------------

@router.get("/templates", response_model=List[SMSDocumentTemplateRead])
async def list_document_templates(
    campus_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
):
    """List configured document templates for this school."""
    return await DocumentService.list_templates(
        db=db,
        org_id=principal.org_id,
        campus_id=campus_id,
    )


@router.post("/templates", response_model=SMSDocumentTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_or_update_template(
    payload: SMSDocumentTemplateCreate,
    campus_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
):
    """Create or update a document template layout."""
    return await DocumentService.create_or_update_template(
        db=db,
        org_id=principal.org_id,
        payload=payload,
        campus_id=campus_id,
        user_id=principal.user_id if hasattr(principal, "user_id") else None,
    )


# ---------------------------------------------------------------------------
# Document Issuance, Preview & Verification Endpoints
# ---------------------------------------------------------------------------

@router.post("/render/{doc_type}", response_model=DocumentRenderResponse)
async def render_document_preview(
    doc_type: str,
    payload: DocumentRenderRequest,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF])),
):
    """Consolidate document data with school branding for high-fidelity client-side rendering."""
    branding = await DocumentService.get_or_create_branding(
        db=db,
        org_id=principal.org_id,
        campus_id=payload.campus_id,
    )

    doc_num = payload.data.get("document_number") or payload.data.get("voucher_no") or payload.data.get("slip_no") or "DOC-PREVIEW"
    rec_name = payload.data.get("student_name") or payload.data.get("staff_name") or "Recipient"

    verification_hash = DocumentService.generate_verification_hash(
        org_id=principal.org_id,
        doc_type=doc_type,
        document_number=doc_num,
        recipient_name=rec_name,
    )

    return DocumentRenderResponse(
        doc_type=doc_type,
        branding=branding.model_dump(),
        document_data=payload.data,
        verification_hash=verification_hash,
        verification_url=f"/verify-doc/{verification_hash}",
        rendered_at=branding.updated_at.isoformat(),
    )


@router.post("/issue", response_model=DocumentIssueResponse, status_code=status.HTTP_201_CREATED)
async def issue_official_document(
    payload: DocumentIssueRequest,
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF])),
):
    """Officially issue a document, stamp it with a cryptographic verification hash, and log the audit entry."""
    audit_entry = await DocumentService.issue_document(
        db=db,
        org_id=principal.org_id,
        payload=payload,
        user_id=principal.user_id if hasattr(principal, "user_id") else None,
        user_name=getattr(principal, "preferred_username", None) or getattr(principal, "email", "Authorized Issuer"),
    )
    return DocumentIssueResponse(
        id=audit_entry.id,
        org_id=audit_entry.org_id,
        campus_id=audit_entry.campus_id,
        doc_type=audit_entry.doc_type,
        document_number=audit_entry.document_number,
        recipient_id=audit_entry.recipient_id,
        recipient_name=audit_entry.recipient_name,
        verification_hash=audit_entry.verification_hash,
        verification_url=audit_entry.verification_url or f"/verify-doc/{audit_entry.verification_hash}",
        qr_data_url=audit_entry.qr_data_url,
        created_at=audit_entry.created_at,
    )


@router.get("/verify/{verification_hash}", response_model=DocumentVerificationResponse)
async def verify_document(
    verification_hash: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Public tamper-evident verification endpoint for third-parties, employers, and banks."""
    return await DocumentService.verify_document(db=db, verification_hash=verification_hash)


@router.get("/audit-logs", response_model=List[DocumentAuditLogRead])
async def list_document_audit_logs(
    doc_type: Optional[str] = Query(None),
    recipient_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, STAFF])),
):
    """Fetch audit history of issued official documents."""
    return await DocumentService.list_audit_logs(
        db=db,
        org_id=principal.org_id,
        doc_type=doc_type,
        recipient_id=recipient_id,
        limit=limit,
        offset=offset,
    )
