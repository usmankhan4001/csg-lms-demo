/**
 * Real fetch calls against `apps/api/src/routers/sms_revops.py`
 * (mounted at `/api/v1/revops` -- NOT /sms/revops; see router.py:598-601).
 *
 * The `/webhook/{channel}` endpoint is deliberately absent: it is a
 * server-to-server intake guarded by an `X-Webhook-Secret` shared secret, so
 * a browser has no business calling it. Receptionists capture walk-ins and
 * phone inquiries through `createLead` below instead.
 */

import { apiGet, apiPatch, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  BatchScoringRequest,
  BatchScoringResponse,
  CampaignPlan,
  CampaignPlanRequest,
  LeadActivityCreate,
  LeadActivityRead,
  LeadConsentUpdate,
  LeadConversationResponse,
  LeadCreate,
  LeadDetailResponse,
  LeadListFilters,
  LeadUpdate,
  EnrollLeadRequest,
  EnrollLeadResponse,
  LeadOutboundTouchesResponse,
  LeadQualifyResult,
  LeadRead,
  LeadStageUpdate,
  NurtureSequenceResult,
  OfferCopyResult,
  OfferStatus,
  OutreachCopyDraft,
  PipelineResponse,
  ResearchBrief,
  ScholarshipOfferCreate,
  ScholarshipOfferRead,
  SdrReplyResult,
} from './types'

export function getLeadPipeline(campusId?: number): Promise<PipelineResponse> {
  return apiGet<PipelineResponse>(`/revops/leads/pipeline${toQueryString({ campus_id: campusId })}`)
}

export function updateLeadStage(leadId: number, payload: LeadStageUpdate): Promise<LeadRead> {
  return apiPatch<LeadRead>(`/revops/leads/${leadId}/stage`, payload)
}

/** `POST /leads` -- sms_revops.py:64. Manual capture for walk-ins / phone inquiries. */
export function createLead(payload: LeadCreate): Promise<LeadRead> {
  return apiPost<LeadRead>('/revops/leads', payload)
}

/**
 * `GET /leads` -- sms_revops.py:117. The FLAT list, as distinct from
 * `getLeadPipeline`'s stage-grouped kanban payload.
 *
 * Server-side filters are exactly: campus_id, stage, source, origin,
 * intent_level, search (parent/student name, email, phone). It always orders
 * by `created_at` DESC and takes no limit -- so officer, date-range and any
 * other sort are client-side over this result, not query params. Passing an
 * unsupported filter would be silently ignored rather than erroring.
 */
export function listLeads(filters: LeadListFilters = {}): Promise<LeadRead[]> {
  // Spelled out rather than spread: `toQueryString` only accepts scalars, and
  // passing the object through a cast would let a future non-scalar field on
  // LeadListFilters serialise as "[object Object]" instead of failing to
  // compile.
  return apiGet<LeadRead[]>(
    `/revops/leads${toQueryString({
      campus_id: filters.campus_id,
      stage: filters.stage,
      source: filters.source,
      origin: filters.origin,
      intent_level: filters.intent_level,
      search: filters.search,
    })}`
  )
}

/**
 * `GET /leads/{id}` -- sms_revops.py:165.
 *
 * The endpoint actually returns `LeadDetailResponse` (LeadRead PLUS its
 * activities and offers), so one request populates a whole detail page. This
 * was previously typed as a bare `LeadRead`, which meant the embedded
 * activities and offers were being fetched and thrown away.
 */
export function getLead(leadId: number): Promise<LeadDetailResponse> {
  return apiGet<LeadDetailResponse>(`/revops/leads/${leadId}`)
}

/** `PATCH /leads/{id}` -- sms_revops.py:208. Partial update; unset fields untouched. */
export function updateLead(leadId: number, payload: LeadUpdate): Promise<LeadRead> {
  return apiPatch<LeadRead>(`/revops/leads/${leadId}`, payload)
}

/**
 * `POST /leads/{id}/enroll` -- sms_revops.py:255. THE seam between admissions
 * and the school proper: creates the learner account, grants the STUDENT
 * role, enrols them into a section and moves the lead to ENROLLED, in one
 * transaction. Idempotent -- a repeat call returns the existing student and
 * sets `already_provisioned`, so the UI must read that rather than assuming
 * success means "new".
 */
export function enrollLead(
  leadId: number,
  payload: EnrollLeadRequest
): Promise<EnrollLeadResponse> {
  return apiPost<EnrollLeadResponse>(`/revops/leads/${leadId}/enroll`, payload)
}

/** `POST /leads/batch-score` -- sms_revops.py:353. Persists scores, so refetch after. */
export function batchScoreLeads(payload: BatchScoringRequest = {}): Promise<BatchScoringResponse> {
  return apiPost<BatchScoringResponse>('/revops/leads/batch-score', payload)
}

/** `GET /offers/{id}` -- sms_revops.py:416. */
export function getOffer(offerId: number): Promise<ScholarshipOfferRead> {
  return apiGet<ScholarshipOfferRead>(`/revops/offers/${offerId}`)
}

/**
 * `PATCH /leads/{id}/consent` -- sms_revops.py:272.
 * The compliance record that gates whether outbound automation may contact
 * this lead on a channel. At least one channel must be supplied.
 */
export function updateLeadConsent(leadId: number, payload: LeadConsentUpdate): Promise<LeadRead> {
  return apiPatch<LeadRead>(`/revops/leads/${leadId}/consent`, payload)
}

/** `GET /leads/{id}/activities` -- sms_revops.py:309. Chronological, newest first. */
export function listLeadActivities(leadId: number): Promise<LeadActivityRead[]> {
  return apiGet<LeadActivityRead[]>(`/revops/leads/${leadId}/activities`)
}

/** `POST /leads/{id}/activities` -- sms_revops.py:292. */
export function logLeadActivity(
  leadId: number,
  payload: LeadActivityCreate
): Promise<LeadActivityRead> {
  return apiPost<LeadActivityRead>(`/revops/leads/${leadId}/activities`, payload)
}

/**
 * `POST /leads/{id}/ai-qualify` -- sms_revops.py:576.
 * Runs the real 5-factor scoring engine and PERSISTS the resulting score and
 * intent onto the lead, so this mutates rather than merely reads.
 */
export function aiQualifyLead(leadId: number): Promise<LeadQualifyResult> {
  return apiPost<LeadQualifyResult>(`/revops/leads/${leadId}/ai-qualify`)
}

/**
 * `GET /offers` -- sms_revops.py:385. Filters: lead_id, campus_id, and
 * `status` (the query alias for `offer_status`). Ordered created_at DESC.
 */
export function listOffers(params: {
  leadId?: number
  campusId?: number
  status?: OfferStatus
} = {}): Promise<ScholarshipOfferRead[]> {
  return apiGet<ScholarshipOfferRead[]>(
    `/revops/offers${toQueryString({
      lead_id: params.leadId,
      campus_id: params.campusId,
      status: params.status,
    })}`
  )
}

/**
 * `POST /offers/generate` -- sms_revops.py:345.
 * Also transitions the lead to OFFER_SENT, so the board must refetch after.
 */
export function generateOffer(payload: ScholarshipOfferCreate): Promise<ScholarshipOfferRead> {
  return apiPost<ScholarshipOfferRead>('/revops/offers/generate', payload)
}

/* ------------------------------------------------------------------ AI ----
 * M23/M25/M26/M27/M29, wired against `sms_revops.py` and `revops_agents.py`.
 *
 * None of these send anything. They draft or propose; the hourly nurture
 * runner is what delivers, and only to a lead that has consented.
 *
 * They also REFUSE rather than invent: a lead with no campus, or an offer
 * with no tuition, raises server-side (`MissingSchoolIdentity` /
 * `MissingOfferFacts`) and comes back as a 4xx whose message names the fix.
 * Callers must surface `ApiError.message` verbatim rather than collapsing it
 * into a generic failure -- the message is how the operator learns what to
 * configure.
 */

/** `GET /leads/{id}/conversation` -- sms_revops.py:841. Oldest turn first. */
export function getLeadConversation(
  leadId: number,
  limit?: number
): Promise<LeadConversationResponse> {
  return apiGet<LeadConversationResponse>(
    `/revops/leads/${leadId}/conversation${toQueryString({ limit })}`
  )
}

/**
 * `GET /leads/{id}/outbound-touches` -- sms_revops.py:859.
 * Every automated message attempted and what actually happened to it.
 */
export function getLeadOutboundTouches(leadId: number): Promise<LeadOutboundTouchesResponse> {
  return apiGet<LeadOutboundTouchesResponse>(`/revops/leads/${leadId}/outbound-touches`)
}

/**
 * `POST /leads/{id}/sdr-reply` -- sms_revops.py:677.
 * Stores both turns, so the next message is answered with context. A lead
 * opted out of the channel gets `consent_blocked: true` and no copy.
 */
export function draftSdrReply(
  leadId: number,
  payload: { message: string; channel?: string | null }
): Promise<SdrReplyResult> {
  return apiPost<SdrReplyResult>(`/revops/leads/${leadId}/sdr-reply`, payload)
}

/**
 * `POST /leads/{id}/nurture-sequence` -- sms_revops.py:761.
 * Schedules the drip. Re-running refreshes copy but never rewinds progress,
 * so a parent is not re-sent the welcome message.
 */
export function startNurtureSequence(leadId: number): Promise<NurtureSequenceResult> {
  return apiPost<NurtureSequenceResult>(`/revops/leads/${leadId}/nurture-sequence`)
}

/**
 * `POST /leads/{id}/offer-copy` -- sms_revops.py:806.
 * Draft letter text only. Issuing an offer is still `generateOffer` above, so
 * generated text can never be mistaken for a sent offer.
 */
export function generateOfferCopy(
  leadId: number,
  payload?: {
    discount_pct?: number
    annual_tuition?: number
    validity_days?: number
    special_conditions?: string | null
  }
): Promise<OfferCopyResult> {
  return apiPost<OfferCopyResult>(`/revops/leads/${leadId}/offer-copy`, payload ?? {})
}

/**
 * `GET /agents/research/{id}` -- revops_agents.py:102.
 * No external lookup, nothing inferred about the family: gaps come back in
 * `unknown_fields` instead of being filled in.
 */
export function getLeadResearchBrief(leadId: number): Promise<ResearchBrief> {
  return apiGet<ResearchBrief>(`/revops/agents/research/${leadId}`)
}

/** `POST /agents/copy/{id}` -- revops_agents.py:203. Always a DRAFT. */
export function draftOutreachCopy(
  leadId: number,
  payload: { channel?: string; stage_override?: string | null; refine?: boolean } = {}
): Promise<OutreachCopyDraft> {
  return apiPost<OutreachCopyDraft>(`/revops/agents/copy/${leadId}`, {
    channel: payload.channel ?? 'email',
    stage_override: payload.stage_override ?? null,
    refine: payload.refine ?? false,
  })
}

/**
 * `POST /agents/campaign/plan` -- revops_agents.py:148.
 * Segment-level, so it lives on the insights page rather than a lead dialog.
 * Proposes only; `status` is always PROPOSED and nothing is contacted.
 */
export function planCampaign(payload: CampaignPlanRequest): Promise<CampaignPlan> {
  return apiPost<CampaignPlan>('/revops/agents/campaign/plan', payload)
}
