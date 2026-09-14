/**
 * Shared formatting and tone mapping for the gradebook module.
 *
 * Three rules encoded here rather than repeated per screen:
 *
 * 1. NO GRADE IS NOT A ZERO GRADE. `cumulative_gpa` and `unweighted_gpa` are
 *    nullable (`schemas/sms_gradebook.py:125`, and `calculate_cumulative_gpa`
 *    returns `unweighted_gpa: None`). The GPA endpoint previously returned a
 *    hardcoded 4.0 / "Good Standing" / honor_roll: true for a student with
 *    ZERO grades — live in the router for weeks. Rendering a null as "0.00" or
 *    "F" would rebuild the same lie from the other direction.
 *
 * 2. `drafted_ungraded` IS NOT `drafted`. The backend returns them separately
 *    precisely so a teacher cannot send a section believing every card carried
 *    a grade. They must never share a tone or a label.
 *
 * 3. STUDENT NAMES COME FROM A SECOND CALL. `StudentEnrollmentRead` carries no
 *    joined name, so the roster alone renders "Student #37". The attendance
 *    module's `useStudentNames` hook is reused rather than duplicated — it is
 *    generic (campus id in, name map out) and not attendance-specific.
 */

import type { StatusTone } from '@/components/widgets'
import type { ReportCardOutcome, ReportCardStatus } from './types'

/**
 * Tone per batch outcome.
 *
 * `drafted_ungraded` is CAUTION, not positive: the operation succeeded, but
 * the resulting card has no grade on it. Treating it as a success is exactly
 * the misreading this distinction exists to prevent.
 */
export const OUTCOME_TONE: Record<ReportCardOutcome, StatusTone> = {
  drafted: 'positive',
  drafted_ungraded: 'caution',
  recalculated: 'info',
  sent: 'positive',
  skipped_sent: 'neutral',
  already_sent: 'neutral',
  no_report_card: 'caution',
  not_found: 'critical',
}

/** Human label per outcome. Worded so the consequence is legible without the
 *  reader having to know the enum. */
export const OUTCOME_LABEL: Record<ReportCardOutcome, string> = {
  drafted: 'Drafted',
  drafted_ungraded: 'Drafted — no grades',
  recalculated: 'Recalculated',
  sent: 'Sent',
  skipped_sent: 'Skipped (already sent)',
  already_sent: 'Already sent',
  no_report_card: 'No card to recalculate',
  not_found: 'Not found',
}

/** One line explaining what the outcome means for the student in question. */
export const OUTCOME_EXPLANATION: Record<ReportCardOutcome, string> = {
  drafted: 'A draft card was created or refreshed from current marks.',
  drafted_ungraded:
    'A card exists but carries no grade — nothing has been marked for this student. Sending it would give a family a blank report.',
  recalculated: 'Recomputed from current marks.',
  sent: 'Sent to the family. This cannot be recalled.',
  skipped_sent: 'Left untouched because it has already been sent to the family.',
  already_sent: 'This card was already sent, so it was not sent again.',
  no_report_card: 'No draft card exists for this student yet — draft first.',
  not_found: 'No report card with that id.',
}

export const REPORT_CARD_STATUS_TONE: Record<ReportCardStatus, StatusTone> = {
  draft: 'caution',
  sent: 'positive',
}

export const REPORT_CARD_STATUS_LABEL: Record<ReportCardStatus, string> = {
  draft: 'Draft',
  sent: 'Sent',
}

/**
 * A GPA, or an explicit statement that there isn't one.
 *
 * Never returns "0.00" for a null — see rule 1 above.
 */
export function formatGpa(gpa: number | null | undefined): string {
  if (gpa == null) return 'No grades recorded'
  return gpa.toFixed(2)
}

/** Compact variant for a table cell, where the long phrase would not fit. */
export function formatGpaShort(gpa: number | null | undefined): string {
  if (gpa == null) return '—'
  return gpa.toFixed(2)
}

/** A letter grade, or an em dash. An ungraded student has no letter — and
 *  emphatically not an "F", which is a real, earned grade. */
export function formatLetterGrade(letter: string | null | undefined): string {
  return letter && letter.trim() ? letter : '—'
}

export function formatCredits(credits: number | null | undefined): string {
  if (credits == null) return '—'
  return credits.toFixed(1)
}

/** A display name if the lookup resolved one, else the id — never a blank,
 *  which would make a row look empty rather than unresolved. */
export function studentLabel(studentId: number, names: Map<number, string>): string {
  return names.get(studentId) ?? `Student #${studentId}`
}

/** Renders an ISO timestamp for a human, or says it is not recorded. */
export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return 'Not recorded'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return 'Not recorded'
  return d.toLocaleString()
}

/**
 * Describes a single audit-trail event in one sentence.
 *
 * A `created` row has `previous_raw_score: null` — there was no previous mark.
 * That is deliberately distinct from a previous score of 0.0, which is a real
 * mark somebody earned, so the two must not read the same.
 */
export function describeGradeChange(
  action: string,
  previous: number | null | undefined,
  next: number,
  max: number
): string {
  if (action === 'created' || previous == null) {
    return `First entered as ${next} / ${max}`
  }
  return `Changed from ${previous} / ${max} to ${next} / ${max}`
}
