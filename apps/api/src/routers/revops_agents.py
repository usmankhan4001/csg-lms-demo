"""
AI RevOps Agents Router (M23 Research, M25 Marketing, M26 Copywriting)
=====================================================================
Mounted under `/revops/agents` -- a sub-path of the same `/revops` prefix the
admissions CRM uses (see `src/router.py`). Note the prefix is `/revops`, NOT
`/sms/revops`; a wrong prefix here silently broke the admissions kanban for a
release, so it is worth stating plainly.

These three endpoints generate and propose. None of them sends anything, and
none writes to the lead record. Delivery belongs to the nurture scheduler and
stage changes belong to the CRM endpoints -- keeping generation side-effect
free means a mis-targeted campaign or an odd-sounding draft is caught while it
is still a proposal on someone's screen.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.core.keycloak_auth import (
    SCHOOL_ADMIN,
    STAFF,
    SUPER_ADMIN,
    KeycloakUserPrincipal,
    require_roles,
)
from src.db.sms_revops import AdmissionsLead, LeadActivityLog
from src.security.features_utils.dependencies import require_revops_feature
from src.services.ai.revops_copywriting_agent import (
    generate_outreach_copy,
    refine_copy_with_model,
)
from src.services.ai.revops_marketing_agent import plan_campaign
from src.services.ai.revops_research_agent import build_lead_research_brief

# Feature gate lives on the router, matching sms_revops.py, so it is not also
# repeated at the mount point (that double-gating bug is documented in router.py).
router = APIRouter(dependencies=[Depends(require_revops_feature)])

# Same role set the CRM's own write endpoints use.
_REVOPS_ROLES = [SUPER_ADMIN, SCHOOL_ADMIN, STAFF]


def _lead_to_dict(lead: AdmissionsLead) -> Dict[str, Any]:
    """Flatten a lead row for the agent services, which take plain dicts."""
    return {
        "id": lead.id,
        "campus_id": lead.campus_id,
        "parent_name": lead.parent_name,
        "student_name": lead.student_name,
        "email": lead.email,
        "phone": lead.phone,
        "grade_applying_for": lead.grade_applying_for,
        "grade": lead.grade_applying_for,
        "source": lead.source,
        "origin": lead.origin,
        "stage": lead.stage,
        "lead_score": lead.lead_score,
        "intent_level": lead.intent_level,
        "budget_range": lead.budget_range,
        "notes": lead.notes,
        "whatsapp_consent": lead.whatsapp_consent,
        "email_consent": lead.email_consent,
        "last_contacted_at": lead.last_contacted_at,
    }


async def _get_lead_or_404(session: AsyncSession, lead_id: int) -> AdmissionsLead:
    result = await session.execute(select(AdmissionsLead).where(AdmissionsLead.id == lead_id))
    lead = result.scalars().first()
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admissions lead {lead_id} not found",
        )
    return lead


# ---------------------------------------------------------------------------
# M23 -- Research Agent
# ---------------------------------------------------------------------------

class ResearchBriefResponse(BaseModel):
    lead_id: Optional[int] = None
    student_name: Optional[str] = None
    grade_applying_for: Optional[str] = None
    known_facts: Dict[str, Any] = {}
    unknown_fields: List[str] = []
    questions_to_ask: List[str] = []
    grade_demand: Dict[str, Any] = {}
    engagement: Dict[str, Any] = {}
    score_summary: Dict[str, Any] = {}
    talking_points: List[str] = []
    sources: List[str] = []
    disclaimer: str


@router.get(
    "/agents/research/{lead_id}",
    response_model=ResearchBriefResponse,
    summary="Research brief for a lead (M23)",
    description=(
        "Compiles what the school knows about a lead, what it demonstrably "
        "does not, and the questions worth asking. No external lookup is "
        "performed and nothing about the family is inferred."
    ),
)
async def get_research_brief(
    lead_id: int,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_REVOPS_ROLES)),
) -> ResearchBriefResponse:
    lead = await _get_lead_or_404(session, lead_id)

    activity_result = await session.execute(
        select(LeadActivityLog)
        .where(LeadActivityLog.lead_id == lead_id)
        .order_by(LeadActivityLog.created_at.desc())
    )
    activities = [
        {"activity_type": a.activity_type, "summary": a.summary, "created_at": a.created_at}
        for a in activity_result.scalars().all()
    ]

    brief = build_lead_research_brief(_lead_to_dict(lead), activities=activities)
    return ResearchBriefResponse(**brief)


# ---------------------------------------------------------------------------
# M25 -- Marketing Agent
# ---------------------------------------------------------------------------

class CampaignPlanRequest(BaseModel):
    channel: str = Field(..., description="Outbound channel: 'whatsapp' or 'email'.")
    campaign_name: Optional[str] = None
    stages: Optional[List[str]] = Field(default=None, description="Funnel stages to target.")
    grades: Optional[List[str]] = None
    sources: Optional[List[str]] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    campus_id: Optional[int] = None


@router.post(
    "/agents/campaign/plan",
    summary="Propose an outreach campaign (M25)",
    description=(
        "Segments leads for a campaign and returns the audience, channel, "
        "timing and angle. Leads without EXPLICIT consent for the channel are "
        "excluded and counted -- outbound is opt-in, so unknown consent is not "
        "treated as permission. Sends nothing."
    ),
)
async def post_campaign_plan(
    payload: CampaignPlanRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_REVOPS_ROLES)),
) -> Dict[str, Any]:
    query = select(AdmissionsLead)
    # Scope to the caller's campus unless they explicitly asked for another.
    campus_id = payload.campus_id if payload.campus_id is not None else principal.campus_id
    if campus_id is not None:
        query = query.where(AdmissionsLead.campus_id == campus_id)

    result = await session.execute(query)
    leads = [_lead_to_dict(lead) for lead in result.scalars().all()]

    return plan_campaign(
        leads,
        channel=payload.channel,
        stages=payload.stages,
        grades=payload.grades,
        sources=payload.sources,
        min_score=payload.min_score,
        max_score=payload.max_score,
        campaign_name=payload.campaign_name,
    )


# ---------------------------------------------------------------------------
# M26 -- Copywriting Agent
# ---------------------------------------------------------------------------

class CopyRequest(BaseModel):
    channel: str = Field(default="email", description="'email' or 'whatsapp'.")
    stage_override: Optional[str] = Field(
        default=None,
        description="Write for a different funnel stage than the lead's current one.",
    )
    refine: bool = Field(
        default=False,
        description=(
            "Polish the draft with the configured model, metered against the "
            "org's monthly token budget. Falls back to the deterministic draft."
        ),
    )


@router.post(
    "/agents/copy/{lead_id}",
    summary="Draft outreach copy for a lead (M26)",
    description=(
        "Generates stage-appropriate subject and body copy. Always returns a "
        "DRAFT for a human to review -- this endpoint never sends."
    ),
)
async def post_outreach_copy(
    lead_id: int,
    payload: CopyRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: KeycloakUserPrincipal = Depends(require_roles(_REVOPS_ROLES)),
) -> Dict[str, Any]:
    lead = await _get_lead_or_404(session, lead_id)

    draft = generate_outreach_copy(
        _lead_to_dict(lead),
        channel=payload.channel,
        stage_override=payload.stage_override,
    )

    if payload.refine:
        draft = await refine_copy_with_model(draft, org_id=principal.org_id)

    return draft
