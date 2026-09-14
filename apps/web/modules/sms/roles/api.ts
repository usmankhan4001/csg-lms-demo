import { apiDelete, apiGet, apiPost } from '@/lib/api/api-client'
import type {
  AssignRolePayload,
  BulkProvisionResult,
  DirectoryEntry,
  ProvisionPersonPayload,
  ProvisionPersonResult,
  GuardianLinkRecord,
  LinkGuardianPayload,
  SchoolPerson,
  ResendPendingResult,
  SchoolInvite,
  SchoolRoleType,
  SMSUserRoleRecord,
} from './types'

export async function listSchoolRoles(params?: { user_id?: number; org_id?: number }): Promise<SMSUserRoleRecord[]> {
  const query = new URLSearchParams()
  if (params?.user_id) query.set('user_id', String(params.user_id))
  if (params?.org_id) query.set('org_id', String(params.org_id))
  const qs = query.toString() ? `?${query.toString()}` : ''
  return apiGet<SMSUserRoleRecord[]>(`/sms/identity/roles${qs}`)
}

export async function assignSchoolRole(payload: AssignRolePayload): Promise<SMSUserRoleRecord> {
  return apiPost<SMSUserRoleRecord>('/sms/identity/roles', payload)
}

export async function revokeSchoolRole(roleId: number): Promise<void> {
  return apiDelete<void>(`/sms/identity/roles/${roleId}`)
}

export async function listSchoolPeople(role: SchoolRoleType, campusId?: number): Promise<SchoolPerson[]> {
  const query = new URLSearchParams({ role })
  if (campusId) query.set('campus_id', String(campusId))
  return apiGet<SchoolPerson[]>(`/sms/identity/people?${query.toString()}`)
}

export async function listGuardianLinks(params?: { student_id?: number; guardian_user_id?: number }): Promise<GuardianLinkRecord[]> {
  const query = new URLSearchParams()
  if (params?.student_id) query.set('student_id', String(params.student_id))
  if (params?.guardian_user_id) query.set('guardian_user_id', String(params.guardian_user_id))
  const qs = query.toString() ? `?${query.toString()}` : ''
  return apiGet<GuardianLinkRecord[]>(`/sms/identity/guardians${qs}`)
}

export async function linkGuardian(payload: LinkGuardianPayload): Promise<GuardianLinkRecord> {
  return apiPost<GuardianLinkRecord>('/sms/identity/guardians', payload)
}

export async function unlinkGuardian(guardianId: number): Promise<void> {
  return apiDelete<void>(`/sms/identity/guardians/${guardianId}`)
}

// --- Account provisioning ---------------------------------------------------
//
// `assignSchoolRole` above needs a user who already exists. These create the
// person. No password is sent or received on any of them -- the backend sets
// an unusable hash and the person sets their own through password reset.

export async function provisionPerson(payload: ProvisionPersonPayload): Promise<ProvisionPersonResult> {
  return apiPost<ProvisionPersonResult>('/sms/identity/provision', payload)
}

export async function bulkProvisionPeople(people: ProvisionPersonPayload[]): Promise<BulkProvisionResult> {
  return apiPost<BulkProvisionResult>('/sms/identity/provision/bulk', { people })
}

export async function listSchoolDirectory(params?: {
  campus_id?: number
  unassigned_only?: boolean
}): Promise<DirectoryEntry[]> {
  const query = new URLSearchParams()
  if (params?.campus_id) query.set('campus_id', String(params.campus_id))
  if (params?.unassigned_only) query.set('unassigned_only', 'true')
  const qs = query.toString() ? `?${query.toString()}` : ''
  return apiGet<DirectoryEntry[]>(`/sms/identity/directory${qs}`)
}

// --- Invitations ----------------------------------------------------------
// Provisioning creates an account with no usable password by design, so the
// invitation is the only way its owner ever gets in. These surface whether
// that actually happened.

export async function listSchoolInvites(status?: string): Promise<SchoolInvite[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : ''
  return apiGet<SchoolInvite[]>(`/sms/identity/invites${qs}`)
}

export async function resendSchoolInvite(userId: number): Promise<SchoolInvite> {
  return apiPost<SchoolInvite>(`/sms/identity/invites/${userId}/resend`, {})
}

export async function resendPendingInvites(): Promise<ResendPendingResult> {
  return apiPost<ResendPendingResult>('/sms/identity/invites/resend-pending', {})
}
