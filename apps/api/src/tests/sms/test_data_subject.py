"""Data-subject access and erasure.

The fault these cover: `export_user_data` was labelled "Full GDPR data export"
and touched no `sms_` table, so a family asking what the school held about
their child received LMS course trails and nothing else. That is worse than no
export, because it looks like compliance.

The subtle requirement is the confidentiality one. `routers/sms_counseling.py`
enforces 404-never-403 so a non-psychologist can never infer that a counselling
record exists. An export is the obvious way round that, and reporting
"withheld: 2 counselling sessions" leaks exactly what the 404 protects. So the
tests below assert ABSENCE, not refusal.
"""

import datetime

import pytest
from types import SimpleNamespace

from src.db.ai_oversight import AITutorTranscript
from src.db.sms_attendance import StudentAttendance
from src.db.sms_counseling import CounselingSession
from src.services.sms.data_subject import (
    _CLINICAL,
    _GENERAL,
    _LEAD,
    _SAFEGUARDING_INCIDENTS,
    _STAFF_BY_PROFILE,
    collect_school_record,
    erase_school_record,
)


def _subject(user_id=901, uuid="user_dsr_901", email="dsr901@example.com"):
    """A subject stand-in. collect/erase only read id, user_uuid and email."""
    return SimpleNamespace(id=user_id, user_uuid=uuid, email=email)


# ---------------------------------------------------------------------------
# Spec integrity. These catch a mis-keyed column BEFORE it silently omits a
# whole module from a subject-access response -- the exact failure mode that
# made the original export look complete while returning nothing.
# ---------------------------------------------------------------------------

def test_every_spec_column_exists_on_its_model():
    bad = []
    for group in (_GENERAL, _LEAD, _STAFF_BY_PROFILE, _CLINICAL, _SAFEGUARDING_INCIDENTS):
        for spec in group:
            if not hasattr(spec.model, spec.column):
                bad.append(f"{spec.key}: {spec.model.__name__}.{spec.column}")
            for field in spec.scrub_fields:
                if not hasattr(spec.model, field):
                    bad.append(f"{spec.key}: scrub {spec.model.__name__}.{field}")
    assert not bad, f"Spec references columns that do not exist: {bad}"


def test_academic_and_safeguarding_records_are_not_marked_erasable():
    """Deleting a grade corrupts a cohort aggregate; deleting a safeguarding
    record breaches a statutory duty. Neither may ever be flagged erasable."""
    protected = {
        "grades", "report_cards", "exam_results", "attendance", "enrolments",
        "fee_vouchers", "counselling_sessions", "counselling_activity",
        "ai_safety_incidents", "salary_slips",
    }
    for group in (_GENERAL, _LEAD, _STAFF_BY_PROFILE, _CLINICAL, _SAFEGUARDING_INCIDENTS):
        for spec in group:
            if spec.key in protected:
                assert not spec.erasable, f"{spec.key} must never be erasable"
                assert spec.retention_basis, f"{spec.key} must state a retention basis"


def test_every_non_erasable_table_states_a_basis():
    """'Some data is retained' is not an answer. Each one must say why."""
    for group in (_GENERAL, _LEAD, _STAFF_BY_PROFILE, _CLINICAL, _SAFEGUARDING_INCIDENTS):
        for spec in group:
            if not spec.erasable and not spec.scrub_fields:
                assert spec.retention_basis, f"{spec.key} retains without a stated basis"


# ---------------------------------------------------------------------------
# Behaviour against a real session.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subject_with_no_records_exports_empty_not_error(db):
    record = await collect_school_record(
        db, _subject(user_id=99001, uuid="nobody", email="nobody@example.com"),
        include_clinical=False, include_safeguarding=False,
    )
    assert record == {}, "A subject with no records must export empty, not raise"


@pytest.mark.asyncio
async def test_export_includes_school_data_when_it_exists(db):
    subject = _subject(user_id=90210)
    db.add(StudentAttendance(
        student_id=90210, section_id=1, date=datetime.date(2026, 3, 2),
        status="PRESENT", org_id=1,
    ))
    await db.commit()

    record = await collect_school_record(
        db, subject, include_clinical=False, include_safeguarding=False
    )
    assert "attendance" in record, "Attendance must appear in a subject-access export"
    assert len(record["attendance"]) == 1


@pytest.mark.asyncio
async def test_counselling_is_absent_not_refused_for_an_unauthorised_caller(db):
    """The crux. A caller without clinical authority must get a response
    indistinguishable from a child who has no counselling record at all."""
    subject = _subject(user_id=90310)
    db.add(CounselingSession(
        student_id=90310, psychologist_id="psy-1",
        session_date=datetime.datetime(2026, 3, 2, tzinfo=datetime.timezone.utc),
        duration_minutes=30, notes="session notes",
    ))
    await db.commit()

    without = await collect_school_record(
        db, subject, include_clinical=False, include_safeguarding=False
    )
    assert "counselling_sessions" not in without
    # And nothing anywhere in the payload hints that something was held back.
    assert "withheld" not in str(without).lower()
    assert "counsel" not in str(without).lower()

    with_auth = await collect_school_record(
        db, subject, include_clinical=True, include_safeguarding=True
    )
    assert "counselling_sessions" in with_auth, "A psychologist must see the record"


@pytest.mark.asyncio
async def test_erasure_removes_transcripts_and_retains_academic_records(db):
    subject = _subject(user_id=90410)
    db.add(AITutorTranscript(
        student_id=90410, org_id=1, prompt="hello", outcome="answered",
    ))
    db.add(StudentAttendance(
        student_id=90410, section_id=1, date=datetime.date(2026, 3, 3),
        status="ABSENT", org_id=1,
    ))
    await db.commit()

    outcome = await erase_school_record(
        db, subject, include_clinical=False, include_safeguarding=False
    )

    assert outcome["erased"].get("tutor_transcripts") == 1, "Transcripts are erasable"

    retained_keys = {r["category"] for r in outcome["retained"]}
    assert "attendance" in retained_keys, "Attendance must be retained, not deleted"

    # And it must actually still be there -- a claim of retention that deleted
    # the row would be the mirror of the bug this module exists to fix.
    remaining = await collect_school_record(
        db, subject, include_clinical=False, include_safeguarding=False
    )
    assert "attendance" in remaining
    assert "tutor_transcripts" not in remaining


@pytest.mark.asyncio
async def test_retention_statement_is_itemised_with_a_basis(db):
    subject = _subject(user_id=90510)
    db.add(StudentAttendance(
        student_id=90510, section_id=1, date=datetime.date(2026, 3, 4),
        status="PRESENT", org_id=1,
    ))
    await db.commit()

    outcome = await erase_school_record(
        db, subject, include_clinical=False, include_safeguarding=False
    )
    assert outcome["retained"], "Retention must be itemised, not summarised"
    for item in outcome["retained"]:
        assert item["category"] and item["basis"], "Each retained item needs a basis"
        assert len(item["basis"]) > 30, "A basis must be a real reason, not a label"


@pytest.mark.asyncio
async def test_erasure_never_reports_counselling_to_an_unauthorised_caller(db):
    """Retention statements are the other existence leak: listing
    'counselling_sessions retained' tells the caller they exist."""
    subject = _subject(user_id=90610)
    db.add(CounselingSession(
        student_id=90610, psychologist_id="psy-2",
        session_date=datetime.datetime(2026, 3, 5, tzinfo=datetime.timezone.utc),
        duration_minutes=45, notes="session notes",
    ))
    await db.commit()

    outcome = await erase_school_record(
        db, subject, include_clinical=False, include_safeguarding=False
    )
    assert "counsel" not in str(outcome).lower()
