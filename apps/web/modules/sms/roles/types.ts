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

// NOTE: these field names are the backend's (`StudentGuardianRead` in
// db/sms_identity.py). They were previously declared here as
// `relation_type` / `is_primary`, which exist nowhere on the wire -- so both
// read as undefined at runtime while type-checking cleanly.
export interface GuardianLinkRecord {
  id: number
  guardian_user_id: number
  student_id: number
  relationship?: string | null
  is_primary_contact: boolean
  created_at?: string
}

export interface LinkGuardianPayload {
  guardian_user_id: number
  student_id: number
  relationship?: string
  is_primary_contact?: boolean
}


/**
 * Roles an administrator may hand out by provisioning an account.
 *
 * SUPER_ADMIN is deliberately absent and must stay absent: it is
 * cross-organization platform control, the backend refuses it on this surface
 * for every caller (`PROVISIONABLE_ROLES` in
 * services/sms/people_provisioning.py), and offering it in a picker would only
 * produce a 403 the administrator cannot act on.
 */
export type ProvisionableRole = Exclude<SchoolRoleType, 'SUPER_ADMIN'>

export interface ProvisionPersonPayload {
  role: ProvisionableRole
  email: string
  first_name: string
  last_name?: string
  campus_id?: number
  /** STUDENT only. Both are required together, or neither. */
  section_id?: number
  academic_year_id?: number
  roll_number?: string
  /** PARENT only. */
  child_student_id?: number
  relationship?: string
  is_primary_contact?: boolean
}

/**
 * What happened to the invitation, which is NOT the same question as what
 * happened to the account. PENDING means the email provider accepted the
 * message; DELIVERY_FAILED means it refused; UNKNOWN means the outcome could
 * not be determined and is reported honestly rather than assumed to be a
 * success; NOT_SENT means an administrator deliberately withheld it.
 */
export type InviteStatus =
  | 'PENDING'
  | 'DELIVERY_FAILED'
  | 'UNKNOWN'
  | 'ACCEPTED'
  | 'REVOKED'
  | 'NOT_SENT'

export interface ProvisionPersonResult {
  user_id: number
  email: string
  role: SchoolRoleType
  created_user: boolean
  created_role: boolean
  created_enrollment: boolean
  created_guardian_link: boolean
  invite_status?: InviteStatus | null
  invite_error?: string | null
}

export interface SchoolInvite {
  id: number
  subject_user_id: number
  subject_email: string
  subject_role: SchoolRoleType
  status: InviteStatus
  delivery_error?: string | null
  sent_count: number
  last_sent_at?: string | null
  expires_at?: string | null
  accepted_at?: string | null
}

export interface ResendPendingResult {
  attempted: number
  sent: number
  failed: number
  results: SchoolInvite[]
}

export interface BulkProvisionRowResult {
  /** 0-based index into the submitted list, so a spreadsheet line is findable. */
  row: number
  email?: string | null
  status: 'created' | 'reused' | 'failed'
  user_id?: number | null
  created_enrollment: boolean
  created_guardian_link: boolean
  error?: string | null
  invite_status?: InviteStatus | null
  invite_error?: string | null
}

export interface BulkProvisionResult {
  created: number
  reused: number
  failed: number
  results: BulkProvisionRowResult[]
  /** Counted separately from `created`: an account whose invite bounced is not
   *  a success, and the two numbers differing is the signal to act on. */
  invites_sent: number
  invites_failed: number
}

export interface DirectoryEntry {
  user_id: number
  name?: string | null
  email?: string | null
  /** Empty means no school role yet -- not a default, and never guessed. */
  roles: SchoolRoleType[]
  campus_id?: number | null
}
