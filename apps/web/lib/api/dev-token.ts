/**
 * Dev-only Keycloak Bearer token storage & decoding.
 * ====================================================
 *
 * WHY THIS EXISTS: the SMS/RevOps backend routers (`apps/api/src/routers/sms_*.py`)
 * now require a Keycloak-shaped JWT via `get_current_user_principal`. No real
 * Keycloak server has ever been deployed for this project, and Learnhouse's own
 * login flow (`app/auth/login`, `lib/auth/server.ts`) is a completely separate,
 * unrelated native auth system that knows nothing about Keycloak roles/org_id/
 * campus_id. See `apps/api/src/core/dev_tokens.py` for the backend half of this.
 *
 * HOW TO GET A TOKEN:
 *   1. `cd apps/api && uv run python scripts/mint_dev_keycloak_token.py --role TEACHER`
 *      (or `POST /api/v1/dev/mint_keycloak_token` if you have a superadmin
 *      Learnhouse session -- see that script's docstring for both).
 *   2. Paste the printed token into the browser console:
 *        localStorage.setItem('csg_dev_keycloak_token', '<token>')
 *      then reload. Every SMS module `api.ts` call (via `apiFetch` in
 *      `./api-client`) automatically attaches it as `Authorization: Bearer <token>`.
 *
 * This module never talks to the network itself -- it only reads/writes
 * localStorage and decodes the JWT payload (base64, unverified) so the
 * frontend can read the CSG-LMS dev convenience claims (`subject_id`,
 * `section_id`, `academic_term_id`, `children_ids`) that let the 5 dashboard
 * pages ask for "my" data. Decoding here does NOT verify the signature --
 * that already happened server-side; the frontend trusts its own token only
 * to read back the claims it (or the dev script) put there.
 */

export const DEV_TOKEN_STORAGE_KEY = 'csg_dev_keycloak_token'

export interface DevSessionClaims {
  sub: string
  email?: string | null
  name?: string | null
  org_id?: number | null
  campus_id?: number | null
  /** CSG-LMS dev convenience claim: "my" student_id / staff_id / teacher_id. */
  subject_id?: number | null
  section_id?: number | null
  academic_term_id?: number | null
  children_ids?: number[] | null
  realm_access?: { roles?: string[] }
  exp?: number
  [key: string]: unknown
}

export function getDevToken(): string | null {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage.getItem(DEV_TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setDevToken(token: string): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(DEV_TOKEN_STORAGE_KEY, token)
  } catch {
    // localStorage unavailable (private mode, disabled storage) -- fail silently,
    // apiFetch will simply proceed unauthenticated and surface a 401.
  }
}

export function clearDevToken(): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(DEV_TOKEN_STORAGE_KEY)
  } catch {
    // ignore
  }
}

/** Decodes (does NOT verify) a JWT's payload segment. Returns null on any malformed input. */
export function decodeJwtPayload<T = DevSessionClaims>(token: string | null | undefined): T | null {
  if (!token) return null
  const parts = token.split('.')
  if (parts.length !== 3) return null
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4)
    const binary = typeof window !== 'undefined' ? window.atob(padded) : Buffer.from(padded, 'base64').toString('binary')
    // Re-encode each byte as UTF-8 so non-ASCII claim values (names, etc.) decode correctly.
    const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0))
    const json = new TextDecoder('utf-8').decode(bytes)
    return JSON.parse(json)
  } catch {
    return null
  }
}

/** Current dev session claims decoded from the stored token, or null if none/invalid/expired. */
export function getDevSession(): DevSessionClaims | null {
  const token = getDevToken()
  const claims = decodeJwtPayload(token)
  if (!claims) return null
  if (typeof claims.exp === 'number' && claims.exp * 1000 < Date.now()) return null
  return claims
}

export function getDevSessionRole(): string | null {
  const session = getDevSession()
  return session?.realm_access?.roles?.[0] ?? null
}
