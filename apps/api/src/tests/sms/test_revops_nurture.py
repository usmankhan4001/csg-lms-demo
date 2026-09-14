"""
Tests for the autonomous admissions nurture funnel and conversation memory.

Covers the three claims that matter, because each one is a promise made to a
real family:

1. Consent actually blocks outbound. A lead who opted out must not receive
   marketing, and the suppression must be visible rather than silent.
2. The scheduled job genuinely advances a sequence -- the drip engine produced
   stages for a long time that nothing ever sent.
3. Conversation memory is fed back, so a follow-up is not answered cold.
"""

import datetime
from unittest.mock import patch

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.revops_conversation import (
    LeadNurtureState,
    LeadOutboundTouch,
    TouchStatus,
    TurnDirection,
)
from src.db.sms_revops import AdmissionsLead, LeadSource, LeadStage
from src.services.ai.revops_conversation import load_history, record_turn
from src.services.ai.revops_nurture_runner import (
    advance_nurture_sequences,
    enrol_lead_in_sequence,
)

# A real campus record: these tests exercise consent and scheduling, not
# school identity. The drip engine now refuses to invent a campus name.
_REAL_CAMPUS = {"name": "Lighthouse Main Campus", "city": "Islamabad"}


def _email_configured():
    """Declare email available for tests that are about scheduling, not capability.

    The runner now resolves channel capability BEFORE attempting a send, so a
    deployment with no mail provider reports UNAVAILABLE rather than attempting
    a send that would fail with a confusing provider error. The test
    environment has no provider configured, so these scheduling tests must say
    "assume email works" to reach the code they are actually testing.
    """
    from src.services.sms.revops_channels import DeliveryRoute

    return patch(
        "src.services.ai.revops_nurture_runner.resolve_delivery_route",
        return_value=DeliveryRoute(channel="email", address="parent@example.com"),
    )


async def _make_lead(
    db: AsyncSession,
    *,
    email: str = "parent@example.com",
    email_consent: bool = True,
    whatsapp_consent: bool = True,
    stage: LeadStage = LeadStage.NEW_INQUIRY,
    created_days_ago: int = 5,
) -> AdmissionsLead:
    lead = AdmissionsLead(
        parent_name="Nadia Khan",
        student_name="Zara Khan",
        email=email,
        phone="+92-300-1234567",
        grade_applying_for="Grade 6",
        source=LeadSource.WEBSITE_FORM,
        stage=stage,
        email_consent=email_consent,
        whatsapp_consent=whatsapp_consent,
        created_at=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=created_days_ago),
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


async def _touches(db: AsyncSession, lead_id: int):
    res = await db.execute(
        select(LeadOutboundTouch).where(LeadOutboundTouch.lead_id == lead_id)
    )
    return list(res.scalars().all())


@pytest.mark.asyncio
async def test_consent_optout_blocks_outbound_and_is_recorded(db: AsyncSession):
    """An opted-out lead gets no marketing, and we can prove why."""
    lead = await _make_lead(db, email_consent=False, whatsapp_consent=False)
    await enrol_lead_in_sequence(db, lead, campus_info=_REAL_CAMPUS)

    with patch("src.services.email.utils.send_email") as mock_send:
        with patch(
            "src.core.events.database._async_session_factory",
            lambda: _SessionCtx(db),
        ):
            await advance_nurture_sequences()

    mock_send.assert_not_called()

    rows = await _touches(db, lead.id)
    assert len(rows) == 1
    assert rows[0].status == TouchStatus.CONSENT_BLOCKED
    # The reason must be legible, not merely inferable.
    assert "opted out" in (rows[0].detail or "").lower()


@pytest.mark.asyncio
async def test_scheduled_job_sends_due_stage_and_advances(db: AsyncSession):
    """The whole point: a due stage actually goes out and the sequence moves on."""
    lead = await _make_lead(db)
    state = await enrol_lead_in_sequence(db, lead, campus_info=_REAL_CAMPUS)
    assert state.last_stage_sent == 0

    with _email_configured(), patch("src.services.email.utils.send_email") as mock_send:
        with patch(
            "src.core.events.database._async_session_factory",
            lambda: _SessionCtx(db),
        ):
            counts = await advance_nurture_sequences()

    assert counts["sent"] == 1
    mock_send.assert_called_once()
    # Sent to the lead's real address, not a placeholder.
    assert mock_send.call_args.args[0] == "parent@example.com"

    await db.refresh(state)
    assert state.last_stage_sent == 1
    assert state.next_due_at is not None

    rows = await _touches(db, lead.id)
    assert rows[0].status == TouchStatus.SENT


@pytest.mark.asyncio
async def test_enrolled_lead_stops_receiving_nurture(db: AsyncSession):
    """A family who already enrolled must stop being marketed to."""
    lead = await _make_lead(db)
    state = await enrol_lead_in_sequence(db, lead, campus_info=_REAL_CAMPUS)

    lead.stage = LeadStage.ENROLLED
    db.add(lead)
    await db.commit()

    with patch("src.services.email.utils.send_email") as mock_send:
        with patch(
            "src.core.events.database._async_session_factory",
            lambda: _SessionCtx(db),
        ):
            counts = await advance_nurture_sequences()

    mock_send.assert_not_called()
    assert counts["stopped"] == 1
    await db.refresh(state)
    assert state.is_active is False
    assert "ENROLLED" in (state.stopped_reason or "")


@pytest.mark.asyncio
async def test_failed_send_is_recorded_not_swallowed(db: AsyncSession):
    """A delivery failure must leave evidence."""
    lead = await _make_lead(db)
    await enrol_lead_in_sequence(db, lead, campus_info=_REAL_CAMPUS)

    with _email_configured(), patch(
        "src.services.email.utils.send_email", side_effect=RuntimeError("smtp down")
    ):
        with patch(
            "src.core.events.database._async_session_factory",
            lambda: _SessionCtx(db),
        ):
            counts = await advance_nurture_sequences()

    assert counts["failed"] == 1
    rows = await _touches(db, lead.id)
    assert rows[0].status == TouchStatus.FAILED
    assert "smtp down" in (rows[0].detail or "")


@pytest.mark.asyncio
async def test_reenrolling_does_not_rewind_progress(db: AsyncSession):
    """Clicking the button twice must not re-send the welcome message."""
    lead = await _make_lead(db)
    state = await enrol_lead_in_sequence(db, lead, campus_info=_REAL_CAMPUS)
    state.last_stage_sent = 2
    db.add(state)
    await db.commit()

    again = await enrol_lead_in_sequence(db, lead, campus_info=_REAL_CAMPUS)
    assert again.last_stage_sent == 2


@pytest.mark.asyncio
async def test_conversation_memory_round_trips(db: AsyncSession):
    """History comes back oldest-first with both sides, so a reply has context."""
    lead = await _make_lead(db)

    await record_turn(
        db, lead_id=lead.id, direction=TurnDirection.INBOUND,
        message="What are your fees for Grade 6?", channel="email",
        detected_intent="fee_inquiry",
    )
    await record_turn(
        db, lead_id=lead.id, direction=TurnDirection.OUTBOUND,
        message="Our fee structure covers textbooks and activities.", channel="email",
        detected_intent="fee_inquiry",
    )

    history = await load_history(db, lead.id)
    assert len(history) == 2
    assert history[0]["role"] == "parent"
    assert "fees" in history[0]["message"].lower()
    assert history[1]["role"] == "admissions"


@pytest.mark.asyncio
async def test_sdr_reply_uses_stored_history(db: AsyncSession):
    """The endpoint must feed real history into the agent, not answer cold."""
    from src.routers.sms_revops import sdr_reply_to_lead

    lead = await _make_lead(db)
    await record_turn(
        db, lead_id=lead.id, direction=TurnDirection.INBOUND,
        message="Do you offer transport?", channel="email",
    )

    result = await sdr_reply_to_lead(
        lead_id=lead.id,
        payload={"message": "And what about the fees?", "channel": "email"},
        session=db,
        principal=None,
    )

    assert result["consent_blocked"] is False
    assert result["history_turns_used"] >= 1
    assert result["response"]

    # Both new turns persisted, so the next message sees three.
    history = await load_history(db, lead.id)
    assert len(history) == 3


@pytest.mark.asyncio
async def test_sdr_reply_blocked_for_optout_channel(db: AsyncSession):
    """An opted-out channel returns a stated block, never silent empty copy."""
    from src.routers.sms_revops import sdr_reply_to_lead

    lead = await _make_lead(db, whatsapp_consent=False)

    result = await sdr_reply_to_lead(
        lead_id=lead.id,
        payload={"message": "Hello", "channel": "whatsapp"},
        session=db,
        principal=None,
    )

    assert result["consent_blocked"] is True
    assert result["blocked_channel"] == "whatsapp"
    assert "opted out" in result["detail"].lower()


class _SessionCtx:
    """Async-context wrapper so the job can reuse the test's session.

    The job opens its own session via `_async_session_factory()` because it
    runs outside request scope; in tests that would be a second connection
    which cannot see uncommitted fixture state.
    """

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False
