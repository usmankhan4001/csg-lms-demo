'use client'

import { useEffect, useState } from 'react'
import { getDevSession, type DevSessionClaims } from './dev-token'

/**
 * Reads the dev Keycloak session (see `./dev-token.ts`) after mount rather
 * than during render, so server-rendered and first-client-render output
 * match (no `window`/localStorage access during SSR) and there's no
 * hydration mismatch warning.
 */
export function useDevSession(): { session: DevSessionClaims | null; checked: boolean } {
  const [session, setSession] = useState<DevSessionClaims | null>(null)
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    setSession(getDevSession())
    setChecked(true)
  }, [])

  return { session, checked }
}
