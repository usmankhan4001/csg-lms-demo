/**
 * Dependency-free JWT payload decoding + SecureStore-backed session storage.
 * =============================================================================
 *
 * WHY THIS EXISTS: see `apps/api/src/core/dev_tokens.py` and
 * `apps/api/scripts/mint_dev_keycloak_token.py` — this project has no real
 * Keycloak server deployed, so the SMS/RevOps backend (`get_current_user_principal`
 * in `apps/api/src/core/keycloak_auth.py`) is exercised locally with an
 * HS256 dev token minted by that script. The web app's equivalent is
 * `apps/web/lib/api/dev-token.ts` (stores the pasted token in
 * `localStorage`, decodes it client-side WITHOUT verifying the signature —
 * verification already happened server-side when the token was minted / is
 * re-checked on every API call). This module is the mobile counterpart,
 * using `expo-secure-store` instead of `localStorage`.
 *
 * Decoding is hand-rolled (no `atob`/`Buffer`/`TextDecoder`) so it behaves
 * identically across Hermes versions/platforms without depending on which
 * optional Web APIs a given RN/Hermes build happens to ship.
 */

import * as SecureStore from 'expo-secure-store';
import type { Session, SessionClaims } from './types';

export const SESSION_TOKEN_KEY = 'csg_lms_session_token';

const BASE64_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

function base64UrlToBytes(base64Url: string): number[] {
  const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
  const bytes: number[] = [];
  let buffer = 0;
  let bits = 0;
  for (let i = 0; i < base64.length; i++) {
    const char = base64[i];
    if (char === '=') break;
    const value = BASE64_CHARS.indexOf(char);
    if (value === -1) continue; // skip whitespace/invalid chars defensively
    buffer = (buffer << 6) | value;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      bytes.push((buffer >> bits) & 0xff);
    }
  }
  return bytes;
}

/** Manual UTF-8 byte decoding so non-ASCII claim values (names, etc.) come through correctly without relying on a global `TextDecoder`. */
function utf8BytesToString(bytes: number[]): string {
  let result = '';
  let i = 0;
  while (i < bytes.length) {
    const b1 = bytes[i++];
    if (b1 < 0x80) {
      result += String.fromCharCode(b1);
    } else if (b1 >= 0xc0 && b1 < 0xe0 && i < bytes.length) {
      const b2 = bytes[i++];
      result += String.fromCharCode(((b1 & 0x1f) << 6) | (b2 & 0x3f));
    } else if (b1 >= 0xe0 && b1 < 0xf0 && i + 1 < bytes.length) {
      const b2 = bytes[i++];
      const b3 = bytes[i++];
      result += String.fromCharCode(((b1 & 0x0f) << 12) | ((b2 & 0x3f) << 6) | (b3 & 0x3f));
    } else if (b1 >= 0xf0 && i + 2 < bytes.length) {
      const b2 = bytes[i++];
      const b3 = bytes[i++];
      const b4 = bytes[i++];
      let codepoint = ((b1 & 0x07) << 18) | ((b2 & 0x3f) << 12) | ((b3 & 0x3f) << 6) | (b4 & 0x3f);
      codepoint -= 0x10000;
      result += String.fromCharCode(0xd800 + (codepoint >> 10), 0xdc00 + (codepoint & 0x3ff));
    } else {
      i++; // malformed byte sequence, skip forward defensively
    }
  }
  return result;
}

/**
 * Decodes (does NOT verify) a JWT's payload segment. Returns null on any
 * malformed input. Mirrors `apps/web/lib/api/dev-token.ts`'s `decodeJwtPayload`.
 */
export function decodeJwtPayload<T = SessionClaims>(token: string | null | undefined): T | null {
  if (!token) return null;
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  try {
    const json = utf8BytesToString(base64UrlToBytes(parts[1]));
    return JSON.parse(json) as T;
  } catch {
    return null;
  }
}

export function isExpired(claims: SessionClaims | null): boolean {
  if (!claims || typeof claims.exp !== 'number') return false;
  return claims.exp * 1000 < Date.now();
}

/** Builds a full `Session` from a raw token, or null if malformed/expired/roleless. */
export function sessionFromToken(token: string): Session | null {
  const claims = decodeJwtPayload(token);
  if (!claims || !claims.sub) return null;
  if (isExpired(claims)) return null;
  const role = claims.realm_access?.roles?.[0];
  if (!role) return null;
  return { token, claims, role: role as Session['role'] };
}

export async function loadStoredSession(): Promise<Session | null> {
  try {
    const token = await SecureStore.getItemAsync(SESSION_TOKEN_KEY);
    if (!token) return null;
    const session = sessionFromToken(token);
    if (!session) {
      // Stale/expired/malformed token left over from a previous run — clean it up.
      await SecureStore.deleteItemAsync(SESSION_TOKEN_KEY).catch(() => {});
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

export async function storeSessionToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(SESSION_TOKEN_KEY, token);
}

export async function clearStoredSession(): Promise<void> {
  await SecureStore.deleteItemAsync(SESSION_TOKEN_KEY).catch(() => {});
}
