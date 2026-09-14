import { apiDelete, apiGet, apiPost } from '@/lib/api/api-client'
import type {
  AssignRolePayload,
  GuardianLinkRecord,
  LinkGuardianPayload,
  SchoolPerson,
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
