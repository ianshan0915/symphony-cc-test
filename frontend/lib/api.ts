/**
 * Centralized API client with JWT authentication.
 *
 * All backend requests should go through this module so the Authorization
 * header is attached automatically and 401 responses trigger a logout.
 */

import { config } from "./config";

const TOKEN_KEY = "symphony_token";

// ---------------------------------------------------------------------------
// Token helpers
// ---------------------------------------------------------------------------

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ---------------------------------------------------------------------------
// Logout callback (set by AuthProvider so we can redirect on 401)
// ---------------------------------------------------------------------------

let logoutCallback: (() => void) | null = null;

export function setLogoutCallback(cb: () => void): void {
  logoutCallback = cb;
}

// ---------------------------------------------------------------------------
// Token refresh logic
// ---------------------------------------------------------------------------

/** In-flight refresh promise used to deduplicate concurrent refresh attempts. */
let refreshPromise: Promise<boolean> | null = null;

/**
 * Attempt to obtain a fresh JWT via `POST /auth/refresh`.
 *
 * Returns `true` when a new token was stored, `false` otherwise.  Concurrent
 * callers share a single in-flight request so we never fire multiple refresh
 * calls at the same time.
 */
async function attemptTokenRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const token = getToken();
      if (!token) return false;

      const res = await fetch(`${config.apiUrl}/auth/refresh`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) return false;

      const data = await res.json();
      const newToken: string | undefined =
        data?.access_token ?? data?.token;
      if (!newToken) return false;

      setToken(newToken);
      return true;
    } catch {
      return false;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

// ---------------------------------------------------------------------------
// Authenticated fetch wrapper
// ---------------------------------------------------------------------------

/**
 * Wrapper around `fetch` that:
 * 1. Prepends the API base URL when the path starts with `/`
 * 2. Attaches the `Authorization: Bearer <token>` header
 * 3. On 401, attempts a token refresh and retries the request once
 * 4. If the refresh also fails, clears the token and triggers logout
 */
export async function apiFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const url = path.startsWith("http") ? path : `${config.apiUrl}${path}`;

  const headers = new Headers(init?.headers);
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...init,
    headers,
  });

  if (response.status === 401) {
    // Don't try to refresh if this request was itself a refresh call
    if (path === "/auth/refresh") {
      clearToken();
      logoutCallback?.();
      return response;
    }

    const refreshed = await attemptTokenRefresh();

    if (refreshed) {
      // Retry the original request with the new token
      const retryHeaders = new Headers(init?.headers);
      const newToken = getToken();
      if (newToken) {
        retryHeaders.set("Authorization", `Bearer ${newToken}`);
      }
      return fetch(url, { ...init, headers: retryHeaders });
    }

    // Refresh failed — hard logout
    clearToken();
    logoutCallback?.();
  }

  return response;
}

/**
 * Convenience wrapper for JSON API calls.
 */
export async function apiJson<T = unknown>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const { json, ...rest } = init ?? {};

  const headers = new Headers(rest.headers);
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await apiFetch(path, {
    ...rest,
    headers,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new ApiError(response.status, detail?.detail ?? response.statusText);
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
