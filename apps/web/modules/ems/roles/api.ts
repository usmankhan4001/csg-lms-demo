import { apiDelete, apiGet, apiPost, apiPut } from '@/lib/api/api-client'
import { EMSRole, EMSUserRoleAssignment, EMSPermissionRule } from '@/lib/ems-permissions'

export interface CreateRolePayload {
  name: string
  slug?: string
  description?: string
  is_clinical_specialist?: boolean
  rules?: Partial<EMSPermissionRule>[]
}

export interface UpdateRolePayload {
  name?: string
  description?: string
  is_clinical_specialist?: boolean
  rules?: Partial<EMSPermissionRule>[]
}

export interface AssignRolePayload {
  user_id: number
  role_id: number
  campus_id?: number
  department_id?: number
  section_id?: number
}

export async function listEMSRoles(): Promise<EMSRole[]> {
  return apiGet<EMSRole[]>('/ems/roles')
}

export async function listEMSTemplates(): Promise<EMSRole[]> {
  return apiGet<EMSRole[]>('/ems/roles/templates')
}

export async function createEMSRole(payload: CreateRolePayload): Promise<EMSRole> {
  return apiPost<EMSRole>('/ems/roles', payload)
}

export async function updateEMSRole(roleId: string | number, payload: UpdateRolePayload): Promise<EMSRole> {
  return apiPut<EMSRole>(`/ems/roles/${roleId}`, payload)
}

export async function deleteEMSRole(roleId: string | number): Promise<void> {
  return apiDelete<void>(`/ems/roles/${roleId}`)
}

export async function assignEMSRole(payload: AssignRolePayload): Promise<EMSUserRoleAssignment> {
  return apiPost<EMSUserRoleAssignment>('/ems/roles/assign', payload)
}

export async function revokeEMSRoleAssignment(assignmentId: string | number): Promise<void> {
  return apiDelete<void>(`/ems/roles/assign/${assignmentId}`)
}
