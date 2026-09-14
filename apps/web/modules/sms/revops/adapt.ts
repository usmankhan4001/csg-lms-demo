/**
 * Adapts the real `LeadRead` payload from `GET /sms/revops/leads/pipeline`
 * into the shape the existing admissions CRM page renders.
 *
 * The page predates the backend and its `Lead` interface asks for a number of
 * fields the API genuinely does not store. Those are mapped to explicit EMPTY
 * values here (0 / '' / []) and never to invented plausible-looking data —
 * this page was previously 100% mock and the point of wiring it is to stop it
 * lying about what the system knows.
 *
 * Fields with NO backend source today:
 *   previousSchool, estimatedTuitionPKR, discountOffered,
 *   aiScoreBreakdown, aiRecommendedPitch, aiSdrSummary, tags
 * `activityTimeline` is also empty here: real activities exist behind
 * `GET /sms/revops/leads/{id}/activities`, but the pipeline response doesn't
 * embed them and fetching per-card would be an N+1 on every board render.
 */

import type { Lead, LeadRead, LeadStage, StageId } from './types'

/**
 * STALLED has no column on this board. The backend's own `LeadStage` docstring
 * states stalled leads "re-enter the funnel at NEW_INQUIRY", so showing them
 * in the inquiry column matches documented behavior rather than hiding them.
 */
const STAGE_TO_COLUMN: Record<LeadStage, StageId> = {
  NEW_INQUIRY: 'inquiry',
  CONTACTED: 'contacted',
  TOUR_BOOKED: 'tour_booked',
  ASSESSMENT_SCHEDULED: 'assessment',
  OFFER_SENT: 'offer_sent',
  ENROLLED: 'enrolled',
  LOST: 'lost',
  STALLED: 'inquiry',
}

export const COLUMN_TO_STAGE: Record<StageId, LeadStage> = {
  inquiry: 'NEW_INQUIRY',
  contacted: 'CONTACTED',
  tour_booked: 'TOUR_BOOKED',
  assessment: 'ASSESSMENT_SCHEDULED',
  offer_sent: 'OFFER_SENT',
  enrolled: 'ENROLLED',
  lost: 'LOST',
}

const SOURCE_MAP: Record<string, Lead['source']> = {
  WEBSITE_FORM: 'web',
  WHATSAPP: 'whatsapp',
  META_ADS: 'ads',
  GOOGLE_ADS: 'ads',
  WALK_IN: 'walkin',
  REFERRAL: 'referral',
}

/** The card id the page uses; `leadIdFromCardId` reverses it for API calls. */
export function cardIdForLead(lead: LeadRead): string {
  return `lead-${lead.id}`
}

export function leadIdFromCardId(cardId: string): number | null {
  const raw = cardId.startsWith('lead-') ? cardId.slice('lead-'.length) : cardId
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
}

function formatDate(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString()
}

export function adaptLead(lead: LeadRead): Lead {
  return {
    id: cardIdForLead(lead),
    studentName: lead.student_name,
    parentName: lead.parent_name,
    parentPhone: lead.phone,
    parentEmail: lead.email,
    targetGrade: lead.grade_applying_for,
    targetCampus: lead.campus_id ? `Campus #${lead.campus_id}` : '—',
    stage: STAGE_TO_COLUMN[lead.stage] ?? 'inquiry',
    source: SOURCE_MAP[lead.source] ?? 'web',
    score: lead.lead_score,
    assignedSDR: lead.assigned_officer_id ? `Officer #${lead.assigned_officer_id}` : 'Unassigned',
    lastContact: formatDate(lead.last_contacted_at),
    createdAt: formatDate(lead.created_at),
    notes: lead.notes ?? '',

    // ---- No backend source. Deliberately empty, never fabricated. ----
    previousSchool: '',
    estimatedTuitionPKR: 0,
    discountOffered: 0,
    tags: [],
    aiScoreBreakdown: { academicFit: 0, budgetMatch: 0, parentEngagement: 0, decisionUrgency: 0 },
    aiRecommendedPitch: '',
    aiSdrSummary: '',
    activityTimeline: [],
  }
}
