/**
 * Dependency-free JWT payload decoding + SecureStore-backed session storage.
 * =============================================================================
 *
 * Sign-in itself lives in `login.ts`: it POSTs real credentials to Learnhouse's
 * own `/auth/login` and resolves roles from `GET /sms/me`. This module only
 * persists and restores the result.
 *
 * What changed, and why the stored shape is not just a token: a real
 * Learnhouse access token carries `{sub, purpose, amr, exp, iat, type}` and
 * nothing else -- no `realm_access.roles`, and none of the CSG convenience
 * claims (`subject_id`, `section_id`, `children_ids`) the deleted dev token
 * used to mint. So the session's role and identity come from `/sms/me` and are
 * stored alongside the token rather than decoded out of it.
 *
 * The identity is cached here so the app can pick the right persona shell on
 * launch without blocking on a network call. It is a startup hint, not a
 * source of truth: screens read live data through `useSchoolIdentity`, and
 * every endpoint re-authorises server-side regardless of what is cached here.
 *
 * Decoding is hand-rolled (no `atob`/`Buffer`/`TextDecoder`) so it behaves
 * identically across Hermes versions/platforms without depending on which
 * optional Web APIs a given RN/Hermes build happens to ship.
 */

import * as SecureStore from 'expo-secure-store';
import type { MobileRole, Session, SessionClaims } from './types';
import { MOBILE_SUPPORTED_ROLES } from './types';
import type { MyIdentity } from '@/modules/sms/identity/types';

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

const SESSION_RECORD_KEY = 'csg_lms_session_record';

interface StoredRecord {
  token: string;
  expiresAt: number | null;
  identity: MyIdentity;
  role: MobileRole;
}

/** True when the server told us an expiry and that moment has passed. */
export function isSessionExpired(expiresAt: number | null): boolean {
  return typeof expiresAt === 'number' && expiresAt <= Date.now();
}

/**
 * Picks the persona shell for a set of server-resolved roles.
 *
 * Ordered deliberately: a user who both administers and teaches should land in
 * the teacher shell, because that is the one with mobile screens built for it.
 */
export function pickMobileRole(roles: string[] | undefined): MobileRole | null {
  if (!roles?.length) return null;
  for (const candidate of MOBILE_SUPPORTED_ROLES) {
    if (roles.includes(candidate)) return candidate;
  }
  return null;
}

export interface RestoreResult {
  session: Session | null;
  /**
   * True only when a stored session was found and had run out. Lets the
   * sign-in screen say "your session expired" instead of leaving the user to
   * wonder why they were signed out, without confusing that with a first run.
   */
  expired: boolean;
}

export async function loadStoredSession(): Promise<RestoreResult> {
  try {
    const raw = await SecureStore.getItemAsync(SESSION_RECORD_KEY);
    if (!raw) {
      // Clear any token left by the retired paste-a-JWT flow so a stale dev
      // token cannot sit in SecureStore indefinitely.
      await SecureStore.deleteItemAsync(SESSION_TOKEN_KEY).catch(() => {});
      return { session: null, expired: false };
    }
    const record = JSON.parse(raw) as StoredRecord;
    if (!record?.token || !record?.identity || !record?.role) {
      await clearStoredSession();
      return { session: null, expired: false };
    }
    if (isSessionExpired(record.expiresAt)) {
      await clearStoredSession();
      return { session: null, expired: true };
    }
    return {
      session: {
        token: record.token,
        expiresAt: record.expiresAt,
        identity: record.identity,
        role: record.role,
      },
      expired: false,
    };
  } catch {
    return { session: null, expired: false };
  }
}

export async function storeSession(session: Session): Promise<void> {
  const record: StoredRecord = {
    token: session.token,
    expiresAt: session.expiresAt,
    identity: session.identity,
    role: session.role,
  };
  await SecureStore.setItemAsync(SESSION_RECORD_KEY, JSON.stringify(record));
}

export async function clearStoredSession(): Promise<void> {
  await SecureStore.deleteItemAsync(SESSION_RECORD_KEY).catch(() => {});
  await SecureStore.deleteItemAsync(SESSION_TOKEN_KEY).catch(() => {});
}
