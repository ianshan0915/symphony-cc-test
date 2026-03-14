/**
 * Application configuration.
 * Values are read from environment variables at build time (NEXT_PUBLIC_*).
 */
export const config = {
  /** Base URL for the backend API */
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",

  /** Default assistant ID to use for new threads */
  assistantId: process.env.NEXT_PUBLIC_ASSISTANT_ID ?? "general-chat",

  /** Maximum message length (characters) */
  maxMessageLength: 10_000,

  /** Auto-scroll threshold in pixels — if user is within this distance
   *  from the bottom, auto-scroll on new messages */
  autoScrollThreshold: 150,
} as const;
