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
 *
 * Also exports `authReadyPromise` / `markAuthReady()`: on a fresh full page
 * load (e.g. the post-login `window.location.href` redirect straight into a
 * portal), `AuthContext`'s session restore is asynchronous -- it has to
 * round-trip `/api/auth/refresh` before `accessToken` is known. SMS dashboard
 * pages fire their data fetches on mount via `useApiResource`, which doesn't
 * wait for that restore, so `getActiveAccessToken()` was still `null` on the
 * very first request after a fresh load -- confirmed live: every SMS call
 * 401'd immediately after the Phase 5 login redirect landed on a portal
 * page. `api-client.ts` now awaits `authReadyPromise` before reading the
 * token, so the FIRST request after a fresh load waits for that one restore
 * round-trip instead of racing it; every request after that resolves
 * instantly (the promise is only ever settled once).
 */

let activeAccessToken: string | null = null

export function setActiveAccessToken(token: string | null): void {
  activeAccessToken = token
}

export function getActiveAccessToken(): string | null {
  return activeAccessToken
}

let resolveAuthReady: () => void
export const authReadyPromise = new Promise<void>((resolve) => {
  resolveAuthReady = resolve
})

/** Called once by AuthContext.tsx after its initial session-restore settles
 * (authenticated OR unauthenticated) -- safe to call more than once, only
 * the first call has any effect. */
export function markAuthReady(): void {
  resolveAuthReady()
}
