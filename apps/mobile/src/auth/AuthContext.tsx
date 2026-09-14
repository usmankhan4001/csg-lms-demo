import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { clearStoredSession, loadStoredSession, pickMobileRole, storeSession } from './token';
import { login as performLogin } from './login';
import { setUnauthenticatedHandler } from '@/api/client';
import type { Session } from './types';

export type AuthStatus = 'hydrating' | 'signedOut' | 'signedIn';

export interface LoginResult {
  ok: boolean;
  error?: string;
}

interface AuthContextValue {
  status: AuthStatus;
  session: Session | null;
  /**
   * Sign in with real credentials against Learnhouse's `/auth/login`.
   * Replaces the retired paste-a-dev-token flow.
   */
  login: (email: string, password: string) => Promise<LoginResult>;
  logout: () => Promise<void>;
  /**
   * Set when a restored session had already expired, so the sign-in screen can
   * explain why the user is back there instead of silently appearing to have
   * been signed out. Cleared on the next successful sign-in.
   */
  expiredNotice: string | null;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('hydrating');
  const [session, setSession] = useState<Session | null>(null);
  const [expiredNotice, setExpiredNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // `loadStoredSession` drops an expired record and reports it, so a user
    // returning to a run-out session is told why rather than just finding
    // themselves signed out.
    //
    // There is deliberately NO refresh attempt here. The login response does
    // carry a refresh_token, but `GET /auth/refresh` reads it from an httpOnly
    // COOKIE (apps/api/src/routers/auth.py:278), which this client has no way
    // to present. Building a header-based refresh would mean changing the
    // server, so expiry sends the user back to sign-in instead of inventing a
    // scheme that only half works.
    loadStoredSession().then(({ session: restored, expired }) => {
      if (cancelled) return;
      if (expired) {
        setExpiredNotice('Your session expired. Please sign in again.');
      }
      setSession(restored);
      setStatus(restored ? 'signedIn' : 'signedOut');
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<LoginResult> => {
    if (!email.trim() || !password) {
      return { ok: false, error: 'Enter your email and password.' };
    }

    const outcome = await performLogin(email, password);
    if (!outcome.ok) {
      return { ok: false, error: outcome.message };
    }

    const role = pickMobileRole(outcome.identity.roles);
    if (!role) {
      // They authenticated, but hold no role this app has screens for
      // (SCHOOL_ADMIN is web-only by product decision). Say so rather than
      // dropping them into an empty shell.
      return {
        ok: false,
        error:
          'Your account signs in, but this app has no screens for your role yet. Please use the web dashboard.',
      };
    }

    const next: Session = {
      token: outcome.token,
      expiresAt: outcome.expiresAt,
      identity: outcome.identity,
      role,
    };
    await storeSession(next);
    setExpiredNotice(null);
    setSession(next);
    setStatus('signedIn');
    return { ok: true };
  }, []);

  // A 401 from any endpoint means the token is no longer accepted -- almost
  // always because it expired mid-session. Sign out and say why, instead of
  // leaving the user on a shell where every screen shows an error.
  useEffect(() => {
    setUnauthenticatedHandler(() => {
      setExpiredNotice('Your session expired. Please sign in again.');
      setSession(null);
      setStatus('signedOut');
      void clearStoredSession();
    });
    return () => setUnauthenticatedHandler(null);
  }, []);

  const logout = useCallback(async () => {
    await clearStoredSession();
    setSession(null);
    setStatus('signedOut');
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, session, login, logout, expiredNotice }),
    [status, session, login, logout, expiredNotice]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
