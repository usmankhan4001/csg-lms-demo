/**
 * Real fetch calls against `apps/api/src/routers/sms_identity.py`, mounted at
 * `/api/v1/sms` (router.py:516-517).
 */

import { apiGet, toQueryString } from '@/api/client'
import type { ChildContext, MyIdentity, SchoolPerson, SchoolRoleName } from './types'

/** GET /sms/me — sms_identity.py:113. The caller's school identity. */
export function getMyIdentity(): Promise<MyIdentity> {
  return apiGet<MyIdentity>('/sms/me')
}

/**
 * GET /sms/identity/children/{student_id}/context — sms_identity.py:181.
 * Gated by `require_own_student_or_privileged`: the student, one of their
 * guardians, SCHOOL_ADMIN or SUPER_ADMIN. A parent asking for someone else's
 * child gets a 403 from the server, not a filtered list from us.
 */
export function getChildContext(studentId: number): Promise<ChildContext> {
  return apiGet<ChildContext>(`/sms/identity/children/${studentId}/context`)
}

/**
 * GET /sms/identity/people — sms_identity.py:369.
 * Requires SUPER_ADMIN, SCHOOL_ADMIN, STAFF or TEACHER; a PARENT calling this
 * gets 403, which is why no parent-facing screen uses it.
 */
export function listSchoolPeople(role: SchoolRoleName, campusId?: number): Promise<SchoolPerson[]> {
  return apiGet<SchoolPerson[]>(`/sms/identity/people${toQueryString({ role, campus_id: campusId })}`)
}
