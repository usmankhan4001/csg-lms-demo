"""M01 Admissions — the application lifecycle.

RevOps (`sms_revops.py`) is the LEAD funnel: an enquiry being nurtured toward
interest. This module is what happens once a family actually APPLIES —
a submitted application, supporting documents, an assessment, and a recorded
decision.

Before this existed a lead went straight from OFFER_SENT to ENROLLED with
nothing in between: no application record, no documents, no assessment, no
decision trail. A real school cannot admit a child that way. It has to be able
to answer "where is this application right now" at any moment, and "why was
this place given, or refused" months later.

Deliberately decoupled from AdmissionsLead: `lead_id` is nullable because a
family can walk in and apply without ever having been a tracked lead. Making
the lead mandatory would have forced the front desk to fabricate a marketing
record in order to accept a paper form.
"""

import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlmodel import Field, SQLModel


class ApplicationStatus(str, Enum):
    """Where an application actually is, from the office's point of view.

    Each value answers a different question a registrar gets asked, which is
    why they are not collapsed:

    - DRAFT / SUBMITTED separates "a family started a form" from "the school
      has been asked to consider a child". Only the second starts any clock.
    - DOCUMENTS_PENDING is its own state because it is the single most common
      reason an application stalls, and the action needed (chase the family)
      differs from every other waiting state.
    - UNDER_REVIEW / ASSESSMENT_SCHEDULED distinguish "with staff" from "with
      the family", which is what a stalled-application report has to show.
    - WITHDRAWN is separate from REJECTED. A family that changed its mind was
      not refused a place, and conflating them would misreport both the
      school's acceptance rate and its reason-for-refusal record.
    - OFFERED / ACCEPTED / ENROLLED track the closing steps. ENROLLED is set
      only once a real student record exists, so this field never claims a
      child is on roll before they are.
    """

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    DOCUMENTS_PENDING = "DOCUMENTS_PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    ASSESSMENT_SCHEDULED = "ASSESSMENT_SCHEDULED"
    ASSESSED = "ASSESSED"
    OFFERED = "OFFERED"
    ACCEPTED = "ACCEPTED"
    ENROLLED = "ENROLLED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class DocumentType(str, Enum):
    """Supporting evidence a school actually asks for."""

    BIRTH_CERTIFICATE = "BIRTH_CERTIFICATE"
    PRIOR_SCHOOL_RECORD = "PRIOR_SCHOOL_RECORD"
    TRANSFER_CERTIFICATE = "TRANSFER_CERTIFICATE"
    MEDICAL_RECORD = "MEDICAL_RECORD"
    IMMUNISATION_RECORD = "IMMUNISATION_RECORD"
    PHOTOGRAPH = "PHOTOGRAPH"
    GUARDIAN_ID = "GUARDIAN_ID"
    PROOF_OF_ADDRESS = "PROOF_OF_ADDRESS"
    OTHER = "OTHER"


class DocumentVerificationStatus(str, Enum):
    """A school CHECKS a birth certificate; it does not merely receive one.

    PENDING is the honest default for an uploaded file nobody has looked at:
    it must never read as verified. REJECTED carries a reason so a family can
    be told what to resubmit.
    """

    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class AssessmentOutcome(str, Enum):
    """Result of an admission assessment.

    There is deliberately no default: an applicant who has not sat an
    assessment has NO outcome, and the absence is represented by the row not
    existing or the field being NULL -- never by a placeholder value.
    """

    PASSED = "PASSED"
    FAILED = "FAILED"
    BORDERLINE = "BORDERLINE"
    NOT_ATTENDED = "NOT_ATTENDED"


class AdmissionDecision(str, Enum):
    """The school's decision, recorded with its reason."""

    OFFERED = "OFFERED"
    REJECTED = "REJECTED"
    WAITLISTED = "WAITLISTED"


class StudentApplication(SQLModel, table=True):
    """A family's application for a place.

    NOTE on indexes: every index here is declared in ``__table_args__`` with an
    explicit name, and NO column uses ``index=True``. SQLAlchemy auto-names a
    column index ``ix_<table>_<column>``; declaring both forms for one column
    makes ``create_all`` emit CREATE INDEX twice, which has already taken this
    API down once.
    """

    __tablename__ = "sms_student_application"
    __table_args__ = (
        Index("ix_sms_application_campus_status", "campus_id", "status"),
        Index("ix_sms_application_lead", "lead_id"),
        Index("ix_sms_application_year_grade", "academic_year_id", "grade_applying_for"),
        Index("ix_sms_application_number", "application_number"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # The reference a family quotes on the phone. Unique per school.
    application_number: str = Field(sa_column=Column(String(64), nullable=False))

    org_id: int = Field(sa_column=Column(Integer, nullable=False))
    campus_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    # Nullable on purpose: a walk-in family may never have been a lead.
    lead_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    student_name: str = Field(sa_column=Column(String(255), nullable=False))
    date_of_birth: Optional[datetime.date] = Field(
        default=None, sa_column=Column(Date, nullable=True)
    )
    guardian_name: str = Field(sa_column=Column(String(255), nullable=False))
    guardian_email: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    guardian_phone: Optional[str] = Field(default=None, sa_column=Column(String(50), nullable=True))

    grade_applying_for: str = Field(sa_column=Column(String(50), nullable=False))
    academic_year_id: Optional[int] = Field(default=None, sa_column=Column(Integer, nullable=True))

    status: ApplicationStatus = Field(
        default=ApplicationStatus.DRAFT,
        sa_column=Column(
            SAEnum(ApplicationStatus, name="sms_application_status", native_enum=False),
            nullable=False,
            default=ApplicationStatus.DRAFT,
        ),
    )

    # Set when the family actually submits, NOT at row creation. A DRAFT that
    # was never submitted has no submission date, and reporting must not
    # pretend otherwise.
    submitted_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # Populated only once provisioning creates a real student user.
    enrolled_student_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )

    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ApplicationDocument(SQLModel, table=True):
    """A supporting document, and the record of it being checked.

    The stored file itself lives under the org's content directory with a
    uuid4-prefixed filename (see ``services/sms/admissions.py``), so it is not
    reachable by guessing. This row holds only the pointer and the
    verification state; nothing here is publicly addressable.
    """

    __tablename__ = "sms_application_document"
    __table_args__ = (
        Index("ix_sms_appdoc_application", "application_id"),
        Index("ix_sms_appdoc_status", "verification_status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(sa_column=Column(Integer, nullable=False))

    document_type: DocumentType = Field(
        sa_column=Column(
            SAEnum(DocumentType, name="sms_application_document_type", native_enum=False),
            nullable=False,
        ),
    )

    # Storage pointer. `stored_filename` carries a uuid4 prefix from
    # upload_file(), so it is unguessable; `directory` is org-scoped.
    stored_filename: str = Field(sa_column=Column(String(512), nullable=False))
    storage_directory: str = Field(sa_column=Column(String(512), nullable=False))
    original_filename: Optional[str] = Field(
        default=None, sa_column=Column(String(512), nullable=True)
    )

    verification_status: DocumentVerificationStatus = Field(
        default=DocumentVerificationStatus.PENDING,
        sa_column=Column(
            SAEnum(
                DocumentVerificationStatus,
                name="sms_application_doc_verification",
                native_enum=False,
            ),
            nullable=False,
            default=DocumentVerificationStatus.PENDING,
        ),
    )
    # Who checked it, and when. Both NULL while PENDING -- an unverified
    # document must never carry a verifier.
    verified_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    verified_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    rejection_reason: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    uploaded_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    uploaded_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ApplicationAssessment(SQLModel, table=True):
    """A scheduled assessment and, once sat, its result.

    `score` and `outcome` are both nullable and stay NULL until the assessment
    is actually marked. A scheduled-but-unsat assessment reports as unsat --
    never as zero, and never as failed.
    """

    __tablename__ = "sms_application_assessment"
    __table_args__ = (
        Index("ix_sms_appassess_application", "application_id"),
        Index("ix_sms_appassess_scheduled", "scheduled_for"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(sa_column=Column(Integer, nullable=False))

    assessment_name: str = Field(sa_column=Column(String(255), nullable=False))
    scheduled_for: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    venue: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))

    # NULL until marked. See class docstring.
    score: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    max_score: Optional[float] = Field(default=None, sa_column=Column(Float, nullable=True))
    outcome: Optional[AssessmentOutcome] = Field(
        default=None,
        sa_column=Column(
            SAEnum(AssessmentOutcome, name="sms_assessment_outcome", native_enum=False),
            nullable=True,
        ),
    )
    assessor_notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    assessed_by_user_id: Optional[int] = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    assessed_at: Optional[datetime.datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AdmissionDecisionRecord(SQLModel, table=True):
    """Append-only trail of admission decisions.

    A school challenged on why a place was refused must be able to answer, so
    this is never updated or deleted -- a changed mind adds a row. The reason
    is REQUIRED: a decision without a recorded rationale is exactly what this
    table exists to prevent.
    """

    __tablename__ = "sms_admission_decision"
    __table_args__ = (
        Index("ix_sms_admdecision_application", "application_id"),
        Index("ix_sms_admdecision_decided_at", "decided_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(sa_column=Column(Integer, nullable=False))

    decision: AdmissionDecision = Field(
        sa_column=Column(
            SAEnum(AdmissionDecision, name="sms_admission_decision_kind", native_enum=False),
            nullable=False,
        ),
    )
    reason: str = Field(sa_column=Column(Text, nullable=False))

    # Attributed to the AUTHENTICATED caller, never a client-supplied id --
    # the same rule applied to grade attribution and live-class host tokens
    # elsewhere in this codebase after both were found forgeable.
    decided_by_user_id: int = Field(sa_column=Column(Integer, nullable=False))
    decided_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
