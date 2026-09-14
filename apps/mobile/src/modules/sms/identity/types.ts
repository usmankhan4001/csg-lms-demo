/**
 * Mirrors `MyIdentityResponse` / `ChildContextResponse` / `SchoolPersonRead`
 * in `apps/api/src/routers/sms_identity.py` field-for-field.
 */

export interface MyIdentity {
  roles: string[]
  org_id?: number | null
  campus_id?: number | null
  student_id?: number | null
  staff_id?: number | null
  section_id?: number | null
  academic_term_id?: number | null
  /**
   * Resolved SERVER-SIDE from the `StudentGuardian` table for the signed-in
   * guardian (sms_identity.py: the PARENT branch of GET /me). This is the
   * authoritative parent->child link. Do NOT substitute the `children_ids`
   * JWT claim that `useSessionSubject` exposes: that is client-supplied and
   * a parent must only ever see children the server says are theirs.
   */
  children_ids: number[]
  name?: string | null
  email?: string | null
}

export interface ChildContext {
  student_id: number
  name?: string | null
  section_id?: number | null
  academic_term_id?: number | null
}

export interface SchoolPerson {
  user_id: number
  name?: string | null
  email?: string | null
  role: string
  campus_id?: number | null
}

export type SchoolRoleName =
  | 'SUPER_ADMIN'
  | 'SCHOOL_ADMIN'
  | 'TEACHER'
  | 'STUDENT'
  | 'PARENT'
  | 'STAFF'
  | 'PSYCHOLOGIST'
