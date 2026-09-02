'use client';

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react';
import { login as apiLogin, logout as apiLogout, getMe } from '@/api/auth';
import { setAccessToken, getAccessToken } from '@/api/client';
import type { User, Workspace, UserRole } from '@/types';
import { getMyWorkspace } from '@/api/workspace';

interface AuthState {
  user: User | null;
  workspace: Workspace | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  role: UserRole | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    workspace: null,
    isLoading: true,
    isAuthenticated: false,
  });

  // On mount — try to restore session using stored refresh token
  useEffect(() => {
    const restore = async () => {
      const storedRefresh =
        typeof window !== 'undefined'
          ? localStorage.getItem('cortex_refresh_token')
          : null;

      if (!storedRefresh) {
        setState((s) => ({ ...s, isLoading: false }));
        return;
      }

      try {
        // If we have a refresh token, try to get user (the axios interceptor
        // will auto-refresh on 401 using the stored refresh token)
        // But access token is lost on page reload, so we refresh manually
        const { default: axios } = await import('axios');
        const BASE_URL =
          process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
        const resp = await axios.post(`${BASE_URL}/auth/refresh`, {
          refresh_token: storedRefresh,
        });
        setAccessToken(resp.data.access_token);
        localStorage.setItem('cortex_refresh_token', resp.data.refresh_token);

        const [user, workspace] = await Promise.all([
          getMe(),
          getMyWorkspace(),
        ]);
        setState({ user, workspace, isLoading: false, isAuthenticated: true });
      } catch {
        setAccessToken(null);
        localStorage.removeItem('cortex_refresh_token');
        setState({ user: null, workspace: null, isLoading: false, isAuthenticated: false });
      }
    };
    restore();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { user } = await apiLogin(email, password);
    // After login, access token is already set in client.ts
    // Fetch workspace
    const workspace = await getMyWorkspace();
    setState({ user, workspace, isLoading: false, isAuthenticated: true });
  }, []);

  const logout = useCallback(async () => {
    const storedRefresh =
      typeof window !== 'undefined'
        ? localStorage.getItem('cortex_refresh_token')
        : null;
    if (storedRefresh) {
      await apiLogout(storedRefresh);
    }
    setState({ user: null, workspace: null, isLoading: false, isAuthenticated: false });
  }, []);

  const value: AuthContextValue = {
    ...state,
    login,
    logout,
    role: state.user?.role ?? null,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export function useRole(): UserRole | null {
  return useAuth().role;
}
