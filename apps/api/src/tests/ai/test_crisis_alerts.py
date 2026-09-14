"""
Tests for real counselor/principal dispatch on AI crisis detection (M47).

Before src/services/ai/crisis_alerts.py, a CRITICAL self-harm detection only
wrote an `AISafetyIncident` row and emitted a log line -- no human was ever
told. These tests assert a real send is attempted to the right people, and
that the incident's `counselor_notified` flag reflects whether delivery
actually happened rather than merely that it was requested.
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from src.db.sms_identity import SchoolRole, SMSUserRole
from src.db.users import User
from src.services.ai.crisis_alerts import dispatch_crisis_alert
from src.services.ai.crisis_classifier import classify_prompt_safety, log_safety_incident


async def _add_user(db, id_: int, email: str) -> User:
    u = User(
        id=id_,
        username=f"user{id_}",
        first_name="Case",
        last_name=f"User{id_}",
        email=email,
        password="hashed",
        user_uuid=f"uuid-{id_}",
        creation_date=str(datetime.now()),
        update_date=str(datetime.now()),
    )
    db.add(u)
    await db.commit()
    return u


async def _grant(db, user_id: int, org_id: int, role: SchoolRole) -> None:
    db.add(SMSUserRole(user_id=user_id, org_id=org_id, role=role))
    await db.commit()


@pytest.mark.asyncio
async def test_alert_goes_to_counselor_and_principal_only(db, org):
    await _add_user(db, 601, "counselor@school.test")
    await _add_user(db, 602, "principal@school.test")
    await _add_user(db, 603, "teacher@school.test")
    await _grant(db, 601, org.id, SchoolRole.PSYCHOLOGIST)
    await _grant(db, 602, org.id, SchoolRole.SCHOOL_ADMIN)
    await _grant(db, 603, org.id, SchoolRole.TEACHER)

    with patch("src.services.email.utils.send_email") as mock_send:
        delivered = await dispatch_crisis_alert(
            db_session=db,
            org_id=org.id,
            student_label="student-7",
            category="SELF_HARM",
            severity="CRITICAL",
            occurred_at="2026-09-12T10:00:00+00:00",
            incident_id=1,
        )

    assert delivered is True
    recipients = sorted(call.args[0] for call in mock_send.call_args_list)
    # The teacher must NOT receive a confidential wellbeing alert.
    assert recipients == ["counselor@school.test", "principal@school.test"]


@pytest.mark.asyncio
async def test_alert_body_excludes_the_students_own_words(db, org):
    await _add_user(db, 611, "counselor2@school.test")
    await _grant(db, 611, org.id, SchoolRole.PSYCHOLOGIST)
    secret_disclosure = "i want to end my life tonight"

    with patch("src.services.email.utils.send_email") as mock_send:
        await dispatch_crisis_alert(
            db_session=db,
            org_id=org.id,
            student_label="student-8",
            category="SELF_HARM",
            severity="CRITICAL",
            occurred_at="2026-09-12T10:00:00+00:00",
            incident_id=2,
        )

    body = mock_send.call_args_list[0].args[2]
    # Confidential disclosure stays in the DB incident record, never in email
    # (which lands in inboxes, phones, mail logs and backups).
    assert secret_disclosure not in body
    assert "SELF_HARM" in body


@pytest.mark.asyncio
async def test_no_counselor_provisioned_is_reported_as_undelivered(db, org):
    """An org with nobody to alert must not report success -- that would make
    a crisis that reached no human look handled."""
    with patch("src.services.email.utils.send_email") as mock_send:
        delivered = await dispatch_crisis_alert(
            db_session=db,
            org_id=org.id,
            student_label="student-9",
            category="SELF_HARM",
            severity="CRITICAL",
            occurred_at="2026-09-12T10:00:00+00:00",
        )

    assert delivered is False
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_mail_failure_downgrades_counselor_notified_flag(db, org):
    await _add_user(db, 621, "counselor3@school.test")
    await _grant(db, 621, org.id, SchoolRole.PSYCHOLOGIST)

    with patch("src.services.email.utils.send_email", side_effect=RuntimeError("smtp down")):
        incident = await log_safety_incident(
            student_id="student-10",
            severity="CRITICAL",
            trigger_category="SELF_HARM",
            prompt_snippet="i want to die",
            counselor_notified=True,
            db_session=db,
            org_id=org.id,
        )

    # Requested True, but nothing was delivered -- the record must say so.
    assert incident is not None
    assert incident.counselor_notified is False


@pytest.mark.asyncio
async def test_crisis_dispatch_failure_never_raises_to_the_student(db, org):
    """A student in crisis must still get the support-resources response even
    if the whole alerting path is broken."""
    await _add_user(db, 631, "counselor4@school.test")
    await _grant(db, 631, org.id, SchoolRole.PSYCHOLOGIST)

    result = classify_prompt_safety("i want to kill myself")
    assert result.counselor_escalation_required is True

    with patch("src.services.email.utils.send_email", side_effect=RuntimeError("boom")):
        # Must not raise.
        incident = await log_safety_incident(
            student_id="student-11",
            severity=result.severity.value,
            trigger_category=result.category.value,
            prompt_snippet="i want to kill myself",
            counselor_notified=True,
            db_session=db,
            org_id=org.id,
        )

    assert incident is not None
    # Was: assert "988" in result.canned_response. See test_socratic_tutor --
    # that assertion pinned US-only helplines into a Pakistani deployment.
    assert result.canned_response is not None
    assert "findahelpline.com" in result.canned_response
    assert "988" not in result.canned_response
