"""M01 Admissions — the application lifecycle.

Gating rationale, stated once here because it is the point of the module:

These records hold a child's birth certificate, medical history and guardian
identity documents. TEACHER is deliberately NOT admitted to any endpoint in
this router. A class teacher has a legitimate need for a roster and a
gradebook; they have none for a family's immunisation record or proof of
address. That is a narrower gate than most SMS modules use, and it is
intentional -- the same reasoning that removed TEACHER from safety-incident
visibility elsewhere in this codebase.

Documents are never addressable by URL. `DocumentRead` carries no path, and
the bytes are served only through `GET /documents/{id}/content`, which
re-resolves the parent application and re-checks campus scope on every call.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import UploadFile

from src.core.events.database import get_db_session
from src.core.keycloak_auth import KeycloakUserPrincipal, require_roles
from src.db.organizations import Organization
from src.db.sms_admissions import (
    AdmissionDecisionRecord,
    ApplicationAssessment,
    ApplicationDocument,
    ApplicationStatus,
    DocumentType,
    DocumentVerificationStatus,
    StudentApplication,
)
from src.schemas.sms_admissions import (
    ApplicationCreate,
    ApplicationDetailRead,
    ApplicationRead,
    ApplicationStatusUpdate,
    ApplicationUpdate,
    AssessmentRead,
    AssessmentResultRequest,
    AssessmentScheduleRequest,
    DecisionCreate,
    DecisionRead,
    DocumentRead,
    DocumentVerifyRequest,
)
from src.security.ems_rbac import require_permission
from src.security.school_ownership import assert_campus_allowed, resolve_scoped_campus_id
from src.services.sms import admissions as svc

# Admissions staff and school leadership. TEACHER excluded -- see module
# docstring. STAFF is included because the admissions office IS back-office
# staff; a receptionist taking a walk-in application is the normal case.
_ADMISSIONS = ["SUPER_ADMIN", "SCHOOL_ADMIN", "STAFF"]

# --- Dynamic RBAC (src/security/ems_rbac.py) -------------------------------
#
# Fine-grained second gate behind the coarse `require_roles(_ADMISSIONS)` /
# `require_roles(_ADMISSIONS_LEAD)`. Admissions is the `revops` domain of
# `ResourceDomain` (src/db/ems_roles.py) -- the same mapping
# RESOURCE_DOMAIN_MAP already uses for 'admissions' and
# 'admissions.applications'.
#
# OPERATOR ACTION REQUIRED: the built-in `staff` template grants NOTHING on
# revops, so a backfilled STAFF user (the receptionist this module exists for)
# passes the coarse gate and is then refused here. Grant revops to the role
# your admissions office actually uses -- that is what the dynamic store is
# for -- or run with EMS_RBAC_LEGACY_FALLBACK=1 until you have.
ADMISSIONS = "revops.admissions"

# Decisions and document verification are accountable acts that carry the
# school's name. Narrower than _ADMISSIONS on purpose: a receptionist may
# receive a birth certificate, but confirming it is genuine, and refusing a
# child a place, are leadership acts.
_ADMISSIONS_LEAD = ["SUPER_ADMIN", "SCHOOL_ADMIN"]

router = APIRouter()


def _caller_user_id(principal: KeycloakUserPrincipal) -> Optional[int]:
    return (principal.raw_claims or {}).get("lh_user_id")


async def _resolve_org_uuid(session: AsyncSession, org_id: int) -> str:
    """The storage path is org-scoped, so a document cannot land in, or be
    read from, another organisation's directory."""
    result = await session.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalars().first()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found."
        )
    return org.org_uuid


async def _load_application_in_scope(
    session: AsyncSession,
    principal: KeycloakUserPrincipal,
    application_id: int,
) -> StudentApplication:
    """Load an application the caller is actually entitled to see.

    A campus-bound caller asking for another campus's application gets 404,
    not 403: confirming that application 812 exists tells them a named family
    applied to a campus they have no business seeing.
    """
    application = await svc.get_application(session, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found."
        )

    if principal.org_id is not None and application.org_id != principal.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found."
        )

    if not principal.is_superadmin and principal.campus_id is not None:
        if application.campus_id != principal.campus_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Application not found."
            )
    return application


# ── Applications ───────────────────────────────────────────────────────────


@router.post(
    "/applications",
    response_model=ApplicationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Application",
    description=(
        "Start an application. `lead_id` is optional -- a walk-in family may "
        "never have been a tracked RevOps lead, and requiring one would force "
        "the front desk to fabricate a marketing record to accept a form."
    ),
    dependencies=[Depends(require_permission(ADMISSIONS, "create"))],
)
async def create_application(
    payload: ApplicationCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> ApplicationRead:
    # A write naming a campus fails loudly rather than landing on another one.
    assert_campus_allowed(principal, payload.campus_id)
    campus_id = payload.campus_id if payload.campus_id is not None else principal.campus_id

    if principal.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account is not attached to a school organisation.",
        )

    application = await svc.create_application(
        session,
        org_id=principal.org_id,
        campus_id=campus_id,
        lead_id=payload.lead_id,
        student_name=payload.student_name,
        guardian_name=payload.guardian_name,
        grade_applying_for=payload.grade_applying_for,
        date_of_birth=payload.date_of_birth,
        guardian_email=payload.guardian_email,
        guardian_phone=payload.guardian_phone,
        academic_year_id=payload.academic_year_id,
        notes=payload.notes,
    )
    return ApplicationRead.model_validate(application)


@router.get(
    "/applications",
    response_model=List[ApplicationRead],
    summary="List Applications",
    description=(
        "Applications for the caller's school. A campus-bound caller is "
        "narrowed to their own campus even when they request none -- an "
        "omitted filter must not widen access."
    ),
    dependencies=[Depends(require_permission(ADMISSIONS, "read"))],
)
async def list_applications(
    campus_id: Optional[int] = Query(None),
    status_filter: Optional[ApplicationStatus] = Query(None, alias="status"),
    academic_year_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> List[ApplicationRead]:
    if principal.org_id is None:
        return []
    scoped_campus = resolve_scoped_campus_id(principal, campus_id)
    rows = await svc.list_applications(
        session,
        org_id=principal.org_id,
        campus_id=scoped_campus,
        status_filter=status_filter,
        academic_year_id=academic_year_id,
        limit=limit,
        offset=offset,
    )
    return [ApplicationRead.model_validate(r) for r in rows]


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationDetailRead,
    summary="Application Detail",
    description=(
        "Everything the office needs on one screen. `assessments` and "
        "`decisions` are empty lists when nothing has been recorded -- an "
        "applicant with no assessment has no assessment, never a zero score."
    ),
    dependencies=[Depends(require_permission(ADMISSIONS, "read"))],
)
async def get_application_detail(
    application_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> ApplicationDetailRead:
    application = await _load_application_in_scope(session, principal, application_id)
    documents = await svc.list_documents(session, application_id)
    assessments = await svc.list_assessments(session, application_id)
    decisions = await svc.list_decisions(session, application_id)
    complete, missing = svc.evaluate_document_completeness(documents)

    return ApplicationDetailRead(
        application=ApplicationRead.model_validate(application),
        documents=[DocumentRead.model_validate(d) for d in documents],
        assessments=[AssessmentRead.model_validate(a) for a in assessments],
        decisions=[DecisionRead.model_validate(d) for d in decisions],
        documents_complete=complete,
        missing_document_types=missing,
    )


@router.patch(
    "/applications/{application_id}",
    response_model=ApplicationRead,
    summary="Update Application",
    dependencies=[Depends(require_permission(ADMISSIONS, "update"))],
)
async def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> ApplicationRead:
    application = await _load_application_in_scope(session, principal, application_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(application, field, value)
    session.add(application)
    await session.commit()
    await session.refresh(application)
    return ApplicationRead.model_validate(application)


@router.post(
    "/applications/{application_id}/submit",
    response_model=ApplicationRead,
    summary="Submit Application",
    dependencies=[Depends(require_permission(ADMISSIONS, "approve"))],
)
async def submit_application(
    application_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> ApplicationRead:
    application = await _load_application_in_scope(session, principal, application_id)
    updated = await svc.submit_application(session, application)
    return ApplicationRead.model_validate(updated)


@router.patch(
    "/applications/{application_id}/status",
    response_model=ApplicationRead,
    summary="Set Application Status",
    dependencies=[Depends(require_permission(ADMISSIONS, "update"))],
)
async def set_status(
    application_id: int,
    payload: ApplicationStatusUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> ApplicationRead:
    application = await _load_application_in_scope(session, principal, application_id)
    updated = await svc.set_application_status(session, application, payload.status)
    return ApplicationRead.model_validate(updated)


# ── Documents ──────────────────────────────────────────────────────────────


@router.post(
    "/applications/{application_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Supporting Document",
    description=(
        "Stored through the shared upload primitive, which validates type and "
        "size and produces a uuid4-prefixed filename -- so a document is not "
        "reachable by guessing an application id. Uploads land as PENDING: an "
        "unchecked file must never read as verified."
    ),
    dependencies=[Depends(require_permission(ADMISSIONS, "create"))],
)
async def upload_document(
    application_id: int,
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> DocumentRead:
    application = await _load_application_in_scope(session, principal, application_id)
    org_uuid = await _resolve_org_uuid(session, application.org_id)
    document = await svc.store_document(
        session,
        application=application,
        document_type=document_type,
        file=file,
        org_uuid=org_uuid,
        uploaded_by_user_id=_caller_user_id(principal),
    )
    return DocumentRead.model_validate(document)


@router.get(
    "/applications/{application_id}/documents",
    response_model=List[DocumentRead],
    summary="List Supporting Documents",
    dependencies=[Depends(require_permission(ADMISSIONS, "read"))],
)
async def list_documents(
    application_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> List[DocumentRead]:
    await _load_application_in_scope(session, principal, application_id)
    rows = await svc.list_documents(session, application_id)
    return [DocumentRead.model_validate(r) for r in rows]


@router.get(
    "/documents/{document_id}/content",
    summary="Download Supporting Document",
    description=(
        "Serves the stored bytes. The parent application is re-loaded and "
        "re-scoped on every call, so a document id alone is never sufficient "
        "authority to read a child's identity papers."
    ),
    dependencies=[Depends(require_permission(ADMISSIONS, "read"))],
)
async def download_document(
    document_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> Response:
    document = await svc.get_document(session, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    # Re-authorise through the parent application rather than trusting the id.
    application = await _load_application_in_scope(
        session, principal, document.application_id
    )
    org_uuid = await _resolve_org_uuid(session, application.org_id)
    data = await svc.read_document_bytes(document, org_uuid)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            # Always an attachment: these are identity documents, never
            # something to render inline in a browser tab.
            "Content-Disposition": f'attachment; filename="{document.stored_filename}"',
        },
    )


@router.patch(
    "/documents/{document_id}/verify",
    response_model=DocumentRead,
    summary="Verify or Reject Document",
    description=(
        "Records the check against the AUTHENTICATED verifier, never a "
        "client-supplied id. A rejection requires a reason so the family knows "
        "what to resubmit."
    ),
    dependencies=[Depends(require_permission(ADMISSIONS, "approve"))],
)
async def verify_document(
    document_id: int,
    payload: DocumentVerifyRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS_LEAD)),
) -> DocumentRead:
    document = await svc.get_document(session, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    await _load_application_in_scope(session, principal, document.application_id)

    verifier_id = _caller_user_id(principal)
    if verifier_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot attribute this verification: no user id on the session.",
        )

    updated = await svc.verify_document(
        session,
        document,
        new_status=payload.verification_status,
        verified_by_user_id=verifier_id,
        rejection_reason=payload.rejection_reason,
    )
    return DocumentRead.model_validate(updated)


# ── Assessments ────────────────────────────────────────────────────────────


@router.post(
    "/applications/{application_id}/assessments",
    response_model=AssessmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule Assessment",
    dependencies=[Depends(require_permission(ADMISSIONS, "create"))],
)
async def schedule_assessment(
    application_id: int,
    payload: AssessmentScheduleRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> AssessmentRead:
    await _load_application_in_scope(session, principal, application_id)
    assessment = await svc.schedule_assessment(
        session,
        application_id=application_id,
        assessment_name=payload.assessment_name,
        scheduled_for=payload.scheduled_for,
        venue=payload.venue,
    )
    return AssessmentRead.model_validate(assessment)


@router.get(
    "/applications/{application_id}/assessments",
    response_model=List[AssessmentRead],
    summary="List Assessments",
    dependencies=[Depends(require_permission(ADMISSIONS, "read"))],
)
async def list_assessments(
    application_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> List[AssessmentRead]:
    await _load_application_in_scope(session, principal, application_id)
    rows = await svc.list_assessments(session, application_id)
    return [AssessmentRead.model_validate(r) for r in rows]


@router.patch(
    "/assessments/{assessment_id}/result",
    response_model=AssessmentRead,
    summary="Record Assessment Result",
    description=(
        "A NOT_ATTENDED outcome cannot carry a score: an applicant who never "
        "sat the paper did not score zero on it."
    ),
    dependencies=[Depends(require_permission(ADMISSIONS, "update"))],
)
async def record_assessment_result(
    assessment_id: int,
    payload: AssessmentResultRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> AssessmentRead:
    assessment = await svc.get_assessment(session, assessment_id)
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found."
        )
    await _load_application_in_scope(session, principal, assessment.application_id)

    assessor_id = _caller_user_id(principal)
    if assessor_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot attribute this result: no user id on the session.",
        )

    updated = await svc.record_assessment_result(
        session,
        assessment,
        outcome=payload.outcome,
        score=payload.score,
        max_score=payload.max_score,
        assessor_notes=payload.assessor_notes,
        assessed_by_user_id=assessor_id,
    )
    return AssessmentRead.model_validate(updated)


# ── Decisions ──────────────────────────────────────────────────────────────


@router.post(
    "/applications/{application_id}/decisions",
    response_model=DecisionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record Admission Decision",
    description=(
        "Append-only. A reversed decision adds a row rather than editing one, "
        "so a school challenged months later can show what was decided, by "
        "whom, and why. The reason is required."
    ),
    dependencies=[Depends(require_permission(ADMISSIONS, "approve"))],
)
async def record_decision(
    application_id: int,
    payload: DecisionCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS_LEAD)),
) -> DecisionRead:
    application = await _load_application_in_scope(session, principal, application_id)

    decider_id = _caller_user_id(principal)
    if decider_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot attribute this decision: no user id on the session.",
        )

    record = await svc.record_decision(
        session,
        application=application,
        decision=payload.decision,
        reason=payload.reason,
        decided_by_user_id=decider_id,
    )
    return DecisionRead.model_validate(record)


@router.get(
    "/applications/{application_id}/decisions",
    response_model=List[DecisionRead],
    summary="List Admission Decisions",
    dependencies=[Depends(require_permission(ADMISSIONS, "read"))],
)
async def list_decisions(
    application_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> List[DecisionRead]:
    await _load_application_in_scope(session, principal, application_id)
    rows = await svc.list_decisions(session, application_id)
    return [DecisionRead.model_validate(r) for r in rows]
