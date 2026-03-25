"use client";

import * as React from "react";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { groupToolCounts, getToolSummary } from "@/lib/toolLabels";
import { ToolCallCard } from "./ToolCallCard";
import { CodeExecutionCard } from "./CodeExecutionCard";
import type { ToolCall } from "@/lib/types";

export interface ToolCallGroupProps {
  /** The grouped tool calls to display */
  toolCalls: ToolCall[];
  /** Additional class names */
  className?: string;
}

/**
 * ToolCallGroup — groups multiple consecutive tool calls into a single
 * collapsible summary card. Reduces visual clutter when the agent makes
 * many tool calls in a row.
 *
 * - Collapsed by default, shows summary like "✅ Completed 17 actions · 📄 12 files read · ▶ 5 commands run"
 * - Expanded shows individual ToolCallCard / CodeExecutionCard for each call
 */
export function ToolCallGroup({ toolCalls, className }: ToolCallGroupProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);

  const allCompleted = toolCalls.every(
    (tc) => tc.status === "completed" || tc.status === "rejected" || tc.status === "error"
  );
  const hasRunning = toolCalls.some(
    (tc) => tc.status === "running" || tc.status === "pending"
  );

  const toolNames = toolCalls.map((tc) => tc.name);
  const groups = groupToolCounts(toolNames);

  const totalCount = toolCalls.length;

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card overflow-hidden text-sm",
        className
      )}
    >
      {/* Summary header */}
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        className="flex w-full items-center gap-2 px-3 py-2 hover:bg-accent/50 transition-colors text-left"
        aria-expanded={isExpanded}
        aria-label={`${totalCount} tool calls`}
      >
        {/* Status icon */}
        {hasRunning ? (
          <Loader2 className="h-4 w-4 shrink-0 text-primary animate-spin" />
        ) : (
          <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600" />
        )}

        {/* Summary text */}
        <div className="flex-1 min-w-0">
          <span className="font-medium text-xs">
            {hasRunning
              ? `Running ${totalCount} action${totalCount > 1 ? "s" : ""}…`
              : `Completed ${totalCount} action${totalCount > 1 ? "s" : ""}`}
          </span>
          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
            {groups.map((group) => (
              <span
                key={group.label}
                className="text-[11px] text-muted-foreground"
              >
                {group.icon} {group.count} {group.label}
              </span>
            ))}
          </div>
        </div>

        {/* Expand/collapse chevron */}
        {isExpanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        )}
      </button>

      {/* Expanded details — individual cards */}
      {isExpanded && (
        <div className="border-t border-border p-2 space-y-2">
          {toolCalls.map((toolCall) =>
            toolCall.name === "execute" ? (
              <CodeExecutionCard key={toolCall.id} toolCall={toolCall} />
            ) : (
              <ToolCallCard key={toolCall.id} toolCall={toolCall} />
            )
          )}
        </div>
      )}
    </div>
  );
}
