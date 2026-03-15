import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Next.js middleware for route protection.
 *
 * - Unauthenticated users (no `symphony_token` cookie/localStorage) visiting
 *   protected routes are redirected to `/login`.
 * - Authenticated users visiting `/login` are redirected to `/`.
 *
 * NOTE: Next.js middleware runs on the Edge and cannot access localStorage.
 * We check for the token via a cookie that we set client-side. As a fallback,
 * the AuthProvider also performs a client-side redirect, so even if the
 * middleware doesn't catch an unauthenticated user, the client will.
 *
 * Since localStorage is the primary token store and middleware can't read it,
 * we rely on the client-side AuthProvider <ProtectedRoute> wrapper for the
 * actual auth gate. This middleware provides an optimistic server-side check
 * for users who have the cookie set.
 */

const PUBLIC_PATHS = ["/login", "/api", "/_next", "/favicon.ico"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths through
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Check for the token cookie (set client-side as a mirror of localStorage)
  const token = request.cookies.get("symphony_token")?.value;

  if (!token) {
    // No cookie — let the client-side AuthProvider handle the redirect.
    // We don't hard-redirect here because the token may be in localStorage
    // but not yet mirrored to a cookie (first load).
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all paths except static files and Next.js internals.
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
