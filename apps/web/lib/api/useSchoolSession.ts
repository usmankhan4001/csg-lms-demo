'use client'

import { useEffect, useState } from 'react'
import { apiGet } from './api-client'

/**
 * Replaces `useDevSession()` (`./useDevSession.ts`, now removed): the same
 * "who am I at school" identity, but resolved server-side from the real
 * Learnhouse session via `GET /api/v1/sms/me` instead of decoded client-side
 * from a dev-only Keycloak JWT. See PROJECT_DOCS/ARCHITECTURE.md.
 */
export interface SchoolSessionClaims {
  roles: string[]
  org_id: number | null
  campus_id: number | null
  student_id: number | null
  staff_id: number | null
  section_id: number | null
  academic_term_id: number | null
  children_ids: number[]
  name: string | null
  email: string | null
}

export interface ChildContext {
  student_id: number
  name: string | null
  section_id: number | null
  academic_term_id: number | null
}

/**
 * A specific child's own current section/term -- `SchoolSessionClaims`'s
 * `section_id`/`academic_term_id` are the CALLER's own (only ever populated
 * for the STUDENT role), so a PARENT with multiple children needs this
 * per-child instead. Access is enforced server-side (guardian of that child,
 * the student themselves, or a school admin/superadmin) -- see
 * GET /sms/identity/children/{student_id}/context.
 */
export function getChildContext(studentId: number): Promise<ChildContext> {
  return apiGet<ChildContext>(`/sms/identity/children/${studentId}/context`)
}

export function useSchoolSession(): { session: SchoolSessionClaims | null; checked: boolean } {
  const [session, setSession] = useState<SchoolSessionClaims | null>(null)
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    let cancelled = false
    apiGet<SchoolSessionClaims>('/sms/me')
      .then((result) => {
        if (!cancelled) setSession(result)
      })
      .catch(() => {
        if (!cancelled) setSession(null)
      })
      .finally(() => {
        if (!cancelled) setChecked(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return { session, checked }
}
