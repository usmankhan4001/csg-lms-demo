"""
Tests for the inbound lead webhook (M21) and AI lead qualification (M22).

Both endpoints previously referenced enum members and model fields that do
not exist (`LeadSource.GOOGLE_SEARCH`, `LeadOrigin.INBOUND_FORM`,
`LeadIntent.HIGH`, `lead.qualification_score`, `LeadCreate(target_grade=...)`)
and so would have raised on any real call. Neither had any test coverage,
which is why that went unnoticed. These tests exercise them for real.
"""

import os
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_revops import LeadIntent, LeadOrigin, LeadSource, LeadStage
from src.routers.sms_revops import (
    WEBHOOK_SECRET_ENV,
    ai_qualify_lead,
    inbound_lead_webhook,
    verify_revops_webhook_secret,
)

TEST_SECRET = "test-webhook-secret-value"


# ── Webhook secret verification ──

@pytest.mark.asyncio
async def test_webhook_secret_accepts_matching_secret():
    with patch.dict(os.environ, {WEBHOOK_SECRET_ENV: TEST_SECRET}):
        # Must not raise.
        await verify_revops_webhook_secret(x_webhook_secret=TEST_SECRET)


@pytest.mark.asyncio
async def test_webhook_secret_rejects_wrong_secret():
    with patch.dict(os.environ, {WEBHOOK_SECRET_ENV: TEST_SECRET}):
        with pytest.raises(HTTPException) as exc:
            await verify_revops_webhook_secret(x_webhook_secret="not-the-secret")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_webhook_fails_closed_when_secret_is_unconfigured():
    """An unconfigured deployment must reject, not silently accept anonymous
    writes into the admissions CRM."""
    with patch.dict(os.environ, {WEBHOOK_SECRET_ENV: ""}):
        with pytest.raises(HTTPException) as exc:
            await verify_revops_webhook_secret(x_webhook_secret="anything")
    assert exc.value.status_code == 403


# ── Webhook ingestion ──

@pytest.mark.asyncio
async def test_webhook_ingests_lead_with_real_enum_values(db: AsyncSession):
    result = await inbound_lead_webhook(
        channel="meta",
        payload={
            "parent_name": "Sara Ahmed",
            "student_name": "Bilal Ahmed",
            "email": "sara.ahmed@example.com",
            "phone": "+1-555-0101",
            "grade_applying_for": "Grade 9",
            "campus_id": 1,
        },
        session=db,
    )

    assert result["status"] == "ingested"
    assert result["lead_id"] is not None
    assert result["assigned_stage"] == LeadStage.NEW_INQUIRY

    from sqlalchemy import select

    from src.db.sms_revops import AdmissionsLead

    lead = (
        await db.execute(select(AdmissionsLead).where(AdmissionsLead.id == result["lead_id"]))
    ).scalar_one()
    # These are the exact values the broken version got wrong.
    assert lead.source == LeadSource.META_ADS
    assert lead.origin == LeadOrigin.INBOUND
    assert lead.grade_applying_for == "Grade 9"


@pytest.mark.asyncio
async def test_webhook_maps_each_channel_to_its_real_source(db: AsyncSession):
    # Each case needs a distinct email AND phone, or de-duplication (correctly)
    # folds it into the previous lead instead of creating a new one.
    cases = [
        ("google", LeadSource.GOOGLE_ADS, "chan-google@example.com", "+1-555-9001"),
        ("whatsapp", LeadSource.WHATSAPP, "chan-whatsapp@example.com", "+1-555-9002"),
        ("web", LeadSource.WEBSITE_FORM, "chan-web@example.com", "+1-555-9003"),
        ("unknown-channel", LeadSource.WEBSITE_FORM, "chan-unknown@example.com", "+1-555-9004"),
    ]
    from sqlalchemy import select

    from src.db.sms_revops import AdmissionsLead

    for channel, expected_source, email, phone in cases:
        result = await inbound_lead_webhook(
            channel=channel,
            payload={"name": "Parent X", "email": email, "phone": phone},
            session=db,
        )
        lead = (
            await db.execute(select(AdmissionsLead).where(AdmissionsLead.id == result["lead_id"]))
        ).scalar_one()
        assert lead.source == expected_source, f"channel {channel}"


@pytest.mark.asyncio
async def test_webhook_deduplicates_repeat_inquiry_by_email(db: AsyncSession):
    payload = {
        "parent_name": "Dedup Parent",
        "student_name": "Dedup Child",
        "email": "dedup@example.com",
        "phone": "+1-555-7777",
        "grade_applying_for": "Grade 6",
    }
    first = await inbound_lead_webhook(channel="web", payload=payload, session=db)
    assert first["status"] == "ingested"

    # Same prospect submits again — must NOT create a second lead.
    second = await inbound_lead_webhook(channel="meta", payload=payload, session=db)
    assert second["status"] == "deduplicated"
    assert second["lead_id"] == first["lead_id"]

    from sqlalchemy import func, select

    from src.db.sms_revops import AdmissionsLead

    count = (
        await db.execute(
            select(func.count(AdmissionsLead.id)).where(AdmissionsLead.email == "dedup@example.com")
        )
    ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_webhook_deduplicates_by_phone_when_email_differs(db: AsyncSession):
    await inbound_lead_webhook(
        channel="web",
        payload={"name": "Phone Parent", "email": "first@example.com", "phone": "+1-555-8888"},
        session=db,
    )
    second = await inbound_lead_webhook(
        channel="whatsapp",
        payload={"name": "Phone Parent", "email": "second@example.com", "phone": "+1-555-8888"},
        session=db,
    )
    assert second["status"] == "deduplicated"


@pytest.mark.asyncio
async def test_webhook_rejects_payload_with_no_contact(db: AsyncSession):
    """Rather than fabricating a placeholder email/phone (which would be
    unreachable AND defeat de-duplication, since every synthesised value is
    unique)."""
    with pytest.raises(HTTPException) as exc:
        await inbound_lead_webhook(
            channel="web",
            payload={"parent_name": "No Contact"},
            session=db,
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_webhook_rejects_payload_with_no_name(db: AsyncSession):
    with pytest.raises(HTTPException) as exc:
        await inbound_lead_webhook(
            channel="web",
            payload={"email": "nameless@example.com"},
            session=db,
        )
    assert exc.value.status_code == 422


# ── AI qualification ──

@pytest.mark.asyncio
async def test_ai_qualify_scores_lead_via_real_engine(db: AsyncSession):
    created = await inbound_lead_webhook(
        channel="web",
        payload={
            "parent_name": "Quality Parent",
            "student_name": "Quality Student",
            "email": "quality@example.com",
            "phone": "+1-555-2222",
            "grade_applying_for": "Grade 9",
        },
        session=db,
    )

    result = await ai_qualify_lead(lead_id=created["lead_id"], session=db)

    assert result["lead_id"] == created["lead_id"]
    assert 0 <= result["lead_score"] <= 100
    assert result["intent_level"] in (LeadIntent.HOT, LeadIntent.WARM, LeadIntent.COLD)
    # Proof it routed through the multi-factor AI engine rather than the old
    # hand-rolled `score = 65 + bumps` duplicate.
    assert set(result["breakdown"]) == {
        "completeness_score",
        "responsiveness_score",
        "grade_demand_score",
        "budget_fit_score",
        "timeline_score",
    }
    assert isinstance(result["key_conversion_factors"], list)
    assert result["recommended_next_action"]


@pytest.mark.asyncio
async def test_ai_qualify_persists_score_and_intent(db: AsyncSession):
    created = await inbound_lead_webhook(
        channel="web",
        payload={
            "parent_name": "Persist Parent",
            "student_name": "Persist Student",
            "email": "persist@example.com",
            "phone": "+1-555-3333",
            "grade_applying_for": "Grade 11",
        },
        session=db,
    )
    result = await ai_qualify_lead(lead_id=created["lead_id"], session=db)

    from sqlalchemy import select

    from src.db.sms_revops import AdmissionsLead

    lead = (
        await db.execute(select(AdmissionsLead).where(AdmissionsLead.id == created["lead_id"]))
    ).scalar_one()
    assert lead.lead_score == result["lead_score"]
    assert lead.intent_level == result["intent_level"]


@pytest.mark.asyncio
async def test_ai_qualify_404_for_unknown_lead(db: AsyncSession):
    with pytest.raises(HTTPException) as exc:
        await ai_qualify_lead(lead_id=999999, session=db)
    assert exc.value.status_code == 404
