/**
 * Jest global setup — runs after the test framework is installed.
 *
 * Polyfills Web APIs that are available in Node 18+ and real browsers
 * but are missing from the jsdom environment used by Jest.
 */

// TextEncoder / TextDecoder are used by the SSE streaming code (handleSend)
// and by test helpers that encode SSE event bytes. jsdom does not expose the
// Node.js built-ins to the global scope, so we polyfill them here.
if (typeof globalThis.TextEncoder === "undefined") {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const utils = require("util") as typeof import("util");
  // Cast through unknown to satisfy strict assignability between Node util
  // types and the DOM global declarations.
  (globalThis as unknown as Record<string, unknown>).TextEncoder = utils.TextEncoder;
  (globalThis as unknown as Record<string, unknown>).TextDecoder = utils.TextDecoder;
}
