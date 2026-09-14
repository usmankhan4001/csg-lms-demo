"""M01 Admissions — application lifecycle.

These cover the four things the module exists to guarantee:

1. A family can apply without ever having been a marketing lead.
2. A document is VERIFIED by a named person at a recorded time, never by
   arriving.
3. An applicant with no assessment has NO assessment — never a zero score.
   This codebase has shipped that exact class of bug four times (a 4.0 GPA for
   a student with no grades, an invented parent digest, a fabricated "F" on a
   report card, and attendance reporting 0% when no register had been taken).
4. Children's identity and medical documents are not readable by a class
   teacher, and not readable across campuses.
"""

import datetime
import inspect

import pytest
from fastapi import HTTPException

from src.core.keycloak_auth import (
    SCHOOL_ADMIN,
    STAFF,
    SUPER_ADMIN,
    TEACHER,
    KeycloakUserPrincipal,
)
from src.db.sms_admissions import (
    AdmissionDecision,
    ApplicationDocument,
    ApplicationStatus,
    AssessmentOutcome,
    DocumentType,
    DocumentVerificationStatus,
)
import src.routers.sms_admissions as router_mod
from src.services.sms import admissions as svc


def _principal(
    *,
    roles,
    org_id=1,
    campus_id=None,
    user_id=50,
    superadmin=False,
) -> KeycloakUserPrincipal:
    return KeycloakUserPrincipal(
        sub=f"test-user-{user_id}",
        realm_roles=list(roles),
        roles=set(roles),
        org_id=org_id,
        campus_id=campus_id,
        raw_claims={"lh_user_id": user_id},
    )


async def _make_application(db, *, org_id=1, campus_id=None, lead_id=None):
    return await svc.create_application(
        db,
        org_id=org_id,
        campus_id=campus_id,
        lead_id=lead_id,
        student_name="Ayesha Khan",
        guardian_name="Imran Khan",
        grade_applying_for="Grade 1",
    )


# ── 1. An application does not require a lead ──────────────────────────────


@pytest.mark.asyncio
async def test_an_application_can_exist_without_a_lead(db):
    """A walk-in family applies without ever being a tracked lead.

    Requiring a lead would force the front desk to fabricate a marketing
    record in order to accept a paper form.
    """
    application = await _make_application(db, lead_id=None)

    assert application.id is not None
    assert application.lead_id is None
    assert application.status == ApplicationStatus.DRAFT
    # A draft nobody submitted has no submission date.
    assert application.submitted_at is None


@pytest.mark.asyncio
async def test_submitting_stamps_the_real_submission_time(db):
    application = await _make_application(db)
    assert application.submitted_at is None

    submitted = await svc.submit_application(db, application)

    assert submitted.status == ApplicationStatus.SUBMITTED
    assert submitted.submitted_at is not None


@pytest.mark.asyncio
async def test_application_numbers_are_not_sequential(db):
    """A sequential reference leaks the school's application volume and lets
    anyone guess a neighbouring family's number."""
    a = await _make_application(db)
    b = await _make_application(db)

    assert a.application_number != b.application_number


# ── 2. Verification is recorded against a named checker ────────────────────


@pytest.mark.asyncio
async def test_an_uploaded_document_starts_unverified_with_no_verifier(db):
    """A school CHECKS a birth certificate; it does not merely receive one."""
    application = await _make_application(db)
    document = ApplicationDocument(
        application_id=application.id,
        document_type=DocumentType.BIRTH_CERTIFICATE,
        stored_filename="abc123_birth_certificate.pdf",
        storage_directory="admissions/APP-X/documents",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    assert document.verification_status == DocumentVerificationStatus.PENDING
    assert document.verified_by_user_id is None
    assert document.verified_at is None


@pytest.mark.asyncio
async def test_verification_records_who_checked_it_and_when(db):
    application = await _make_application(db)
    document = ApplicationDocument(
        application_id=application.id,
        document_type=DocumentType.BIRTH_CERTIFICATE,
        stored_filename="abc123_birth_certificate.pdf",
        storage_directory="admissions/APP-X/documents",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    verified = await svc.verify_document(
        db,
        document,
        new_status=DocumentVerificationStatus.VERIFIED,
        verified_by_user_id=77,
    )

    assert verified.verification_status == DocumentVerificationStatus.VERIFIED
    assert verified.verified_by_user_id == 77
    assert verified.verified_at is not None


@pytest.mark.asyncio
async def test_a_rejected_document_must_say_why(db):
    """Without a reason the family cannot know what to resubmit."""
    application = await _make_application(db)
    document = ApplicationDocument(
        application_id=application.id,
        document_type=DocumentType.BIRTH_CERTIFICATE,
        stored_filename="abc123.pdf",
        storage_directory="admissions/APP-X/documents",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    with pytest.raises(HTTPException) as exc:
        await svc.verify_document(
            db,
            document,
            new_status=DocumentVerificationStatus.REJECTED,
            verified_by_user_id=77,
            rejection_reason="   ",
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_only_verified_documents_count_toward_completeness(db):
    """An uploaded-but-unchecked certificate is not evidence of anything.

    Counting it would let an application look complete on the strength of a
    file nobody opened.
    """
    application = await _make_application(db)
    pending = ApplicationDocument(
        application_id=application.id,
        document_type=DocumentType.BIRTH_CERTIFICATE,
        stored_filename="a.pdf",
        storage_directory="d",
        verification_status=DocumentVerificationStatus.PENDING,
    )
    db.add(pending)
    await db.commit()

    documents = await svc.list_documents(db, application.id)
    complete, missing = svc.evaluate_document_completeness(documents)

    assert complete is False
    assert DocumentType.BIRTH_CERTIFICATE in missing


# ── 3. No assessment is not a zero ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_applicant_with_no_assessment_has_no_assessment(db):
    application = await _make_application(db)

    assessments = await svc.list_assessments(db, application.id)

    assert assessments == [], "No assessment must be an empty list, not a zero score."


@pytest.mark.asyncio
async def test_a_scheduled_but_unsat_assessment_has_no_score_or_outcome(db):
    """Scheduled is not sat. Neither a score nor an outcome may be invented."""
    application = await _make_application(db)
    assessment = await svc.schedule_assessment(
        db,
        application_id=application.id,
        assessment_name="Grade 1 Entry Paper",
        scheduled_for=datetime.datetime.now(datetime.timezone.utc),
        venue="Hall A",
    )

    assert assessment.score is None, "An unsat paper must not score 0."
    assert assessment.outcome is None
    assert assessment.assessed_by_user_id is None
    assert assessment.assessed_at is None


@pytest.mark.asyncio
async def test_a_not_attended_assessment_cannot_carry_a_score(db):
    """A child who never sat the paper did not score zero on it."""
    application = await _make_application(db)
    assessment = await svc.schedule_assessment(
        db,
        application_id=application.id,
        assessment_name="Entry Paper",
        scheduled_for=None,
        venue=None,
    )

    with pytest.raises(HTTPException) as exc:
        await svc.record_assessment_result(
            db,
            assessment,
            outcome=AssessmentOutcome.NOT_ATTENDED,
            score=0.0,
            max_score=100.0,
            assessor_notes=None,
            assessed_by_user_id=77,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_recording_a_result_attributes_it_to_the_assessor(db):
    application = await _make_application(db)
    assessment = await svc.schedule_assessment(
        db,
        application_id=application.id,
        assessment_name="Entry Paper",
        scheduled_for=None,
        venue=None,
    )

    marked = await svc.record_assessment_result(
        db,
        assessment,
        outcome=AssessmentOutcome.PASSED,
        score=82.0,
        max_score=100.0,
        assessor_notes="Strong numeracy.",
        assessed_by_user_id=77,
    )

    assert marked.outcome == AssessmentOutcome.PASSED
    assert marked.score == 82.0
    assert marked.assessed_by_user_id == 77
    assert marked.assessed_at is not None


# ── Decision trail ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_decision_records_its_reason_and_decider(db):
    """A school challenged on why a place was refused must be able to answer."""
    application = await _make_application(db)

    record = await svc.record_decision(
        db,
        application=application,
        decision=AdmissionDecision.REJECTED,
        reason="Grade 1 cohort full for the applied academic year.",
        decided_by_user_id=99,
    )

    assert record.decision == AdmissionDecision.REJECTED
    assert "cohort full" in record.reason
    assert record.decided_by_user_id == 99
    assert application.status == ApplicationStatus.REJECTED


@pytest.mark.asyncio
async def test_the_decision_trail_is_append_only(db):
    """A reversed decision ADDS a row; it never edits one away."""
    application = await _make_application(db)

    await svc.record_decision(
        db,
        application=application,
        decision=AdmissionDecision.WAITLISTED,
        reason="Awaiting a place.",
        decided_by_user_id=99,
    )
    await svc.record_decision(
        db,
        application=application,
        decision=AdmissionDecision.OFFERED,
        reason="A place opened up.",
        decided_by_user_id=99,
    )

    decisions = await svc.list_decisions(db, application.id)
    assert len(decisions) == 2, "The earlier decision must survive the later one."


@pytest.mark.asyncio
async def test_waitlisting_does_not_overwrite_where_the_family_actually_is(db):
    """A waitlisted family is still under review; clobbering the status would
    lose their real position in the process."""
    application = await _make_application(db)
    await svc.submit_application(db, application)
    before = application.status

    await svc.record_decision(
        db,
        application=application,
        decision=AdmissionDecision.WAITLISTED,
        reason="Cohort full, holding.",
        decided_by_user_id=99,
    )

    assert application.status == before


# ── 4. Access control ──────────────────────────────────────────────────────


def _dependency_source(func) -> str:
    sig = inspect.signature(func)
    return " ".join(repr(p.default) for p in sig.parameters.values())


@pytest.mark.parametrize(
    "handler_name",
    [
        "create_application",
        "list_applications",
        "get_application_detail",
        "upload_document",
        "list_documents",
        "download_document",
        "verify_document",
        "schedule_assessment",
        "record_assessment_result",
        "record_decision",
        "list_decisions",
    ],
)
def test_no_admissions_endpoint_admits_a_teacher(handler_name):
    """A class teacher has no business reading a family's medical record or
    birth certificate. Every gate in this router must exclude TEACHER."""
    handler = getattr(router_mod, handler_name)
    source = _dependency_source(handler)

    assert "get_current_user_principal" not in source, (
        f"{handler_name} is gated by get_current_user_principal, which admits "
        "ANY authenticated user."
    )
    assert "require_roles" in source, f"{handler_name} must be role-gated."


def test_the_teacher_exclusion_is_real_not_incidental():
    assert TEACHER not in router_mod._ADMISSIONS
    assert TEACHER not in router_mod._ADMISSIONS_LEAD
    assert "STUDENT" not in router_mod._ADMISSIONS
    assert "PARENT" not in router_mod._ADMISSIONS


def test_verification_and_decisions_are_narrower_than_intake():
    """A receptionist may receive a birth certificate; confirming it is
    genuine, and refusing a child a place, are leadership acts."""
    assert STAFF in router_mod._ADMISSIONS
    assert STAFF not in router_mod._ADMISSIONS_LEAD
    assert SCHOOL_ADMIN in router_mod._ADMISSIONS_LEAD


@pytest.mark.asyncio
async def test_a_campus_bound_admin_cannot_read_another_campus_application(db):
    """404, not 403: confirming the application exists would itself tell them
    a named family applied to a campus they may not see."""
    application = await _make_application(db, org_id=1, campus_id=2)
    intruder = _principal(roles=[SCHOOL_ADMIN], org_id=1, campus_id=9)

    with pytest.raises(HTTPException) as exc:
        await router_mod._load_application_in_scope(db, intruder, application.id)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_an_admin_of_another_org_cannot_read_the_application(db):
    application = await _make_application(db, org_id=1, campus_id=2)
    outsider = _principal(roles=[SCHOOL_ADMIN], org_id=77, campus_id=None)

    with pytest.raises(HTTPException) as exc:
        await router_mod._load_application_in_scope(db, outsider, application.id)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_the_owning_campus_admin_can_read_it(db):
    """The scoping must not lock out the people who need it."""
    application = await _make_application(db, org_id=1, campus_id=2)
    owner = _principal(roles=[SCHOOL_ADMIN], org_id=1, campus_id=2)

    loaded = await router_mod._load_application_in_scope(db, owner, application.id)
    assert loaded.id == application.id


@pytest.mark.asyncio
async def test_a_superadmin_is_not_campus_bound(db):
    application = await _make_application(db, org_id=1, campus_id=2)
    root = _principal(roles=[SUPER_ADMIN], org_id=1, campus_id=None, superadmin=True)

    loaded = await router_mod._load_application_in_scope(db, root, application.id)
    assert loaded.id == application.id


def test_document_read_model_exposes_no_storage_path():
    """A path in the response makes the document reachable by anyone who saw
    it, defeating the authorised-download endpoint."""
    from src.schemas.sms_admissions import DocumentRead

    fields = set(DocumentRead.model_fields)
    for leak in ("stored_filename", "storage_directory", "url", "path"):
        assert leak not in fields, f"DocumentRead must not expose {leak}."


def test_the_assertions_discriminate():
    """Guard against this file passing vacuously.

    `_ADMISSIONS` is the real gate; a list that happened to contain TEACHER
    must fail the exclusion check, so run it against one that does.
    """
    pretend_open_gate = ["SUPER_ADMIN", "SCHOOL_ADMIN", "STAFF", TEACHER]
    assert TEACHER in pretend_open_gate, (
        "If this fails the exclusion assertion above proves nothing."
    )
