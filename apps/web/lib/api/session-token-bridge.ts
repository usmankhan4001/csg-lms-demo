/**
 * Mirrors the current Learnhouse access token into a plain module-level
 * variable so `lib/api/api-client.ts` (a plain module, no React hook access)
 * can read it synchronously. `AuthContext.tsx`'s `SessionProvider` calls
 * `setActiveAccessToken()` directly in its render body whenever `accessToken`
 * changes -- the same pattern it already uses for its own internal
 * `accessTokenRef` mirror, just exposed outside the component.
 *
 * This replaces the dev Keycloak token (`./dev-token.ts`) as the source
 * `api-client.ts` attaches to SMS module fetches -- see PROJECT_DOCS/ARCHITECTURE.md.
 */

let activeAccessToken: string | null = null

export function setActiveAccessToken(token: string | null): void {
  activeAccessToken = token
}

export function getActiveAccessToken(): string | null {
  return activeAccessToken
}
