/**
 * Real calls against `apps/api/src/routers/sms_alumni.py`, mounted at
 * `/api/v1/sms/alumni` (the prefix is on the APIRouter itself, not on the
 * include_router call in `router.py`).
 *
 * WHAT THE API ACTUALLY ENFORCES -- read before assuming a role split:
 *
 *   POST /profiles    [SUPER_ADMIN, SCHOOL_ADMIN, STAFF]
 *   GET  /profiles    any authenticated principal
 *   POST /milestones  [SUPER_ADMIN, SCHOOL_ADMIN, STAFF]
 *
 * So reading the register is open to any signed-in user while writing is
 * staff-only. Listing is org-scoped in the service layer (`alumni.py`
 * `list_profiles` filters on `org_id` from the principal), never by a
 * caller-supplied org; the filters below are FILTERS, not authorisation
 * claims.
 *
 * There is no PATCH and no DELETE. See `types.ts`.
 */

import { apiGet, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  AlumniFilters,
  AlumniMilestone,
  AlumniMilestoneCreate,
  AlumniProfile,
  AlumniProfileCreate,
} from './types'

const BASE = '/sms/alumni'

export function listAlumniProfiles(filters: AlumniFilters = {}): Promise<AlumniProfile[]> {
  const qs = toQueryString({
    graduation_year: filters.graduation_year,
    industry: filters.industry,
    willing_to_mentor: filters.willing_to_mentor,
  })
  return apiGet<AlumniProfile[]>(`${BASE}/profiles${qs}`)
}

/** Staff-only. A 409 means a profile already exists for that user id. */
export function createAlumniProfile(payload: AlumniProfileCreate): Promise<AlumniProfile> {
  return apiPost<AlumniProfile>(`${BASE}/profiles`, payload)
}

/**
 * Staff-only. Readable back via `listAlumniProfiles`, which nests milestones
 * on each profile -- so this is not a write into a void.
 */
export function addAlumniMilestone(payload: AlumniMilestoneCreate): Promise<AlumniMilestone> {
  return apiPost<AlumniMilestone>(`${BASE}/milestones`, payload)
}
