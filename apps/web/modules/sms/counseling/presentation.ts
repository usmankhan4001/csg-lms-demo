/**
 * Presentation helpers for the counselling module.
 *
 * Deliberately has NO student-name resolution. `GET /sms/identity/people` --
 * the source every other module joins against for names -- is gated
 * `[SUPER_ADMIN, SCHOOL_ADMIN, STAFF, TEACHER]` (`sms_identity.py:383`), and
 * PSYCHOLOGIST is absent from that list. So the one role that can read a
 * counselling record cannot call the name endpoint at all: reusing
 * `useStudentNames` here would fire a 403 on every screen for the only user
 * who has any business being on it.
 */

import type { StatusTone } from '@/components/widgets'

export function formatDate(value: string | null | undefined): string {
  if (!value) return 'Not recorded'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return 'Not recorded'
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return 'Not recorded'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return 'Not recorded'
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Ids only -- see the module note above. */
export function studentLabel(studentId: number): string {
  return `Student #${studentId}`
}

export function formatDuration(minutes: number | null | undefined): string {
  if (minutes == null) return 'Not recorded'
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m === 0 ? `${h} hr` : `${h} hr ${m} min`
}

export const SEVERITY_TONE: Record<string, StatusTone> = {
  low: 'neutral',
  medium: 'caution',
  high: 'critical',
  critical: 'critical',
}

export function severityTone(severity: string | null | undefined): StatusTone {
  if (!severity) return 'neutral'
  return SEVERITY_TONE[severity.toLowerCase()] ?? 'neutral'
}

/**
 * A session is either shared with the family or it is not. Worded as a
 * statement of fact rather than a status, because "Private" is the default
 * and must not read as an anomaly a counsellor should fix.
 */
export function sharingLabel(shared: boolean): { label: string; tone: StatusTone } {
  return shared
    ? { label: 'Summary shared with family', tone: 'positive' }
    : { label: 'Not shared', tone: 'neutral' }
}
