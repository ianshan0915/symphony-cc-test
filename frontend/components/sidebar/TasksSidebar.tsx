"use client";

import * as React from "react";
import {
  CheckCircle2,
  Circle,
  Loader2,
  AlertCircle,
  ShieldAlert,
  ListTodo,
  ClipboardList,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/utils";
import type { AgentTask, TodoItem } from "@/lib/types";

export interface TasksSidebarProps {
  /** List of agent tasks derived from tool calls */
  tasks: AgentTask[];
  /** Structured planning todos from the agent's write_todos tool */
  todos?: TodoItem[];
  /** Additional class names */
  className?: string;
}

const taskStatusConfig: Record<
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

const todoStatusConfig: Record<
  TodoItem["status"],
  { icon: React.ElementType; color: string; label: string }
> = {
  pending: {
    icon: Circle,
    color: "text-muted-foreground",
    label: "Pending",
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
};

const priorityConfig: Record<
  NonNullable<TodoItem["priority"]>,
  { label: string; color: string }
> = {
  high: { label: "High", color: "text-red-500 bg-red-500/10" },
  medium: { label: "Med", color: "text-amber-500 bg-amber-500/10" },
  low: { label: "Low", color: "text-muted-foreground bg-secondary" },
};

/**
 * TasksSidebar — displays the agent's structured plan and tool-call tasks.
 *
 * When `todos` are present (from the agent's write_todos planning tool), they
 * are shown prominently as the agent's plan with real-time status transitions.
 * Tool-call tasks derived from SSE events are displayed below as a secondary
 * section, so users can see both what the agent intends to do and what it has
 * already executed.
 */
export function TasksSidebar({ tasks, todos = [], className }: TasksSidebarProps) {
  const hasTodos = todos.length > 0;

  // Progress metrics — prefer todos when present
  const todoCompletedCount = todos.filter((t) => t.status === "completed").length;
  const taskCompletedCount = tasks.filter((t) => t.status === "completed").length;

  const progressNumerator = hasTodos ? todoCompletedCount : taskCompletedCount;
  const progressDenominator = hasTodos ? todos.length : tasks.length;
  const progressPercent =
    progressDenominator > 0
      ? (progressNumerator / progressDenominator) * 100
      : 0;

  const todoPendingCount = todos.filter(
    (t) => t.status === "pending" || t.status === "in_progress"
  ).length;
  const taskPendingCount = tasks.filter(
    (t) =>
      t.status === "planned" ||
      t.status === "in_progress" ||
      t.status === "awaiting_approval"
  ).length;

  const pendingCount = hasTodos ? todoPendingCount : taskPendingCount;
  const isEmpty = todos.length === 0 && tasks.length === 0;

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
          {progressNumerator}/{progressDenominator}
        </span>
      </div>

      {/* Progress bar */}
      {!isEmpty && (
        <div className="px-4 py-2 border-b border-border">
          <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
            <div
              className="h-full bg-green-600 rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <p className="text-[10px] text-muted-foreground mt-1">
            {pendingCount > 0
              ? `${pendingCount} task${pendingCount !== 1 ? "s" : ""} remaining`
              : "All tasks completed"}
          </p>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-3">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <ListTodo className="h-8 w-8 mb-2 opacity-50" />
            <p className="text-xs">No tasks yet</p>
            <p className="text-[10px] mt-1">
              Tasks will appear as the agent plans actions
            </p>
          </div>
        ) : (
          <>
            {/* Structured plan (todos from write_todos) */}
            {hasTodos && (
              <section aria-label="Agent plan">
                <div className="flex items-center gap-1.5 px-2 mb-1">
                  <ClipboardList className="h-3 w-3 text-muted-foreground" />
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Agent Plan
                  </p>
                </div>
                <div className="space-y-0.5">
                  {todos.map((todo, index) => (
                    <TodoItemRow key={todo.id} todo={todo} index={index} />
                  ))}
                </div>
              </section>
            )}

            {/* Tool-call tasks */}
            {tasks.length > 0 && (
              <section aria-label="Tool calls">
                {hasTodos && (
                  <div className="flex items-center gap-1.5 px-2 mb-1 mt-2">
                    <ListTodo className="h-3 w-3 text-muted-foreground" />
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Tool Calls
                    </p>
                  </div>
                )}
                <div className="space-y-0.5">
                  {tasks.map((task) => (
                    <TaskItem key={task.id} task={task} />
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </aside>
  );
}

/** Renders a single structured todo item from the agent's planning tool. */
function TodoItemRow({ todo, index }: { todo: TodoItem; index: number }) {
  const config = todoStatusConfig[todo.status];
  const StatusIcon = config.icon;
  const isAnimated = todo.status === "in_progress";

  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-lg px-2 py-1.5 text-sm transition-colors",
        todo.status === "in_progress" && "bg-primary/5",
        todo.status === "completed" && "opacity-70",
      )}
      role="listitem"
      aria-label={`Todo: ${todo.content}`}
    >
      {/* Step number / status icon */}
      <div className="relative shrink-0 mt-0.5">
        <StatusIcon
          className={cn(
            "h-4 w-4",
            config.color,
            isAnimated && "animate-spin"
          )}
          aria-label={config.label}
        />
        <span className="sr-only">{config.label}</span>
      </div>

      <div className="min-w-0 flex-1">
        <p
          className={cn(
            "text-xs font-medium leading-snug",
            todo.status === "completed" && "line-through text-muted-foreground"
          )}
        >
          <span className="text-[10px] text-muted-foreground mr-1 font-normal">
            {index + 1}.
          </span>
          {todo.content}
        </p>

        {todo.priority && (
          <span
            className={cn(
              "inline-block text-[9px] font-medium rounded px-1 mt-0.5",
              priorityConfig[todo.priority].color
            )}
          >
            {priorityConfig[todo.priority].label}
          </span>
        )}
      </div>
    </div>
  );
}

/** Renders a single tool-call task (existing behaviour, unchanged). */
function TaskItem({ task }: { task: AgentTask }) {
  const config = taskStatusConfig[task.status];
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
