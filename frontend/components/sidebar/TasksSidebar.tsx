"use client";

import * as React from "react";
import {
  CheckCircle2,
  Circle,
  Loader2,
  AlertCircle,
  ShieldAlert,
  ListTodo,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/utils";
import type { AgentTask } from "@/lib/types";

export interface TasksSidebarProps {
  /** List of agent tasks to display */
  tasks: AgentTask[];
  /** Additional class names */
  className?: string;
}

const statusConfig: Record<
  AgentTask["status"],
  { icon: React.ElementType; color: string; label: string }
> = {
  planned: {
    icon: Circle,
    color: "text-muted-foreground",
    label: "Planned",
  },
  in_progress: {
    icon: Loader2,
    color: "text-primary",
    label: "In Progress",
  },
  completed: {
    icon: CheckCircle2,
    color: "text-green-600",
    label: "Completed",
  },
  failed: {
    icon: AlertCircle,
    color: "text-destructive",
    label: "Failed",
  },
  awaiting_approval: {
    icon: ShieldAlert,
    color: "text-amber-500",
    label: "Awaiting Approval",
  },
};

/**
 * TasksSidebar — displays the agent's planned and completed tasks.
 *
 * Shows a vertical timeline-style list of tasks with status indicators,
 * tool names, and timestamps. Tasks requiring approval are highlighted.
 */
export function TasksSidebar({ tasks, className }: TasksSidebarProps) {
  const pendingCount = tasks.filter(
    (t) => t.status === "planned" || t.status === "in_progress" || t.status === "awaiting_approval"
  ).length;
  const completedCount = tasks.filter((t) => t.status === "completed").length;

  return (
    <aside
      className={cn(
        "flex flex-col h-full w-72 border-l border-border bg-background",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <ListTodo className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold">Agent Tasks</h2>
        <span className="ml-auto text-xs text-muted-foreground">
          {completedCount}/{tasks.length}
        </span>
      </div>

      {/* Progress bar */}
      {tasks.length > 0 && (
        <div className="px-4 py-2 border-b border-border">
          <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
            <div
              className="h-full bg-green-600 rounded-full transition-all duration-500"
              style={{
                width: `${tasks.length > 0 ? (completedCount / tasks.length) * 100 : 0}%`,
              }}
            />
          </div>
          <p className="text-[10px] text-muted-foreground mt-1">
            {pendingCount > 0
              ? `${pendingCount} task${pendingCount !== 1 ? "s" : ""} remaining`
              : "All tasks completed"}
          </p>
        </div>
      )}

      {/* Task list */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
        {tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <ListTodo className="h-8 w-8 mb-2 opacity-50" />
            <p className="text-xs">No tasks yet</p>
            <p className="text-[10px] mt-1">
              Tasks will appear as the agent plans actions
            </p>
          </div>
        ) : (
          tasks.map((task) => <TaskItem key={task.id} task={task} />)
        )}
      </div>
    </aside>
  );
}

function TaskItem({ task }: { task: AgentTask }) {
  const config = statusConfig[task.status];
  const StatusIcon = config.icon;
  const isAnimated = task.status === "in_progress";

  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-lg px-2 py-2 text-sm transition-colors",
        task.status === "awaiting_approval" && "bg-amber-500/10 border border-amber-500/20",
        task.status === "in_progress" && "bg-primary/5",
      )}
    >
      <StatusIcon
        className={cn(
          "h-4 w-4 shrink-0 mt-0.5",
          config.color,
          isAnimated && "animate-spin"
        )}
      />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium truncate">{task.name}</p>
        {task.description && (
          <p className="text-[10px] text-muted-foreground mt-0.5 line-clamp-2">
            {task.description}
          </p>
        )}
        {task.toolName && (
          <span className="inline-block text-[10px] text-muted-foreground bg-secondary rounded px-1 mt-1">
            {task.toolName}
          </span>
        )}
        <p className="text-[10px] text-muted-foreground mt-0.5">
          {task.completedAt
            ? formatRelativeTime(task.completedAt)
            : formatRelativeTime(task.createdAt)}
        </p>
      </div>
    </div>
  );
}
