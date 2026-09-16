'use client'

import { useMemo } from 'react'
import { useOrg } from '@/components/Contexts/OrgContext'
import { useSchoolSession } from '@/lib/api/useSchoolSession'
import { isFeatureAvailable } from '@services/plans/plans'
import type { SearchMetaSchoolAccess } from '@/lib/dashboard-search/types'

/**
 * One implementation of "may this viewer see this school surface".
 *
 * The same role arithmetic had grown independent copies -- DashLeftMenu,
 * DashMobileMenu, CommandPalette and SchoolDashboardHome -- and in-module tabs
 * would have been another. N copies of an access rule is where one of them
 * quietly rots and starts showing a teacher something it should not. This is
 * the single source: CommandPalette, SchoolDashboardHome and ModuleTabs read
 * it, and the two menus are being moved onto it. Any NEW surface must use this
 * rather than re-deriving roles.
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
  /** False until `GET /sms/me` settles, so callers can wait for the roles. */
  checked: boolean
  /** Campus & Sections: the school's structural root. See the note below. */
  showCampus: boolean
  /** Resolves a `schoolAccess` level the same way the palette and nav do. */
  allows: (level?: SearchMetaSchoolAccess) => boolean
  /** `resolved_features` lookup, matching DashLeftMenu's `isEnabled`. */
  isFeatureEnabled: (feature: string) => boolean
  /** `resolved_features` when the key is present, else the plan fallback. */
  isFeatureVisible: (feature: string) => boolean
}

export function useSchoolAccess(): SchoolAccess {
  const org = useOrg() as any
  const { session, checked } = useSchoolSession()
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

    // `isFeatureEnabled` answers "did the org switch this on". A key that is
    // absent from `resolved_features` entirely is a different question -- the
    // org config predates the flag, or the deployment bypasses flags -- and the
    // palette has always fallen back to the deployment mode for those. Kept as
    // a separate predicate so the two rules stay distinguishable.
    const isFeatureVisible = (feature: string) => {
      const rf = resolvedFeatures?.[feature]
      if (rf) return rf.enabled
      return isFeatureAvailable(feature)
    }

    // Campus & Sections is the school's structural root (campuses -> years ->
    // terms -> sections); nothing else in the school system works until one
    // exists, so it carries no feature toggle -- the same reasoning that keeps
    // School Settings ungated (gating the page that switches modules on behind
    // a module toggle would strand a fresh deployment). It therefore cannot
    // depend on sms_attendance/sms_gradebook/sms_timetable: a school that runs
    // only fees and exams would hide the very screen it needs to create the
    // sections those modules report on.
    const showCampus = canAdminister

    return {
      roles: r,
      noSchoolRole,
      canAdminister,
      canTeach,
      canBackOffice,
      canCounsel,
      hasAnyRole,
      checked,
      showCampus,
      allows,
      isFeatureEnabled,
      isFeatureVisible,
    }
  }, [roles, resolvedFeatures, checked])
}
