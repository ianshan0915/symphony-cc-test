"use client";

import * as React from "react";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getToolSummary } from "@/lib/toolLabels";
import type { ToolCall } from "@/lib/types";

export interface ToolCallCardProps {
  /** The tool call to display */
  toolCall: ToolCall;
  /** Additional class names */
  className?: string;
}

/** Status icon and color mappings */
const statusConfig: Record<
  NonNullable<ToolCall["status"]>,
  { icon: React.ElementType; color: string }
> = {
  pending: { icon: Loader2, color: "text-muted-foreground" },
  running: { icon: Loader2, color: "text-primary" },
  completed: { icon: CheckCircle2, color: "text-green-600" },
  error: { icon: AlertCircle, color: "text-destructive" },
  awaiting_approval: { icon: Clock, color: "text-amber-500" },
  rejected: { icon: AlertCircle, color: "text-destructive" },
};

/**
 * ToolCallCard — displays a tool invocation with human-readable labels.
 *
 * Collapsed by default. Shows an icon, friendly label, and optional detail.
 * Expandable to show raw arguments and result for power users.
 */
export function ToolCallCard({ toolCall, className }: ToolCallCardProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);

  const status = toolCall.status ?? "completed";
  const StatusIcon = statusConfig[status].icon;
  const statusColor = statusConfig[status].color;
  const isAnimated = status === "running" || status === "pending";

  const { icon, label, detail } = getToolSummary(
    toolCall.name,
    toolCall.args,
    status
  );

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card overflow-hidden text-sm",
        className
      )}
    >
      {/* Header — always visible */}
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        className="flex w-full items-center gap-2 px-3 py-2 hover:bg-accent/50 transition-colors text-left"
        aria-expanded={isExpanded}
        aria-label={`Tool call: ${label}`}
      >
        {/* Tool icon */}
        <span className="text-sm shrink-0" role="img" aria-hidden>
          {icon}
        </span>

        {/* Human-readable label + detail */}
        <span className="flex-1 min-w-0">
          <span className="font-medium text-xs">{label}</span>
          {detail && (
            <span className="text-xs text-muted-foreground ml-1.5">
              · {detail}
            </span>
          )}
        </span>

        {/* Status icon */}
        <StatusIcon
          className={cn(
            "h-3.5 w-3.5 shrink-0",
            statusColor,
            isAnimated && "animate-spin"
          )}
        />

        {/* Expand/collapse chevron */}
        {isExpanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        )}
      </button>

      {/* Expandable details */}
      {isExpanded && (
        <div className="border-t border-border px-3 py-2 space-y-2">
          {/* Arguments */}
          {toolCall.args && Object.keys(toolCall.args).length > 0 && (
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1">
                Arguments
              </p>
              <pre className="text-xs bg-secondary rounded-md p-2 overflow-x-auto whitespace-pre-wrap break-all">
                {JSON.stringify(toolCall.args, null, 2)}
              </pre>
            </div>
          )}

          {/* Result */}
          {toolCall.result !== undefined && (
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1">
                Result
              </p>
              <pre className="text-xs bg-secondary rounded-md p-2 overflow-x-auto whitespace-pre-wrap break-all max-h-[200px] overflow-y-auto custom-scrollbar">
                {toolCall.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
