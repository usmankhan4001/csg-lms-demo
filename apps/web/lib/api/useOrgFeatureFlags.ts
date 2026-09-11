'use client'

import { useEffect, useState } from 'react'
import { fetchOrgResolvedFeatures, type ResolvedFeatureMap } from './org-features'

/**
 * Fetches the org's resolved SMS feature flags once per mount for
 * `RoleSidebar` nav gating. See `./org-features.ts` for the endpoint, the
 * org-slug limitation, and the fail-open policy.
 */
export function useOrgFeatureFlags(): { flags: ResolvedFeatureMap | null; loading: boolean } {
  const [flags, setFlags] = useState<ResolvedFeatureMap | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetchOrgResolvedFeatures().then((result) => {
      if (cancelled) return
      setFlags(result)
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [])

  return { flags, loading }
}
