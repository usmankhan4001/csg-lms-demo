"""M01 Admissions — application lifecycle service.

Storage note: documents go through the EXISTING `upload_file` primitive
(`services/utils/upload_content.py`), the same path communities and course
PDFs use. It validates type and size, and produces a uuid4-prefixed filename,
so a stored document is not reachable by guessing an application id. There is
deliberately no second storage implementation here.
"""

import datetime
import uuid
from typing import List, Optional, Sequence, Tuple

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_admissions import (
    AdmissionDecision,
    AdmissionDecisionRecord,
    ApplicationAssessment,
    ApplicationDocument,
    ApplicationStatus,
    AssessmentOutcome,
    DocumentType,
    DocumentVerificationStatus,
    StudentApplication,
)
from src.services.utils.upload_content import read_content, upload_file

# Document types a school will not admit a child without. PHOTOGRAPH and
# PROOF_OF_ADDRESS are deliberately NOT here: useful, but a place is not
# refused for want of them, and treating them as blocking would misreport
# every application as incomplete.
REQUIRED_DOCUMENT_TYPES: Tuple[DocumentType, ...] = (
    DocumentType.BIRTH_CERTIFICATE,
    DocumentType.PRIOR_SCHOOL_RECORD,
)

# Applications close in one of these states; a decision cannot reopen them.
TERMINAL_STATUSES = (
    ApplicationStatus.ENROLLED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
)

_ALLOWED_DOC_UPLOAD_TYPES = ["image", "document"]
_MAX_DOCUMENT_BYTES = 10 * 1024 * 1024  # 10 MB


def generate_application_number(org_id: int) -> str:
    """A reference a family can quote on the phone.

    Uses a uuid4 fragment rather than a sequential counter: a sequential
    number leaks how many families applied, and lets anyone guess a
    neighbouring application's reference.
    """
    year = datetime.datetime.now(datetime.timezone.utc).year
    return f"APP-{year}-{org_id}-{uuid.uuid4().hex[:8].upper()}"


async def create_application(
    session: AsyncSession,
    *,
    org_id: int,
    campus_id: Optional[int],
    lead_id: Optional[int],
    student_name: str,
    guardian_name: str,
    grade_applying_for: str,
    date_of_birth: Optional[datetime.date] = None,
    guardian_email: Optional[str] = None,
    guardian_phone: Optional[str] = None,
    academic_year_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> StudentApplication:
    """Create an application. A lead is optional -- see the module docstring."""
    application = StudentApplication(
        application_number=generate_application_number(org_id),
        org_id=org_id,
        campus_id=campus_id,
        lead_id=lead_id,
        student_name=student_name.strip(),
        date_of_birth=date_of_birth,
        guardian_name=guardian_name.strip(),
        guardian_email=guardian_email,
        guardian_phone=guardian_phone,
        grade_applying_for=grade_applying_for.strip(),
        academic_year_id=academic_year_id,
        notes=notes,
        status=ApplicationStatus.DRAFT,
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)
    return application


async def get_application(
    session: AsyncSession, application_id: int
) -> Optional[StudentApplication]:
    result = await session.execute(
        select(StudentApplication).where(StudentApplication.id == application_id)
    )
    return result.scalars().first()


async def list_applications(
    session: AsyncSession,
    *,
    org_id: int,
    campus_id: Optional[int] = None,
    status_filter: Optional[ApplicationStatus] = None,
    academic_year_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[StudentApplication]:
    query = select(StudentApplication).where(StudentApplication.org_id == org_id)
    if campus_id is not None:
        query = query.where(StudentApplication.campus_id == campus_id)
    if status_filter is not None:
        query = query.where(StudentApplication.status == status_filter)
    if academic_year_id is not None:
        query = query.where(StudentApplication.academic_year_id == academic_year_id)
    query = query.order_by(StudentApplication.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    return result.scalars().all()


async def submit_application(
    session: AsyncSession, application: StudentApplication
) -> StudentApplication:
    """Move DRAFT -> SUBMITTED and stamp the real submission time.

    `submitted_at` is set here and nowhere else, so it always means "the family
    asked the school to consider this child" rather than "a row was created".
    """
    if application.status != ApplicationStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only a DRAFT application can be submitted; this one is {application.status.value}.",
        )
    application.status = ApplicationStatus.SUBMITTED
    application.submitted_at = datetime.datetime.now(datetime.timezone.utc)
    application.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(application)
    await session.commit()
    await session.refresh(application)
    return application


async def set_application_status(
    session: AsyncSession,
    application: StudentApplication,
    new_status: ApplicationStatus,
) -> StudentApplication:
    if application.status in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This application is {application.status.value} and cannot be "
                "moved again. Create a new application instead."
            ),
        )
    application.status = new_status
    application.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(application)
    await session.commit()
    await session.refresh(application)
    return application


# ── Documents ──────────────────────────────────────────────────────────────


async def store_document(
    session: AsyncSession,
    *,
    application: StudentApplication,
    document_type: DocumentType,
    file: UploadFile,
    org_uuid: str,
    uploaded_by_user_id: Optional[int],
) -> ApplicationDocument:
    """Store a supporting document via the shared upload primitive.

    The returned filename carries a uuid4 prefix, so the stored object is not
    addressable from the application id alone.
    """
    directory = f"admissions/{application.application_number}/documents"
    stored_filename = await upload_file(
        file=file,
        directory=directory,
        type_of_dir="orgs",
        uuid=org_uuid,
        allowed_types=_ALLOWED_DOC_UPLOAD_TYPES,
        filename_prefix=document_type.value.lower(),
        max_size=_MAX_DOCUMENT_BYTES,
    )

    document = ApplicationDocument(
        application_id=application.id,  # type: ignore[arg-type]
        document_type=document_type,
        stored_filename=stored_filename,
        storage_directory=directory,
        original_filename=file.filename,
        verification_status=DocumentVerificationStatus.PENDING,
        uploaded_by_user_id=uploaded_by_user_id,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


async def read_document_bytes(
    document: ApplicationDocument, org_uuid: str
) -> bytes:
    """Fetch the stored bytes. Callers MUST authorise first."""
    return await read_content(
        directory=document.storage_directory,
        type_of_dir="orgs",
        uuid=org_uuid,
        file_and_format=document.stored_filename,
    )


async def list_documents(
    session: AsyncSession, application_id: int
) -> Sequence[ApplicationDocument]:
    result = await session.execute(
        select(ApplicationDocument)
        .where(ApplicationDocument.application_id == application_id)
        .order_by(ApplicationDocument.uploaded_at.desc())
    )
    return result.scalars().all()


async def get_document(
    session: AsyncSession, document_id: int
) -> Optional[ApplicationDocument]:
    result = await session.execute(
        select(ApplicationDocument).where(ApplicationDocument.id == document_id)
    )
    return result.scalars().first()


async def verify_document(
    session: AsyncSession,
    document: ApplicationDocument,
    *,
    new_status: DocumentVerificationStatus,
    verified_by_user_id: int,
    rejection_reason: Optional[str] = None,
) -> ApplicationDocument:
    """Record a verification decision against the AUTHENTICATED checker.

    A rejection without a reason leaves the family unable to act, so it is
    refused. Moving back to PENDING clears the verifier, because a document
    awaiting check must never carry one.
    """
    if new_status == DocumentVerificationStatus.REJECTED and not (rejection_reason or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A rejected document needs a reason so the family knows what to resubmit.",
        )

    document.verification_status = new_status
    if new_status == DocumentVerificationStatus.PENDING:
        document.verified_by_user_id = None
        document.verified_at = None
        document.rejection_reason = None
    else:
        document.verified_by_user_id = verified_by_user_id
        document.verified_at = datetime.datetime.now(datetime.timezone.utc)
        document.rejection_reason = (
            rejection_reason if new_status == DocumentVerificationStatus.REJECTED else None
        )

    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


def evaluate_document_completeness(
    documents: Sequence[ApplicationDocument],
) -> Tuple[bool, List[DocumentType]]:
    """Which required documents are still outstanding.

    Only a VERIFIED document counts. An uploaded-but-unchecked birth
    certificate is not evidence the school has verified anything, and counting
    it would let an application look complete on the strength of a file nobody
    opened.
    """
    verified_types = {
        d.document_type
        for d in documents
        if d.verification_status == DocumentVerificationStatus.VERIFIED
    }
    missing = [t for t in REQUIRED_DOCUMENT_TYPES if t not in verified_types]
    return (len(missing) == 0, missing)


# ── Assessments ────────────────────────────────────────────────────────────


async def schedule_assessment(
    session: AsyncSession,
    *,
    application_id: int,
    assessment_name: str,
    scheduled_for: Optional[datetime.datetime],
    venue: Optional[str],
) -> ApplicationAssessment:
    """Schedule an assessment. Score and outcome stay NULL until it is sat."""
    assessment = ApplicationAssessment(
        application_id=application_id,
        assessment_name=assessment_name.strip(),
        scheduled_for=scheduled_for,
        venue=venue,
    )
    session.add(assessment)
    await session.commit()
    await session.refresh(assessment)
    return assessment


async def get_assessment(
    session: AsyncSession, assessment_id: int
) -> Optional[ApplicationAssessment]:
    result = await session.execute(
        select(ApplicationAssessment).where(ApplicationAssessment.id == assessment_id)
    )
    return result.scalars().first()


async def list_assessments(
    session: AsyncSession, application_id: int
) -> Sequence[ApplicationAssessment]:
    result = await session.execute(
        select(ApplicationAssessment)
        .where(ApplicationAssessment.application_id == application_id)
        .order_by(ApplicationAssessment.created_at.desc())
    )
    return result.scalars().all()


async def record_assessment_result(
    session: AsyncSession,
    assessment: ApplicationAssessment,
    *,
    outcome: AssessmentOutcome,
    score: Optional[float],
    max_score: Optional[float],
    assessor_notes: Optional[str],
    assessed_by_user_id: int,
) -> ApplicationAssessment:
    """Record a result against the AUTHENTICATED assessor.

    A NOT_ATTENDED outcome must not carry a score: writing 0 for a child who
    never sat the paper would misrepresent them as having failed it.
    """
    if outcome == AssessmentOutcome.NOT_ATTENDED and score is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A NOT_ATTENDED assessment cannot carry a score -- an applicant "
                "who did not sit the paper did not score zero on it."
            ),
        )
    if score is not None and max_score is not None and score > max_score:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Score cannot exceed the maximum score.",
        )

    assessment.outcome = outcome
    assessment.score = score
    assessment.max_score = max_score
    assessment.assessor_notes = assessor_notes
    assessment.assessed_by_user_id = assessed_by_user_id
    assessment.assessed_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(assessment)
    await session.commit()
    await session.refresh(assessment)
    return assessment


# ── Decisions ──────────────────────────────────────────────────────────────


async def record_decision(
    session: AsyncSession,
    *,
    application: StudentApplication,
    decision: AdmissionDecision,
    reason: str,
    decided_by_user_id: int,
) -> AdmissionDecisionRecord:
    """Append a decision and move the application to match it.

    Append-only: a reversed decision adds a row rather than editing one, so the
    trail shows what was decided, by whom, and when -- which is the whole point
    of being able to answer a challenge months later.
    """
    if not reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An admission decision must record a reason.",
        )

    record = AdmissionDecisionRecord(
        application_id=application.id,  # type: ignore[arg-type]
        decision=decision,
        reason=reason.strip(),
        decided_by_user_id=decided_by_user_id,
    )
    session.add(record)

    if decision == AdmissionDecision.OFFERED:
        application.status = ApplicationStatus.OFFERED
    elif decision == AdmissionDecision.REJECTED:
        application.status = ApplicationStatus.REJECTED
    # WAITLISTED deliberately leaves the status alone: a waitlisted family is
    # still under review, and overwriting the status would lose where they
    # actually are in the process.

    application.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(application)

    await session.commit()
    await session.refresh(record)
    return record


async def list_decisions(
    session: AsyncSession, application_id: int
) -> Sequence[AdmissionDecisionRecord]:
    result = await session.execute(
        select(AdmissionDecisionRecord)
        .where(AdmissionDecisionRecord.application_id == application_id)
        .order_by(AdmissionDecisionRecord.decided_at.desc())
    )
    return result.scalars().all()
