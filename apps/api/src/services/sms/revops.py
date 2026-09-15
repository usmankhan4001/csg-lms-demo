import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.sms_revops import (
    ActivityType,
    AdmissionsLead,
    LeadActivityLog,
    LeadIntent,
    LeadOrigin,
    LeadSource,
    LeadStage,
    OfferStatus,
    ScholarshipOffer,
)
from src.schemas.sms_revops import (
    BatchScoringRequest,
    BatchScoringResponse,
    LeadActivityCreate,
    LeadConsentUpdate,
    LeadCreate,
    LeadRead,
    LeadScoringResult,
    LeadStageUpdate,
    PipelineResponse,
    PipelineStageGroup,
    ScholarshipOfferCreate,
)

logger = logging.getLogger(__name__)

# Paid-ads / pixel-tracked acquisition channels are treated as OUTBOUND nurture
# paths; everything else (organic form fills, referrals, walk-ins, organic
# WhatsApp) is treated as INBOUND. Used only as a default when the caller
# doesn't explicitly tag `origin` on lead creation.
OUTBOUND_LEAD_SOURCES = {LeadSource.META_ADS, LeadSource.GOOGLE_ADS}


def infer_lead_origin(source: LeadSource) -> LeadOrigin:
    """
    Infers the inbound/outbound nurture-path tag from the acquisition source
    when the caller does not explicitly supply one.
    """
    return LeadOrigin.OUTBOUND if source in OUTBOUND_LEAD_SOURCES else LeadOrigin.INBOUND


def calculate_lead_score(
    lead: AdmissionsLead,
    activity_count: int = 0,
) -> Tuple[int, LeadIntent, Dict[str, Any]]:
    """
    AI Lead Scoring Engine for Admissions CRM.
    Evaluates attribution channel, recruitment funnel stage, profile completeness,
    and outreach engagement frequency to compute a score (0-100) and intent category.
    """
    source_weights = {
        LeadSource.WALK_IN: 30,
        LeadSource.REFERRAL: 25,
        LeadSource.WEBSITE_FORM: 20,
        LeadSource.WHATSAPP: 20,
        LeadSource.GOOGLE_ADS: 15,
        LeadSource.META_ADS: 10,
    }

    stage_weights = {
        LeadStage.ENROLLED: 40,
        LeadStage.OFFER_SENT: 35,
        LeadStage.ASSESSMENT_SCHEDULED: 30,
        LeadStage.TOUR_BOOKED: 25,
        LeadStage.CONTACTED: 15,
        LeadStage.NEW_INQUIRY: 5,
        LeadStage.STALLED: 5,
        LeadStage.LOST: 0,
    }

    source_score = source_weights.get(lead.source, 15)
    stage_score = stage_weights.get(lead.stage, 5)

    completeness_score = 0
    if lead.email and "@" in lead.email and lead.phone:
        completeness_score += 10
    if lead.budget_range:
        completeness_score += 10
    if lead.notes:
        completeness_score += 5

    engagement_score = min(15, activity_count * 5)

    total_score = min(100, max(0, source_score + stage_score + completeness_score + engagement_score))

    if total_score >= 65:
        intent = LeadIntent.HOT
    elif total_score >= 35:
        intent = LeadIntent.WARM
    else:
        intent = LeadIntent.COLD

    breakdown = {
        "source_score": source_score,
        "stage_score": stage_score,
        "completeness_score": completeness_score,
        "engagement_score": engagement_score,
        "raw_total": source_score + stage_score + completeness_score + engagement_score,
        "calculated_score": total_score,
    }

    return total_score, intent, breakdown


async def create_admissions_lead(
    session: AsyncSession,
    payload: LeadCreate,
) -> AdmissionsLead:
    """
    Creates an admissions lead and logs the initial acquisition activity.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    origin = payload.origin or infer_lead_origin(payload.source)
    lead = AdmissionsLead(
        campus_id=payload.campus_id,
        parent_name=payload.parent_name,
        student_name=payload.student_name,
        email=payload.email,
        phone=payload.phone,
        grade_applying_for=payload.grade_applying_for,
        academic_year_id=payload.academic_year_id,
        source=payload.source,
        origin=origin,
        stage=LeadStage.NEW_INQUIRY,
        budget_range=payload.budget_range,
        notes=payload.notes,
        assigned_officer_id=payload.assigned_officer_id,
        whatsapp_consent=payload.whatsapp_consent,
        whatsapp_consent_updated_at=now if payload.whatsapp_consent else None,
        email_consent=payload.email_consent,
        email_consent_updated_at=now if payload.email_consent else None,
        created_at=now,
        updated_at=now,
    )

    # Initial score calculation
    score, intent, _ = calculate_lead_score(lead, activity_count=0)
    lead.lead_score = score
    lead.intent_level = payload.intent_level or intent

    session.add(lead)
    # Flush rather than commit: the id is needed for the activity row below,
    # but a commit here published the lead in its own transaction. An
    # interruption before the second commit left a lead with no acquisition
    # entry at all -- the CRM would show an inquiry that arrived from nowhere,
    # and lead scoring counts activities, so the record would also score low
    # for the rest of its life.
    await session.flush()

    # Create initial activity log
    initial_activity = LeadActivityLog(
        lead_id=lead.id,
        activity_type=ActivityType.NOTE,
        summary=f"Inquiry captured from {lead.source.value} for grade {lead.grade_applying_for}.",
        metadata_json={
            "source": lead.source.value,
            "origin": lead.origin.value,
            "grade": lead.grade_applying_for,
            "initial_score": lead.lead_score,
            "intent": lead.intent_level.value,
            "whatsapp_consent": lead.whatsapp_consent,
            "email_consent": lead.email_consent,
        },
        created_at=now,
    )
    session.add(initial_activity)
    await session.commit()
    await session.refresh(lead)

    return lead


async def get_pipeline_kanban(
    session: AsyncSession,
    campus_id: Optional[int] = None,
) -> PipelineResponse:
    """
    Retrieves admissions leads organized into Kanban funnel stages.
    """
    query = select(AdmissionsLead).order_by(AdmissionsLead.created_at.desc())
    if campus_id is not None:
        query = query.where(AdmissionsLead.campus_id == campus_id)

    leads = (await session.execute(query)).scalars().all()

    stage_titles = {
        LeadStage.NEW_INQUIRY: "New Inquiry",
        LeadStage.CONTACTED: "Contacted",
        LeadStage.TOUR_BOOKED: "Campus Tour Booked",
        LeadStage.ASSESSMENT_SCHEDULED: "Assessment Scheduled",
        LeadStage.OFFER_SENT: "Offer Sent",
        LeadStage.ENROLLED: "Enrolled",
        LeadStage.LOST: "Lost / Dropped",
        LeadStage.STALLED: "Stalled / Non-Converted (Looping Back)",
    }

    grouped: Dict[LeadStage, List[LeadRead]] = {stage: [] for stage in LeadStage}

    for lead in leads:
        read_obj = LeadRead.model_validate(lead)
        if lead.stage in grouped:
            grouped[lead.stage].append(read_obj)
        else:
            grouped[lead.stage] = [read_obj]

    stage_groups: List[PipelineStageGroup] = []
    for stage in LeadStage:
        stage_leads = grouped.get(stage, [])
        stage_groups.append(
            PipelineStageGroup(
                stage=stage,
                stage_name=stage_titles.get(stage, stage.value),
                count=len(stage_leads),
                leads=stage_leads,
            )
        )

    return PipelineResponse(
        stages=stage_groups,
        total_leads=len(leads),
    )


async def update_lead_stage(
    session: AsyncSession,
    lead_id: int,
    payload: LeadStageUpdate,
) -> AdmissionsLead:
    """
    Updates admissions lead stage, recalculates score, and appends a stage change audit log.
    """
    stmt = select(AdmissionsLead).where(AdmissionsLead.id == lead_id)
    lead = (await session.execute(stmt)).scalar_one_or_none()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admissions lead {lead_id} not found.",
        )

    old_stage = lead.stage
    new_stage = payload.stage
    lead.stage = new_stage
    now = datetime.datetime.now(datetime.timezone.utc)
    lead.updated_at = now

    # Count existing activities to factor into scoring
    act_stmt = select(func.count(LeadActivityLog.id)).where(LeadActivityLog.lead_id == lead_id)
    act_count = (await session.execute(act_stmt)).scalar() or 0

    score, intent, _ = calculate_lead_score(lead, activity_count=act_count + 1)
    lead.lead_score = score
    lead.intent_level = intent

    # The funnel is a loop, not a line: a STALLED (non-converted) lead moving
    # back to NEW_INQUIRY re-enters Lead Research/Sourcing for another
    # re-nurturing cycle. Record this distinctly in the audit trail so it can
    # be told apart from an ordinary forward stage change.
    is_loopback = old_stage == LeadStage.STALLED and new_stage == LeadStage.NEW_INQUIRY

    if is_loopback:
        summary_text = (
            f"Stalled lead looped back from {old_stage.value} to {new_stage.value} "
            f"(re-entering Lead Research/Sourcing for another nurture cycle)."
        )
    else:
        summary_text = f"Stage transitioned from {old_stage.value} to {new_stage.value}."
    if payload.reason:
        summary_text += f" Reason / Notes: {payload.reason}"

    metadata_json = dict(payload.metadata_json) if payload.metadata_json else {
        "from_stage": old_stage.value,
        "to_stage": new_stage.value,
    }
    metadata_json.setdefault("from_stage", old_stage.value)
    metadata_json.setdefault("to_stage", new_stage.value)
    metadata_json["is_loopback"] = is_loopback

    activity = LeadActivityLog(
        lead_id=lead.id,
        activity_type=ActivityType.STAGE_CHANGE,
        summary=summary_text,
        metadata_json=metadata_json,
        created_at=now,
    )
    session.add(activity)
    session.add(lead)
    await session.commit()
    await session.refresh(lead)

    return lead


async def update_lead_consent(
    session: AsyncSession,
    lead_id: int,
    payload: LeadConsentUpdate,
) -> AdmissionsLead:
    """
    Records an opt-in/opt-out consent change for a lead's outbound WhatsApp
    and/or Email channels, stamping the change timestamp per channel and
    appending a compliance audit log entry. This is the record that gates
    whether outbound WhatsApp/Email automation (SDR agent, drip engine) is
    permitted to fire for the lead.
    """
    if payload.whatsapp_consent is None and payload.email_consent is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of whatsapp_consent or email_consent must be provided.",
        )

    stmt = select(AdmissionsLead).where(AdmissionsLead.id == lead_id)
    lead = (await session.execute(stmt)).scalar_one_or_none()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admissions lead {lead_id} not found.",
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    changes: Dict[str, Any] = {}

    if payload.whatsapp_consent is not None:
        lead.whatsapp_consent = payload.whatsapp_consent
        lead.whatsapp_consent_updated_at = now
        changes["whatsapp_consent"] = payload.whatsapp_consent

    if payload.email_consent is not None:
        lead.email_consent = payload.email_consent
        lead.email_consent_updated_at = now
        changes["email_consent"] = payload.email_consent

    lead.updated_at = now

    channel_summaries = [
        f"{channel.replace('_consent', '').upper()} consent {'GRANTED' if granted else 'REVOKED'}"
        for channel, granted in changes.items()
    ]
    summary_text = "; ".join(channel_summaries) + "."
    if payload.reason:
        summary_text += f" Reason / Notes: {payload.reason}"

    activity = LeadActivityLog(
        lead_id=lead.id,
        activity_type=ActivityType.CONSENT_UPDATE,
        summary=summary_text,
        metadata_json={"changes": changes, "reason": payload.reason},
        created_at=now,
    )
    session.add(activity)
    session.add(lead)
    await session.commit()
    await session.refresh(lead)

    return lead


async def log_activity_for_lead(
    session: AsyncSession,
    lead_id: int,
    payload: LeadActivityCreate,
) -> LeadActivityLog:
    """
    Records an interaction activity (Call, WhatsApp, Email, Tour, Note) and updates lead touchpoint.
    """
    stmt = select(AdmissionsLead).where(AdmissionsLead.id == lead_id)
    lead = (await session.execute(stmt)).scalar_one_or_none()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admissions lead {lead_id} not found.",
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    activity = LeadActivityLog(
        lead_id=lead_id,
        activity_type=payload.activity_type,
        summary=payload.summary,
        metadata_json=payload.metadata_json,
        created_at=now,
    )
    session.add(activity)

    lead.last_contacted_at = now
    lead.updated_at = now

    # Advance stage from NEW_INQUIRY to CONTACTED if first communication
    if lead.stage == LeadStage.NEW_INQUIRY and payload.activity_type in (
        ActivityType.CALL,
        ActivityType.WHATSAPP,
        ActivityType.EMAIL,
        ActivityType.TOUR,
    ):
        lead.stage = LeadStage.CONTACTED

    # Re-calculate score
    act_stmt = select(func.count(LeadActivityLog.id)).where(LeadActivityLog.lead_id == lead_id)
    act_count = (await session.execute(act_stmt)).scalar() or 0
    score, intent, _ = calculate_lead_score(lead, activity_count=act_count + 1)
    lead.lead_score = score
    lead.intent_level = intent

    session.add(lead)
    await session.commit()
    await session.refresh(activity)
    return activity


async def generate_scholarship_offer(
    session: AsyncSession,
    payload: ScholarshipOfferCreate,
) -> ScholarshipOffer:
    """
    Computes dynamic tuition discount and generates an institutional scholarship offer letter.
    """
    stmt = select(AdmissionsLead).where(AdmissionsLead.id == payload.lead_id)
    lead = (await session.execute(stmt)).scalar_one_or_none()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admissions lead {payload.lead_id} not found.",
        )

    discount_pct = payload.tuition_discount_percentage
    final_amount = round(payload.base_tuition_amount * (1.0 - (discount_pct / 100.0)), 2)
    final_amount = max(0.0, final_amount)

    now = datetime.datetime.now(datetime.timezone.utc)
    offer_status = payload.status or OfferStatus.SENT

    offer = ScholarshipOffer(
        lead_id=payload.lead_id,
        campus_id=payload.campus_id or lead.campus_id,
        tuition_discount_percentage=discount_pct,
        final_tuition_amount=final_amount,
        valid_until=payload.valid_until,
        status=offer_status,
        created_at=now,
    )
    session.add(offer)
    # Flush, not commit. The id is needed to build the offer-letter URL below,
    # but committing here published the offer as a separate transaction from
    # everything that gives it meaning: an interruption in the window left a
    # ScholarshipOffer row with a NULL letter URL, a lead still sitting in its
    # previous stage, and no activity entry -- an offer the CRM had no record
    # of having made, while the family had been told one was coming.
    await session.flush()

    # Set dynamic offer letter URL
    offer.offer_letter_url = f"/api/v1/revops/offers/{offer.id}/offer-letter.pdf"
    session.add(offer)

    # Move lead to OFFER_SENT stage if not already enrolled
    if lead.stage not in (LeadStage.OFFER_SENT, LeadStage.ENROLLED):
        lead.stage = LeadStage.OFFER_SENT

    lead.updated_at = now
    lead.last_contacted_at = now

    # Log activity for offer generation
    offer_activity = LeadActivityLog(
        lead_id=lead.id,
        activity_type=ActivityType.EMAIL,
        summary=(
            f"Scholarship offer generated: {discount_pct}% tuition discount, "
            f"final tuition {final_amount}. Valid until {payload.valid_until}."
        ),
        metadata_json={
            "offer_id": offer.id,
            "base_tuition": payload.base_tuition_amount,
            "discount_percentage": discount_pct,
            "final_tuition_amount": final_amount,
            "valid_until": str(payload.valid_until),
            "remarks": payload.remarks,
        },
        created_at=now,
    )
    session.add(offer_activity)

    act_stmt = select(func.count(LeadActivityLog.id)).where(LeadActivityLog.lead_id == lead.id)
    act_count = (await session.execute(act_stmt)).scalar() or 0
    score, intent, _ = calculate_lead_score(lead, activity_count=act_count + 1)
    lead.lead_score = score
    lead.intent_level = intent
    session.add(lead)

    await session.commit()
    await session.refresh(offer)
    return offer


async def batch_score_leads(
    session: AsyncSession,
    payload: BatchScoringRequest,
) -> BatchScoringResponse:
    """
    Runs AI scoring engine across a selection or full batch of admissions leads.
    """
    query = select(AdmissionsLead)
    conditions = []
    if payload.lead_ids:
        conditions.append(AdmissionsLead.id.in_(payload.lead_ids))
    if payload.campus_id is not None:
        conditions.append(AdmissionsLead.campus_id == payload.campus_id)

    if conditions:
        query = query.where(and_(*conditions))

    leads = (await session.execute(query)).scalars().all()
    results: List[LeadScoringResult] = []

    for lead in leads:
        act_stmt = select(func.count(LeadActivityLog.id)).where(LeadActivityLog.lead_id == lead.id)
        act_count = (await session.execute(act_stmt)).scalar() or 0

        score, intent, breakdown = calculate_lead_score(lead, activity_count=act_count)
        lead.lead_score = score
        lead.intent_level = intent
        lead.updated_at = datetime.datetime.now(datetime.timezone.utc)
        session.add(lead)

        results.append(
            LeadScoringResult(
                lead_id=lead.id,
                score=score,
                intent_level=intent,
                breakdown=breakdown,
            )
        )

    await session.commit()
    return BatchScoringResponse(
        processed_count=len(results),
        results=results,
    )


async def enroll_lead(
    session: AsyncSession,
    lead_id: int,
    section_id: int,
    academic_year_id: int,
    student_email: str,
    roll_number: Optional[str] = None,
):
    """Close the admissions loop: provision the learner and mark the lead ENROLLED.

    Everything -- the user account, the STUDENT role grant, the enrollment row,
    the lead's own stage change and its audit entry -- is staged on one session
    and committed exactly once at the end. If any step raises, nothing is
    written, so a failure can never leave a lead holding an account with no
    enrollment (which would be invisible to every school module while
    occupying an email address).

    Idempotent: calling this twice converges on a single student rather than
    minting a second account. See `revops_enrollment.provision_learner_from_lead`.
    """
    from src.services.sms.revops_enrollment import provision_learner_from_lead

    stmt = select(AdmissionsLead).where(AdmissionsLead.id == lead_id)
    lead = (await session.execute(stmt)).scalar_one_or_none()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admissions lead {lead_id} not found.",
        )

    if lead.stage == LeadStage.LOST:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This lead is marked Lost. Move it back into the funnel before "
                "enrolling."
            ),
        )

    result = await provision_learner_from_lead(
        session,
        lead,
        section_id=section_id,
        academic_year_id=academic_year_id,
        student_email=student_email,
        roll_number=roll_number,
    )

    now = datetime.datetime.now(datetime.timezone.utc)
    previous_stage = lead.stage

    # Only log a stage transition when one actually happened -- a repeat call
    # on an already-ENROLLED lead should not litter the audit trail with
    # ENROLLED -> ENROLLED entries.
    if previous_stage != LeadStage.ENROLLED:
        lead.stage = LeadStage.ENROLLED
        lead.updated_at = now
        session.add(lead)
        session.add(
            LeadActivityLog(
                lead_id=lead.id,
                activity_type=ActivityType.STAGE_CHANGE,
                summary=(
                    f"Stage transitioned from {previous_stage.value} to "
                    f"{LeadStage.ENROLLED.value}. Learner provisioned as "
                    f"user #{result.user.id} and enrolled in section {section_id}."
                ),
                metadata_json={
                    "from_stage": previous_stage.value,
                    "to_stage": LeadStage.ENROLLED.value,
                    "is_loopback": False,
                    "student_id": result.user.id,
                    "section_id": section_id,
                    "academic_year_id": academic_year_id,
                },
                created_at=now,
            )
        )

    await session.commit()
    await session.refresh(lead)
    await session.refresh(result.user)
    await session.refresh(result.enrollment)

    return lead, result
