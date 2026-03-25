/**
 * Safe localStorage wrapper that gracefully handles:
 * - Private browsing mode (where storage may be unavailable)
 * - Storage quota exceeded
 * - Server-side rendering (no `window`)
 *
 * Falls back to an in-memory Map when localStorage is unavailable.
 */

const memoryFallback = new Map<string, string>();
let _storageAvailable: boolean | null = null;

function isStorageAvailable(): boolean {
  if (_storageAvailable !== null) return _storageAvailable;
  try {
    if (typeof window === "undefined") {
      _storageAvailable = false;
      return false;
    }
    const testKey = "__storage_test__";
    window.localStorage.setItem(testKey, "1");
    window.localStorage.removeItem(testKey);
    _storageAvailable = true;
  } catch {
    _storageAvailable = false;
  }
  return _storageAvailable;
}

export function safeGetItem(key: string): string | null {
  try {
    if (isStorageAvailable()) {
      return window.localStorage.getItem(key);
    }
  } catch {
    // Fall through to memory fallback
  }
  return memoryFallback.get(key) ?? null;
}

export function safeSetItem(key: string, value: string): void {
  try {
    if (isStorageAvailable()) {
      window.localStorage.setItem(key, value);
      return;
    }
  } catch {
    // Fall through to memory fallback
  }
  memoryFallback.set(key, value);
}

export function safeRemoveItem(key: string): void {
  try {
    if (isStorageAvailable()) {
      window.localStorage.removeItem(key);
      return;
    }
  } catch {
    // Fall through to memory fallback
  }
  memoryFallback.delete(key);
}
