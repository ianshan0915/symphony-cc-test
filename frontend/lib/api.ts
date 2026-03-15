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
// Authenticated fetch wrapper
// ---------------------------------------------------------------------------

/**
 * Wrapper around `fetch` that:
 * 1. Prepends the API base URL when the path starts with `/`
 * 2. Attaches the `Authorization: Bearer <token>` header
 * 3. Intercepts 401 responses and triggers logout
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
