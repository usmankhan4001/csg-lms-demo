/**
 * How a live class's state is described to a human.
 *
 * Kept out of the components because the recording states carry real
 * consequences and must read identically wherever they appear. In particular
 * UNAVAILABLE and FAILED are different facts and must never collapse into one
 * "no recording" message: UNAVAILABLE means this deployment has no object
 * storage, so recording was never possible and no teacher action will fix it;
 * FAILED means it was attempted and broke. Telling a teacher their recording
 * failed when nobody ever configured storage sends them chasing the wrong
 * problem -- and the server draws the same distinction deliberately
 * (`apps/api/src/db/sms_live_class.py` RecordingStatus).
 */

import type { StatusTone } from '@/components/widgets'
import type { LiveClassStatus, RecordingStatus } from './types'

export interface Described {
  label: string
  tone: StatusTone
  /** A sentence a user can act on, or null when the label says it all. */
  hint: string | null
}

export function describeClassStatus(status: LiveClassStatus): Described {
  switch (status) {
    case 'LIVE':
      return { label: 'Live now', tone: 'positive', hint: null }
    case 'SCHEDULED':
      return { label: 'Scheduled', tone: 'info', hint: null }
    case 'ENDED':
      return { label: 'Ended', tone: 'neutral', hint: null }
    case 'CANCELLED':
      return { label: 'Cancelled', tone: 'critical', hint: null }
    default:
      // An unknown status is reported as unknown rather than guessed into one
      // of the four above -- a class shown as "Scheduled" that is not is worse
      // than a class shown as unrecognised.
      return { label: String(status), tone: 'neutral', hint: 'Unrecognised status.' }
  }
}

export function describeRecording(status: RecordingStatus): Described {
  switch (status) {
    case 'NOT_REQUESTED':
      return {
        label: 'Not recording',
        tone: 'neutral',
        hint: 'Recording is off for this class. A host can turn it on before the class starts.',
      }
    case 'UNAVAILABLE':
      return {
        label: 'Unavailable',
        tone: 'caution',
        // Deliberately NOT "failed": nothing broke and nothing the teacher
        // does will fix it. This is a deployment configuration gap.
        hint: 'Recording is not available on this deployment because no storage has been configured. This is a setup task for your administrator, not a fault with this class.',
      }
    case 'PENDING':
      return { label: 'Starting', tone: 'info', hint: 'Recording will begin when the class starts.' }
    case 'RECORDING':
      return { label: 'Recording', tone: 'positive', hint: null }
    case 'PROCESSING':
      return {
        label: 'Processing',
        tone: 'info',
        hint: 'The class has ended and the recording is still being prepared.',
      }
    case 'READY':
      return { label: 'Ready', tone: 'positive', hint: null }
    case 'FAILED':
      return {
        label: 'Failed',
        tone: 'critical',
        hint: 'Recording was attempted and did not complete. The class itself was unaffected.',
      }
    default:
      return { label: String(status), tone: 'neutral', hint: 'Unrecognised recording state.' }
  }
}

/**
 * A duration that was never measured is not zero.
 *
 * `duration_seconds` is null until a recording actually completes, and
 * rendering that as "0m" tells a teacher the recording captured nothing when
 * in fact nothing has been measured yet.
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return 'Not measured'
  if (seconds < 60) return `${Math.round(seconds)}s`
  const mins = Math.floor(seconds / 60)
  const hrs = Math.floor(mins / 60)
  if (hrs > 0) return `${hrs}h ${mins % 60}m`
  return `${mins}m`
}

/** A missing timestamp reads as absent, never as the epoch or "now". */
export function formatWhen(iso: string | null | undefined): string {
  if (!iso) return 'Not set'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'Not set'
  return d.toLocaleString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Whether a class can still be joined.
 *
 * A cancelled or ended class must not offer a join button that would 409 --
 * the server refuses both, and offering the action anyway teaches people the
 * buttons lie.
 */
export function isJoinable(status: LiveClassStatus): boolean {
  return status === 'SCHEDULED' || status === 'LIVE'
}
