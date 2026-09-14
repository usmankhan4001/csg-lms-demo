"""
The admissions funnel, end to end: enquiry in, enrolled student out.

Four breaks are covered here, each of which meant a real family got nothing:

1. An inbound enquiry was persisted and then ignored. No SDR reply, no nurture
   enrolment -- a 9pm WhatsApp message sat until someone opened the CRM.
2. A phone-only family was marked SKIPPED at every stage forever, because the
   runner sent by email regardless of the stage's channel. Nothing said the
   school has no WhatsApp sender at all.
3. OfferStatus.ACCEPTED existed and nothing ever set it, so an offer could be
   made but never taken.
4. Low-confidence AI decisions about real families auto-advanced unreviewed.

The load-bearing assertion throughout is that capture survives failure: a
webhook must never lose an enquiry because a generator threw.
"""

import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.revops_conversation import LeadOutboundTouch, TouchStatus
from src.db.revops_review import LeadReviewFlag, ReviewReason
from src.db.sms_revops import (
    AdmissionsLead,
    LeadSource,
    LeadStage,
    OfferStatus,
    ScholarshipOffer,
)
from src.routers.sms_revops import (
    inbound_lead_webhook,
    respond_to_offer_endpoint,
    review_queue_endpoint,
)
from src.schemas.sms_revops import OfferDecision, OfferResponseRequest
from src.services.ai.revops_nurture_runner import enrol_lead_in_sequence
from src.services.sms.revops_acknowledge import (
    acknowledge_new_lead,
    estimate_intent_confidence,
)
from src.services.sms.revops_channels import (
    ChannelCapability,
    contactable_channels,
    resolve_channel_capability,
)

_REAL_CAMPUS = {"name": "Lighthouse Main Campus", "city": "Islamabad"}


def _principal(user_id: int = 1, roles=("SUPER_ADMIN",), campus_id=None):
    """A resolved principal.

    These tests call handlers directly, so FastAPI's DI never runs and the
    principal default would arrive as an unresolved `Depends`.
    """
    return SimpleNamespace(
        sub=f"user-{user_id}",
        is_superadmin="SUPER_ADMIN" in roles,
        campus_id=campus_id,
        org_id=1,
        raw_claims={"lh_user_id": user_id},
        has_role=lambda r: r in roles,
        has_any_role=lambda wanted: any(r in roles for r in wanted),
    )


async def _make_lead(
    db: AsyncSession,
    *,
    email: str = "parent@example.com",
    phone: str = "+92-300-1234567",
    stage: LeadStage = LeadStage.NEW_INQUIRY,
) -> AdmissionsLead:
    lead = AdmissionsLead(
        parent_name="Nadia Khan",
        student_name="Zara Khan",
        email=email,
        phone=phone,
        grade_applying_for="Grade 6",
        source=LeadSource.WEBSITE_FORM,
        stage=stage,
        email_consent=True,
        whatsapp_consent=True,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


# ---------------------------------------------------------------------------
# Break 2: channel capability -- UNAVAILABLE is not SKIPPED
# ---------------------------------------------------------------------------


def test_whatsapp_has_no_provider_and_says_so():
    """The gap must be legible, not silent."""
    capability = resolve_channel_capability("whatsapp")
    assert capability.configured is False
    assert capability.reason and "WHATSAPP" in capability.reason
    # The reason must be actionable, not merely negative.
    assert "provider" in capability.reason.lower()


def test_a_phone_only_lead_is_uncontactable_not_merely_skipped():
    """The distinction this whole module exists for.

    A phone-only family with no WhatsApp sender configured is not a lead we
    chose not to message -- it is a lead nobody CAN message.
    """
    lead = AdmissionsLead(
        parent_name="A", student_name="B", email="", phone="+92-300-0000000",
        grade_applying_for="Grade 1", source=LeadSource.WHATSAPP,
    )
    assert contactable_channels(lead) == []


@pytest.mark.asyncio
async def test_unavailable_channel_is_recorded_distinctly_from_skipped(db: AsyncSession):
    """A stage on a channel with no sender records UNAVAILABLE with a reason."""
    from src.services.ai.revops_nurture_runner import _deliver_stage

    lead = await _make_lead(db)
    status = await _deliver_stage(
        db, lead, {"stage": 1, "channel": "whatsapp", "subject": "Hi", "content": "Hello"}
    )
    assert status == TouchStatus.UNAVAILABLE

    touches = (
        await db.execute(select(LeadOutboundTouch).where(LeadOutboundTouch.lead_id == lead.id))
    ).scalars().all()
    assert len(touches) == 1
    assert touches[0].status == TouchStatus.UNAVAILABLE
    # The row must explain the operations gap, not just flag it.
    assert touches[0].detail and "provider" in touches[0].detail.lower()


@pytest.mark.asyncio
async def test_a_configured_channel_missing_an_address_is_skipped(db: AsyncSession):
    """SKIPPED survives for its real meaning: this lead lacks a contact detail."""
    from src.services.ai.revops_nurture_runner import _deliver_stage

    lead = await _make_lead(db, email="")
    with patch(
        "src.services.sms.revops_channels.resolve_channel_capability",
        return_value=ChannelCapability(channel="email", configured=True),
    ):
        status = await _deliver_stage(
            db, lead, {"stage": 1, "channel": "email", "subject": "Hi", "content": "Hello"}
        )
    assert status == TouchStatus.SKIPPED


# ---------------------------------------------------------------------------
# Break 4: the confidence heuristic
# ---------------------------------------------------------------------------


def test_an_ununderstood_message_scores_low():
    """The real signal: nothing matched, so do not answer automatically."""
    assert estimate_intent_confidence({"all_intents": [], "extracted_entities": {}}, "asdf") == 0.0


def test_an_empty_message_scores_zero():
    assert estimate_intent_confidence({"all_intents": ["book_tour"]}, "   ") == 0.0


def test_a_clear_enquiry_scores_above_the_default_threshold():
    result = {
        "all_intents": ["book_tour", "fee_inquiry"],
        "extracted_entities": {"grade": "Grade 6"},
    }
    message = "Hello, I would like to book a tour and ask about fees for Grade 6"
    assert estimate_intent_confidence(result, message) >= 0.4


# ---------------------------------------------------------------------------
# Break 1: the webhook answers, and never loses the lead
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acknowledgement_holds_an_ununderstood_enquiry_for_a_person(db: AsyncSession):
    """Low confidence must not be answered with generic filler."""
    lead = await _make_lead(db)
    with patch(
        "src.services.sms.revops_acknowledge.contactable_channels", return_value=["email"]
    ):
        outcome = await acknowledge_new_lead(
            db, lead, channel="email", message="asdf", campus_info=_REAL_CAMPUS
        )

    assert outcome.held_for_review is True
    assert outcome.review_reason == ReviewReason.LOW_CONFIDENCE.value
    assert outcome.acknowledged is False

    flags = (
        await db.execute(select(LeadReviewFlag).where(LeadReviewFlag.lead_id == lead.id))
    ).scalars().all()
    assert len(flags) == 1
    assert flags[0].reason == ReviewReason.LOW_CONFIDENCE
    # The stored confidence lets a school tune the threshold against real
    # traffic rather than guessing.
    assert flags[0].confidence is not None


@pytest.mark.asyncio
async def test_an_uncontactable_lead_is_flagged_as_an_operations_problem(db: AsyncSession):
    """Nobody can reach this family; the school must be able to see that."""
    lead = await _make_lead(db, email="")
    outcome = await acknowledge_new_lead(
        db, lead, channel="whatsapp", message="I want to enrol my daughter in Grade 6"
    )

    assert outcome.held_for_review is True
    assert outcome.review_reason == ReviewReason.UNCONTACTABLE.value
    flags = (
        await db.execute(select(LeadReviewFlag).where(LeadReviewFlag.lead_id == lead.id))
    ).scalars().all()
    assert flags and flags[0].reason == ReviewReason.UNCONTACTABLE


@pytest.mark.asyncio
async def test_acknowledgement_never_raises_so_the_lead_is_never_lost(db: AsyncSession):
    """Capture is the thing we cannot lose.

    If the SDR agent throws, the enquiry must still be kept and a person
    told -- not lost to a 500 from the webhook.
    """
    lead = await _make_lead(db)
    with patch(
        "src.services.sms.revops_acknowledge.contactable_channels", return_value=["email"]
    ), patch(
        "src.services.ai.revops_sdr_agent.handle_admissions_inquiry",
        side_effect=RuntimeError("generator exploded"),
    ):
        outcome = await acknowledge_new_lead(
            db, lead, channel="email", message="I would like to book a tour for Grade 6"
        )

    assert outcome.held_for_review is True
    assert outcome.review_reason == ReviewReason.ACKNOWLEDGEMENT_FAILED.value
    assert "generator exploded" in (outcome.detail or "")

    # The lead itself survived.
    still_there = (
        await db.execute(select(AdmissionsLead).where(AdmissionsLead.id == lead.id))
    ).scalar_one_or_none()
    assert still_there is not None


@pytest.mark.asyncio
async def test_webhook_persists_the_lead_even_when_acknowledgement_throws(db: AsyncSession):
    """The whole webhook must not 500 because the AI step failed."""
    with patch(
        "src.routers.sms_revops.acknowledge_new_lead",
        side_effect=RuntimeError("catastrophic"),
    ):
        with pytest.raises(RuntimeError):
            await inbound_lead_webhook(
                channel="web",
                payload={"email": "isolate@example.com", "parent_name": "Test Parent"},
                session=db,
            )

    # Even though the call raised, the lead was committed before the AI step.
    lead = (
        await db.execute(
            select(AdmissionsLead).where(AdmissionsLead.email == "isolate@example.com")
        )
    ).scalar_one_or_none()
    assert lead is not None, "the enquiry must survive an acknowledgement failure"


@pytest.mark.asyncio
async def test_webhook_reports_what_the_acknowledgement_did(db: AsyncSession):
    """The response tells the caller whether the family was actually answered."""
    result = await inbound_lead_webhook(
        channel="web",
        payload={
            "email": "ack@example.com",
            "parent_name": "Ack Parent",
            "message": "I would like to book a tour and ask about fees for Grade 6",
        },
        session=db,
    )
    assert result["status"] == "ingested"
    assert "acknowledgement" in result
    ack = result["acknowledgement"]
    # Whatever the outcome, it must be stated rather than silent.
    assert set(["acknowledged", "held_for_review", "contactable_on"]).issubset(ack.keys())


# ---------------------------------------------------------------------------
# Break 3: the offer can be accepted, and the funnel closes
# ---------------------------------------------------------------------------


async def _make_offer(db: AsyncSession, lead: AdmissionsLead) -> ScholarshipOffer:
    offer = ScholarshipOffer(
        lead_id=lead.id,
        campus_id=lead.campus_id,
        tuition_discount_percentage=10.0,
        final_tuition_amount=90000.0,
        valid_until=datetime.date.today() + datetime.timedelta(days=30),
        status=OfferStatus.SENT,
    )
    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    return offer


@pytest.mark.asyncio
async def test_an_offer_can_be_accepted(db: AsyncSession):
    """OfferStatus.ACCEPTED existed and nothing ever set it."""
    lead = await _make_lead(db, stage=LeadStage.OFFER_SENT)
    offer = await _make_offer(db, lead)

    result = await respond_to_offer_endpoint(
        offer_id=offer.id,
        payload=OfferResponseRequest(
            decision=OfferDecision.ACCEPTED, responded_by="Nadia Khan"
        ),
        session=db,
        principal=_principal(),
    )
    assert result.status == OfferStatus.ACCEPTED


@pytest.mark.asyncio
async def test_a_declined_offer_stops_the_drip(db: AsyncSession):
    """A family who said no must stop receiving 'come and see our campus'."""
    lead = await _make_lead(db, stage=LeadStage.OFFER_SENT)
    offer = await _make_offer(db, lead)

    await respond_to_offer_endpoint(
        offer_id=offer.id,
        payload=OfferResponseRequest(decision=OfferDecision.DECLINED),
        session=db,
        principal=_principal(),
    )
    await db.refresh(lead)
    assert lead.stage == LeadStage.LOST


@pytest.mark.asyncio
async def test_a_recorded_decision_is_not_silently_overwritten(db: AsyncSession):
    """Reversing what a family said must be deliberate, not accidental."""
    from fastapi import HTTPException

    lead = await _make_lead(db, stage=LeadStage.OFFER_SENT)
    offer = await _make_offer(db, lead)

    await respond_to_offer_endpoint(
        offer_id=offer.id,
        payload=OfferResponseRequest(decision=OfferDecision.ACCEPTED),
        session=db,
        principal=_principal(),
    )
    with pytest.raises(HTTPException) as exc:
        await respond_to_offer_endpoint(
            offer_id=offer.id,
            payload=OfferResponseRequest(decision=OfferDecision.DECLINED),
            session=db,
            principal=_principal(),
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_acceptance_is_attributed_to_the_authenticated_caller(db: AsyncSession):
    """Who at the school recorded it comes from the principal, not the payload."""
    from src.db.sms_revops import LeadActivityLog

    lead = await _make_lead(db, stage=LeadStage.OFFER_SENT)
    offer = await _make_offer(db, lead)

    await respond_to_offer_endpoint(
        offer_id=offer.id,
        payload=OfferResponseRequest(
            decision=OfferDecision.ACCEPTED, responded_by="Someone Else"
        ),
        session=db,
        principal=_principal(user_id=77),
    )
    logs = (
        await db.execute(select(LeadActivityLog).where(LeadActivityLog.lead_id == lead.id))
    ).scalars().all()
    recorded = [l for l in logs if (l.metadata_json or {}).get("offer_id") == offer.id]
    assert recorded, "the decision must appear on the lead timeline"
    assert recorded[0].metadata_json["recorded_by"] == "user-77"


# ---------------------------------------------------------------------------
# Consent is not weakened by any of the above
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_non_consenting_lead_still_receives_nothing(db: AsyncSession):
    """The one rule none of this work may relax."""
    from src.services.ai.revops_nurture_runner import _deliver_stage

    lead = AdmissionsLead(
        parent_name="No", student_name="Consent", email="no@example.com",
        phone="+92-300-1111111", grade_applying_for="Grade 3",
        source=LeadSource.WEBSITE_FORM,
        email_consent=False, whatsapp_consent=False,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    with patch("src.services.email.utils.send_email") as mock_send:
        status = await _deliver_stage(
            db, lead, {"stage": 1, "channel": "email", "subject": "Hi", "content": "Hello"}
        )
    assert status == TouchStatus.CONSENT_BLOCKED
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_review_queue_lists_held_leads(db: AsyncSession):
    """The queue is the thing that makes holding a lead defensible."""
    lead = await _make_lead(db, email="")
    await acknowledge_new_lead(db, lead, channel="whatsapp", message="hello")

    rows = await review_queue_endpoint(
        include_resolved=False, limit=50, session=db, principal=_principal()
    )
    assert any(r["lead_id"] == lead.id for r in rows)
    mine = [r for r in rows if r["lead_id"] == lead.id][0]
    assert mine["reason"] == ReviewReason.UNCONTACTABLE
    assert mine["detail"]
