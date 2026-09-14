export type SchoolRoleType =
  | 'SUPER_ADMIN'
  | 'SCHOOL_ADMIN'
  | 'TEACHER'
  | 'STUDENT'
  | 'PARENT'
  | 'STAFF'
  | 'PSYCHOLOGIST'

export interface SMSUserRoleRecord {
  id: number
  user_id: number
  org_id?: number
  campus_id?: number
  role: SchoolRoleType
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface SchoolPerson {
  user_id: number
  name?: string
  email?: string
  role: SchoolRoleType
  campus_id?: number
}

export interface AssignRolePayload {
  user_id: number
  org_id?: number
  campus_id?: number
  role: SchoolRoleType
}

export interface GuardianLinkRecord {
  id: number
  guardian_user_id: number
  student_id: number
  relation_type?: string
  is_primary: boolean
  created_at?: string
}

export interface LinkGuardianPayload {
  guardian_user_id: number
  student_id: number
  relation_type?: string
  is_primary?: boolean
}
