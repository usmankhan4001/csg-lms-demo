/**
 * Real sign-in against Learnhouse's own auth endpoint.
 * =============================================================================
 *
 * Replaces the dev-token paste flow, which was dead: `dev_tokens.py` was
 * deleted and `get_current_user_principal` now depends on
 * `get_authenticated_user` -- a real Learnhouse session -- so a locally-minted
 * Keycloak-shaped JWT is no longer recognised and every authenticated screen
 * 401'd.
 *
 * Two things about the real token differ from the dev one, and both matter:
 *
 * 1. It is FORM-ENCODED in, not JSON. `POST /api/v1/auth/login` declares
 *    `username: str = Form(...)`, `password: str = Form(...)`
 *    (apps/api/src/routers/auth.py:487). A JSON body gets a 422.
 *
 * 2. It carries NO ROLE CLAIM. Verified against the running API, the payload
 *    is `{sub, purpose, amr, exp, iat, type}` and `sub` is the user's EMAIL --
 *    there is no `realm_access.roles`. The old `sessionFromToken()` read the
 *    role out of that claim, so it would return null for every real token.
 *    Roles now come from `GET /sms/me`, which resolves them server-side from
 *    the `SMSUserRole` table.
 *
 * That second point is an improvement rather than a workaround: which roles a
 * user holds is exactly the kind of question the client must not answer for
 * itself, and it is the same reasoning `useSchoolIdentity` already documents
 * for the guardian->child link.
 */

import { API_BASE_URL } from '@/config/env';
import type { MyIdentity } from '@/modules/sms/identity/types';
import { decodeJwtPayload } from './token';

/** Distinguishable failure modes, so the UI never says "login failed" to all of them. */
export type LoginFailure =
  | 'invalid_credentials'
  | 'account_locked'
  | 'rate_limited'
  | 'email_not_verified'
  | 'mfa_required'
  | 'no_school_role'
  | 'network'
  | 'server';

export interface LoginSuccess {
  ok: true;
  token: string;
  /** Epoch ms at which the access token stops being accepted, when the server says. */
  expiresAt: number | null;
  identity: MyIdentity;
}

export interface LoginError {
  ok: false;
  reason: LoginFailure;
  message: string;
}

export type LoginOutcome = LoginSuccess | LoginError;

/** Maps the server's own error codes to a message a parent or teacher can act on. */
function describeFailure(status: number, code: string | undefined, serverMessage?: string): LoginError {
  if (status === 401) {
    return {
      ok: false,
      reason: 'invalid_credentials',
      // Deliberately does not distinguish unknown-email from wrong-password:
      // the server goes to some length to make those indistinguishable
      // (a dummy Argon2 verify on the unknown-user path) so that this endpoint
      // cannot be used to discover which families have accounts.
      message: 'Incorrect email or password.',
    };
  }
  if (status === 423) {
    return {
      ok: false,
      reason: 'account_locked',
      message: serverMessage ?? 'This account is temporarily locked after too many failed attempts.',
    };
  }
  if (status === 429) {
    return {
      ok: false,
      reason: 'rate_limited',
      message: serverMessage ?? 'Too many sign-in attempts. Please wait a few minutes and try again.',
    };
  }
  if (status === 403 && code === 'EMAIL_NOT_VERIFIED') {
    return {
      ok: false,
      reason: 'email_not_verified',
      message: 'Please verify your email address before signing in.',
    };
  }
  if (status >= 500) {
    return {
      ok: false,
      reason: 'server',
      message: 'The school server is not responding correctly. Please try again shortly.',
    };
  }
  return {
    ok: false,
    reason: 'server',
    message: serverMessage ?? 'Sign-in failed. Please try again.',
  };
}

/**
 * Signs in and resolves the caller's school identity.
 *
 * Returns the token rather than storing it: storage is `token.ts`'s job, and
 * keeping this function free of side effects makes it testable and keeps the
 * credential's lifetime obvious at the call site.
 */
export async function login(email: string, password: string): Promise<LoginOutcome> {
  const body = new URLSearchParams();
  body.append('username', email.trim());
  body.append('password', password);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });
  } catch {
    // A thrown fetch is a transport problem, never a credential problem --
    // telling the user their password is wrong when the Wi-Fi is down sends
    // them down completely the wrong path.
    return {
      ok: false,
      reason: 'network',
      message: 'Could not reach the school server. Check your connection and try again.',
    };
  }

  let payload: any = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail = payload?.detail;
    const code = typeof detail === 'object' ? detail?.code : undefined;
    const message = typeof detail === 'object' ? detail?.message : typeof detail === 'string' ? detail : undefined;
    return describeFailure(response.status, code, message);
  }

  // A second factor means nothing is authenticated yet: the server returns a
  // short-lived pending token and no session. This app has no MFA screen, so
  // say so plainly rather than appearing to sign in.
  if (payload?.mfa_required) {
    return {
      ok: false,
      reason: 'mfa_required',
      message:
        'This account uses two-factor authentication, which the mobile app does not support yet. Please sign in on the web.',
    };
  }

  const token: string | undefined = payload?.tokens?.access_token;
  if (!token) {
    return {
      ok: false,
      reason: 'server',
      message: 'The server did not return a session. Please try again.',
    };
  }

  // Expiry, preferring the token's own `exp` claim over the response field.
  //
  // `tokens.expiry` comes from `get_token_expiry_ms()` and is null in this
  // deployment -- verified against the running API -- so relying on it alone
  // would produce a session that never expires locally and instead dies as a
  // surprise 401 mid-task. The JWT always carries a standard `exp` (epoch
  // SECONDS, hence the x1000), so read that first and treat the response
  // field as the fallback.
  const claims = decodeJwtPayload(token);
  const expFromClaim =
    claims && typeof claims.exp === 'number' ? claims.exp * 1000 : null;
  const lifetimeMs: unknown = payload?.tokens?.expiry;
  const expFromResponse =
    typeof lifetimeMs === 'number' && lifetimeMs > 0 ? Date.now() + lifetimeMs : null;
  const expiresAt = expFromClaim ?? expFromResponse;

  // Resolve roles server-side. Done here, before the session is stored, so a
  // user with no school role never reaches a persona shell that cannot render.
  let identity: MyIdentity;
  try {
    const meResponse = await fetch(`${API_BASE_URL}/api/v1/sms/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!meResponse.ok) {
      return {
        ok: false,
        reason: meResponse.status === 401 ? 'invalid_credentials' : 'server',
        message: 'Signed in, but your school profile could not be loaded. Contact your school administrator.',
      };
    }
    identity = (await meResponse.json()) as MyIdentity;
  } catch {
    return {
      ok: false,
      reason: 'network',
      message: 'Signed in, but the connection dropped before your profile loaded. Please try again.',
    };
  }

  if (!identity?.roles?.length) {
    return {
      ok: false,
      reason: 'no_school_role',
      message:
        'Your account is not linked to a school role yet. Ask your school administrator to grant you access.',
    };
  }

  return { ok: true, token, expiresAt, identity };
}
