"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  apiJson,
  clearToken,
  getToken,
  setLogoutCallback,
  setToken,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AuthUser {
  id: string;
  email: string;
  created_at: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  /** True while the initial session check is running */
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // ---- Logout ----
  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    setTokenState(null);
    // Redirect to login (only in browser)
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }, []);

  // Register the logout callback so the API client can call it on 401
  useEffect(() => {
    setLogoutCallback(logout);
  }, [logout]);

  // ---- Restore session on mount ----
  useEffect(() => {
    async function restore() {
      const existing = getToken();
      if (!existing) {
        setIsLoading(false);
        return;
      }

      try {
        const me = await apiJson<AuthUser>("/auth/me");
        setUser(me);
        setTokenState(existing);
      } catch {
        // Token is invalid — clear it
        clearToken();
      } finally {
        setIsLoading(false);
      }
    }

    restore();
  }, []);

  // ---- Login ----
  const login = useCallback(async (email: string, password: string) => {
    const res = await apiJson<{ access_token: string; token_type: string }>(
      "/auth/login",
      { method: "POST", json: { email, password } },
    );
    setToken(res.access_token);
    setTokenState(res.access_token);

    // Fetch the user profile
    const me = await apiJson<AuthUser>("/auth/me");
    setUser(me);
  }, []);

  // ---- Register ----
  const register = useCallback(async (email: string, password: string) => {
    const res = await apiJson<{ access_token: string; token_type: string }>(
      "/auth/register/token",
      { method: "POST", json: { email, password } },
    );
    setToken(res.access_token);
    setTokenState(res.access_token);

    const me = await apiJson<AuthUser>("/auth/me");
    setUser(me);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: !!user,
      isLoading,
      login,
      register,
      logout,
    }),
    [user, token, isLoading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an <AuthProvider>");
  }
  return ctx;
}
