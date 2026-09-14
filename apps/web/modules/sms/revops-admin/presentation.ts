/**
 * Shared rendering rules for the RevOps admin screens.
 *
 * Kept in one place because both screens describe the same two concepts --
 * where a setting came from, and whether a knowledge entry is safe to quote --
 * and two copies would eventually disagree about the same row.
 */

import type {
  KnowledgeEntryRead,
  KnowledgeEntryStatus,
  LeadScoringSettings,
  RevOpsConfigSource,
} from './types'

type Tone = 'positive' | 'neutral' | 'caution' | 'critical'

/**
 * How a config group's origin is shown.
 *
 * DEFAULT is deliberately NOT styled as a saved choice: nothing has been
 * configured, the built-in behaviour is running, and an admin who reads it as
 * "someone set this" will not realise their first edit creates the row.
 */
export function describeConfigSource(source: RevOpsConfigSource): {
  label: string
  tone: Tone
  explanation: string
} {
  switch (source) {
    case 'CAMPUS':
      return {
        label: 'Campus override',
        tone: 'positive',
        explanation:
          'Set for this campus. Editing changes this campus only; other campuses keep what they inherit.',
      }
    case 'ORG':
      return {
        label: 'Inherited from organisation',
        tone: 'neutral',
        explanation:
          'No campus setting exists, so the organisation-wide values are in force. Saving while a campus is selected creates a campus override.',
      }
    case 'DEFAULT':
    default:
      return {
        label: 'Built-in default',
        tone: 'caution',
        explanation:
          'Nothing has been configured at either level — these are the values the code ships with, not a saved choice. Saving stores them for the first time.',
      }
  }
}

/**
 * The weights are a RATIO, not a percentage out of 100.
 *
 * `total_possible` is returned by the scoring service alongside every score
 * (services/sms/revops_config.py:241) precisely so a number is never shown
 * "out of 100" when re-weighting means it is not. This screen cannot call that
 * service, so it states the ceiling the current weights produce instead of
 * implying one.
 */
export function scoringWeightTotal(values: Partial<LeadScoringSettings>): number {
  return (
    Number(values.weight_completeness ?? 0) +
    Number(values.weight_responsiveness ?? 0) +
    Number(values.weight_grade_demand ?? 0) +
    Number(values.weight_budget_fit ?? 0) +
    Number(values.weight_timeline ?? 0)
  )
}

/**
 * Whether the human-review gate is actually doing anything.
 *
 * 0.0 is the shipped default and means NO gate. Rendering it as "review below
 * 0" would read as a configured threshold rather than an unused feature.
 */
export function describeReviewGate(threshold: number): {
  active: boolean
  label: string
} {
  if (!threshold || threshold <= 0) {
    return {
      active: false,
      label: 'Off — every lead advances without human review',
    }
  }
  return {
    active: true,
    label: `On — leads scoring below ${threshold} await human review`,
  }
}

export function describeKnowledgeStatus(status: KnowledgeEntryStatus): {
  label: string
  tone: Tone
} {
  switch (status) {
    case 'PUBLISHED':
      return { label: 'Published', tone: 'positive' }
    case 'ARCHIVED':
      return { label: 'Archived', tone: 'neutral' }
    case 'DRAFT':
    default:
      return { label: 'Draft', tone: 'caution' }
  }
}

/**
 * A knowledge entry's citation, or the plain fact that it has none.
 *
 * Never invents a label for a bare URL and never implies a source exists. The
 * whole point of `is_sourceless` is that a reviewer can find unbacked claims
 * before an agent quotes one at a family.
 */
export function describeSource(entry: KnowledgeEntryRead): string {
  if (entry.is_sourceless) return 'No source recorded'
  return entry.source_label || entry.source_url || 'No source recorded'
}

/** Only a published, sourced entry is unambiguously safe for an agent to quote. */
export function isQuotableWithConfidence(entry: KnowledgeEntryRead): boolean {
  return entry.status === 'PUBLISHED' && !entry.is_sourceless
}
