"use client";

import * as React from "react";
import {
  Terminal,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ToolCall } from "@/lib/types";

export interface CodeExecutionCardProps {
  /** The tool call to display (must be an execute-type tool call) */
  toolCall: ToolCall;
  /** Additional class names */
  className?: string;
}

/** Maximum characters shown before the output section becomes scrollable */
const OUTPUT_COLLAPSE_THRESHOLD = 500;

/**
 * CodeExecutionCard — displays code execution results in a terminal-like style.
 *
 * Features:
 * - Dark terminal background with monospace font
 * - stdout and stderr displayed in separate sections (stderr in red)
 * - Exit code badge with success (green) / failure (red) indicator
 * - Collapsible output for long content
 * - Spinner while the execution is still running
 */
export function CodeExecutionCard({
  toolCall,
  className,
}: CodeExecutionCardProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  // Guard so the auto-expand fires only once per mount — prevents re-expansion
  // of an output the user has manually collapsed when the parent re-renders
  // (e.g. a new SSE token arrives and creates a new `execution` object reference).
  const autoExpandedRef = React.useRef(false);

  const { execution } = toolCall;
  const status = toolCall.status ?? "completed";
  const isRunning = status === "running" || status === "pending";

  const isLongOutput =
    execution &&
    (execution.stdout.length + execution.stderr.length >
      OUTPUT_COLLAPSE_THRESHOLD);

  // Auto-expand once when execution arrives and output is within threshold.
  // Includes the empty-output case so users don't need to click to see "(no output)".
  React.useEffect(() => {
    if (!autoExpandedRef.current && execution && !isLongOutput) {
      autoExpandedRef.current = true;
      setIsExpanded(true);
    }
  }, [execution, isLongOutput]);

  const exitSuccess = execution && execution.exitCode === 0;
  const exitUnknown = execution && execution.exitCode === null;

  return (
    <div
      className={cn(
        "rounded-lg border border-border overflow-hidden text-sm font-mono",
        className
      )}
      data-testid="code-execution-card"
    >
      {/* Header — always visible */}
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        className="flex w-full items-center gap-2 px-3 py-2 bg-zinc-900 hover:bg-zinc-800 transition-colors text-left"
        aria-expanded={isExpanded}
        aria-label={`Code execution: ${toolCall.name}`}
      >
        <Terminal className="h-3.5 w-3.5 text-zinc-400 shrink-0" />
        <span className="font-medium text-xs truncate flex-1 text-zinc-200">
          {toolCall.name}
        </span>

        {/* Status indicator */}
        {isRunning ? (
          <Loader2
            className="h-3.5 w-3.5 shrink-0 text-zinc-400 animate-spin"
            aria-label="Running"
          />
        ) : execution != null ? (
          <span
            className={cn(
              "inline-flex items-center gap-1 text-[10px] font-sans font-medium rounded px-1.5 py-0.5 shrink-0",
              exitUnknown
                ? "bg-zinc-800 text-zinc-400"
                : exitSuccess
                  ? "bg-green-900/60 text-green-400"
                  : "bg-red-900/60 text-red-400"
            )}
            aria-label={
              exitUnknown ? "Exit code unknown" : `Exit code ${execution.exitCode}`
            }
            data-testid="exit-code-badge"
          >
            {exitUnknown ? (
              <HelpCircle className="h-3 w-3" />
            ) : exitSuccess ? (
              <CheckCircle2 className="h-3 w-3" />
            ) : (
              <XCircle className="h-3 w-3" />
            )}
            {exitUnknown ? "exit ?" : `exit ${execution.exitCode}`}
          </span>
        ) : null}

        {/* Expand/collapse chevron */}
        {isExpanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-zinc-500 shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-zinc-500 shrink-0" />
        )}
      </button>

      {/* Expandable output area */}
      {isExpanded && (
        <div className="bg-zinc-950 border-t border-zinc-800">
          {isRunning && !execution && (
            <p className="px-3 py-2 text-xs text-zinc-400 italic">
              Running…
            </p>
          )}

          {execution && (
            <>
              {/* stdout */}
              {execution.stdout.length > 0 && (
                <div data-testid="stdout-section">
                  <p className="px-3 pt-2 text-[10px] font-sans font-medium uppercase tracking-wider text-zinc-500">
                    stdout
                  </p>
                  <pre
                    className={cn(
                      "px-3 py-2 text-xs text-zinc-100 whitespace-pre-wrap break-all overflow-x-auto",
                      isLongOutput && "max-h-[300px] overflow-y-auto custom-scrollbar"
                    )}
                  >
                    {execution.stdout}
                  </pre>
                </div>
              )}

              {/* stderr */}
              {execution.stderr.length > 0 && (
                <div
                  data-testid="stderr-section"
                  className={
                    execution.stdout.length > 0
                      ? "border-t border-zinc-800"
                      : undefined
                  }
                >
                  <p className="px-3 pt-2 text-[10px] font-sans font-medium uppercase tracking-wider text-red-500">
                    stderr
                  </p>
                  <pre
                    className={cn(
                      "px-3 py-2 text-xs text-red-300 whitespace-pre-wrap break-all overflow-x-auto",
                      isLongOutput && "max-h-[300px] overflow-y-auto custom-scrollbar"
                    )}
                  >
                    {execution.stderr}
                  </pre>
                </div>
              )}

              {/* No output at all */}
              {execution.stdout.length === 0 &&
                execution.stderr.length === 0 && (
                  <p className="px-3 py-2 text-xs text-zinc-500 italic">
                    (no output)
                  </p>
                )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
