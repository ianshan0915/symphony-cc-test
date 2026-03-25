"use client";

import * as React from "react";
import { Bot, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { getToolLabel } from "@/lib/toolLabels";

export interface LoadingIndicatorProps {
  /** The name of the currently active tool (if any) */
  currentToolName?: string | null;
  /** Additional class names */
  className?: string;
}

/**
 * LoadingIndicator — contextual loading state shown in the chat stream.
 *
 * Shows what the agent is doing:
 * - "Thinking…" when no tool is active
 * - "🔍 Searching the web…" when a tool is running
 * - Includes an elapsed time counter
 */
export function LoadingIndicator({
  currentToolName,
  className,
}: LoadingIndicatorProps) {
  const [elapsed, setElapsed] = React.useState(0);
  const startTimeRef = React.useRef(0);

  // Reset timer when tool changes
  React.useEffect(() => {
    startTimeRef.current = Date.now();
    setElapsed(0);
  }, [currentToolName]);

  // Update elapsed time every second
  React.useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [currentToolName]);

  const toolConfig = currentToolName ? getToolLabel(currentToolName) : null;
  const icon = toolConfig?.icon ?? "🤔";
  const label = toolConfig?.runningLabel ?? "Thinking…";

  return (
    <div
      className={cn("flex items-center gap-3", className)}
      data-testid="loading-indicator"
    >
      {/* Avatar */}
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary">
        <Bot className="h-4 w-4 text-secondary-foreground" />
      </div>

      {/* Loading card */}
      <div className="rounded-2xl rounded-bl-md bg-card border border-border px-4 py-2.5 flex items-center gap-2">
        {/* Tool icon or thinking emoji */}
        <span className="text-sm" role="img" aria-hidden>
          {icon}
        </span>

        {/* Status label */}
        <span className="text-sm text-foreground/80">{label}</span>

        {/* Elapsed time */}
        {elapsed > 0 && (
          <span className="text-xs text-muted-foreground ml-1">
            ({elapsed}s)
          </span>
        )}

        {/* Pulsing dot to show activity */}
        <Loader2 className="h-3 w-3 text-muted-foreground animate-spin ml-1" />
      </div>
    </div>
  );
}
