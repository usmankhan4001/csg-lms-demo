/**
 * Shared fetch client for the CSG-LMS SMS modules — the mobile counterpart of
 * `apps/web/lib/api/api-client.ts`. Same base URL convention (`/api/v1`),
 * same `ApiError` shape/`kind` classification (so UI state components can
 * share logic conceptually across web and mobile), same Bearer-token
 * attachment idea — except the token comes from `expo-secure-store` (see
 * `src/auth/token.ts`) instead of `localStorage`.
 *
 * Every module's `api.ts` should call `apiGet`/`apiPost`/etc. from here
 * rather than calling `fetch` directly.
 */

import { API_BASE_URL } from '@/config/env';
import { loadStoredSession } from '@/auth/token';

export type ApiErrorKind =
  | 'network'
  | 'unauthenticated'
  | 'permission_denied'
  | 'not_found'
  | 'validation'
  | 'server'
  | 'unknown';

/**
 * Normalized error every screen can branch on to pick the right one of the
 * DESIGN-SYSTEM.md §4 states — Error vs Offline vs Permission-denied need
 * different treatment, not just "something broke".
 */
export class ApiError extends Error {
  readonly status: number;
  readonly kind: ApiErrorKind;
  readonly code?: string;

  constructor(status: number, message: string, kind: ApiErrorKind, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.kind = kind;
    this.code = code;
  }
}

function classifyStatus(status: number): ApiErrorKind {
  if (status === 401) return 'unauthenticated';
  if (status === 403) return 'permission_denied';
  if (status === 404) return 'not_found';
  if (status === 422 || status === 400) return 'validation';
  if (status >= 500) return 'server';
  return 'unknown';
}

/**
 * Notified when the server rejects our token (401) mid-session.
 *
 * Access tokens last ~8 hours, so this fires in normal use: without it an
 * expired session leaves every screen showing an error the user cannot act on,
 * with no route back to sign-in. A module-level callback rather than a hook
 * because this file is plain TypeScript with no React context available --
 * `AuthProvider` registers itself on mount.
 */
type UnauthenticatedHandler = () => void;
let onUnauthenticated: UnauthenticatedHandler | null = null;

export function setUnauthenticatedHandler(handler: UnauthenticatedHandler | null): void {
  onUnauthenticated = handler;
}

async function getBearerToken(): Promise<string | null> {
  const { session } = await loadStoredSession();
  return session?.token ?? null;
}

export interface ApiFetchOptions extends RequestInit {
  /** Skip attaching a JSON Content-Type header (e.g. for FormData bodies). */
  rawBody?: boolean;
}

/**
 * Low-level fetch wrapper: builds the full URL, attaches auth + JSON headers,
 * and turns any non-2xx response (or a thrown network error) into an
 * `ApiError` with a `kind` the UI can switch on.
 */
export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { rawBody, headers: headersInit, ...rest } = options;
  const headers = new Headers(headersInit);
  if (!rawBody && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  headers.set('Accept', 'application/json');

  const token = await getBearerToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const url = `${API_BASE_URL}/api/v1${path.startsWith('/') ? path : `/${path}`}`;

  let response: Response;
  try {
    response = await fetch(url, { ...rest, headers });
  } catch {
    // fetch() rejects on DNS failure, connection refused, or the device
    // being offline -- this is the Offline-state trigger (DESIGN-SYSTEM.md §4/§8).
    throw new ApiError(0, 'Could not reach the server. Check your connection and try again.', 'network');
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  let body: unknown = undefined;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    const detail =
      (body && typeof body === 'object' && 'detail' in (body as Record<string, unknown>)
        ? String((body as Record<string, unknown>).detail)
        : undefined) || response.statusText || 'Request failed';
    const code =
      body && typeof body === 'object' && 'code' in (body as Record<string, unknown>)
        ? String((body as Record<string, unknown>).code)
        : undefined;
    const kind = classifyStatus(response.status);
    if (kind === 'unauthenticated') {
      // Signs the user out so they land on the sign-in screen with an
      // explanation, rather than on a shell where every request fails.
      onUnauthenticated?.();
    }
    throw new ApiError(response.status, detail, kind, code);
  }

  return body as T;
}

export function apiGet<T>(path: string, options?: ApiFetchOptions): Promise<T> {
  return apiFetch<T>(path, { ...options, method: 'GET' });
}

export function apiPost<T>(path: string, body?: unknown, options?: ApiFetchOptions): Promise<T> {
  return apiFetch<T>(path, { ...options, method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined });
}

export function apiPatch<T>(path: string, body?: unknown, options?: ApiFetchOptions): Promise<T> {
  return apiFetch<T>(path, { ...options, method: 'PATCH', body: body !== undefined ? JSON.stringify(body) : undefined });
}

export function apiPut<T>(path: string, body?: unknown, options?: ApiFetchOptions): Promise<T> {
  return apiFetch<T>(path, { ...options, method: 'PUT', body: body !== undefined ? JSON.stringify(body) : undefined });
}

export function apiDelete<T>(path: string, options?: ApiFetchOptions): Promise<T> {
  return apiFetch<T>(path, { ...options, method: 'DELETE' });
}

/** Builds a query string from a params object, skipping null/undefined/empty-string values. */
export function toQueryString(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}
