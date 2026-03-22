"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

// Maximum recursion depth before falling back to raw JSON display.
const MAX_DEPTH = 8;

// ---------------------------------------------------------------------------
// Helpers — field-type detection and formatting
// ---------------------------------------------------------------------------

/**
 * Returns true if the string looks like an ISO-8601 date or datetime.
 * Only accepts strings of the form YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS…
 * to avoid false positives from partial dates, version strings, etc.
 */
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}(T[\d:.Z+\-]+)?$/;
function looksLikeDate(value: string): boolean {
  return ISO_DATE_RE.test(value) && !isNaN(Date.parse(value));
}

/** Returns true if the string looks like an absolute URL. */
function looksLikeUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

/**
 * Format a primitive value for display, applying type-specific formatting:
 * - Numbers: locale-aware (with decimal places preserved)
 * - Dates: human-readable local date-time
 * - URLs: rendered as a clickable anchor
 * - Booleans: "Yes" / "No"
 * - null / undefined: em-dash
 */
function formatPrimitive(value: unknown): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground">—</span>;
  }
  if (typeof value === "boolean") {
    return (
      <span
        className={cn(
          "inline-block px-1.5 py-0.5 rounded text-xs font-medium",
          value
            ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
            : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
        )}
      >
        {value ? "Yes" : "No"}
      </span>
    );
  }
  if (typeof value === "number") {
    // Preserve decimals; use locale formatting for thousands separator
    const formatted = Number.isInteger(value)
      ? value.toLocaleString()
      : value.toLocaleString(undefined, { maximumFractionDigits: 6 });
    return <span className="font-mono text-xs">{formatted}</span>;
  }
  if (typeof value === "string") {
    if (looksLikeUrl(value)) {
      return (
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary underline break-all hover:opacity-80"
        >
          {value}
        </a>
      );
    }
    if (looksLikeDate(value)) {
      const date = new Date(value);
      return (
        <span title={value}>
          {date.toLocaleString([], {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      );
    }
    return <span className="break-words">{value}</span>;
  }
  // Fallback for anything else (shouldn't reach here for primitives)
  return <span className="font-mono text-xs">{String(value)}</span>;
}

/** Convert a snake_case / camelCase key to a human-readable label. */
function humaniseKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface FieldValueProps {
  value: unknown;
  depth?: number;
}

/**
 * Recursively render a field value.
 * - Primitives → `formatPrimitive`
 * - Arrays → bulleted list; objects inside arrays get nested cards
 * - Objects → nested key-value table (up to MAX_DEPTH)
 */
function FieldValue({ value, depth = 0 }: FieldValueProps) {
  if (value === null || value === undefined || typeof value !== "object") {
    return <>{formatPrimitive(value)}</>;
  }

  // Depth cap: fall back to raw JSON to avoid stack overflow on deep nesting.
  if (depth >= MAX_DEPTH) {
    return (
      <pre className="font-mono text-xs whitespace-pre-wrap break-all">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-muted-foreground text-xs">[ empty list ]</span>;
    }
    return (
      <ul className="list-disc list-inside space-y-1 pl-2">
        {value.map((item, idx) => (
          <li key={idx} className="text-sm">
            <FieldValue value={item} depth={depth + 1} />
          </li>
        ))}
      </ul>
    );
  }

  // Plain object — render as nested table
  return <StructuredTable data={value as Record<string, unknown>} depth={depth + 1} />;
}

// ---------------------------------------------------------------------------
// StructuredTable — key/value table, optionally nested
// ---------------------------------------------------------------------------

interface StructuredTableProps {
  data: Record<string, unknown>;
  depth?: number;
}

function StructuredTable({ data, depth = 0 }: StructuredTableProps) {
  const entries = Object.entries(data);
  if (entries.length === 0) {
    return <span className="text-muted-foreground text-xs">(empty)</span>;
  }

  return (
    <table
      className={cn(
        "w-full text-sm border-collapse",
        depth > 0 && "mt-1"
      )}
      // Only attach testid at root depth to avoid duplicate testid issues in queries
      {...(depth === 0 ? { "data-testid": "structured-table" } : {})}
    >
      <tbody>
        {entries.map(([key, val]) => {
          const isComplex =
            val !== null &&
            val !== undefined &&
            typeof val === "object";
          return (
            <tr
              key={key}
              className="border-b border-border/40 last:border-0 align-top"
            >
              <td className="pr-3 py-1.5 text-xs font-medium text-muted-foreground whitespace-nowrap w-1/3">
                {humaniseKey(key)}
              </td>
              <td className={cn("py-1.5 text-sm", isComplex && "pt-1")}>
                <FieldValue value={val} depth={depth} />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
// StructuredResponseCard — public component
// ---------------------------------------------------------------------------

export interface StructuredResponseCardProps {
  /** The structured data object to render. */
  data: Record<string, unknown>;
  /** Optional extra class names on the card wrapper. */
  className?: string;
}

/**
 * StructuredResponseCard renders a structured agent response as a formatted
 * card rather than a raw JSON blob.
 *
 * Rendering rules:
 * - Flat objects → key-value table
 * - Nested objects → nested key-value tables (recursive, capped at MAX_DEPTH)
 * - Arrays → bulleted list
 * - Field types: numbers (locale-formatted), dates (human-readable),
 *   URLs (clickable), booleans (Yes/No badge), null (em-dash)
 * - Unknown / un-parseable schemas → formatted JSON fallback
 */
export function StructuredResponseCard({
  data,
  className,
}: StructuredResponseCardProps) {
  // Safety: if data is not a plain object, fall back to formatted JSON.
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    return (
      <div
        className={cn(
          "rounded-xl border border-border bg-muted/40 p-3",
          className
        )}
        data-testid="structured-response-card"
      >
        <pre className="text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all">
          {JSON.stringify(data, null, 2)}
        </pre>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-muted/40 px-3 py-2 text-sm",
        className
      )}
      data-testid="structured-response-card"
    >
      <div className="mb-1.5 text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
        Structured Response
      </div>
      <StructuredTable data={data} depth={0} />
    </div>
  );
}
