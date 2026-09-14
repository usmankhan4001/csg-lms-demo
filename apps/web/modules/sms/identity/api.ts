/**
 * Real fetch calls against `apps/api/src/routers/sms_identity.py`.
 *
 * Mounted at `/api/v1/sms` (verified in `src/router.py:506-510` — the router
 * declares its own `/identity/...` paths, so the full path is
 * `/api/v1/sms/identity/roles`, NOT `/api/v1/sms/identity` under some deeper
 * prefix). Worth stating explicitly: a sibling module shipped for a whole
 * release calling `/sms/revops` when the router was actually mounted at
 * `/revops`, and nothing caught it because the screen failed quietly.
 *
 * These endpoints are how a Learnhouse user becomes a student, teacher or
 * parent. Until this module existed nothing in the frontend called them, so
 * the only way to grant a school role was raw SQL.
 */

import { apiDelete, apiGet, apiPost, toQueryString } from '@/lib/api/api-client'
import type {
  SMSUserRoleCreate,
  SMSUserRoleRead,
  StudentGuardianCreate,
  StudentGuardianRead,
} from './types'

/** School role grants. Both filters are optional; pass what you have. */
export function listSchoolRoles(params: { userId?: number; orgId?: number } = {}): Promise<SMSUserRoleRead[]> {
  const qs = toQueryString({ user_id: params.userId, org_id: params.orgId })
  return apiGet<SMSUserRoleRead[]>(`/sms/identity/roles${qs}`)
}

/** Grant a school role. Backend upserts: re-granting a revoked role reactivates it. */
export function assignSchoolRole(payload: SMSUserRoleCreate): Promise<SMSUserRoleRead> {
  return apiPost<SMSUserRoleRead>('/sms/identity/roles', payload)
}

/**
 * Revoke a grant. Soft on the backend (`is_active = false`) rather than a
 * row delete, so the history of who held what survives.
 */
export function revokeSchoolRole(roleId: number): Promise<void> {
  return apiDelete<void>(`/sms/identity/roles/${roleId}`)
}

/** Guardian↔student links. `student_id`/`guardian_user_id` are both user ids. */
export function listGuardianLinks(
  params: { studentId?: number; guardianUserId?: number } = {}
): Promise<StudentGuardianRead[]> {
  const qs = toQueryString({ student_id: params.studentId, guardian_user_id: params.guardianUserId })
  return apiGet<StudentGuardianRead[]>(`/sms/identity/guardians${qs}`)
}

/** Link a guardian to a student. 409 if the pair is already linked. */
export function linkGuardian(payload: StudentGuardianCreate): Promise<StudentGuardianRead> {
  return apiPost<StudentGuardianRead>('/sms/identity/guardians', payload)
}

/** Unlink. Hard delete on the backend, unlike role revocation. */
export function unlinkGuardian(guardianId: number): Promise<void> {
  return apiDelete<void>(`/sms/identity/guardians/${guardianId}`)
}
