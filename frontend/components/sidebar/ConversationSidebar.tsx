"use client";

import * as React from "react";
import {
  MessageSquare,
  Plus,
  Trash2,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/utils";
import { config } from "@/lib/config";
import { apiFetch } from "@/lib/api";

/** Thread summary returned by GET /threads */
export interface ThreadSummary {
  id: string;
  title: string | null;
  assistant_id: string;
  metadata: Record<string, unknown>;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

interface ThreadListResponse {
  threads: ThreadSummary[];
  total: number;
  offset: number;
  limit: number;
}

export interface ConversationSidebarProps {
  /** Currently selected thread ID */
  currentThreadId: string | null;
  /** Callback when user selects a thread */
  onSelectThread: (threadId: string) => void;
  /** Callback when user starts a new conversation */
  onNewConversation: () => void;
  /** Additional class names */
  className?: string;
}

/**
 * ConversationSidebar — displays a list of past conversation threads
 * and allows users to switch between them or start a new conversation.
 */
export function ConversationSidebar({
  currentThreadId,
  onSelectThread,
  onNewConversation,
  className,
}: ConversationSidebarProps) {
  const [threads, setThreads] = React.useState<ThreadSummary[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const fetchThreads = React.useCallback(async () => {
    try {
      setError(null);
      const response = await apiFetch(
        `${config.apiUrl}/threads?limit=50`
      );
      if (!response.ok) {
        throw new Error(`Failed to load threads: ${response.statusText}`);
      }
      const data: ThreadListResponse = await response.json();
      setThreads(data.threads.filter((t) => !t.is_deleted));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load threads");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch threads on mount and when currentThreadId changes (new thread may have been created)
  React.useEffect(() => {
    fetchThreads();
  }, [fetchThreads, currentThreadId]);

  const handleDelete = React.useCallback(
    async (e: React.MouseEvent, threadId: string) => {
      e.stopPropagation();
      try {
        const response = await apiFetch(
          `${config.apiUrl}/threads/${threadId}`,
          { method: "DELETE" }
        );
        if (!response.ok) {
          throw new Error("Failed to delete thread");
        }
        setThreads((prev) => prev.filter((t) => t.id !== threadId));
        // If we deleted the current thread, start a new conversation
        if (threadId === currentThreadId) {
          onNewConversation();
        }
      } catch (err) {
        console.error("Failed to delete thread:", err);
      }
    },
    [currentThreadId, onNewConversation]
  );

  return (
    <aside
      className={cn(
        "flex flex-col h-full w-64 border-r border-border bg-background",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <MessageSquare className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold">Conversations</h2>
        <span className="ml-auto text-xs text-muted-foreground">
          {threads.length}
        </span>
      </div>

      {/* New conversation button */}
      <div className="px-3 py-2 border-b border-border">
        <button
          onClick={onNewConversation}
          className={cn(
            "flex items-center gap-2 w-full rounded-lg px-3 py-2 text-sm",
            "bg-primary text-primary-foreground hover:bg-primary/90",
            "transition-colors"
          )}
        >
          <Plus className="h-4 w-4" />
          New conversation
        </button>
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin mb-2" />
            <p className="text-xs">Loading conversations...</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
            <p className="text-xs text-destructive">{error}</p>
            <button
              onClick={fetchThreads}
              className="text-xs text-primary hover:underline mt-2"
            >
              Retry
            </button>
          </div>
        ) : threads.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
            <MessageSquare className="h-8 w-8 mb-2 opacity-50" />
            <p className="text-xs">No conversations yet</p>
            <p className="text-[10px] mt-1">
              Start a new conversation to begin
            </p>
          </div>
        ) : (
          threads.map((thread) => (
            <ThreadItem
              key={thread.id}
              thread={thread}
              isActive={thread.id === currentThreadId}
              onSelect={() => onSelectThread(thread.id)}
              onDelete={(e) => handleDelete(e, thread.id)}
            />
          ))
        )}
      </div>
    </aside>
  );
}

function ThreadItem({
  thread,
  isActive,
  onSelect,
  onDelete,
}: {
  thread: ThreadSummary;
  isActive: boolean;
  onSelect: () => void;
  onDelete: (e: React.MouseEvent) => void;
}) {
  const title = thread.title || "Untitled conversation";

  return (
    <button
      onClick={onSelect}
      className={cn(
        "flex items-start gap-2 rounded-lg px-3 py-2 text-sm transition-colors w-full text-left group",
        isActive
          ? "bg-primary/10 text-primary"
          : "hover:bg-muted text-foreground"
      )}
    >
      <MessageSquare
        className={cn(
          "h-4 w-4 shrink-0 mt-0.5",
          isActive ? "text-primary" : "text-muted-foreground"
        )}
      />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium truncate">{title}</p>
        <p className="text-[10px] text-muted-foreground mt-0.5">
          {formatRelativeTime(thread.updated_at)}
        </p>
      </div>
      <button
        onClick={onDelete}
        className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:text-destructive shrink-0"
        title="Delete conversation"
      >
        <Trash2 className="h-3 w-3" />
      </button>
    </button>
  );
}
