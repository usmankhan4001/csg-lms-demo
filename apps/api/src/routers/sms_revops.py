import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import KeycloakUserPrincipal, get_current_user_principal
from src.db.sms_revops import (
    ActivityType,
    AdmissionsLead,
    LeadActivityLog,
    LeadIntent,
    LeadSource,
    LeadStage,
    OfferStatus,
    ScholarshipOffer,
)
from src.schemas.sms_revops import (
    BatchScoringRequest,
    BatchScoringResponse,
    LeadActivityCreate,
    LeadActivityRead,
    LeadCreate,
    LeadDetailResponse,
    LeadRead,
    LeadStageUpdate,
    LeadUpdate,
    PipelineResponse,
    ScholarshipOfferCreate,
    ScholarshipOfferRead,
)
from src.security.features_utils.dependencies import require_revops_feature
from src.services.sms.revops import (
    batch_score_leads,
    create_admissions_lead,
    generate_scholarship_offer as service_generate_offer,
    get_pipeline_kanban,
    log_activity_for_lead,
    update_lead_stage as service_update_stage,
)

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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> LeadRead:
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
    filter_campus_id = campus_id if isinstance(campus_id, int) else None
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
    intent_level: Optional[LeadIntent] = Query(None, description="Filter by Intent Level"),
    search: Optional[str] = Query(None, description="Search parent/student name, email, or phone"),
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> List[LeadRead]:
    conditions = []
    if isinstance(campus_id, int):
        conditions.append(AdmissionsLead.campus_id == campus_id)
    if isinstance(stage, (LeadStage, str)):
        conditions.append(AdmissionsLead.stage == stage)
    if isinstance(source, (LeadSource, str)):
        conditions.append(AdmissionsLead.source == source)
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
) -> LeadRead:
    updated_lead = await service_update_stage(session=session, lead_id=lead_id, payload=payload)
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
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
    principal: KeycloakUserPrincipal = Depends(get_current_user_principal),
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
