/**
 * Client-side helper for the dev Keycloak token flow (see ./dev-token.ts for
 * why this exists: no real Keycloak server has ever been deployed for this
 * project). Without this, getting into the SMS dashboards required opening
 * devtools, running a Python script, and pasting a JWT into localStorage by
 * hand -- a step no one testing the app through the UI would ever discover on
 * their own. This wraps the same backend endpoint
 * (`POST /api/v1/dev/mint_keycloak_token`) behind one function call so a
 * plain "Continue as Student" button can do it instead.
 */

import { getConfig } from '@services/config/config'
import { setDevToken, type DevSessionClaims } from './dev-token'

function getBackendUrl(): string {
  return getConfig('NEXT_PUBLIC_LEARNHOUSE_BACKEND_URL', 'http://localhost:1338').replace(/\/+$/, '')
}

export type DevRealmRole =
  | 'SUPER_ADMIN'
  | 'SCHOOL_ADMIN'
  | 'TEACHER'
  | 'STUDENT'
  | 'PARENT'
  | 'STAFF'
  | 'PSYCHOLOGIST'

export class DevLoginError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'DevLoginError'
    this.status = status
  }
}

/**
 * Mints a dev Keycloak-shaped JWT for the given role using the caller's real
 * Learnhouse superadmin session, then stores it so every SMS module fetch
 * (via lib/api/api-client.ts) picks it up automatically.
 *
 * Requires the current Learnhouse session to be a superadmin -- the backend
 * enforces this independently (see src/routers/dev.py::mint_keycloak_token)
 * and 404s outright if this deployment ever points at a real Keycloak
 * server, so this stays inert/safe in any real deployment.
 */
export async function mintAndStoreDevToken(
  role: DevRealmRole,
  learnhouseAccessToken: string,
): Promise<DevSessionClaims> {
  const res = await fetch(`${getBackendUrl()}/api/v1/dev/mint_keycloak_token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${learnhouseAccessToken}`,
    },
    body: JSON.stringify({ role }),
  })

  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new DevLoginError(res.status, detail?.detail || `Failed to mint dev token (${res.status})`)
  }

  const data = await res.json()
  setDevToken(data.access_token)
  return data.claims as DevSessionClaims
}
