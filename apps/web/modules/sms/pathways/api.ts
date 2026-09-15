/**
 * Real calls against `apps/api/src/routers/sms_pathways.py`, mounted at
 * `/api/v1/sms/pathways` (prefix on the APIRouter, `sms_pathways.py:24`).
 *
 * WHAT THE API ENFORCES:
 *
 *   create_pathway  POST ""                  [SUPER_ADMIN, SCHOOL_ADMIN]
 *   enroll_student  POST "/enroll"           [SUPER_ADMIN, SCHOOL_ADMIN, TEACHER, STAFF]
 *   list_pathways   GET  ""                  any authenticated principal
 *   get_progress    GET  "/progress/{id}"    any authenticated principal
 *
 * Note the root routes use an EMPTY path string, not "/" -- the prefix already
 * carries the full segment, so `${BASE}` with nothing appended is correct and
 * `${BASE}/` would 307-redirect.
 */

import { apiGet, apiPost } from '@/lib/api/api-client'
import type {
  CurricularPathway,
  CurricularPathwayCreate,
  EnrollPathwayPayload,
  StudentPathwayProgress,
} from './types'

const BASE = '/sms/pathways'

export function listPathways(): Promise<CurricularPathway[]> {
  return apiGet<CurricularPathway[]>(BASE)
}

export function createPathway(payload: CurricularPathwayCreate): Promise<CurricularPathway> {
  return apiPost<CurricularPathway>(BASE, payload)
}

export function enrollStudent(payload: EnrollPathwayPayload): Promise<unknown> {
  return apiPost<unknown>(`${BASE}/enroll`, payload)
}

/**
 * The student id comes from the `/sms/identity/people?role=STUDENT` picker
 * (reused via `modules/sms/campus/api.ts::listSchoolPeople`), never typed.
 *
 * The identity endpoint's own description calls itself "the picker source for
 * enrolling a student", and its gate
 * `[SUPER_ADMIN, SCHOOL_ADMIN, STAFF, TEACHER]` is exactly the set that may
 * enrol into a pathway -- so anyone who can use this screen can populate the
 * picker. There is no endpoint that lists a pathway's enrolled students, which
 * is why progress is reached by choosing a student rather than by drilling
 * into a pathway.
 */
export function getStudentPathwayProgress(studentId: number): Promise<StudentPathwayProgress[]> {
  return apiGet<StudentPathwayProgress[]>(`${BASE}/progress/${studentId}`)
}
