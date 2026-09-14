/**
 * Shared formatting and tone mapping for the attendance module.
 *
 * Two rules encoded here rather than repeated per screen:
 *
 * 1. ABSENCE IS NOT ZERO. `attendance_percentage` is `null` when no register
 *    has been taken (`sms_attendance.py:86` returns `Optional[float]`). A head
 *    of year seeing "0%" reads "attended nothing"; the truth is nobody marked
 *    a register. Same for `magnitude` on a pastoral concern, which is null
 *    where the trigger has no natural magnitude and would otherwise read as
 *    "a streak of zero".
 *
 * 2. STUDENT NAMES COME FROM A SECOND CALL. `StudentEnrollmentRead`
 *    (`db/sms_campus.py:350`) carries `student_id` only -- no joined display
 *    name -- so the roster alone can only render "Student #37".
 *    `GET /sms/identity/people?role=STUDENT` DOES return names and permits
 *    TEACHER (`sms_identity.py:383`), so a name map is fetched alongside the
 *    roster and joined client-side. That is a workaround, not a fix: the
 *    enrolment endpoint should join `User` itself.
 */

import type { StatusTone } from '@/components/widgets'
import type {
  AttendanceStatus,
  ExcuseStatus,
  PastoralConcernStatus,
} from './types'

export const ATTENDANCE_TONE: Record<AttendanceStatus, StatusTone> = {
  PRESENT: 'positive',
  ABSENT: 'critical',
  LATE: 'caution',
  EXCUSED: 'info',
}

export const EXCUSE_TONE: Record<ExcuseStatus, StatusTone> = {
  PENDING: 'caution',
  APPROVED: 'positive',
  REJECTED: 'neutral',
}

export const CONCERN_TONE: Record<PastoralConcernStatus, StatusTone> = {
  OPEN: 'critical',
  IN_PROGRESS: 'caution',
  RESOLVED: 'positive',
}

export const CONCERN_LABEL: Record<PastoralConcernStatus, string> = {
  OPEN: 'Open',
  IN_PROGRESS: 'In progress',
  RESOLVED: 'Resolved',
}

/** Percentage, or an honest statement that no register exists. */
export function formatAttendancePercentage(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'Not recorded'
  return `${value.toFixed(1)}%`
}

/** A concern's magnitude, or nothing -- never "0 days". */
export function formatMagnitude(value: number | null | undefined, unit = 'day'): string {
  if (value === null || value === undefined) return '—'
  return `${value} ${unit}${value === 1 ? '' : 's'}`
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return 'Not recorded'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'Not recorded'
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return 'Not recorded'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'Not recorded'
  return d.toLocaleString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Whole days since an ISO timestamp, or null when there is nothing to measure
 * from. Callers render null as "Unknown" -- never 0, because "today" and "no
 * record" are opposite facts.
 */
export function daysSince(iso: string | null | undefined): number | null {
  if (!iso) return null
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return null
  const ms = Date.now() - then.getTime()
  if (ms < 0) return 0
  return Math.floor(ms / 86_400_000)
}

/** ISO date (YYYY-MM-DD) for an offset from today. */
export function isoDate(offsetDays = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return d.toISOString().slice(0, 10)
}

/**
 * A student's display name from the id->name map, falling back to the id.
 * The fallback is deliberately explicit rather than silent: a roster showing
 * "Student #37" is a signal that the name lookup failed or the person holds
 * no STUDENT role grant, not a normal rendering.
 */
export function studentLabel(
  studentId: number,
  names: Map<number, string>,
  rollNumber?: string | null
): string {
  const name = names.get(studentId)
  const roll = rollNumber ? ` (Roll ${rollNumber})` : ''
  return name ? `${name}${roll}` : `Student #${studentId}${roll}`
}
