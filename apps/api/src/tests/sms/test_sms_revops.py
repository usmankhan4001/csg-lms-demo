import datetime
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_revops import (
    ActivityType,
    LeadIntent,
    LeadSource,
    LeadStage,
    OfferStatus,
)
from src.schemas.sms_revops import (
    BatchScoringRequest,
    LeadActivityCreate,
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
    assert len(pipeline.stages) == 7

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
