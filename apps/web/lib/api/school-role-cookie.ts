/**
 * Sets a small, non-sensitive `LH_role` cookie from `GET /sms/me` so
 * `proxy.ts` (edge middleware, no React/hook access) can redirect a
 * freshly-authenticated single-tenancy user straight to their role portal
 * instead of `/home`'s pointless-for-a-single-school org picker.
 *
 * This is a UX hint only, NOT a security boundary -- every SMS route
 * independently authorizes via `get_current_user_principal`/`require_roles`
 * regardless of what this cookie says. See PROJECT_DOCS/ARCHITECTURE.md.
 *
 * Deliberately a standalone function, not routed through `api-client.ts`'s
 * `getBearerToken()`/module-level token bridge: this is called from
 * `AuthContext.tsx` at the exact moment a fresh access token is obtained,
 * before that token has necessarily propagated through a re-render into the
 * bridge -- so it takes the token directly as a parameter instead.
 */

import { getAPIUrl } from '@services/config/config'
import { bucketRealmRole } from '@/components/navigation/types'

const ROLE_COOKIE_NAME = 'LH_role'
const ROLE_COOKIE_MAX_AGE = 60 * 60 * 24 * 7 // 7 days -- generously outlives a session; harmless since it's not a security boundary

function setRoleCookie(role: string): void {
  document.cookie = `${ROLE_COOKIE_NAME}=${role}; Path=/; Max-Age=${ROLE_COOKIE_MAX_AGE}; SameSite=Lax`
}

export function clearRoleCookie(): void {
  document.cookie = `${ROLE_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax`
}

/** Best-effort: never throws, since a stale/missing cookie only degrades the
 * post-login redirect to today's `/home` fallback, not to a broken app. */
export async function refreshSchoolRoleCookie(accessToken: string): Promise<void> {
  try {
    const base = getAPIUrl().replace(/\/+$/, '')
    const res = await fetch(`${base}/sms/me`, {
      headers: { Authorization: `Bearer ${accessToken}`, Accept: 'application/json' },
    })
    if (!res.ok) return
    const data = await res.json()
    const roles: string[] = Array.isArray(data?.roles) ? data.roles : []
    if (roles.length === 0) return
    setRoleCookie(bucketRealmRole(roles[0]))
  } catch {
    // Network error, offline, etc. -- silently leave the cookie as it was.
  }
}
