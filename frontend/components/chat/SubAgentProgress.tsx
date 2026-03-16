"use client";

import * as React from "react";
import {
  Bot,
  Search,
  Code2,
  Pen,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  Cpu,
  Network,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Status of a sub-agent execution */
export type SubAgentStatus =
  | "running"
  | "completed"
  | "error"
  | "waiting";

/** Represents a single sub-agent spawned by the main agent */
export interface SubAgent {
  /** Unique identifier */
  id: string;
  /** Human-readable label for this sub-agent (e.g. "Explore agent", "Plan agent") */
  name: string;
  /** The type / role of the sub-agent */
  type: string;
  /** Current execution status */
  status: SubAgentStatus;
  /** Short description of what this sub-agent is doing */
  description?: string;
  /** Streaming progress text (last token chunk, etc.) */
  progressText?: string;
  /** When the sub-agent was spawned */
  startedAt: string;
  /** When the sub-agent finished (if applicable) */
  completedAt?: string;
}

export interface SubAgentProgressProps {
  /** List of active / recent sub-agents */
  subAgents: SubAgent[];
  /** Additional class names */
  className?: string;
}

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

const statusConfig: Record<
  SubAgentStatus,
  { icon: React.ElementType; color: string; label: string; bgColor: string }
> = {
  running: {
    icon: Loader2,
    color: "text-blue-500",
    label: "Running",
    bgColor: "bg-blue-500/10",
  },
  completed: {
    icon: CheckCircle2,
    color: "text-green-600",
    label: "Completed",
    bgColor: "bg-green-600/10",
  },
  error: {
    icon: AlertCircle,
    color: "text-destructive",
    label: "Error",
    bgColor: "bg-destructive/10",
  },
  waiting: {
    icon: Cpu,
    color: "text-amber-500",
    label: "Waiting",
    bgColor: "bg-amber-500/10",
  },
};

// ---------------------------------------------------------------------------
// Type-specific icon mapping
// ---------------------------------------------------------------------------

/** Maps known subagent type names to representative icons. */
const typeIconMap: Record<string, React.ElementType> = {
  researcher: Search,
  research: Search,
  coder: Code2,
  code: Code2,
  writer: Pen,
  write: Pen,
};

/** Returns the icon for a given agent type, falling back to Bot. */
function getTypeIcon(agentType: string): React.ElementType {
  return typeIconMap[agentType?.toLowerCase()] ?? Bot;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * SubAgentProgress — shows active sub-agents, their status, and streaming
 * progress inline within the chat.
 *
 * When no sub-agents are active, the component renders nothing (graceful
 * fallback). Active sub-agents are visually distinguished from the main agent
 * with a distinct indented card style and a connecting "network" icon.
 */
export function SubAgentProgress({
  subAgents,
  className,
}: SubAgentProgressProps) {
  const [expandedIds, setExpandedIds] = React.useState<Set<string>>(new Set());

  // Auto-expand running agents
  React.useEffect(() => {
    const running = subAgents
      .filter((a) => a.status === "running")
      .map((a) => a.id);
    if (running.length > 0) {
      setExpandedIds((prev) => {
        const next = new Set(prev);
        running.forEach((id) => next.add(id));
        return next;
      });
    }
  }, [subAgents]);

  // Graceful fallback — nothing to show
  if (subAgents.length === 0) return null;

  const activeCount = subAgents.filter((a) => a.status === "running" || a.status === "waiting").length;

  function toggleExpand(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-border/60 bg-card/50 backdrop-blur-sm",
        "mx-2 mb-2 overflow-hidden",
        className,
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border/40">
        <Network className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs font-semibold text-muted-foreground">
          Sub-Agents
        </span>
        {activeCount > 0 && (
          <span className="ml-auto flex items-center gap-1 text-[10px] font-medium text-blue-500">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
            {activeCount} active
          </span>
        )}
        {activeCount === 0 && (
          <span className="ml-auto text-[10px] text-muted-foreground">
            {subAgents.length} completed
          </span>
        )}
      </div>

      {/* Sub-agent list */}
      <div className="divide-y divide-border/30">
        {subAgents.map((agent) => {
          const cfg = statusConfig[agent.status];
          const StatusIcon = cfg.icon;
          const isExpanded = expandedIds.has(agent.id);
          const isRunning = agent.status === "running";

          return (
            <div key={agent.id} className="group">
              {/* Row header */}
              <button
                type="button"
                onClick={() => toggleExpand(agent.id)}
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-2 text-left",
                  "transition-colors hover:bg-accent/40",
                )}
              >
                {/* Status icon */}
                <StatusIcon
                  className={cn(
                    "h-3.5 w-3.5 shrink-0",
                    cfg.color,
                    isRunning && "animate-spin",
                  )}
                />

                {/* Agent info */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    {React.createElement(getTypeIcon(agent.type), {
                      className: "h-3 w-3 text-muted-foreground shrink-0",
                    })}
                    <span className="text-xs font-medium truncate">
                      {agent.name}
                    </span>
                    <span
                      className={cn(
                        "text-[10px] rounded px-1 py-0.5 font-medium",
                        cfg.bgColor,
                        cfg.color,
                      )}
                    >
                      {cfg.label}
                    </span>
                  </div>
                </div>

                {/* Timing */}
                <span className="text-[10px] text-muted-foreground shrink-0">
                  {agent.completedAt
                    ? formatRelativeTime(agent.completedAt)
                    : formatRelativeTime(agent.startedAt)}
                </span>

                <ChevronDown
                  className={cn(
                    "h-3 w-3 text-muted-foreground transition-transform shrink-0",
                    isExpanded && "rotate-180",
                  )}
                />
              </button>

              {/* Expanded details */}
              {isExpanded && (
                <div className="px-3 pb-2 pl-9">
                  {agent.description && (
                    <p className="text-[11px] text-muted-foreground mb-1">
                      {agent.description}
                    </p>
                  )}

                  {/* Type badge */}
                  <span className="inline-block text-[10px] text-muted-foreground bg-secondary rounded px-1 py-0.5 mb-1">
                    {agent.type}
                  </span>

                  {/* Streaming progress — visible while running and after completion */}
                  {agent.progressText && (
                    <div className="mt-1.5 rounded bg-secondary/60 px-2 py-1.5">
                      <p className="text-[11px] text-foreground/80 font-mono leading-relaxed line-clamp-4 whitespace-pre-wrap">
                        {agent.progressText}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
