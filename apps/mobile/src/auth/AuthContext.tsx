import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { clearStoredSession, loadStoredSession, sessionFromToken, storeSessionToken } from './token';
import type { Session } from './types';

export type AuthStatus = 'hydrating' | 'signedOut' | 'signedIn';

export interface LoginResult {
  ok: boolean;
  error?: string;
}

interface AuthContextValue {
  status: AuthStatus;
  session: Session | null;
  /** Paste a dev Keycloak token (see src/auth/token.ts doc comment) and sign in. */
  loginWithToken: (rawToken: string) => Promise<LoginResult>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('hydrating');
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadStoredSession().then((restored) => {
      if (cancelled) return;
      setSession(restored);
      setStatus(restored ? 'signedIn' : 'signedOut');
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const loginWithToken = useCallback(async (rawToken: string): Promise<LoginResult> => {
    const trimmed = rawToken.trim();
    if (!trimmed) {
      return { ok: false, error: 'Paste a token first.' };
    }
    const next = sessionFromToken(trimmed);
    if (!next) {
      return {
        ok: false,
        error:
          "That doesn't look like a usable token. Make sure you copied the full value printed by " +
          'mint_dev_keycloak_token.py, and that it has not expired.',
      };
    }
    await storeSessionToken(trimmed);
    setSession(next);
    setStatus('signedIn');
    return { ok: true };
  }, []);

  const logout = useCallback(async () => {
    await clearStoredSession();
    setSession(null);
    setStatus('signedOut');
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, session, loginWithToken, logout }),
    [status, session, loginWithToken, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
