'use client'

import { useMemo } from 'react'
import { useOrg } from '@/components/Contexts/OrgContext'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import type { SearchMetaSchoolAccess } from '@/lib/dashboard-search/types'

/**
 * One implementation of "may this viewer see this school surface".
 *
 * The same role arithmetic had grown three independent copies -- DashLeftMenu,
 * DashMobileMenu and CommandPalette -- and in-module tabs would have been a
 * fourth. Four copies of an access rule is where one of them quietly rots and
 * starts showing a teacher something it should not. This is the single source;
 * the three existing call sites keep their own inline copies for now, but any
 * NEW surface should use this.
 *
 * Discovery gating only. The backend authorizes every request independently --
 * hiding a tab is a usability decision, not a security boundary.
 */

export interface SchoolAccess {
  roles: string[]
  /** A Learnhouse org admin holding no school role at all. */
  noSchoolRole: boolean
  canAdminister: boolean
  canTeach: boolean
  canBackOffice: boolean
  /** PSYCHOLOGIST, plus the leadership who administer the module. */
  canCounsel: boolean
  hasAnyRole: boolean
  /** Resolves a `schoolAccess` level the same way the palette and nav do. */
  allows: (level?: SearchMetaSchoolAccess) => boolean
  /** `resolved_features` lookup, matching DashLeftMenu's `isEnabled`. */
  isFeatureEnabled: (feature: string) => boolean
}

export function useSchoolAccess(): SchoolAccess {
  const org = useOrg() as any
  const { session } = useSchoolSession()
  const roles = session?.roles

  // `useOrg()` returns the org object itself (OrgContext.tsx:84 -- `context?.org
  // ?? null`), not a { org, ... } wrapper; that wrapper is `useOrgMembership()`.
  // Same path CommandPalette uses, so the two cannot disagree about which
  // features are on.
  const resolvedFeatures = org?.config?.config?.resolved_features

  return useMemo(() => {
    const r = roles ?? []
    // An org admin who holds no school role keeps full visibility: granting
    // the first SMS role requires reaching these screens, so locking them out
    // would make a new school impossible to set up.
    const noSchoolRole = r.length === 0
    const canAdminister =
      r.includes('SUPER_ADMIN') || r.includes('SCHOOL_ADMIN') || noSchoolRole
    const canTeach = canAdminister || r.includes('TEACHER')
    const canBackOffice = canAdminister || r.includes('STAFF')
    // Deliberately NOT `teach`. The counselling backend answers 404 rather
    // than 403 so a teacher cannot learn that a child is seeing a counsellor;
    // pointing them at the surface in the UI would give that away regardless.
    const canCounsel = canAdminister || r.includes('PSYCHOLOGIST')
    const hasAnyRole = r.length > 0 || noSchoolRole

    const allows = (level?: SearchMetaSchoolAccess) => {
      switch (level) {
        case undefined:
          return true
        case 'administer':
          return canAdminister
        case 'teach':
          return canTeach
        case 'backOffice':
          return canBackOffice
        case 'anyRole':
          return hasAnyRole
        case 'counsel':
          return canCounsel
      }
    }

    const isFeatureEnabled = (feature: string) =>
      resolvedFeatures?.[feature]?.enabled === true

    return {
      roles: r,
      noSchoolRole,
      canAdminister,
      canTeach,
      canBackOffice,
      canCounsel,
      hasAnyRole,
      allows,
      isFeatureEnabled,
    }
  }, [roles, resolvedFeatures])
}
