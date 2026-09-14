/**
 * Display helpers for M01 Admissions.
 *
 * The rule this file exists to enforce: ABSENCE IS RENDERED AS ABSENCE.
 * This codebase has torn out fabricated data four separate times — a 4.0 GPA
 * for a student with zero grades, an invented parent digest, outbound copy
 * naming a school that does not exist, and attendance reporting 0% when no
 * register had been taken. Every formatter below returns an explicit
 * "not recorded" string rather than a zero, a dash, or a plausible default.
 */

import type { StatusTone } from '@/components/widgets'
import type {
  AdmissionDecision,
  ApplicationStatus,
  AssessmentOutcome,
  AssessmentRead,
  DocumentType,
  DocumentVerificationStatus,
} from './types'

export const STATUS_LABEL: Record<ApplicationStatus, string> = {
  DRAFT: 'Draft',
  SUBMITTED: 'Submitted',
  DOCUMENTS_PENDING: 'Documents pending',
  UNDER_REVIEW: 'Under review',
  ASSESSMENT_SCHEDULED: 'Assessment scheduled',
  ASSESSED: 'Assessed',
  OFFERED: 'Offered',
  ACCEPTED: 'Accepted',
  ENROLLED: 'Enrolled',
  REJECTED: 'Rejected',
  WITHDRAWN: 'Withdrawn',
}

/**
 * WITHDRAWN is neutral, not critical: a family that changed its mind was not
 * refused a place, and colouring the two alike would misrepresent both the
 * school's acceptance rate and its reason-for-refusal record.
 */
export const STATUS_TONE: Record<ApplicationStatus, StatusTone> = {
  DRAFT: 'neutral',
  SUBMITTED: 'info',
  DOCUMENTS_PENDING: 'caution',
  UNDER_REVIEW: 'info',
  ASSESSMENT_SCHEDULED: 'info',
  ASSESSED: 'info',
  OFFERED: 'positive',
  ACCEPTED: 'positive',
  ENROLLED: 'positive',
  REJECTED: 'critical',
  WITHDRAWN: 'neutral',
}

/** Statuses where the school is waiting on the FAMILY, not on itself. */
export const AWAITING_FAMILY: ApplicationStatus[] = ['DOCUMENTS_PENDING', 'OFFERED']

/** Closed states — a decision cannot reopen these (TERMINAL_STATUSES server-side). */
export const TERMINAL_STATUSES: ApplicationStatus[] = ['ENROLLED', 'REJECTED', 'WITHDRAWN']

export const DOCUMENT_TYPE_LABEL: Record<DocumentType, string> = {
  BIRTH_CERTIFICATE: 'Birth certificate',
  PRIOR_SCHOOL_RECORD: 'Prior school record',
  TRANSFER_CERTIFICATE: 'Transfer certificate',
  MEDICAL_RECORD: 'Medical record',
  IMMUNISATION_RECORD: 'Immunisation record',
  PHOTOGRAPH: 'Photograph',
  GUARDIAN_ID: 'Guardian ID',
  PROOF_OF_ADDRESS: 'Proof of address',
  OTHER: 'Other',
}

export const DOCUMENT_TYPES: DocumentType[] = [
  'BIRTH_CERTIFICATE',
  'PRIOR_SCHOOL_RECORD',
  'TRANSFER_CERTIFICATE',
  'MEDICAL_RECORD',
  'IMMUNISATION_RECORD',
  'PHOTOGRAPH',
  'GUARDIAN_ID',
  'PROOF_OF_ADDRESS',
  'OTHER',
]

export const VERIFICATION_LABEL: Record<DocumentVerificationStatus, string> = {
  // "Not checked" rather than "Pending": pending reads as a process quietly
  // ticking along, when the fact is that nobody has opened the file yet.
  PENDING: 'Not checked',
  VERIFIED: 'Verified',
  REJECTED: 'Rejected',
}

export const VERIFICATION_TONE: Record<DocumentVerificationStatus, StatusTone> = {
  PENDING: 'caution',
  VERIFIED: 'positive',
  REJECTED: 'critical',
}

export const OUTCOME_LABEL: Record<AssessmentOutcome, string> = {
  PASSED: 'Passed',
  FAILED: 'Failed',
  BORDERLINE: 'Borderline',
  NOT_ATTENDED: 'Did not attend',
}

export const OUTCOME_TONE: Record<AssessmentOutcome, StatusTone> = {
  PASSED: 'positive',
  FAILED: 'critical',
  BORDERLINE: 'caution',
  NOT_ATTENDED: 'neutral',
}

export const DECISION_LABEL: Record<AdmissionDecision, string> = {
  OFFERED: 'Place offered',
  REJECTED: 'Refused',
  WAITLISTED: 'Waitlisted',
}

export const DECISION_TONE: Record<AdmissionDecision, StatusTone> = {
  OFFERED: 'positive',
  REJECTED: 'critical',
  WAITLISTED: 'caution',
}

/** A date, or an explicit statement that there isn't one. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return 'Not recorded'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return 'Not recorded'
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return 'Not recorded'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return 'Not recorded'
  return d.toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * An assessment score, or why there isn't one.
 *
 * The NOT_ATTENDED branch is the whole point: a candidate who never sat the
 * paper did not score zero on it, and rendering a 0 there would be a
 * fabricated academic record. The backend refuses to store a score for that
 * outcome; this refuses to imply one.
 */
export function formatScore(assessment: AssessmentRead): string {
  if (assessment.outcome === 'NOT_ATTENDED') return 'Did not attend'
  if (assessment.score === null || assessment.score === undefined) return 'Not recorded'
  if (assessment.max_score === null || assessment.max_score === undefined) {
    return String(assessment.score)
  }
  return `${assessment.score} / ${assessment.max_score}`
}

/** Guardian contact, or a plain statement that the school holds none. */
export function formatContact(email: string | null, phone: string | null): string {
  const parts = [email, phone].filter(Boolean)
  return parts.length ? parts.join(' · ') : 'No contact recorded'
}

/**
 * Whole days since a date — null when there is no date at all.
 *
 * Returns null rather than 0 so callers must distinguish "applied today" from
 * "no submission date recorded". They mean opposite things to a registrar.
 */
export function daysSince(value: string | null | undefined): number | null {
  if (!value) return null
  const then = new Date(value).getTime()
  if (Number.isNaN(then)) return null
  return Math.floor((Date.now() - then) / 86_400_000)
}
