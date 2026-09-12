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
