"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import { safeGetItem, safeSetItem } from "@/lib/safeStorage";

const THEME_KEY = "symphony_theme";

/**
 * ThemeToggle — toggles between light and dark mode.
 *
 * Reads/persists preference in localStorage.
 * Applies the `dark` class to the <html> element.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const [isDark, setIsDark] = React.useState(false);

  // Initialize from localStorage or system preference
  React.useEffect(() => {
    const stored = safeGetItem(THEME_KEY);
    if (stored === "dark") {
      setIsDark(true);
      document.documentElement.classList.add("dark");
    } else if (stored === "light") {
      setIsDark(false);
      document.documentElement.classList.remove("dark");
    } else {
      // Follow system preference
      const prefersDark =
        typeof window.matchMedia === "function"
          ? window.matchMedia("(prefers-color-scheme: dark)").matches
          : false;
      setIsDark(prefersDark);
      if (prefersDark) {
        document.documentElement.classList.add("dark");
      }
    }
  }, []);

  const toggle = React.useCallback(() => {
    setIsDark((prev) => {
      const next = !prev;
      if (next) {
        document.documentElement.classList.add("dark");
        safeSetItem(THEME_KEY, "dark");
      } else {
        document.documentElement.classList.remove("dark");
        safeSetItem(THEME_KEY, "light");
      }
      return next;
    });
  }, []);

  return (
    <button
      type="button"
      onClick={toggle}
      className={cn(
        "flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors focus:outline-none focus:ring-2 focus:ring-ring",
        className
      )}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {isDark ? (
        <Sun className="h-4 w-4" />
      ) : (
        <Moon className="h-4 w-4" />
      )}
    </button>
  );
}
