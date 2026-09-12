/**
 * Shared fetch client for the CSG-LMS SMS modules (`modules/sms/*`).
 * =====================================================================
 *
 * Talks to the FastAPI backend's `/api/v1` surface and attaches a Bearer
 * token to every request:
 *   - the dev Keycloak token from `./dev-token` when present (see that file
 *     and `apps/api/src/core/dev_tokens.py` for how to obtain one locally --
 *     this project has no real Keycloak server deployed yet), otherwise
 *   - the Learnhouse native session's access token from `./learnhouse-session`
 *     if this code ever runs where BOTH systems happen to be present.
 *
 * Every module `api.ts` file should call `apiGet`/`apiPost`/etc. from here
 * rather than calling `fetch` directly, so auth attachment, base URL, and
 * error normalization stay in one place.
 */

import { getDevToken } from './dev-token'
import { getConfig } from '@services/config/config'

// NOT a frozen module-level constant: this file runs in the browser, and
// `getConfig()` reads `window.__RUNTIME_CONFIG__` (populated at container
// startup by server-wrapper.js, see that file + layout.tsx's
// `<script src="/runtime-config.js">`). A plain
// `process.env.NEXT_PUBLIC_LEARNHOUSE_BACKEND_URL` reference here would get
// permanently inlined to whatever (or nothing) was set at `next build` time
// -- which is exactly what silently pointed every SMS module fetch at the
// `http://localhost:1338` fallback in every real deployment so far, since
// none of them export that var at build time, only at container runtime.
function getBackendUrl(): string {
  return (getConfig('NEXT_PUBLIC_LEARNHOUSE_BACKEND_URL', 'http://localhost:1338')).replace(/\/+$/, '')
}

export type ApiErrorKind = 'network' | 'unauthenticated' | 'permission_denied' | 'not_found' | 'validation' | 'server' | 'unknown'

/**
 * Normalized error shape every module's UI can branch on directly to pick
 * the right state per DESIGN-SYSTEM.md §4 (Error vs Permission-denied vs
 * Offline all need different treatments, not just "something broke").
 */
export class ApiError extends Error {
  readonly status: number
  readonly kind: ApiErrorKind
  readonly code?: string

  constructor(status: number, message: string, kind: ApiErrorKind, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.kind = kind
    this.code = code
  }
}

function classifyStatus(status: number): ApiErrorKind {
  if (status === 401) return 'unauthenticated'
  if (status === 403) return 'permission_denied'
  if (status === 404) return 'not_found'
  if (status === 422 || status === 400) return 'validation'
  if (status >= 500) return 'server'
  return 'unknown'
}

function getBearerToken(): string | null {
  // Dev Keycloak token takes priority -- it's what every sms_* endpoint
  // actually authenticates against right now (see module doc comment above).
  return getDevToken()
}

export interface ApiFetchOptions extends RequestInit {
  /** Skip attaching a JSON Content-Type header (e.g. for FormData bodies). */
  rawBody?: boolean
}

/**
 * Low-level fetch wrapper: builds the full URL, attaches auth + JSON headers,
 * and turns any non-2xx response (or a thrown network error) into an
 * `ApiError` with a `kind` the UI can switch on.
 */
export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { rawBody, headers: headersInit, ...rest } = options
  const headers = new Headers(headersInit)
  if (!rawBody && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  headers.set('Accept', 'application/json')

  const token = getBearerToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const url = `${getBackendUrl()}/api/v1${path.startsWith('/') ? path : `/${path}`}`

  let response: Response
  try {
    response = await fetch(url, { ...rest, headers })
  } catch (cause) {
    // fetch() throws (TypeError) on DNS failure, connection refused, or the
    // browser being offline -- this is the Offline state trigger for
    // useApiResource-consuming components (see DESIGN-SYSTEM.md §4/§8).
    throw new ApiError(0, 'Could not reach the server. Check your connection and try again.', 'network')
  }

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  let body: unknown = undefined
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }

  if (!response.ok) {
    const detail =
      (body && typeof body === 'object' && 'detail' in (body as Record<string, unknown>)
        ? String((body as Record<string, unknown>).detail)
        : undefined) || response.statusText || 'Request failed'
    const code =
      body && typeof body === 'object' && 'code' in (body as Record<string, unknown>)
        ? String((body as Record<string, unknown>).code)
        : undefined
    throw new ApiError(response.status, detail, classifyStatus(response.status), code)
  }

  return body as T
}

export function apiGet<T>(path: string, options?: ApiFetchOptions): Promise<T> {
  return apiFetch<T>(path, { ...options, method: 'GET' })
}

export function apiPost<T>(path: string, body?: unknown, options?: ApiFetchOptions): Promise<T> {
  return apiFetch<T>(path, { ...options, method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined })
}

export function apiPatch<T>(path: string, body?: unknown, options?: ApiFetchOptions): Promise<T> {
  return apiFetch<T>(path, { ...options, method: 'PATCH', body: body !== undefined ? JSON.stringify(body) : undefined })
}

export function apiPut<T>(path: string, body?: unknown, options?: ApiFetchOptions): Promise<T> {
  return apiFetch<T>(path, { ...options, method: 'PUT', body: body !== undefined ? JSON.stringify(body) : undefined })
}

export function apiDelete<T>(path: string, options?: ApiFetchOptions): Promise<T> {
  return apiFetch<T>(path, { ...options, method: 'DELETE' })
}

/** Builds a query string from a params object, skipping null/undefined/empty-string values. */
export function toQueryString(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}
