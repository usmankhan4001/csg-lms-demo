import type { ComponentType } from 'react'

export type SearchMetaGroup =
  | 'home'
  | 'navigation'
  | 'content'
  | 'users'
  | 'settings'
  | 'analytics'
  | 'payments'

// Loose so we can use Phosphor, Lucide, or any custom React icon component
// without coupling to a specific icon family's prop types.
export type SearchMetaIcon = ComponentType<any>

/**
 * School-role requirement for an SMS module, mirroring the gating in
 * DashLeftMenu/DashMobileMenu. Without this the palette would surface pages
 * the sidebar deliberately hides — a teacher finding "Staff & Payroll" via
 * Ctrl+K. The backend still authorizes independently; this only keeps
 * discovery consistent with the nav.
 */
/**
 * `counsel` exists because none of the other values can express the
 * counselling module's real rule. `administer`, `teach` and `backOffice` all
 * EXCLUDE PSYCHOLOGIST -- the one role that can read a counselling record --
 * while `anyRole` would surface it to every parent and student. Gating a
 * confidential module with a value that does not match its access rule is how
 * that gating quietly rots.
 */
export type SearchMetaSchoolAccess =
  | 'administer'
  | 'teach'
  | 'backOffice'
  | 'anyRole'
  | 'counsel'

export interface SearchMeta {
  id: string
  titleKey: string
  descriptionKey?: string
  keywordsKey?: string
  icon: SearchMetaIcon
  href: string
  group: SearchMetaGroup
  featureKey?: string
  featureDefaultDisabled?: boolean
  requiresOrgAdmin?: boolean
  schoolAccess?: SearchMetaSchoolAccess
  /**
   * Marks this entry as an ACTION rather than plain navigation: selecting it
   * lands on `href` and the destination page opens the named surface (a
   * dialog, usually) instead of just sitting there.
   *
   * Actions are deep links, not in-place callbacks. The palette is global, so
   * an action almost always targets a page the user is not currently on —
   * a callback would have to navigate first and then race the new page's
   * mount. Encoding the intent in the URL (`?action=<key>`) sidesteps that
   * entirely, survives a reload, and is shareable. See `useDeepLinkAction`.
   *
   * "Open in new tab" is suppressed for these: duplicating a tab to run an
   * action is meaningless, so `data-href` is deliberately omitted.
   */
  action?: string
}

/**
 * Query-string key carrying a deep-linked action. Kept here so the palette
 * that writes it and the `useDeepLinkAction` hook that reads it can never
 * drift apart.
 */
export const ACTION_QUERY_PARAM = 'action'
