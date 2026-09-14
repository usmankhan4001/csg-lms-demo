/**
 * Shared presentation rules for the admissions module.
 *
 * These live here rather than in each screen so the five admissions views
 * cannot drift into describing the same lead differently -- the kanban
 * calling a lead "Offer Sent" while the list calls it "OFFER_SENT" is the
 * kind of inconsistency that makes a product feel like separate tools.
 */

import type { LeadRead, LeadStage, OfferStatus, TouchStatus } from './types'

/** Human labels for the API's stage enum. */
export const STAGE_LABEL: Record<LeadStage, string> = {
  NEW_INQUIRY: 'New enquiry',
  CONTACTED: 'Contacted',
  TOUR_BOOKED: 'Tour booked',
  ASSESSMENT_SCHEDULED: 'Assessment scheduled',
  OFFER_SENT: 'Offer sent',
  ENROLLED: 'Enrolled',
  LOST: 'Lost',
  STALLED: 'Stalled',
}

export const STAGE_ORDER: LeadStage[] = [
  'NEW_INQUIRY',
  'CONTACTED',
  'TOUR_BOOKED',
  'ASSESSMENT_SCHEDULED',
  'OFFER_SENT',
  'ENROLLED',
  'LOST',
  'STALLED',
]

export const STAGE_TONE: Record<LeadStage, 'positive' | 'caution' | 'critical' | 'neutral'> = {
  NEW_INQUIRY: 'neutral',
  CONTACTED: 'neutral',
  TOUR_BOOKED: 'caution',
  ASSESSMENT_SCHEDULED: 'caution',
  OFFER_SENT: 'caution',
  ENROLLED: 'positive',
  LOST: 'critical',
  STALLED: 'critical',
}

export const SOURCE_LABEL: Record<string, string> = {
  WEBSITE_FORM: 'Website form',
  WHATSAPP: 'WhatsApp',
  META_ADS: 'Meta ads',
  GOOGLE_ADS: 'Google ads',
  WALK_IN: 'Walk-in',
  REFERRAL: 'Referral',
}

export const INTENT_TONE: Record<string, 'positive' | 'caution' | 'neutral'> = {
  HOT: 'positive',
  WARM: 'caution',
  COLD: 'neutral',
}

export const OFFER_TONE: Record<OfferStatus, 'positive' | 'caution' | 'critical' | 'neutral'> = {
  DRAFT: 'neutral',
  SENT: 'caution',
  ACCEPTED: 'positive',
  DECLINED: 'critical',
}

export const TOUCH_TONE: Record<TouchStatus, 'positive' | 'caution' | 'critical' | 'neutral'> = {
  SENT: 'positive',
  FAILED: 'critical',
  CONSENT_BLOCKED: 'caution',
  SKIPPED: 'neutral',
}

/** Stages where a lead is still actively moving through the funnel. */
export const ACTIVE_STAGES: LeadStage[] = [
  'NEW_INQUIRY',
  'CONTACTED',
  'TOUR_BOOKED',
  'ASSESSMENT_SCHEDULED',
  'OFFER_SENT',
]

export function isActiveStage(stage: LeadStage): boolean {
  return ACTIVE_STAGES.includes(stage)
}

/**
 * Consent, stated truthfully.
 *
 * Outbound automation is gated server-side on these two flags, so a lead with
 * neither cannot legally be contacted by the drip engine at all. The UI must
 * say so rather than offering a button that will 403 -- an operator needs to
 * know the family has to be asked, not that the software is broken.
 */
export function consentSummary(lead: Pick<LeadRead, 'whatsapp_consent' | 'email_consent'>): {
  blocked: boolean
  label: string
  tone: 'positive' | 'caution' | 'critical'
  channels: string[]
} {
  const channels: string[] = []
  if (lead.email_consent) channels.push('Email')
  if (lead.whatsapp_consent) channels.push('WhatsApp')

  if (channels.length === 0) {
    return {
      blocked: true,
      label: 'No consent',
      tone: 'critical',
      channels,
    }
  }
  return {
    blocked: false,
    label: channels.join(' + '),
    tone: channels.length === 2 ? 'positive' : 'caution',
    channels,
  }
}

/**
 * Days since a lead was last contacted, or since creation if never.
 *
 * Returns null when neither timestamp parses, so callers render "unknown"
 * rather than a misleading 0 -- "contacted today" and "we have no record of
 * contacting them" are opposite facts.
 */
export function daysSinceContact(lead: LeadRead): number | null {
  const raw = lead.last_contacted_at ?? lead.created_at
  if (!raw) return null
  const then = new Date(raw).getTime()
  if (Number.isNaN(then)) return null
  return Math.floor((Date.now() - then) / 86_400_000)
}

/** Staleness banding for the officer worklist. */
export type Staleness = 'fresh' | 'ageing' | 'stale' | 'unknown'

export function staleness(lead: LeadRead): Staleness {
  const days = daysSinceContact(lead)
  if (days === null) return 'unknown'
  if (days <= 2) return 'fresh'
  if (days <= 7) return 'ageing'
  return 'stale'
}

export const STALENESS_TONE: Record<Staleness, 'positive' | 'caution' | 'critical' | 'neutral'> = {
  fresh: 'positive',
  ageing: 'caution',
  stale: 'critical',
  unknown: 'neutral',
}

export function formatDate(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Currency, deliberately unlocalised beyond grouping.
 *
 * The API returns a bare number with no currency code, so stamping one here
 * would be inventing a fact. Callers label the column instead.
 */
export function formatAmount(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
}
