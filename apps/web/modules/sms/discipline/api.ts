/**
 * Real calls against `apps/api/src/routers/sms_discipline.py`, mounted at
 * `/api/v1/sms/discipline` (the prefix is on the APIRouter itself,
 * `sms_discipline.py:36`, not on the include_router call).
 *
 * WHAT THE API ACTUALLY ENFORCES -- read before assuming a role split:
 *
 *   All four incident endpoints share ONE gate:
 *     [SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF, PSYCHOLOGIST]
 *   Suspensions are narrower:
 *     [SUPER_ADMIN, SCHOOL_ADMIN]
 *
 * So a teacher, a staff member and a psychologist see the SAME incidents; the
 * only real split is that suspensions are admin-only. PARENT and STUDENT are
 * in no gate at all, so there is no family-facing view of this module and this
 * client must not pretend to offer one.
 *
 * Listing is org-scoped in the service layer (`discipline.py:57`), never by
 * caller-supplied org. `student_id` here is a FILTER, not an authorisation
 * claim -- the server applies its own org boundary regardless of what is sent.
 */

import { apiGet, apiPatch, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  Incident,
  IncidentCreate,
  IncidentFilters,
  IncidentUpdate,
  Suspension,
  SuspensionCreate,
} from './types'

const BASE = '/sms/discipline'

export function listIncidents(filters: IncidentFilters = {}): Promise<Incident[]> {
  const qs = toQueryString({
    student_id: filters.student_id,
    severity: filters.severity,
    status_filter: filters.status_filter,
  })
  return apiGet<Incident[]>(`${BASE}/incidents${qs}`)
}

export function getIncident(incidentId: number): Promise<Incident> {
  return apiGet<Incident>(`${BASE}/incidents/${incidentId}`)
}

export function createIncident(payload: IncidentCreate): Promise<Incident> {
  return apiPost<Incident>(`${BASE}/incidents`, payload)
}

export function updateIncident(
  incidentId: number,
  payload: IncidentUpdate
): Promise<Incident> {
  return apiPatch<Incident>(`${BASE}/incidents/${incidentId}`, payload)
}

/**
 * SCHOOL_ADMIN / SUPER_ADMIN only. A teacher calling this receives 403, and
 * that is correct: a suspension's existence is not confidential the way a
 * counselling record is, so refusing plainly is the right answer here.
 */
export function createSuspension(payload: SuspensionCreate): Promise<Suspension> {
  return apiPost<Suspension>(`${BASE}/suspensions`, payload)
}
