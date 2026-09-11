import datetime
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_revops import (
    ActivityType,
    LeadIntent,
    LeadOrigin,
    LeadSource,
    LeadStage,
    OfferStatus,
)
from src.schemas.sms_revops import (
    BatchScoringRequest,
    LeadActivityCreate,
    LeadConsentUpdate,
    LeadCreate,
    LeadStageUpdate,
    LeadUpdate,
    ScholarshipOfferCreate,
)
from src.routers.sms_revops import (
    batch_score_leads_endpoint,
    create_lead_endpoint,
    generate_offer_endpoint,
    get_lead_detail_endpoint,
    get_offer_endpoint,
    get_pipeline_endpoint,
    list_lead_activities_endpoint,
    list_leads_endpoint,
    list_offers_endpoint,
    log_activity_endpoint,
    update_lead_consent_endpoint,
    update_lead_endpoint,
    update_lead_stage_endpoint,
)


@pytest.mark.asyncio
async def test_admissions_lead_lifecycle_and_kanban_pipeline(db: AsyncSession):
    """
    Test end-to-end RevOps lead creation, initial scoring, Kanban pipeline grouping,
    stage progression, and activity auditing.
    """
    # 1. Capture new prospective lead from Website Form
    create_payload = LeadCreate(
        parent_name="John Doe",
        student_name="Alice Doe",
        email="john.doe@example.com",
        phone="+1-555-0199",
        grade_applying_for="Grade 9",
        campus_id=1,
        source=LeadSource.WEBSITE_FORM,
        budget_range="$10k-$15k",
        notes="Interested in STEM and Robotics programs.",
    )
    lead = await create_lead_endpoint(payload=create_payload, session=db)
    assert lead.id is not None
    assert lead.student_name == "Alice Doe"
    assert lead.stage == LeadStage.NEW_INQUIRY
    assert lead.source == LeadSource.WEBSITE_FORM
    assert lead.lead_score > 0
    assert lead.intent_level in (LeadIntent.WARM, LeadIntent.HOT)

    # 2. Capture second lead from Walk-in
    lead2 = await create_lead_endpoint(
        payload=LeadCreate(
            parent_name="Sarah Smith",
            student_name="Bob Smith",
            email="sarah.smith@example.com",
            phone="+1-555-0288",
            grade_applying_for="Grade 11",
            campus_id=1,
            source=LeadSource.WALK_IN,
            budget_range="$15k-$20k",
            notes="Walk-in inquiry during open house.",
        ),
        session=db,
    )
    assert lead2.id is not None
    assert lead2.lead_score >= lead.lead_score  # WALK_IN has higher source weight

    # 3. Check Kanban Pipeline Structure
    pipeline = await get_pipeline_endpoint(campus_id=1, session=db)
    assert pipeline.total_leads == 2
    # 8 stages: the original 7-stage pipeline plus STALLED, which loops a
    # non-converted lead back to NEW_INQUIRY per the loop-funnel redesign.
    assert len(pipeline.stages) == 8
    assert any(s.stage == LeadStage.STALLED for s in pipeline.stages)

    new_inquiry_stage = next(s for s in pipeline.stages if s.stage == LeadStage.NEW_INQUIRY)
    assert new_inquiry_stage.count == 2
    assert len(new_inquiry_stage.leads) == 2

    # 4. Log outreach activity (Phone Call) for lead 1
    call_act = await log_activity_endpoint(
        lead_id=lead.id,
        payload=LeadActivityCreate(
            activity_type=ActivityType.CALL,
            summary="Called parent to discuss curriculum and campus tour.",
            metadata_json={"call_duration_seconds": 320, "outcome": "positive"},
        ),
        session=db,
    )
    assert call_act.id is not None
    assert call_act.activity_type == ActivityType.CALL

    # Lead should now auto-advance to CONTACTED
    detail = await get_lead_detail_endpoint(lead_id=lead.id, session=db)
    assert detail.stage == LeadStage.CONTACTED
    assert detail.last_contacted_at is not None
    assert len(detail.activities) == 2  # initial creation note + call

    # 5. Move lead to TOUR_BOOKED stage
    stage_update = await update_lead_stage_endpoint(
        lead_id=lead.id,
        payload=LeadStageUpdate(
            stage=LeadStage.TOUR_BOOKED,
            reason="Campus tour booked for next Tuesday 10 AM.",
        ),
        session=db,
    )
    assert stage_update.stage == LeadStage.TOUR_BOOKED
    assert stage_update.lead_score >= detail.lead_score  # stage progression boosts score

    # 6. Check updated pipeline grouping
    updated_pipeline = await get_pipeline_endpoint(campus_id=1, session=db)
    tour_stage = next(s for s in updated_pipeline.stages if s.stage == LeadStage.TOUR_BOOKED)
    assert tour_stage.count == 1
    assert tour_stage.leads[0].id == lead.id


@pytest.mark.asyncio
async def test_dynamic_scholarship_offer_and_enrollment(db: AsyncSession):
    """
    Test dynamic scholarship pricing calculation, offer letter dispatch,
    stage progression to OFFER_SENT, and final ENROLLED status.
    """
    # 1. Create candidate lead
    lead = await create_lead_endpoint(
        payload=LeadCreate(
            parent_name="Michael Brown",
            student_name="Emma Brown",
            email="mbrown@example.com",
            phone="+1-555-0377",
            grade_applying_for="Grade 10",
            campus_id=2,
            source=LeadSource.REFERRAL,
            notes="High academic achiever, requested merit scholarship evaluation.",
        ),
        session=db,
    )

    # 2. Advance stage to ASSESSMENT_SCHEDULED
    await update_lead_stage_endpoint(
        lead_id=lead.id,
        payload=LeadStageUpdate(
            stage=LeadStage.ASSESSMENT_SCHEDULED,
            reason="Entrance assessment scheduled.",
        ),
        session=db,
    )

    # 3. Generate dynamic Scholarship Offer (30% discount on $12,000 base tuition)
    # Expected final amount = 12000 * 0.70 = 8400.0
    offer_payload = ScholarshipOfferCreate(
        lead_id=lead.id,
        campus_id=2,
        base_tuition_amount=12000.0,
        tuition_discount_percentage=30.0,
        valid_until=datetime.date(2026, 10, 31),
        status=OfferStatus.SENT,
        remarks="Merit scholarship 30% approved by admissions committee.",
    )
    offer = await generate_offer_endpoint(payload=offer_payload, session=db)
    assert offer.id is not None
    assert offer.tuition_discount_percentage == 30.0
    assert offer.final_tuition_amount == 8400.0
    assert offer.status == OfferStatus.SENT
    assert offer.offer_letter_url is not None
    assert offer.offer_letter_url.endswith(".pdf")

    # 4. Lead should automatically be updated to OFFER_SENT
    lead_detail = await get_lead_detail_endpoint(lead_id=lead.id, session=db)
    assert lead_detail.stage == LeadStage.OFFER_SENT
    assert len(lead_detail.offers) == 1
    assert lead_detail.offers[0].id == offer.id

    # 5. List and retrieve offers
    offers_list = await list_offers_endpoint(lead_id=lead.id, session=db)
    assert len(offers_list) == 1

    single_offer = await get_offer_endpoint(offer_id=offer.id, session=db)
    assert single_offer.final_tuition_amount == 8400.0

    # 6. Complete enrollment
    enrolled_lead = await update_lead_stage_endpoint(
        lead_id=lead.id,
        payload=LeadStageUpdate(
            stage=LeadStage.ENROLLED,
            reason="Offer accepted and initial deposit paid.",
        ),
        session=db,
    )
    assert enrolled_lead.stage == LeadStage.ENROLLED
    assert enrolled_lead.intent_level == LeadIntent.HOT


@pytest.mark.asyncio
async def test_batch_ai_scoring_and_filtering(db: AsyncSession):
    """
    Test AI batch scoring engine across multiple leads and list search filters.
    """
    # Create leads with different completeness and sources
    l1 = await create_lead_endpoint(
        payload=LeadCreate(
            parent_name="Carlos Santana",
            student_name="David Santana",
            email="carlos@santana.com",
            phone="+1-555-0901",
            grade_applying_for="Grade 8",
            campus_id=1,
            source=LeadSource.META_ADS,
        ),
        session=db,
    )
    l2 = await create_lead_endpoint(
        payload=LeadCreate(
            parent_name="Elena Rostova",
            student_name="Nikolai Rostov",
            email="elena@rostov.com",
            phone="+1-555-0902",
            grade_applying_for="Grade 8",
            campus_id=1,
            source=LeadSource.WALK_IN,
            budget_range="$20k+",
            notes="Ready to enroll immediately.",
        ),
        session=db,
    )

    # Run batch AI scoring
    batch_resp = await batch_score_leads_endpoint(
        payload=BatchScoringRequest(lead_ids=[l1.id, l2.id]),
        session=db,
    )
    assert batch_resp.processed_count == 2
    r1 = next(r for r in batch_resp.results if r.lead_id == l1.id)
    r2 = next(r for r in batch_resp.results if r.lead_id == l2.id)

    assert r2.score > r1.score
    assert r2.intent_level in (LeadIntent.HOT, LeadIntent.WARM)
    assert "source_score" in r2.breakdown

    # Search filter testing
    search_results = await list_leads_endpoint(search="Santana", session=db)
    assert len(search_results) == 1
    assert search_results[0].parent_name == "Carlos Santana"

    # Stage filter testing
    inquiry_results = await list_leads_endpoint(stage=LeadStage.NEW_INQUIRY, session=db)
    assert len(inquiry_results) >= 2

    # Update basic lead details
    updated = await update_lead_endpoint(
        lead_id=l1.id,
        payload=LeadUpdate(notes="Updated follow-up notes."),
        session=db,
    )
    assert updated.notes == "Updated follow-up notes."

    # List activities
    activities = await list_lead_activities_endpoint(lead_id=l1.id, session=db)
    assert len(activities) >= 1


@pytest.mark.asyncio
async def test_stalled_lead_loopback_transition_and_audit_log(db: AsyncSession):
    """
    Test that a non-converting lead can be marked STALLED and looped back to
    NEW_INQUIRY (Lead Research/Sourcing) per the funnel-loop redesign, with the
    loopback recorded distinctly (not as an ordinary forward stage change) in
    the activity audit log.
    """
    lead = await create_lead_endpoint(
        payload=LeadCreate(
            parent_name="Nora Patel",
            student_name="Aiden Patel",
            email="nora.patel@example.com",
            phone="+1-555-0455",
            grade_applying_for="Grade 6",
            campus_id=3,
            source=LeadSource.META_ADS,
        ),
        session=db,
    )

    # Advance a bit, then stall out (lead exits active nurture without converting)
    await update_lead_stage_endpoint(
        lead_id=lead.id,
        payload=LeadStageUpdate(stage=LeadStage.CONTACTED, reason="Initial outreach sent."),
        session=db,
    )
    stalled_lead = await update_lead_stage_endpoint(
        lead_id=lead.id,
        payload=LeadStageUpdate(stage=LeadStage.STALLED, reason="No response after 3 nurture attempts."),
        session=db,
    )
    assert stalled_lead.stage == LeadStage.STALLED

    # Loop back to research / new inquiry stage for re-nurturing
    looped_lead = await update_lead_stage_endpoint(
        lead_id=lead.id,
        payload=LeadStageUpdate(stage=LeadStage.NEW_INQUIRY, reason="Re-entering nurture with refreshed offer."),
        session=db,
    )
    assert looped_lead.stage == LeadStage.NEW_INQUIRY

    # The loopback must be distinctly flagged in the audit log, separate from
    # an ordinary forward stage change.
    activities = await list_lead_activities_endpoint(lead_id=lead.id, session=db)
    stage_change_entries = [a for a in activities if a.activity_type == ActivityType.STAGE_CHANGE]
    loopback_entries = [
        a for a in stage_change_entries
        if a.metadata_json and a.metadata_json.get("is_loopback") is True
    ]
    non_loopback_entries = [
        a for a in stage_change_entries
        if a.metadata_json and a.metadata_json.get("is_loopback") is False
    ]
    assert len(loopback_entries) == 1
    assert loopback_entries[0].metadata_json["from_stage"] == LeadStage.STALLED.value
    assert loopback_entries[0].metadata_json["to_stage"] == LeadStage.NEW_INQUIRY.value
    assert "looped back" in loopback_entries[0].summary.lower()
    assert len(non_loopback_entries) >= 1  # e.g. NEW_INQUIRY -> CONTACTED, CONTACTED -> STALLED

    # Kanban pipeline recognizes the STALLED bucket even though this lead has
    # already looped back out of it.
    pipeline = await get_pipeline_endpoint(campus_id=3, session=db)
    stalled_group = next(s for s in pipeline.stages if s.stage == LeadStage.STALLED)
    assert stalled_group.count == 0


@pytest.mark.asyncio
async def test_inbound_outbound_origin_tagging(db: AsyncSession):
    """
    Test that leads are tagged with an inbound/outbound nurture-path origin,
    distinct from the generic acquisition `source`: explicit values round-trip
    through create/detail, unset values are auto-inferred from `source`
    (paid-ads sources -> OUTBOUND), and the tag is filterable via list.
    """
    # Explicit inbound (organic content-driven) lead
    inbound_lead = await create_lead_endpoint(
        payload=LeadCreate(
            parent_name="Farah Ali",
            student_name="Zara Ali",
            email="farah.ali@example.com",
            phone="+1-555-0611",
            grade_applying_for="Grade 2",
            campus_id=4,
            source=LeadSource.WEBSITE_FORM,
            origin=LeadOrigin.INBOUND,
        ),
        session=db,
    )
    assert inbound_lead.origin == LeadOrigin.INBOUND

    # Outbound (paid ads / pixel-tracked) lead with no explicit origin -> auto-inferred
    outbound_lead = await create_lead_endpoint(
        payload=LeadCreate(
            parent_name="Omar Siddiqui",
            student_name="Hana Siddiqui",
            email="omar.siddiqui@example.com",
            phone="+1-555-0622",
            grade_applying_for="Grade 3",
            campus_id=4,
            source=LeadSource.META_ADS,
        ),
        session=db,
    )
    assert outbound_lead.origin == LeadOrigin.OUTBOUND

    # Retrievable via detail endpoint (round-trips through DB, not just in-memory)
    detail = await get_lead_detail_endpoint(lead_id=outbound_lead.id, session=db)
    assert detail.origin == LeadOrigin.OUTBOUND

    # Filterable via list endpoint
    outbound_results = await list_leads_endpoint(campus_id=4, origin=LeadOrigin.OUTBOUND, session=db)
    assert len(outbound_results) == 1
    assert outbound_results[0].id == outbound_lead.id

    inbound_results = await list_leads_endpoint(campus_id=4, origin=LeadOrigin.INBOUND, session=db)
    assert len(inbound_results) == 1
    assert inbound_results[0].id == inbound_lead.id


@pytest.mark.asyncio
async def test_consent_capture_and_update_endpoint(db: AsyncSession):
    """
    Test Consent & Compliance tracking: leads default to no outbound consent,
    consent can be captured at intake, and later changed via a dedicated
    endpoint that stamps a per-channel timestamp and writes a compliance audit
    log entry.
    """
    lead = await create_lead_endpoint(
        payload=LeadCreate(
            parent_name="Grace Liu",
            student_name="Ivy Liu",
            email="grace.liu@example.com",
            phone="+1-555-0733",
            grade_applying_for="Grade 5",
            campus_id=5,
            source=LeadSource.WHATSAPP,
            whatsapp_consent=True,
        ),
        session=db,
    )
    assert lead.whatsapp_consent is True
    assert lead.email_consent is False  # default opt-out until explicitly granted
    assert lead.whatsapp_consent_updated_at is not None
    assert lead.email_consent_updated_at is None

    # Opt into email later, opt out of WhatsApp
    updated = await update_lead_consent_endpoint(
        lead_id=lead.id,
        payload=LeadConsentUpdate(
            whatsapp_consent=False,
            email_consent=True,
            reason="Parent requested email-only communication.",
        ),
        session=db,
    )
    assert updated.whatsapp_consent is False
    assert updated.email_consent is True
    assert updated.whatsapp_consent_updated_at is not None
    assert updated.email_consent_updated_at is not None

    activities = await list_lead_activities_endpoint(lead_id=lead.id, session=db)
    consent_entries = [a for a in activities if a.activity_type == ActivityType.CONSENT_UPDATE]
    assert len(consent_entries) == 1
    assert consent_entries[0].metadata_json["changes"]["whatsapp_consent"] is False
    assert consent_entries[0].metadata_json["changes"]["email_consent"] is True
