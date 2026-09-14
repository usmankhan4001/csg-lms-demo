/**
 * Real fetch calls against `apps/api/src/routers/sms_counseling.py`
 * (mounted at `/api/v1/sms/counseling` -- `src/router.py:692-694`).
 *
 * THE CONFIDENTIALITY CONTRACT, which the UI must not defeat:
 * every read here returns an EMPTY LIST (or a generic 404) to an
 * unauthorised caller rather than a 403, because a 403 would itself confirm
 * that a counselling record exists for that child. See the module docstring
 * in `sms_counseling.py` and DESIGN-SYSTEM.md.
 *
 * The practical consequence for this client: **there is nothing to catch**.
 * An unauthorised caller is not an error path here -- it is an empty result,
 * and it must render exactly like a student who has never been seen.
 *
 * NOTE `psychologist_id` is the Keycloak `sub` STRING (`counseling.py:73`
 * stamps `principal.sub`), not the integer user id every other SMS module
 * keys staff on. They cannot be joined, which is why no author name is
 * resolved anywhere in this module.
 */

import { apiGet, apiPatch, apiPost } from '@/lib/api/api-client'
import type {
  ActivityLogCreate,
  ActivityLogRead,
  CareerGuidanceGenerateRequest,
  CareerGuidancePlanRead,
  CounselingSessionCreate,
  CounselingSessionRead,
  CounselingSessionUpdate,
  ParentVisibleSessionSummary,
} from './types'

const BASE = '/sms/counseling'

// --- Sessions (PSYCHOLOGIST-only full record) ------------------------------

/** `sms_counseling.py:137` -- empty list for any non-authoring caller. */
export function listStudentSessions(studentId: number): Promise<CounselingSessionRead[]> {
  return apiGet<CounselingSessionRead[]>(`${BASE}/sessions/student/${studentId}`)
}

/** `sms_counseling.py:152` -- generic 404 for any non-authoring caller. */
export function getSession(sessionId: number): Promise<CounselingSessionRead> {
  return apiGet<CounselingSessionRead>(`${BASE}/sessions/${sessionId}`)
}

/** `sms_counseling.py:116` */
export function createSession(payload: CounselingSessionCreate): Promise<CounselingSessionRead> {
  return apiPost<CounselingSessionRead>(`${BASE}/sessions`, payload)
}

/** `sms_counseling.py:169` */
export function updateSession(
  sessionId: number,
  payload: CounselingSessionUpdate
): Promise<CounselingSessionRead> {
  return apiPatch<CounselingSessionRead>(`${BASE}/sessions/${sessionId}`, payload)
}

/**
 * `sms_counseling.py:191` -- the PARENT/STUDENT slice. Returns an empty list
 * for staff, including the authoring psychologist, because it is not the
 * clinical view. Not used by the staff workspace; exported for the family
 * surface that should consume it.
 */
export function listParentVisibleSessions(
  studentId: number
): Promise<ParentVisibleSessionSummary[]> {
  return apiGet<ParentVisibleSessionSummary[]>(
    `${BASE}/sessions/student/${studentId}/parent-summary`
  )
}

// --- Activity signals (PSYCHOLOGIST-only) ----------------------------------

/** `sms_counseling.py:96` -- empty list for any non-authoring caller. */
export function listStudentActivityLogs(studentId: number): Promise<ActivityLogRead[]> {
  return apiGet<ActivityLogRead[]>(`${BASE}/activity-logs/student/${studentId}`)
}

/** `sms_counseling.py:75` */
export function createActivityLog(payload: ActivityLogCreate): Promise<ActivityLogRead> {
  return apiPost<ActivityLogRead>(`${BASE}/activity-logs`, payload)
}

// --- Career guidance (NOT confidential -- ordinary 403s) --------------------

/** `sms_counseling.py:271` -- deliberately unmasked; advisory, not clinical. */
export function listCareerPlans(studentId: number): Promise<CareerGuidancePlanRead[]> {
  return apiGet<CareerGuidancePlanRead[]>(`${BASE}/career-guidance/student/${studentId}`)
}

/** `sms_counseling.py:237` -- 403 for non-staff, 502 if generation fails. */
export function generateCareerPlan(
  payload: CareerGuidanceGenerateRequest
): Promise<CareerGuidancePlanRead> {
  return apiPost<CareerGuidancePlanRead>(`${BASE}/career-guidance/generate`, payload)
}
