import datetime
import hmac
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    SCHOOL_ADMIN,
    STAFF,
    SUPER_ADMIN,
    KeycloakUserPrincipal,
    get_current_user_principal,
    require_roles,
)
from src.db.revops_review import LeadReviewFlag
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
    EnrollLeadRequest,
    EnrollLeadResponse,
    BatchScoringResponse,
    LeadActivityCreate,
    LeadActivityRead,
    LeadConsentUpdate,
    LeadCreate,
    LeadDetailResponse,
    LeadRead,
    LeadStageUpdate,
    LeadUpdate,
    PipelineResponse,
    OfferDecision,
    OfferResponseRequest,
    ScholarshipOfferCreate,
    ScholarshipOfferRead,
)
from src.security.features_utils.dependencies import require_revops_feature
from src.security.school_ownership import (
    assert_campus_allowed,
    resolve_scoped_campus_id,
)
from src.services.ai.revops_lead_scoring import calculate_lead_score as ai_calculate_lead_score
from src.services.sms.revops_acknowledge import acknowledge_new_lead
from src.services.sms.revops import (
    batch_score_leads,
    create_admissions_lead,
    generate_scholarship_offer as service_generate_offer,
    get_pipeline_kanban,
    log_activity_for_lead,
    update_lead_consent as service_update_consent,
    update_lead_stage as service_update_stage,
    enroll_lead as service_enroll_lead,
)

# Admissions officers. Matches the role set this file already uses on
# enroll_lead / sdr_reply / nurture-sequence.
_ADMISSIONS = [SUPER_ADMIN, SCHOOL_ADMIN, STAFF]

# Consent is a COMPLIANCE record, not a CRM field: the drip engine and SDR
# agent genuinely refuse to contact a lead who has opted out, so whoever can
# flip this can authorise marketing to a family that said no. Narrowed to
# admins, matching generate_lead_offer_copy.
_CONSENT_MANAGER = [SUPER_ADMIN, SCHOOL_ADMIN]

router = APIRouter(dependencies=[Depends(require_revops_feature)])


# ── Admissions Leads Endpoints ──

@router.post(
    "/leads",
    response_model=LeadRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Admissions Lead",
    description="Captures new prospect inquiry from website forms, WhatsApp, meta ads, or walk-ins.",
)
async def create_lead_endpoint(
    payload: LeadCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> LeadRead:
    # Fail loudly. Note the inbound WEBHOOK path is deliberately not scoped
    # this way: it authenticates with a shared secret and has no campus-bound
    # caller, so the form's campus is the only authority available there.
    assert_campus_allowed(principal, getattr(payload, "campus_id", None))
    lead = await create_admissions_lead(session=session, payload=payload)
    return LeadRead.model_validate(lead)


@router.get(
    "/leads/pipeline",
    response_model=PipelineResponse,
    summary="Get Admissions Kanban Pipeline",
    description="Returns prospective student leads grouped across all Kanban conversion stages.",
)
async def get_pipeline_endpoint(
    campus_id: Optional[int] = Query(None, description="Optional Campus ID filter"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> PipelineResponse:
    # Narrow: an omitted filter previously showed every campus's pipeline.
    filter_campus_id = resolve_scoped_campus_id(
        principal, campus_id if isinstance(campus_id, int) else None
    )
    return await get_pipeline_kanban(session=session, campus_id=filter_campus_id)


@router.get(
    "/leads",
    response_model=List[LeadRead],
    summary="List Admissions Leads",
    description="List and filter admissions leads by stage, source, intent, campus, or search query.",
)
async def list_leads_endpoint(
    campus_id: Optional[int] = Query(None, description="Filter by Campus ID"),
    stage: Optional[LeadStage] = Query(None, description="Filter by Lead Stage"),
    source: Optional[LeadSource] = Query(None, description="Filter by Acquisition Source"),
    origin: Optional[LeadOrigin] = Query(None, description="Filter by Inbound/Outbound nurture origin"),
    intent_level: Optional[LeadIntent] = Query(None, description="Filter by Intent Level"),
    search: Optional[str] = Query(None, description="Search parent/student name, email, or phone"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[LeadRead]:
    conditions = []
    # Narrow: an omitted filter previously listed every campus's leads.
    campus_id = resolve_scoped_campus_id(principal, campus_id if isinstance(campus_id, int) else None)
    if isinstance(campus_id, int):
        conditions.append(AdmissionsLead.campus_id == campus_id)
    if isinstance(stage, (LeadStage, str)):
        conditions.append(AdmissionsLead.stage == stage)
    if isinstance(source, (LeadSource, str)):
        conditions.append(AdmissionsLead.source == source)
    if isinstance(origin, (LeadOrigin, str)):
        conditions.append(AdmissionsLead.origin == origin)
    if isinstance(intent_level, (LeadIntent, str)):
        conditions.append(AdmissionsLead.intent_level == intent_level)
    if isinstance(search, str) and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                AdmissionsLead.parent_name.ilike(pattern),
                AdmissionsLead.student_name.ilike(pattern),
                AdmissionsLead.email.ilike(pattern),
                AdmissionsLead.phone.ilike(pattern),
            )
        )

    stmt = select(AdmissionsLead).order_by(AdmissionsLead.created_at.desc())
    if conditions:
        stmt = stmt.where(and_(*conditions))

    leads = (await session.execute(stmt)).scalars().all()
    return [LeadRead.model_validate(l) for l in leads]


@router.get(
    "/leads/{lead_id}",
    response_model=LeadDetailResponse,
    summary="Get Admissions Lead Details",
    description="Retrieves comprehensive lead profile with historical activity timeline and scholarship offers.",
)
async def get_lead_detail_endpoint(
    lead_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> LeadDetailResponse:
    lead_stmt = select(AdmissionsLead).where(AdmissionsLead.id == lead_id)
    lead = (await session.execute(lead_stmt)).scalar_one_or_none()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admissions lead {lead_id} not found.",
        )

    # Fetch activities
    act_stmt = (
        select(LeadActivityLog)
        .where(LeadActivityLog.lead_id == lead_id)
        .order_by(LeadActivityLog.created_at.desc())
    )
    activities = (await session.execute(act_stmt)).scalars().all()

    # Fetch offers
    off_stmt = (
        select(ScholarshipOffer)
        .where(ScholarshipOffer.lead_id == lead_id)
        .order_by(ScholarshipOffer.created_at.desc())
    )
    offers = (await session.execute(off_stmt)).scalars().all()

    lead_data = LeadRead.model_validate(lead).model_dump()
    return LeadDetailResponse(
        **lead_data,
        activities=[LeadActivityRead.model_validate(a) for a in activities],
        offers=[ScholarshipOfferRead.model_validate(o) for o in offers],
    )


@router.patch(
    "/leads/{lead_id}",
    response_model=LeadRead,
    summary="Update Admissions Lead",
    description="Updates information fields for a specific admissions lead.",
)
async def update_lead_endpoint(
    lead_id: int,
    payload: LeadUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> LeadRead:
    stmt = select(AdmissionsLead).where(AdmissionsLead.id == lead_id)
    lead = (await session.execute(stmt)).scalar_one_or_none()
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admissions lead {lead_id} not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(lead, key, value)

    lead.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    return LeadRead.model_validate(lead)


@router.patch(
    "/leads/{lead_id}/stage",
    response_model=LeadRead,
    summary="Update Lead Funnel Stage",
    description="Transitions a lead across recruitment stages (e.g. TOUR_BOOKED, OFFER_SENT, ENROLLED) and logs activity.",
)
async def update_lead_stage_endpoint(
    lead_id: int,
    payload: LeadStageUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> LeadRead:
    updated_lead = await service_update_stage(session=session, lead_id=lead_id, payload=payload)
    return LeadRead.model_validate(updated_lead)


@router.post(
    "/leads/{lead_id}/enroll",
    response_model=EnrollLeadResponse,
    summary="Enroll a Won Lead as a Student",
    description=(
        "Closes the admissions loop: creates the learner account, grants the "
        "STUDENT school role, enrolls them into a class section, and moves the "
        "lead to ENROLLED -- all in one transaction. Idempotent: calling it "
        "again returns the existing student instead of creating a second one."
    ),
    responses={
        400: {"description": "Target section/year missing, or no student email supplied"},
        404: {"description": "Lead not found"},
        409: {"description": "Lead is marked Lost"},
    },
)
async def enroll_lead_endpoint(
    lead_id: int,
    payload: EnrollLeadRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, STAFF])),
) -> EnrollLeadResponse:
    lead, result = await service_enroll_lead(
        session=session,
        lead_id=lead_id,
        section_id=payload.section_id,
        academic_year_id=payload.academic_year_id,
        student_email=payload.student_email,
        roll_number=payload.roll_number,
    )
    return EnrollLeadResponse(
        lead=LeadRead.model_validate(lead),
        student_id=result.user.id,
        enrollment_id=result.enrollment.id,
        created_user=result.created_user,
        created_role=result.created_role,
        created_enrollment=result.created_enrollment,
        already_provisioned=result.already_provisioned,
    )


@router.patch(
    "/leads/{lead_id}/consent",
    response_model=LeadRead,
    summary="Update Lead Consent & Compliance Preferences",
    description=(
        "Records an opt-in/opt-out change for a lead's outbound WhatsApp and/or "
        "Email channels. This is the compliance record that gates whether outbound "
        "automation (SDR agent, drip engine) may contact the lead on that channel."
    ),
)
async def update_lead_consent_endpoint(
    lead_id: int,
    payload: LeadConsentUpdate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_CONSENT_MANAGER)),
) -> LeadRead:
    updated_lead = await service_update_consent(session=session, lead_id=lead_id, payload=payload)
    return LeadRead.model_validate(updated_lead)


@router.post(
    "/leads/{lead_id}/activities",
    response_model=LeadActivityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Log Lead Outreach Activity",
    description="Logs an engagement touchpoint such as Call, WhatsApp message, Campus Tour, or Note.",
)
async def log_activity_endpoint(
    lead_id: int,
    payload: LeadActivityCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> LeadActivityRead:
    activity = await log_activity_for_lead(session=session, lead_id=lead_id, payload=payload)
    return LeadActivityRead.model_validate(activity)


@router.get(
    "/leads/{lead_id}/activities",
    response_model=List[LeadActivityRead],
    summary="List Lead Activity Log",
    description="Retrieves chronological timeline of interactions with the prospect.",
)
async def list_lead_activities_endpoint(
    lead_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[LeadActivityRead]:
    stmt = (
        select(LeadActivityLog)
        .where(LeadActivityLog.lead_id == lead_id)
        .order_by(LeadActivityLog.created_at.desc())
    )
    activities = (await session.execute(stmt)).scalars().all()
    return [LeadActivityRead.model_validate(a) for a in activities]


@router.post(
    "/leads/batch-score",
    response_model=BatchScoringResponse,
    summary="Run AI Lead Scoring Engine",
    description="Batch scores and classifies conversion intent for admissions leads.",
)
async def batch_score_leads_endpoint(
    payload: BatchScoringRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> BatchScoringResponse:
    return await batch_score_leads(session=session, payload=payload)


# ── Dynamic Scholarship Offers ──

@router.post(
    "/offers/generate",
    response_model=ScholarshipOfferRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Dynamic Scholarship Offer",
    description="Calculates discounted tuition, records institutional offer letter, and transitions lead to OFFER_SENT stage.",
)
async def generate_offer_endpoint(
    payload: ScholarshipOfferCreate,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> ScholarshipOfferRead:
    offer = await service_generate_offer(session=session, payload=payload)
    return ScholarshipOfferRead.model_validate(offer)


@router.get(
    "/offers",
    response_model=List[ScholarshipOfferRead],
    summary="List Scholarship Offers",
    description="List all generated scholarship and tuition offers with status filters.",
)
async def list_offers_endpoint(
    lead_id: Optional[int] = Query(None, description="Filter by Lead ID"),
    campus_id: Optional[int] = Query(None, description="Filter by Campus ID"),
    offer_status: Optional[OfferStatus] = Query(None, alias="status", description="Filter by Offer Status"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[ScholarshipOfferRead]:
    conditions = []
    if isinstance(lead_id, int):
        conditions.append(ScholarshipOffer.lead_id == lead_id)
    # Narrow: scholarship offers are campus budget decisions.
    campus_id = resolve_scoped_campus_id(principal, campus_id if isinstance(campus_id, int) else None)
    if isinstance(campus_id, int):
        conditions.append(ScholarshipOffer.campus_id == campus_id)
    if isinstance(offer_status, (OfferStatus, str)):
        conditions.append(ScholarshipOffer.status == offer_status)

    stmt = select(ScholarshipOffer).order_by(ScholarshipOffer.created_at.desc())
    if conditions:
        stmt = stmt.where(and_(*conditions))

    offers = (await session.execute(stmt)).scalars().all()
    return [ScholarshipOfferRead.model_validate(o) for o in offers]


@router.get(
    "/offers/{offer_id}",
    response_model=ScholarshipOfferRead,
    summary="Get Scholarship Offer by ID",
    description="Fetch single scholarship offer details.",
)
async def get_offer_endpoint(
    offer_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> ScholarshipOfferRead:
    stmt = select(ScholarshipOffer).where(ScholarshipOffer.id == offer_id)
    offer = (await session.execute(stmt)).scalar_one_or_none()
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scholarship offer {offer_id} not found.",
        )
    return ScholarshipOfferRead.model_validate(offer)


@router.post(
    "/offers/{offer_id}/respond",
    response_model=ScholarshipOfferRead,
    summary="Record the Family's Answer to an Offer (M27)",
    description=(
        "Records whether the family accepted or declined the offer. Until this "
        "existed, OfferStatus.ACCEPTED was defined and NOTHING ever set it: "
        "offers went DRAFT -> SENT and stopped, so a family could be offered a "
        "place with no way to take it and the funnel could not close. "
        "This is a STAFF action -- the office records what the family told "
        "them. A tokenised self-service link for parents is the obvious next "
        "step, but it would need an email or WhatsApp delivery path to carry "
        "the token, and neither is configured on this deployment; a link "
        "nobody can receive is not a feature. Accepting an offer does NOT "
        "itself create the student account: POST /leads/{lead_id}/enroll "
        "remains the explicit provisioning step, because creating a real user "
        "with a school role should never be an implicit side effect."
    ),
    responses={
        404: {"description": "Offer not found"},
        409: {"description": "Offer already has a recorded response"},
    },
)
async def respond_to_offer_endpoint(
    offer_id: int,
    payload: OfferResponseRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> ScholarshipOfferRead:
    offer = (
        await session.execute(select(ScholarshipOffer).where(ScholarshipOffer.id == offer_id))
    ).scalar_one_or_none()
    if not offer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scholarship offer {offer_id} not found.",
        )

    # Scholarship offers are campus budget decisions; a campus-bound officer
    # must not record an answer against another campus's offer.
    assert_campus_allowed(principal, offer.campus_id)

    if offer.status in (OfferStatus.ACCEPTED, OfferStatus.DECLINED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Offer {offer_id} is already recorded as {offer.status.value}. "
                "Reversing a recorded family decision is a deliberate act -- "
                "generate a fresh offer rather than overwriting the record."
            ),
        )

    lead = await _load_lead_or_404(session, offer.lead_id)

    accepted = payload.decision == OfferDecision.ACCEPTED
    offer.status = OfferStatus.ACCEPTED if accepted else OfferStatus.DECLINED
    session.add(offer)

    # A declined offer ends the conversation; LOST also stops the drip engine
    # dripping "come and see our campus" at a family who said no.
    if not accepted:
        lead.stage = LeadStage.LOST
        lead.updated_at = datetime.datetime.now(datetime.timezone.utc)
        session.add(lead)

    summary_who = payload.responded_by or "the family"
    session.add(
        LeadActivityLog(
            lead_id=lead.id,
            activity_type=ActivityType.NOTE,
            summary=(
                f"Offer {offer_id} {offer.status.value.lower()} by {summary_who}."
            ),
            metadata_json={
                "offer_id": offer_id,
                "decision": offer.status.value,
                # Who at the SCHOOL recorded it, from the authenticated
                # principal -- never from the request body.
                "recorded_by": principal.sub,
                "responded_by": payload.responded_by,
                "note": payload.note,
            },
        )
    )
    await session.commit()
    await session.refresh(offer)
    return ScholarshipOfferRead.model_validate(offer)


@router.get(
    "/review-queue",
    summary="Leads Held for Human Review",
    description=(
        "Enquiries the funnel declined to act on unsupervised: the intent "
        "matcher understood too little, no configured channel can reach the "
        "family, or the automated acknowledgement failed. Each row says which."
    ),
)
async def review_queue_endpoint(
    include_resolved: bool = Query(False, description="Include already-handled flags"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> List[Dict[str, Any]]:
    stmt = select(LeadReviewFlag, AdmissionsLead).join(
        AdmissionsLead, AdmissionsLead.id == LeadReviewFlag.lead_id
    )
    if not include_resolved:
        stmt = stmt.where(LeadReviewFlag.resolved_at.is_(None))

    # Narrow to the caller's own campus; a campus-bound officer sees their own
    # queue, not every campus's.
    scoped_campus = resolve_scoped_campus_id(principal, None)
    if isinstance(scoped_campus, int):
        stmt = stmt.where(AdmissionsLead.campus_id == scoped_campus)

    stmt = stmt.order_by(LeadReviewFlag.created_at.desc()).limit(limit)
    rows = (await session.execute(stmt)).all()

    return [
        {
            "flag_id": flag.id,
            "lead_id": flag.lead_id,
            "reason": flag.reason,
            "detail": flag.detail,
            "confidence": flag.confidence,
            "created_at": flag.created_at,
            "resolved_at": flag.resolved_at,
            "parent_name": lead.parent_name,
            "student_name": lead.student_name,
            "stage": lead.stage,
        }
        for flag, lead in rows
    ]


@router.post(
    "/review-queue/{flag_id}/resolve",
    summary="Mark a Held Lead as Handled",
    description="Records that a person has dealt with this flag. The flag is never deleted, so 'how often is the funnel unsure?' stays answerable.",
    responses={404: {"description": "Flag not found"}},
)
async def resolve_review_flag_endpoint(
    flag_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_ADMISSIONS)),
) -> Dict[str, Any]:
    flag = (
        await session.execute(select(LeadReviewFlag).where(LeadReviewFlag.id == flag_id))
    ).scalar_one_or_none()
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review flag not found.")

    lead = await _load_lead_or_404(session, flag.lead_id)
    assert_campus_allowed(principal, lead.campus_id)

    flag.resolved_at = datetime.datetime.now(datetime.timezone.utc)
    flag.resolved_by_user_id = (principal.raw_claims or {}).get("lh_user_id")
    session.add(flag)
    await session.commit()
    await session.refresh(flag)
    return {"flag_id": flag.id, "resolved_at": flag.resolved_at}


# ── Inbound Lead Webhook (M21) ──
#
# Called by external systems (Meta Lead Ads, Google Ads, the public website
# form, WhatsApp Business), never by a logged-in user — so it cannot use the
# session/principal auth the rest of this router relies on. Authenticity is a
# shared secret instead, matching the `verify_internal_key` pattern already
# used for the collab server (src/routers/boards/boards.py) rather than
# inventing a new scheme.

WEBHOOK_SECRET_ENV = "REVOPS_WEBHOOK_SECRET"

CHANNEL_SOURCE_MAP = {
    "meta": LeadSource.META_ADS,
    "google": LeadSource.GOOGLE_ADS,
    "whatsapp": LeadSource.WHATSAPP,
    "web": LeadSource.WEBSITE_FORM,
}

# Budget descriptors the AI scorer recognises (see
# services/ai/revops_lead_scoring.py's budget-fit branch). A free-text
# `budget_range` like "$10k-$15k" is deliberately NOT forwarded: the scorer
# would fall through to its unrecognised-string branch and score it BELOW the
# no-information default, i.e. stating a budget would hurt the lead.
_RECOGNISED_BUDGET_FIT = {
    "high", "excellent", "full_fee", "corporate_sponsor", "ready",
    "medium", "moderate", "standard", "flexible",
    "low", "scholarship_dependent", "financial_aid",
}


async def verify_revops_webhook_secret(
    x_webhook_secret: str = Header(..., alias="X-Webhook-Secret"),
) -> None:
    """Validate the shared secret on inbound lead webhooks.

    Fails CLOSED when `REVOPS_WEBHOOK_SECRET` is unset: an unconfigured
    deployment must not silently accept anonymous writes into the admissions
    CRM. Uses `hmac.compare_digest` so the comparison is constant-time.
    """
    expected = os.getenv(WEBHOOK_SECRET_ENV, "")
    if not expected or not hmac.compare_digest(x_webhook_secret, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook secret",
        )


def _clean(value: Any) -> Optional[str]:
    """Trimmed non-empty string, else None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@router.post(
    "/webhook/{channel}",
    summary="Multi-Channel Inbound Lead Webhook (M21)",
    description=(
        "Ingests prospective leads from Meta Lead Ads, Google Ads, the website "
        "inquiry form, or WhatsApp. Requires the X-Webhook-Secret shared secret. "
        "De-duplicates against existing leads on email/phone."
    ),
    dependencies=[Depends(verify_revops_webhook_secret)],
    responses={
        403: {"description": "Invalid or missing webhook secret"},
        422: {"description": "Payload lacks a usable contact (email or phone)"},
    },
)
async def inbound_lead_webhook(
    channel: str,
    payload: Dict[str, Any],
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    lead_source = CHANNEL_SOURCE_MAP.get(channel.lower(), LeadSource.WEBSITE_FORM)

    email = _clean(payload.get("email"))
    phone = _clean(payload.get("phone") or payload.get("mobile") or payload.get("contact_number"))

    # A lead with no way to contact it is not a lead. Reject rather than
    # fabricate a placeholder address/number, which would pollute the CRM with
    # unreachable records and defeat de-duplication (every synthesised value is
    # unique, so repeat submissions would pile up as distinct leads).
    if not email and not phone:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Webhook payload must include an email or a phone number.",
        )

    # De-duplicate: the same prospect re-submitting a form, or arriving via a
    # second channel, is the SAME lead with more engagement — not a new one.
    dedup_clauses = []
    if email:
        dedup_clauses.append(AdmissionsLead.email == email)
    if phone:
        dedup_clauses.append(AdmissionsLead.phone == phone)

    existing = (
        await session.execute(
            select(AdmissionsLead).where(or_(*dedup_clauses)).order_by(AdmissionsLead.created_at.asc())
        )
    ).scalars().first()

    if existing:
        # Record the repeat touch (this also bumps last_contacted_at via the
        # service helper) instead of creating a duplicate record.
        await log_activity_for_lead(
            session=session,
            lead_id=existing.id,
            payload=LeadActivityCreate(
                activity_type=ActivityType.NOTE,
                summary=f"Repeat inbound inquiry received via {channel.upper()} webhook.",
                metadata_json={"channel": channel, "source": lead_source.value},
            ),
        )
        return {
            "status": "deduplicated",
            "lead_id": existing.id,
            "channel": channel,
            "assigned_stage": existing.stage,
        }

    parent_name = _clean(payload.get("parent_name") or payload.get("guardian_name") or payload.get("name"))
    student_name = _clean(payload.get("student_name") or payload.get("child_name"))
    grade = _clean(
        payload.get("grade_applying_for") or payload.get("target_grade") or payload.get("grade")
    )

    if not parent_name and not student_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Webhook payload must include a parent or student name.",
        )

    campus_id = payload.get("campus_id")
    if not isinstance(campus_id, int):
        campus_id = None

    lead_create = LeadCreate(
        # One name is enough to act on; mirror it rather than inventing a
        # different person's name for the missing field.
        parent_name=parent_name or student_name,
        student_name=student_name or parent_name,
        # LeadBase requires both; store empty string for the channel that
        # genuinely did not supply one (validated above that at least one exists).
        email=email or "",
        phone=phone or "",
        grade_applying_for=grade or "",
        campus_id=campus_id,
        source=lead_source,
        origin=LeadOrigin.INBOUND,
        notes=_clean(payload.get("notes")) or f"Auto-ingested from {channel.upper()} webhook.",
    )

    lead = await create_admissions_lead(session=session, payload=lead_create)

    # Answer the family NOW. Until this wiring existed the webhook persisted
    # the lead and returned, so a 9pm enquiry sat untouched until someone
    # opened the CRM -- and `enrol_lead_in_sequence` was only ever reached from
    # the manual endpoint, so no drip sequence ever started either.
    #
    # acknowledge_new_lead NEVER raises: capture is the thing we cannot lose,
    # and a webhook that 500s because a copy generator threw would drop the
    # enquiry entirely. Failures come back as an outcome and a review flag.
    inbound_message = (
        _clean(payload.get("message"))
        or _clean(payload.get("enquiry"))
        or _clean(payload.get("notes"))
        or ""
    )
    campus_info = await _campus_info_for_lead(session, lead)
    acknowledgement = await acknowledge_new_lead(
        session,
        lead,
        channel=channel,
        message=inbound_message,
        campus_info=campus_info,
    )

    await session.refresh(lead)
    return {
        "status": "ingested",
        "lead_id": lead.id,
        "channel": channel,
        "assigned_stage": lead.stage,
        "acknowledgement": acknowledgement.as_dict(),
    }


# ── AI Lead Qualification (M22) ──

@router.post(
    "/leads/{lead_id}/ai-qualify",
    summary="AI Lead Qualification & Scoring Agent (M22)",
    description=(
        "Scores a lead through the multi-factor AI scoring engine "
        "(inquiry completeness, engagement, grade demand, budget fit, timeline) "
        "and persists the resulting score and intent level."
    ),
)
async def ai_qualify_lead(
    lead_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> Dict[str, Any]:
    stmt = select(AdmissionsLead).where(AdmissionsLead.id == lead_id)
    lead = (await session.execute(stmt)).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")

    # Real engagement signal rather than a guess: how many interactions this
    # lead has actually had logged against it.
    interactions_count = (
        await session.execute(
            select(func.count(LeadActivityLog.id)).where(LeadActivityLog.lead_id == lead_id)
        )
    ).scalar_one()

    scoring_input: Dict[str, Any] = {
        "id": lead.id,
        "parent_name": lead.parent_name,
        "student_name": lead.student_name,
        "email": lead.email,
        "phone": lead.phone,
        "grade": lead.grade_applying_for,
        "interactions_count": interactions_count,
        "has_replied_whatsapp": lead.whatsapp_consent,
        "has_opened_email": lead.email_consent,
    }
    budget_token = (lead.budget_range or "").strip().lower()
    if budget_token in _RECOGNISED_BUDGET_FIT:
        scoring_input["budget_fit"] = budget_token

    result = ai_calculate_lead_score(scoring_input)

    score = int(result["score"])
    intent_value = str(result["intent"]).upper()
    lead.lead_score = score
    lead.intent_level = LeadIntent(intent_value)
    lead.updated_at = datetime.datetime.now(datetime.timezone.utc)
    session.add(lead)
    await session.commit()
    await session.refresh(lead)

    return {
        "lead_id": lead.id,
        "student_name": lead.student_name,
        "lead_score": score,
        "intent_level": lead.intent_level,
        "breakdown": result["breakdown"],
        "key_conversion_factors": result["key_conversion_factors"],
        "recommended_next_action": result["recommended_next_action"],
    }


# ── AI RevOps Agent Endpoints (M23/M25/M26/M27/M29) ──
#
# The three services below (`revops_sdr_agent`, `revops_drip_engine`,
# `revops_offer_generator`) were 675 lines of real, consent-aware code that
# nothing called -- the "AI" in AI RevOps did not execute. These endpoints are
# the wiring, plus the conversation memory (M29) that lets the SDR agent answer
# a follow-up knowing what was already said.


async def _load_lead_or_404(session: AsyncSession, lead_id: int) -> AdmissionsLead:
    lead = (
        await session.execute(select(AdmissionsLead).where(AdmissionsLead.id == lead_id))
    ).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")
    return lead


async def _campus_info_for_lead(session: AsyncSession, lead: AdmissionsLead) -> Dict[str, Any]:
    """Real campus details for generated copy.

    The generators fall back to placeholder branding ("CSG International
    Academy", a made-up principal and phone number) when given nothing. Passing
    the actual campus keeps invented specifics out of anything a parent reads.
    """
    if not lead.campus_id:
        return {}
    from src.db.sms_campus import Campus

    campus = (
        await session.execute(select(Campus).where(Campus.id == lead.campus_id))
    ).scalar_one_or_none()
    if not campus:
        return {}
    return {"name": campus.name, "campus_name": campus.name}


@router.post(
    "/leads/{lead_id}/sdr-reply",
    summary="Conversational Admissions SDR Agent (M25/M26/M29)",
    description=(
        "Runs an inbound parent message through the SDR agent and drafts a reply, "
        "grounded in this lead's prior conversation. Both turns are stored, so the "
        "next message is answered with context rather than cold. Respects the lead's "
        "per-channel consent: an opted-out channel produces no outbound copy."
    ),
)
async def sdr_reply_to_lead(
    lead_id: int,
    payload: Dict[str, Any],
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, STAFF])),
) -> Dict[str, Any]:
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A non-empty 'message' is required.",
        )
    channel = payload.get("channel")

    lead = await _load_lead_or_404(session, lead_id)

    from src.db.revops_conversation import TurnDirection
    from src.services.ai.revops_conversation import lead_to_context, load_history, record_turn
    from src.services.ai.revops_sdr_agent import handle_admissions_inquiry

    history = await load_history(session, lead_id)
    result = handle_admissions_inquiry(
        message=message,
        lead_context=lead_to_context(lead),
        history=history,
        channel=channel,
    )

    await record_turn(
        session,
        lead_id=lead_id,
        direction=TurnDirection.INBOUND,
        message=message,
        channel=channel,
        detected_intent=result.get("intent"),
    )

    if result.get("consent_blocked"):
        # Say so plainly rather than returning empty copy that reads as a bug.
        blocked_channel = result.get("blocked_channel")
        return {
            "lead_id": lead_id,
            "consent_blocked": True,
            "blocked_channel": blocked_channel,
            "detail": (
                "This lead has opted out of that channel, so no outbound reply "
                "was generated."
            ),
            "intent": result.get("intent"),
            "history_turns_used": len(history),
        }

    await record_turn(
        session,
        lead_id=lead_id,
        direction=TurnDirection.OUTBOUND,
        message=result.get("response") or "",
        channel=channel,
        detected_intent=result.get("intent"),
    )

    return {
        "lead_id": lead_id,
        "consent_blocked": False,
        "intent": result.get("intent"),
        "all_intents": result.get("all_intents"),
        "tour_intent_detected": result.get("tour_intent_detected"),
        "response": result.get("response"),
        "suggested_actions": result.get("suggested_actions"),
        "extracted_entities": result.get("extracted_entities"),
        "history_turns_used": len(history),
    }


@router.post(
    "/leads/{lead_id}/nurture-sequence",
    summary="Generate & Enrol in Nurture Sequence (M25)",
    description=(
        "Generates the 4-stage drip sequence for a lead and schedules it. The stored "
        "sequence is what the autonomous runner later sends, so copy cannot drift "
        "between approval and delivery. Re-running refreshes the copy but never "
        "rewinds progress, so a parent is not re-sent the welcome message."
    ),
)
async def generate_lead_nurture_sequence(
    lead_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN, STAFF])),
) -> Dict[str, Any]:
    lead = await _load_lead_or_404(session, lead_id)

    if lead.stage in (LeadStage.ENROLLED, LeadStage.LOST):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Lead is already closed; nurturing it would keep marketing to a "
                "family who has enrolled or declined."
            ),
        )

    from src.services.ai.revops_nurture_runner import enrol_lead_in_sequence

    campus_info = await _campus_info_for_lead(session, lead)
    state = await enrol_lead_in_sequence(session, lead, campus_info)
    stages = list((state.sequence_json or {}).get("stages") or [])

    return {
        "lead_id": lead_id,
        "enrolled": True,
        "stages": stages,
        "last_stage_sent": state.last_stage_sent,
        "next_due_at": state.next_due_at.isoformat() if state.next_due_at else None,
        "consent": {
            "whatsapp": lead.whatsapp_consent,
            "email": lead.email_consent,
        },
    }


@router.post(
    "/leads/{lead_id}/offer-copy",
    summary="Generate Personalised Offer Letter Copy (M27)",
    description=(
        "Produces formal acceptance / scholarship letter copy for a lead. Returns the "
        "draft only -- issuing an offer remains the existing scholarship-offer endpoint, "
        "so generated text is never mistaken for a sent offer."
    ),
)
async def generate_lead_offer_copy(
    lead_id: int,
    payload: Optional[Dict[str, Any]] = None,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles([SUPER_ADMIN, SCHOOL_ADMIN])),
) -> Dict[str, Any]:
    lead = await _load_lead_or_404(session, lead_id)
    body = payload or {}

    from src.services.ai.revops_offer_generator import generate_personalized_offer_copy

    campus_info = await _campus_info_for_lead(session, lead)
    letter = generate_personalized_offer_copy(
        student_name=lead.student_name,
        grade=lead.grade_applying_for,
        discount_pct=float(body.get("discount_pct") or 0.0),
        campus_name=campus_info.get("name") or "",
        parent_name=lead.parent_name,
        annual_tuition=body.get("annual_tuition"),
        validity_days=int(body.get("validity_days") or 14),
        special_conditions=body.get("special_conditions"),
    )

    return {"lead_id": lead_id, "letter_markdown": letter, "is_draft": True}


@router.get(
    "/leads/{lead_id}/conversation",
    summary="Lead Conversation History (M29)",
    description="Stored inbound/outbound turns for this lead, oldest first.",
)
async def get_lead_conversation(
    lead_id: int,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> Dict[str, Any]:
    await _load_lead_or_404(session, lead_id)
    from src.services.ai.revops_conversation import load_history

    turns = await load_history(session, lead_id, limit=limit)
    return {"lead_id": lead_id, "turns": turns, "count": len(turns)}


@router.get(
    "/leads/{lead_id}/outbound-touches",
    summary="Outbound Delivery Record for a Lead",
    description=(
        "Every automated message attempted for this lead and what actually happened "
        "-- sent, failed with its reason, suppressed for consent, or skipped for a "
        "missing address. A suppressed message is visible here rather than silent."
    ),
)
async def get_lead_outbound_touches(
    lead_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> Dict[str, Any]:
    await _load_lead_or_404(session, lead_id)
    from src.db.revops_conversation import LeadOutboundTouch

    rows = (
        await session.execute(
            select(LeadOutboundTouch)
            .where(LeadOutboundTouch.lead_id == lead_id)
            .order_by(LeadOutboundTouch.created_at.desc())
        )
    ).scalars().all()

    return {
        "lead_id": lead_id,
        "touches": [
            {
                "stage": t.stage,
                "channel": t.channel,
                "subject": t.subject,
                "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                "detail": t.detail,
                "at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in rows
        ],
    }
