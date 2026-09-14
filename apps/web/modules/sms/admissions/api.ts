/**
 * Real fetch calls against `apps/api/src/routers/sms_admissions.py`, mounted
 * at `/api/v1/sms/admissions` (prefix in `src/router.py`).
 *
 * Two verbs differ from what a reader might guess, and both are verified
 * against the router rather than assumed:
 *   - document verification is PATCH /documents/{id}/verify   (not POST)
 *   - assessment result is    PATCH /assessments/{id}/result  (not POST)
 */

import { ApiError, apiFetch, apiGet, apiPatch, apiPost, toQueryString } from '@/lib/api/api-client'
import { authReadyPromise, getActiveAccessToken } from '@/lib/api/session-token-bridge'
import { getConfig } from '@services/config/config'
import type {
  ApplicationCreatePayload,
  ApplicationDetailRead,
  ApplicationListFilters,
  ApplicationRead,
  ApplicationStatusUpdatePayload,
  AssessmentRead,
  AssessmentResultPayload,
  AssessmentSchedulePayload,
  DecisionCreatePayload,
  DecisionRead,
  DocumentRead,
  DocumentType,
  DocumentVerifyPayload,
} from './types'

// ── Applications ────────────────────────────────────────────────────────────

export function listApplications(filters: ApplicationListFilters = {}): Promise<ApplicationRead[]> {
  const qs = toQueryString({
    campus_id: filters.campus_id,
    status: filters.status,
    academic_year_id: filters.academic_year_id,
    limit: filters.limit,
    offset: filters.offset,
  })
  return apiGet<ApplicationRead[]>(`/sms/admissions/applications${qs}`)
}

export function getApplicationDetail(applicationId: number): Promise<ApplicationDetailRead> {
  return apiGet<ApplicationDetailRead>(`/sms/admissions/applications/${applicationId}`)
}

export function createApplication(payload: ApplicationCreatePayload): Promise<ApplicationRead> {
  return apiPost<ApplicationRead>('/sms/admissions/applications', payload)
}

export function submitApplication(applicationId: number): Promise<ApplicationRead> {
  return apiPost<ApplicationRead>(`/sms/admissions/applications/${applicationId}/submit`)
}

export function setApplicationStatus(
  applicationId: number,
  payload: ApplicationStatusUpdatePayload
): Promise<ApplicationRead> {
  return apiPatch<ApplicationRead>(`/sms/admissions/applications/${applicationId}/status`, payload)
}

// ── Documents ───────────────────────────────────────────────────────────────

export function listDocuments(applicationId: number): Promise<DocumentRead[]> {
  return apiGet<DocumentRead[]>(`/sms/admissions/applications/${applicationId}/documents`)
}

/**
 * Multipart upload. `rawBody: true` stops the client setting a JSON
 * Content-Type so the browser can supply its own multipart boundary — without
 * it FastAPI rejects the form.
 */
export function uploadDocument(
  applicationId: number,
  documentType: DocumentType,
  file: File
): Promise<DocumentRead> {
  const form = new FormData()
  form.append('document_type', documentType)
  form.append('file', file)
  return apiFetch<DocumentRead>(`/sms/admissions/applications/${applicationId}/documents`, {
    method: 'POST',
    body: form,
    rawBody: true,
  })
}

/** PATCH, not POST — verified against sms_admissions.py:362. */
export function verifyDocument(
  documentId: number,
  payload: DocumentVerifyPayload
): Promise<DocumentRead> {
  return apiPatch<DocumentRead>(`/sms/admissions/documents/${documentId}/verify`, payload)
}

/**
 * Downloads a supporting document's bytes.
 *
 * These are children's identity papers — birth certificates, medical and
 * immunisation records. Three deliberate properties:
 *
 * 1. NOT a plain `<a href>`. The endpoint requires a Bearer token, so an
 *    anchor would navigate to a 401 — and a URL that did work would be
 *    copyable out of the page, into browser history, and into a screenshot.
 * 2. The blob object URL is revoked in a `finally`, so the bytes are not
 *    retained for the life of the page.
 * 3. The backend serves `Content-Disposition: attachment` and re-authorises
 *    through the parent application on every call, so it never renders inline
 *    in a tab and a document id alone is never sufficient authority.
 */
export async function downloadDocument(documentId: number, filename?: string): Promise<void> {
  await authReadyPromise
  const base = getConfig('NEXT_PUBLIC_LEARNHOUSE_BACKEND_URL', 'http://localhost:1338').replace(/\/+$/, '')
  const token = getActiveAccessToken()

  const response = await fetch(`${base}/api/v1/sms/admissions/documents/${documentId}/content`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })

  if (!response.ok) {
    const detail =
      response.status === 403
        ? 'You do not have access to this document.'
        : response.status === 404
          ? 'That document no longer exists.'
          : 'Could not download the document.'
    throw new ApiError(
      response.status,
      detail,
      response.status === 403 ? 'permission_denied' : response.status === 404 ? 'not_found' : 'server'
    )
  }

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  try {
    const link = document.createElement('a')
    link.href = url
    link.download = filename ?? `document-${documentId}`
    document.body.appendChild(link)
    link.click()
    link.remove()
  } finally {
    URL.revokeObjectURL(url)
  }
}

// ── Assessments ─────────────────────────────────────────────────────────────

export function listAssessments(applicationId: number): Promise<AssessmentRead[]> {
  return apiGet<AssessmentRead[]>(`/sms/admissions/applications/${applicationId}/assessments`)
}

export function scheduleAssessment(
  applicationId: number,
  payload: AssessmentSchedulePayload
): Promise<AssessmentRead> {
  return apiPost<AssessmentRead>(`/sms/admissions/applications/${applicationId}/assessments`, payload)
}

/** PATCH, not POST — verified against sms_admissions.py:443. */
export function recordAssessmentResult(
  assessmentId: number,
  payload: AssessmentResultPayload
): Promise<AssessmentRead> {
  return apiPatch<AssessmentRead>(`/sms/admissions/assessments/${assessmentId}/result`, payload)
}

// ── Decisions ───────────────────────────────────────────────────────────────

export function listDecisions(applicationId: number): Promise<DecisionRead[]> {
  return apiGet<DecisionRead[]>(`/sms/admissions/applications/${applicationId}/decisions`)
}

export function recordDecision(
  applicationId: number,
  payload: DecisionCreatePayload
): Promise<DecisionRead> {
  return apiPost<DecisionRead>(`/sms/admissions/applications/${applicationId}/decisions`, payload)
}
