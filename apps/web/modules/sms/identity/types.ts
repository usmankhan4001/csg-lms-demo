/** Mirrors `apps/api/src/db/sms_identity.py`. */

/**
 * The school roles a Learnhouse user can hold. Deliberately distinct from
 * Learnhouse's own org roles (admin/maintainer/member): a person is a
 * Learnhouse *member* and a school *TEACHER* at the same time, and the two
 * answer different questions. Learnhouse's role decides what they can do to
 * courses; this decides what they are in the school.
 */
export type SchoolRole =
  | 'SUPER_ADMIN'
  | 'SCHOOL_ADMIN'
  | 'TEACHER'
  | 'STUDENT'
  | 'PARENT'
  | 'STAFF'
  | 'PSYCHOLOGIST'

export const SCHOOL_ROLES: SchoolRole[] = [
  'SCHOOL_ADMIN',
  'TEACHER',
  'STUDENT',
  'PARENT',
  'STAFF',
  'PSYCHOLOGIST',
  'SUPER_ADMIN',
]

/** Human labels — the enum values are shouty and not for end users. */
export const SCHOOL_ROLE_LABELS: Record<SchoolRole, string> = {
  SUPER_ADMIN: 'Super admin',
  SCHOOL_ADMIN: 'School admin',
  TEACHER: 'Teacher',
  STUDENT: 'Student',
  PARENT: 'Parent',
  STAFF: 'Staff',
  PSYCHOLOGIST: 'Counsellor',
}

export interface SMSUserRoleRead {
  id: number
  user_id: number
  org_id: number
  campus_id: number | null
  role: SchoolRole
  is_active: boolean
}

export interface SMSUserRoleCreate {
  user_id: number
  org_id: number
  role: SchoolRole
  campus_id?: number | null
}

export interface StudentGuardianRead {
  id: number
  guardian_user_id: number
  student_id: number
  relationship: string | null
  is_primary_contact: boolean
}

export interface StudentGuardianCreate {
  guardian_user_id: number
  student_id: number
  relationship?: string | null
  is_primary_contact?: boolean
}
