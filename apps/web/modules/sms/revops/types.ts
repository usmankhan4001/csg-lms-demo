/**
 * Types mirroring `apps/api/src/schemas/sms_revops.py` and the enums in
 * `apps/api/src/db/sms_revops.py`.
 */

import type { ElementType } from 'react'

export type LeadStage =
  | 'NEW_INQUIRY'
  | 'CONTACTED'
  | 'TOUR_BOOKED'
  | 'ASSESSMENT_SCHEDULED'
  | 'OFFER_SENT'
  | 'ENROLLED'
  | 'LOST'
  | 'STALLED'

export type LeadSource = 'WEBSITE_FORM' | 'WHATSAPP' | 'META_ADS' | 'GOOGLE_ADS' | 'WALK_IN' | 'REFERRAL'
export type LeadOrigin = 'INBOUND' | 'OUTBOUND'
export type LeadIntent = 'HOT' | 'WARM' | 'COLD'

export interface LeadRead {
  id: number
  parent_name: string
  student_name: string
  email: string
  phone: string
  grade_applying_for: string
  campus_id?: number | null
  academic_year_id?: number | null
  source: LeadSource
  origin: LeadOrigin
  stage: LeadStage
  lead_score: number
  intent_level: LeadIntent
  budget_range?: string | null
  notes?: string | null
  assigned_officer_id?: number | null
  whatsapp_consent: boolean
  email_consent: boolean
  last_contacted_at?: string | null
  created_at: string
  updated_at: string
}

export interface PipelineStageGroup {
  stage: LeadStage
  stage_name: string
  count: number
  leads: LeadRead[]
}

export interface PipelineResponse {
  stages: PipelineStageGroup[]
  total_leads: number
}

export interface LeadStageUpdate {
  stage: LeadStage
  reason?: string | null
  metadata_json?: Record<string, unknown> | null
}

/** `LeadCreate` -- schemas/sms_revops.py:38, extending LeadBase (:15). */
export interface LeadCreate {
  parent_name: string
  student_name: string
  email: string
  phone: string
  grade_applying_for: string
  campus_id?: number | null
  academic_year_id?: number | null
  source?: LeadSource
  /** Left unset lets the server infer inbound/outbound from `source`. */
  origin?: LeadOrigin | null
  budget_range?: string | null
  notes?: string | null
  assigned_officer_id?: number | null
  whatsapp_consent?: boolean
  email_consent?: boolean
  intent_level?: LeadIntent | null
}

/** `LeadConsentUpdate` -- schemas/sms_revops.py:79. At least one channel required. */
export interface LeadConsentUpdate {
  whatsapp_consent?: boolean
  email_consent?: boolean
  reason?: string | null
}

/** `ActivityType` -- db/sms_revops.py:70. */
export type ActivityType =
  | 'NOTE'
  | 'CALL'
  | 'EMAIL'
  | 'WHATSAPP'
  | 'TOUR'
  | 'STAGE_CHANGE'
  | 'CONSENT_UPDATE'

/** `LeadActivityCreate` -- schemas/sms_revops.py:96. */
export interface LeadActivityCreate {
  activity_type: ActivityType
  summary: string
  metadata_json?: Record<string, unknown> | null
}

/** `LeadActivityRead` -- schemas/sms_revops.py:103. */
export interface LeadActivityRead {
  id: number
  lead_id: number
  activity_type: ActivityType
  summary: string
  metadata_json?: Record<string, unknown> | null
  created_at: string
}

/**
 * Return shape of `POST /leads/{id}/ai-qualify` -- sms_revops.py:629-637.
 * `breakdown` keys come straight from the scorer
 * (services/ai/revops_lead_scoring.py:221-227).
 */
export interface LeadScoreBreakdown {
  completeness_score: number
  responsiveness_score: number
  grade_demand_score: number
  budget_fit_score: number
  timeline_score: number
}

export interface LeadQualifyResult {
  lead_id: number
  student_name: string
  lead_score: number
  intent_level: LeadIntent
  breakdown: LeadScoreBreakdown
  key_conversion_factors: string[]
  recommended_next_action: string
}

/**
 * `OfferStatus` -- db/sms_revops.py:81. Exactly these four; there is no
 * EXPIRED state, so do not branch on one.
 */
export type OfferStatus = 'DRAFT' | 'SENT' | 'ACCEPTED' | 'DECLINED'

/** `ScholarshipOfferCreate` -- schemas/sms_revops.py:115. */
export interface ScholarshipOfferCreate {
  lead_id: number
  campus_id?: number | null
  base_tuition_amount: number
  tuition_discount_percentage?: number
  /** ISO date (YYYY-MM-DD). */
  valid_until: string
  status?: OfferStatus
  remarks?: string | null
}

/** `ScholarshipOfferRead` -- schemas/sms_revops.py:126. */
export interface ScholarshipOfferRead {
  id: number
  lead_id: number
  campus_id?: number | null
  tuition_discount_percentage: number
  final_tuition_amount: number
  valid_until: string
  status: OfferStatus
  offer_letter_url?: string | null
  created_at: string
}

/* ------------------------------------------------------------------ AI ----
 * M23/M25/M26/M27/M29. Every one of these returns a DRAFT or a PROPOSAL --
 * none of them send. Delivery is the hourly nurture runner's job, and only
 * for leads that have consented.
 */

/** Turn shape from `GET /leads/{id}/conversation` -- sms_revops.py:841. */
export interface LeadConversationTurn {
  direction: 'INBOUND' | 'OUTBOUND'
  message: string
  channel?: string | null
  detected_intent?: string | null
  created_at?: string | null
}

export interface LeadConversationResponse {
  lead_id: number
  turns: LeadConversationTurn[]
  count: number
}

/**
 * `TouchStatus` -- db/revops_conversation.py. A FAILED or CONSENT_BLOCKED row
 * existing at all is the point of this table: a suppressed message is visible
 * rather than silently dropped.
 */
export type TouchStatus = 'SENT' | 'FAILED' | 'CONSENT_BLOCKED' | 'SKIPPED'

/** One row of `GET /leads/{id}/outbound-touches` -- sms_revops.py:859. */
export interface LeadOutboundTouch {
  stage: number
  channel: string
  subject?: string | null
  status: TouchStatus
  detail?: string | null
  at?: string | null
}

export interface LeadOutboundTouchesResponse {
  lead_id: number
  touches: LeadOutboundTouch[]
}

/**
 * `POST /leads/{id}/sdr-reply` -- sms_revops.py:677. A consent-blocked lead
 * returns `consent_blocked: true` with a `detail` explaining it, NOT empty
 * copy; the two shapes are unioned so a caller has to handle both.
 */
export interface SdrReplyBlocked {
  lead_id: number
  consent_blocked: true
  blocked_channel?: string | null
  detail: string
  intent?: string | null
  history_turns_used: number
}

export interface SdrReplyDrafted {
  lead_id: number
  consent_blocked: false
  intent?: string | null
  all_intents?: string[] | null
  tour_intent_detected?: boolean | null
  response?: string | null
  suggested_actions?: string[] | null
  extracted_entities?: Record<string, unknown> | null
  history_turns_used: number
}

export type SdrReplyResult = SdrReplyBlocked | SdrReplyDrafted

/** One generated drip stage, as stored in `sequence_json.stages`. */
export interface NurtureStage {
  stage: number
  channel?: string
  subject?: string
  body?: string
  send_after_days?: number
  consent_blocked?: boolean
  [key: string]: unknown
}

/** `POST /leads/{id}/nurture-sequence` -- sms_revops.py:761. */
export interface NurtureSequenceResult {
  lead_id: number
  enrolled: boolean
  stages: NurtureStage[]
  last_stage_sent?: number | null
  next_due_at?: string | null
  consent: { whatsapp: boolean; email: boolean }
}

/** `POST /leads/{id}/offer-copy` -- sms_revops.py:806. Draft markdown only. */
export interface OfferCopyResult {
  lead_id: number
  letter_markdown: string
  is_draft: boolean
}

/**
 * `GET /agents/research/{id}` -- revops_agents.py:102. `unknown_fields` is
 * load-bearing: the agent performs no external lookup and infers nothing
 * about a family, so a gap is reported rather than filled.
 */
export interface ResearchBrief {
  lead_id?: number | null
  student_name?: string | null
  grade_applying_for?: string | null
  known_facts: Record<string, unknown>
  unknown_fields: string[]
  questions_to_ask: string[]
  grade_demand: Record<string, unknown>
  engagement: Record<string, unknown>
  score_summary: Record<string, unknown>
  talking_points: string[]
  sources: string[]
  disclaimer: string
}

/** `POST /agents/copy/{id}` -- revops_agents.py:203. Always a DRAFT. */
export interface OutreachCopyDraft {
  lead_id?: number | null
  channel: string
  stage?: string | null
  subject?: string | null
  body?: string | null
  status: 'DRAFT'
  refined?: boolean
  refinement_note?: string | null
  [key: string]: unknown
}

export interface CampaignPlanRequest {
  channel: string
  campaign_name?: string | null
  stages?: string[] | null
  grades?: string[] | null
  sources?: string[] | null
  min_score?: number | null
  max_score?: number | null
  campus_id?: number | null
}

/**
 * `POST /agents/campaign/plan` -- revops_agents.py:148. Outbound is opt-IN
 * here: a lead without EXPLICIT consent for the channel is excluded and
 * counted, which is stricter than the SDR agent's reply path on purpose.
 */
export interface CampaignPlan {
  campaign_name: string
  channel: string
  recommended_channel?: string | null
  dominant_stage?: string | null
  stage_mix: Record<string, number>
  angle: string
  timing: string
  audience: {
    eligible_count: number
    eligible_lead_ids: number[]
    excluded_no_consent: number
    excluded_no_consent_ids: number[]
    excluded_by_stage: number
    excluded_by_filter: number
    reasons: Record<string, string>
  }
  warnings: string[]
  status: 'PROPOSED'
  note: string
}

// -----------------------------------------------------------------------------
// Admissions CRM board view-model
//
// These describe the KANBAN BOARD's own shape, not the API's. They previously
// lived in `app/(dashboard)/admissions/crm/page.tsx` and were imported from
// that route file, which is why the legacy shell could never be retired.
// `adapt.ts` maps the real `LeadRead` payload onto them.
//
// Note the deliberate mismatch with `LeadStage` above: the board has no
// STALLED column, and `adapt.ts` folds STALLED into `inquiry` because the
// backend's own docstring says stalled leads re-enter the funnel there.
// -----------------------------------------------------------------------------

export type StageId =
  | 'inquiry'
  | 'contacted'
  | 'tour_booked'
  | 'assessment'
  | 'offer_sent'
  | 'enrolled'
  | 'lost'

export interface PipelineStage {
  id: StageId
  title: string
  color: string
  borderAccent: string
  bgLight: string
  badgeColor: string
  icon: ElementType
  description: string
}

export interface ActivityLog {
  id: string
  type: 'call' | 'whatsapp' | 'email' | 'tour' | 'assessment' | 'ai_drip' | 'note'
  title: string
  description: string
  timestamp: string
  agent: string
}

// Named to avoid colliding with the API's own `LeadScoreBreakdown` above
// (completeness/responsiveness/grade-demand/budget/timeline). This is the
// board's older four-factor display shape, which `adapt.ts` fills with zeros
// because the pipeline payload does not carry a breakdown.
export interface BoardLeadScoreBreakdown {
  academicFit: number
  budgetMatch: number
  parentEngagement: number
  decisionUrgency: number
}

export interface Lead {
  id: string
  studentName: string
  parentName: string
  parentPhone: string
  parentEmail: string
  targetGrade: string
  targetCampus: string
  previousSchool: string
  stage: StageId
  source: 'whatsapp' | 'ads' | 'web' | 'referral' | 'walkin'
  score: number // 0-100
  estimatedTuitionPKR: number
  discountOffered: number // 0-50%
  assignedSDR: string
  lastContact: string
  createdAt: string
  notes: string
  tags: string[]
  aiScoreBreakdown: BoardLeadScoreBreakdown
  aiRecommendedPitch: string
  aiSdrSummary: string
  activityTimeline: ActivityLog[]
}

/* --------------------------------------------------- Detail / list / enrol --
 * Shapes that already exist server-side but were never surfaced. The kanban
 * only ever consumed `PipelineResponse`, so the list, detail, update and
 * enrolment contracts below went unused despite being live.
 */

/** `LeadDetailResponse` -- schemas/sms_revops.py:175. Extends LeadRead. */
export interface LeadDetailResponse extends LeadRead {
  activities: LeadActivityRead[]
  offers: ScholarshipOfferRead[]
}

/** `LeadUpdate` -- schemas/sms_revops.py:43. Every field optional. */
export interface LeadUpdate {
  parent_name?: string
  student_name?: string
  email?: string
  phone?: string
  grade_applying_for?: string
  campus_id?: number | null
  academic_year_id?: number | null
  source?: LeadSource
  origin?: LeadOrigin
  stage?: LeadStage
  lead_score?: number
  intent_level?: LeadIntent
  budget_range?: string | null
  notes?: string | null
  assigned_officer_id?: number | null
  last_contacted_at?: string | null
}

/** Query filters accepted by `GET /leads` -- sms_revops.py:122-127. */
export interface LeadListFilters {
  campus_id?: number
  stage?: LeadStage
  source?: LeadSource
  origin?: LeadOrigin
  intent_level?: LeadIntent
  search?: string
}

/**
 * `EnrollLeadRequest` -- schemas/sms_revops.py:181.
 *
 * `student_email` is REQUIRED and deliberately not derived from the lead:
 * `AdmissionsLead.email` is the PARENT's address, so reusing it would
 * mis-attribute the account or collide for a second sibling.
 */
export interface EnrollLeadRequest {
  section_id: number
  academic_year_id: number
  student_email: string
  roll_number?: string | null
}

/**
 * `EnrollLeadResponse` -- schemas/sms_revops.py:196. The `created_*` and
 * `already_provisioned` flags exist so the UI can say "already enrolled"
 * rather than implying a duplicate was made; the call is idempotent.
 */
export interface EnrollLeadResponse {
  lead: LeadRead
  student_id: number
  enrollment_id: number
  created_user: boolean
  created_role: boolean
  created_enrollment: boolean
  already_provisioned: boolean
}

/** `BatchScoringRequest` -- drives `POST /leads/batch-score`. */
export interface BatchScoringRequest {
  lead_ids?: number[] | null
  campus_id?: number | null
  stage?: LeadStage | null
}

export interface BatchScoringResponse {
  scored_count: number
  results: LeadQualifyResult[]
  [key: string]: unknown
}
