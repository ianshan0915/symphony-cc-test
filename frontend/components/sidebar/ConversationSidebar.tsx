"use client";

import * as React from "react";
import {
  MessageSquare,
  Plus,
  Trash2,
  Loader2,
  Search,
  Pencil,
  Check,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/utils";
import { config } from "@/lib/config";
import { apiFetch } from "@/lib/api";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/Dialog";

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
  const [searchQuery, setSearchQuery] = React.useState("");
  const [deleteTarget, setDeleteTarget] = React.useState<string | null>(null);
  const [editingThreadId, setEditingThreadId] = React.useState<string | null>(null);
  const [editTitle, setEditTitle] = React.useState("");

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

  const handleDeleteClick = React.useCallback(
    (e: React.MouseEvent, threadId: string) => {
      e.stopPropagation();
      setDeleteTarget(threadId);
    },
    []
  );

  const handleConfirmDelete = React.useCallback(async () => {
    if (!deleteTarget) return;
    try {
      const response = await apiFetch(
        `${config.apiUrl}/threads/${deleteTarget}`,
        { method: "DELETE" }
      );
      if (!response.ok) {
        throw new Error("Failed to delete thread");
      }
      setThreads((prev) => prev.filter((t) => t.id !== deleteTarget));
      // If we deleted the current thread, start a new conversation
      if (deleteTarget === currentThreadId) {
        onNewConversation();
      }
    } catch (err) {
      console.error("Failed to delete thread:", err);
    } finally {
      setDeleteTarget(null);
    }
  }, [deleteTarget, currentThreadId, onNewConversation]);

  const handleRenameThread = React.useCallback(
    async (threadId: string, newTitle: string) => {
      const trimmed = newTitle.trim();
      if (!trimmed) {
        setEditingThreadId(null);
        return;
      }
      try {
        const response = await apiFetch(
          `${config.apiUrl}/threads/${threadId}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: trimmed }),
          }
        );
        if (response.ok) {
          setThreads((prev) =>
            prev.map((t) => (t.id === threadId ? { ...t, title: trimmed } : t))
          );
        }
      } catch (err) {
        console.error("Failed to rename thread:", err);
      } finally {
        setEditingThreadId(null);
      }
    },
    []
  );

  // Filter threads by search query
  const filteredThreads = React.useMemo(() => {
    if (!searchQuery.trim()) return threads;
    const q = searchQuery.toLowerCase();
    return threads.filter(
      (t) =>
        (t.title ?? "").toLowerCase().includes(q) ||
        t.id.toLowerCase().includes(q)
    );
  }, [threads, searchQuery]);

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
      <div className="px-3 py-2 border-b border-border space-y-2">
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
        {/* Search filter (P3-11) */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-md border border-border bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
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
        ) : filteredThreads.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
            <MessageSquare className="h-8 w-8 mb-2 opacity-50" />
            <p className="text-xs">
              {searchQuery ? "No matching conversations" : "No conversations yet"}
            </p>
            {!searchQuery && (
              <p className="text-[10px] mt-1">
                Start a new conversation to begin
              </p>
            )}
          </div>
        ) : (
          filteredThreads.map((thread) => (
            <ThreadItem
              key={thread.id}
              thread={thread}
              isActive={thread.id === currentThreadId}
              isEditing={editingThreadId === thread.id}
              editTitle={editTitle}
              onEditTitleChange={setEditTitle}
              onSelect={() => onSelectThread(thread.id)}
              onDelete={(e) => handleDeleteClick(e, thread.id)}
              onStartRename={() => {
                setEditingThreadId(thread.id);
                setEditTitle(thread.title || "");
              }}
              onConfirmRename={() => handleRenameThread(thread.id, editTitle)}
              onCancelRename={() => setEditingThreadId(null)}
            />
          ))
        )}
      </div>

      {/* Delete confirmation dialog (P1-4) */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete conversation?</DialogTitle>
            <DialogDescription>
              This will permanently delete this conversation and all its messages.
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <button
              onClick={() => setDeleteTarget(null)}
              className="px-4 py-2 text-sm rounded-md border border-border hover:bg-muted transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirmDelete}
              className="px-4 py-2 text-sm rounded-md bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors"
            >
              Delete
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  );
}

function ThreadItem({
  thread,
  isActive,
  isEditing,
  editTitle,
  onEditTitleChange,
  onSelect,
  onDelete,
  onStartRename,
  onConfirmRename,
  onCancelRename,
}: {
  thread: ThreadSummary;
  isActive: boolean;
  isEditing: boolean;
  editTitle: string;
  onEditTitleChange: (value: string) => void;
  onSelect: () => void;
  onDelete: (e: React.MouseEvent) => void;
  onStartRename: () => void;
  onConfirmRename: () => void;
  onCancelRename: () => void;
}) {
  const title = thread.title || "Untitled conversation";

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(); } }}
      className={cn(
        "flex items-start gap-2 rounded-lg px-3 py-2 text-sm transition-colors w-full text-left group cursor-pointer",
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
        {isEditing ? (
          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
            <input
              type="text"
              value={editTitle}
              onChange={(e) => onEditTitleChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") onConfirmRename();
                if (e.key === "Escape") onCancelRename();
              }}
              autoFocus
              className="w-full text-xs bg-background border border-border rounded px-1 py-0.5 focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <button
              onClick={(e) => { e.stopPropagation(); onConfirmRename(); }}
              className="p-0.5 hover:text-primary shrink-0"
              title="Save"
            >
              <Check className="h-3 w-3" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onCancelRename(); }}
              className="p-0.5 hover:text-destructive shrink-0"
              title="Cancel"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        ) : (
          <>
            <p className="text-xs font-medium truncate">{title}</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              {formatRelativeTime(thread.updated_at)}
            </p>
          </>
        )}
      </div>
      {!isEditing && (
        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
          <button
            onClick={(e) => { e.stopPropagation(); onStartRename(); }}
            className="p-1 hover:text-primary"
            title="Rename conversation"
          >
            <Pencil className="h-3 w-3" />
          </button>
          <button
            onClick={onDelete}
            className="p-1 hover:text-destructive"
            title="Delete conversation"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
}
