/**
 * Application configuration.
 *
 * Reads values from `NEXT_PUBLIC_*` environment variables at build time
 * and provides typed, validated access to them throughout the frontend.
 */

function requireEnv(name: string, fallback?: string): string {
  const value = process.env[name] ?? fallback;
  if (!value) {
    throw new Error(
      `Missing required environment variable: ${name}. ` +
        "Check your .env.local file or deployment config.",
    );
  }
  return value;
}

/** Configuration object for the Symphony frontend. */
export const config = {
  /** Base URL of the LangGraph / backend API. */
  apiUrl: requireEnv(
    "NEXT_PUBLIC_LANGGRAPH_API_URL",
    "http://localhost:8000",
  ),

  /** Default assistant identifier used when creating new threads. */
  assistantId: requireEnv("NEXT_PUBLIC_ASSISTANT_ID", "general-chat"),
} as const;

export type AppConfig = typeof config;
