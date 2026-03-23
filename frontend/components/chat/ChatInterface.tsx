"use client";

import * as React from "react";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { ApprovalDialog } from "./ApprovalDialog";
import { AssistantSelector } from "./AssistantSelector";
import { SubAgentProgress } from "./SubAgentProgress";
import { TasksSidebar } from "@/components/sidebar/TasksSidebar";
import { FilesSidebar } from "@/components/sidebar/FilesSidebar";
import { ConversationSidebar } from "@/components/sidebar/ConversationSidebar";
import { ArtifactPanel } from "@/components/artifacts/ArtifactPanel";
import { cn } from "@/lib/utils";
import { config } from "@/lib/config";
import { apiFetch } from "@/lib/api";
import { UserMenu } from "@/components/UserMenu";
import { MemoryModal } from "@/components/memory/MemoryModal";
import { BookOpen } from "lucide-react";
import {
  isArtifactProducingTool,
  extractContentFromArgs,
  createArtifactFromToolCall,
  updateArtifactContent,
} from "@/lib/artifacts";
import type {
  Message,
  ApprovalRequest,
  AgentTask,
  Artifact,
  FileOperation,
  SubAgent,
  ThreadDetail,
  TodoItem,
} from "@/lib/types";
import { safeGetItem, safeSetItem, safeRemoveItem } from "@/lib/safeStorage";
import type { AssistantConfig } from "./AssistantSelector";

export interface ChatInterfaceProps {
  /** Additional class names */
  className?: string;
}

/**
 * ChatInterface — the top-level container that composes all chat components.
 *
 * Manages local message state, SSE streaming from the backend, and
 * human-in-the-loop approval flow for sensitive tool calls.
 *
 * Layout: TasksSidebar | Chat | FilesSidebar
 */
const THREAD_ID_KEY = "symphony_current_thread_id";

function getPersistedThreadId(): string | null {
  return safeGetItem(THREAD_ID_KEY);
}

function persistThreadId(threadId: string | null): void {
  if (threadId) {
    safeSetItem(THREAD_ID_KEY, threadId);
  } else {
    safeRemoveItem(THREAD_ID_KEY);
  }
}

export function ChatInterface({ className }: ChatInterfaceProps) {
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [currentThreadId, setCurrentThreadId] = React.useState<string | null>(
    getPersistedThreadId
  );

  // Approval state
  const [pendingApproval, setPendingApprovalRaw] =
    React.useState<ApprovalRequest | null>(null);
  const [isApprovalSubmitting, setIsApprovalSubmitting] = React.useState(false);

  // Wrap setPendingApproval so that whenever a *new* approval request arrives
  // we automatically clear the submitting flag.  This prevents the dialog from
  // getting stuck in "Approving..." when the backend resumes and immediately
  // hits another interrupt before the previous handleApprovalDecision callback
  // has finished (race condition between SSE handler and the approval POST
  // callback that both update pendingApproval).
  const setPendingApproval = React.useCallback(
    (value: React.SetStateAction<ApprovalRequest | null>) => {
      setPendingApprovalRaw((prev) => {
        const next = typeof value === "function" ? value(prev) : value;
        // If we're setting a NEW approval request (not clearing), reset submitting state
        if (next !== null && next !== prev) {
          setIsApprovalSubmitting(false);
        }
        return next;
      });
    },
    []
  );

  // Sidebar state
  const [tasks, setTasks] = React.useState<AgentTask[]>([]);
  const [todos, setTodos] = React.useState<TodoItem[]>([]);
  const [fileOps, setFileOps] = React.useState<FileOperation[]>([]);

  // Artifact state
  const [artifacts, setArtifacts] = React.useState<Map<string, Artifact>>(
    () => new Map()
  );
  const [activeArtifactId, setActiveArtifactId] = React.useState<string | null>(
    null
  );

  // Assistant selector state
  const [selectedAssistant, setSelectedAssistant] =
    React.useState<AssistantConfig | null>(null);

  // Sub-agent tracking
  const [subAgents, setSubAgents] = React.useState<SubAgent[]>([]);
  // Accumulates token text per subagent across progress events (keyed by subagent_name/id).
  // Using a ref so mutations don't trigger re-renders — re-renders are driven by setSubAgents.
  const subAgentProgressRef = React.useRef<Map<string, string>>(new Map());

  // Memory modal state
  const [isMemoryOpen, setIsMemoryOpen] = React.useState(false);
  // Badge shown on the memory button when the agent saves new memories.
  const [memoryUpdated, setMemoryUpdated] = React.useState(false);

  // AbortController ref for cancelling in-flight SSE streams (P1-3)
  const abortControllerRef = React.useRef<AbortController | null>(null);

  // Cancel any active stream on unmount
  React.useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  // Persist currentThreadId to localStorage whenever it changes
  React.useEffect(() => {
    persistThreadId(currentThreadId);
  }, [currentThreadId]);

  // Load messages for the current thread on mount or when switching threads
  const loadThreadMessages = React.useCallback(
    async (threadId: string) => {
      try {
        const response = await apiFetch(
          `${config.apiUrl}/threads/${threadId}`
        );
        if (!response.ok) {
          // Thread may have been deleted — clear persisted ID
          if (response.status === 404) {
            setCurrentThreadId(null);
            setMessages([]);
            return;
          }
          throw new Error(`Failed to load thread: ${response.statusText}`);
        }
        const thread: ThreadDetail = await response.json();
        const loadedMessages: Message[] = thread.messages.map((m) => ({
          id: m.id,
          role: m.role as Message["role"],
          content: m.content,
          toolCalls: m.tool_calls
            ? parsePersistedToolCalls(m.tool_calls)
            : undefined,
          createdAt: m.created_at,
        }));
        setMessages(loadedMessages);

        // Reconstruct tasks and file ops from persisted tool calls (P1-6)
        const restoredTasks: AgentTask[] = [];
        const restoredFileOps: FileOperation[] = [];
        for (const msg of loadedMessages) {
          if (msg.toolCalls) {
            for (const tc of msg.toolCalls) {
              restoredTasks.push({
                id: tc.id,
                name: `Execute ${tc.name}`,
                description: tc.args
                  ? JSON.stringify(tc.args).slice(0, 100)
                  : undefined,
                status: tc.status === "completed" ? "completed" : "in_progress",
                toolName: tc.name,
                toolArgs: tc.args,
                result: tc.result,
                createdAt: msg.createdAt || new Date().toISOString(),
                completedAt: tc.status === "completed" ? msg.createdAt : undefined,
              });
              if (isFileOperation(tc.name, tc.args)) {
                restoredFileOps.push(
                  extractFileOperation(tc.name, tc.args, tc.id)
                );
              }
            }
          }
        }
        setTasks(restoredTasks);
        setFileOps(restoredFileOps);
      } catch (err) {
        console.error("Failed to load thread messages:", err);
        // Don't clear thread ID on network errors — user can retry
      }
    },
    []
  );

  React.useEffect(() => {
    if (currentThreadId && !isLoading) {
      loadThreadMessages(currentThreadId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentThreadId, isLoading]);

  // Handlers for ConversationSidebar
  const handleSelectThread = React.useCallback(
    (threadId: string) => {
      if (threadId === currentThreadId) return;
      // Abort any in-flight stream (P1-3)
      abortControllerRef.current?.abort();
      // Reset state for new thread
      setMessages([]);
      setTasks([]);
      setTodos([]);
      setFileOps([]);
      setSubAgents([]);
      setArtifacts(new Map());
      setActiveArtifactId(null);
      setPendingApproval(null);
      subAgentProgressRef.current.clear();
      setCurrentThreadId(threadId);
    },
    [currentThreadId]
  );

  const handleNewConversation = React.useCallback(() => {
    // Abort any in-flight stream (P1-3)
    abortControllerRef.current?.abort();
    setCurrentThreadId(null);
    setMessages([]);
    setTasks([]);
    setTodos([]);
    setFileOps([]);
    setSubAgents([]);
    setArtifacts(new Map());
    setActiveArtifactId(null);
    subAgentProgressRef.current.clear();
    setPendingApproval(null);
  }, []);

  /**
   * Handle sending a new user message via SSE streaming.
   */
  const handleSend = React.useCallback(
    async (content: string) => {
      const userMessage: Message = {
        id: `msg-${Date.now()}-user`,
        role: "user",
        content,
        createdAt: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      // Abort any previous in-flight stream (P1-3)
      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      // Clear sub-agents from previous turn
      setSubAgents([]);
      subAgentProgressRef.current.clear();

      // Build the streaming URL
      const url = new URL(`${config.apiUrl}/chat/stream`);
      if (currentThreadId) {
        url.searchParams.set("thread_id", currentThreadId);
      }
      if (selectedAssistant) {
        url.searchParams.set("assistant_id", selectedAssistant.id);
      }

      try {
        const response = await apiFetch(url.toString(), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: content }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let assistantContent = "";
        let assistantMsgId = `msg-${Date.now()}-assistant`;
        let currentToolCalls: Message["toolCalls"] = [];

        // Add empty assistant message that we'll update as tokens arrive
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMsgId,
            role: "assistant",
            content: "",
            toolCalls: [],
            createdAt: new Date().toISOString(),
          },
        ]);

        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE events from buffer.
          // SSE format: each event is terminated by a blank line (\n\n).
          // We split on double-newline to get complete event blocks, keeping
          // any trailing incomplete block as the new buffer.
          const parts = buffer.split("\n\n");
          // Last part may be incomplete (no trailing \n\n) — keep as buffer
          buffer = parts.pop() ?? "";

          for (const part of parts) {
            if (!part.trim()) continue;
            let eventType = "";
            let eventData = "";
            for (const line of part.split("\n")) {
              if (line.startsWith("event: ")) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith("data: ")) {
                eventData = line.slice(6);
              }
            }
            if (eventType && eventData) {
              try {
                const data = JSON.parse(eventData);
                processSSEEvent(
                  eventType,
                  data,
                  assistantMsgId,
                  assistantContent,
                  currentToolCalls ?? [],
                  {
                    setMessages,
                    setCurrentThreadId,
                    setPendingApproval,
                    setTasks,
                    setTodos,
                    setFileOps,
                    setArtifacts,
                    setActiveArtifactId,
                    setSubAgents,
                    subAgentProgressMap: subAgentProgressRef.current,
                    setMemoryUpdated,
                    updateAssistantContent: (newContent: string) => {
                      assistantContent = newContent;
                    },
                    updateToolCalls: (newCalls: Message["toolCalls"]) => {
                      currentToolCalls = newCalls;
                    },
                  }
                );
              } catch {
                // Skip malformed JSON
              }
            }
          }
        }
      } catch (error) {
        // Don't show error for intentional aborts (P1-3)
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        const errorMsg: Message = {
          id: `msg-${Date.now()}-error`,
          role: "assistant",
          content: `Sorry, an error occurred: ${error instanceof Error ? error.message : "Unknown error"}`,
          createdAt: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        // Clear the controller ref if it's still the current one
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
        setIsLoading(false);
      }
    },
    [currentThreadId, selectedAssistant]
  );

  /**
   * Shared handler for all approval decisions (approve / reject / edit).
   * Submits the decision to the backend and updates local task/message state.
   */
  const handleApprovalDecision = React.useCallback(
    async (
      decision: "approve" | "reject" | "edit",
      options?: { reason?: string; modifiedArgs?: Record<string, unknown> }
    ) => {
      if (!pendingApproval) return;
      setIsApprovalSubmitting(true);

      const approvalId = pendingApproval.id;

      try {
        const response = await apiFetch(`${config.apiUrl}/chat/approval`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            thread_id: pendingApproval.threadId,
            decision,
            ...(options?.reason !== undefined ? { reason: options.reason } : {}),
            ...(options?.modifiedArgs !== undefined ? { modified_args: options.modifiedArgs } : {}),
          }),
        });

        if (!response.ok) {
          throw new Error(`Approval decision failed: ${response.statusText}`);
        }

        if (decision === "reject") {
          // Update task status to failed
          setTasks((prev) =>
            prev.map((t) => (t.id === approvalId ? { ...t, status: "failed" as const } : t))
          );
          // Mark tool call as rejected in messages
          setMessages((prev) =>
            prev.map((msg) => {
              if (!msg.toolCalls) return msg;
              return {
                ...msg,
                toolCalls: msg.toolCalls.map((tc) =>
                  tc.id === approvalId
                    ? { ...tc, status: "rejected" as const, result: options?.reason ?? "Rejected by user" }
                    : tc
                ),
              };
            })
          );
        } else {
          // approve or edit — advance to in_progress, optionally update args
          setTasks((prev) =>
            prev.map((t) =>
              t.id === approvalId
                ? {
                    ...t,
                    status: "in_progress" as const,
                    ...(options?.modifiedArgs !== undefined ? { toolArgs: options.modifiedArgs } : {}),
                  }
                : t
            )
          );
        }

        setPendingApproval(null);
      } catch (error) {
        console.error("Failed to submit approval decision:", error);
      } finally {
        setIsApprovalSubmitting(false);
      }
    },
    [pendingApproval]
  );

  const handleApprove = React.useCallback(
    (_approvalId: string) => handleApprovalDecision("approve"),
    [handleApprovalDecision]
  );

  const handleReject = React.useCallback(
    (_approvalId: string, reason?: string) => handleApprovalDecision("reject", { reason }),
    [handleApprovalDecision]
  );

  const handleEdit = React.useCallback(
    (_approvalId: string, modifiedArgs: Record<string, unknown>) =>
      handleApprovalDecision("edit", { modifiedArgs }),
    [handleApprovalDecision]
  );

  // --- Artifact handlers ---

  const handleOpenArtifact = React.useCallback((artifactId: string) => {
    setActiveArtifactId((prev) => (prev === artifactId ? null : artifactId));
  }, []);

  const handleCloseArtifact = React.useCallback(() => {
    setActiveArtifactId(null);
  }, []);

  const handleUpdateArtifact = React.useCallback(
    (artifactId: string, content: string) => {
      setArtifacts((prev) => {
        const existing = prev.get(artifactId);
        if (!existing) return prev;
        const updated = updateArtifactContent(existing, content, "user");
        const next = new Map(prev);
        next.set(artifactId, updated);
        return next;
      });
    },
    []
  );

  const activeArtifact = activeArtifactId
    ? artifacts.get(activeArtifactId) ?? null
    : null;

  return (
    <div
      className={cn("flex h-full w-full bg-background", className)}
    >
      {/* Conversation history sidebar */}
      <ConversationSidebar
        currentThreadId={currentThreadId}
        onSelectThread={handleSelectThread}
        onNewConversation={handleNewConversation}
        className="hidden lg:flex"
      />

      {/* Tasks sidebar */}
      <TasksSidebar tasks={tasks} todos={todos} className="hidden lg:flex" />

      {/* Main chat area */}
      <div className="flex flex-col h-full flex-1 max-w-3xl mx-auto">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-3">
            <div>
              <h1 className="text-base font-semibold">Symphony Chat</h1>
              <p className="text-xs text-muted-foreground">
                Powered by LangChain Deep Agents
              </p>
            </div>
            <AssistantSelector
              selectedId={selectedAssistant?.id ?? null}
              onSelect={setSelectedAssistant}
              disabled={isLoading}
            />
          </div>
          <div className="flex items-center gap-2">
            {pendingApproval && (
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-500 bg-amber-500/10 rounded-full px-2.5 py-1">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                Approval pending
              </span>
            )}
            {/* Memory button — badge appears when agent saves new memories */}
            <button
              type="button"
              onClick={() => {
                if (memoryUpdated) setMemoryUpdated(false);
                setIsMemoryOpen(true);
              }}
              title={
                memoryUpdated
                  ? "Agent saved new memories — click to view"
                  : "View and edit agent memory"
              }
              aria-label={
                memoryUpdated
                  ? "Open agent memory (updated)"
                  : "Open agent memory"
              }
              className="relative flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <BookOpen className="h-4 w-4" />
              {memoryUpdated && (
                <span
                  aria-hidden="true"
                  className="absolute top-1 right-1 h-2 w-2 rounded-full bg-blue-500"
                />
              )}
            </button>
            <UserMenu />
          </div>
        </header>

        {/* Message list — takes up remaining vertical space */}
        <MessageList
          messages={messages}
          isLoading={isLoading}
          artifacts={artifacts}
          onOpenArtifact={handleOpenArtifact}
          activeArtifactId={activeArtifactId}
        />

        {/* Sub-agent progress (above input, only when agents are active) */}
        <SubAgentProgress subAgents={subAgents} />

        {/* Input area */}
        <ChatInput
          onSend={handleSend}
          isLoading={isLoading}
          disabled={!!pendingApproval}
          placeholder={
            pendingApproval
              ? "Waiting for approval decision..."
              : undefined
          }
        />
      </div>

      {/* Files sidebar — shown when no artifact is active */}
      {!activeArtifact && (
        <FilesSidebar files={fileOps} className="hidden lg:flex" />
      )}

      {/* Artifact panel — replaces files sidebar when an artifact is open */}
      {activeArtifact && (
        <ArtifactPanel
          artifact={activeArtifact}
          onUpdate={handleUpdateArtifact}
          onClose={handleCloseArtifact}
          className="hidden lg:flex"
        />
      )}

      {/* Approval dialog */}
      <ApprovalDialog
        approval={pendingApproval}
        onApprove={handleApprove}
        onReject={handleReject}
        onEdit={handleEdit}
        isSubmitting={isApprovalSubmitting}
      />

      {/* Memory modal */}
      <MemoryModal
        open={isMemoryOpen}
        onClose={() => setIsMemoryOpen(false)}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Persisted tool call parser (P1-5)
// ---------------------------------------------------------------------------

/**
 * Parse tool calls from their persisted DB format back into frontend ToolCall[].
 *
 * The backend stores tool_calls as `{"calls": [...]}` but the frontend expects
 * a flat array. This function handles both formats gracefully.
 */
function parsePersistedToolCalls(
  raw: Record<string, unknown>
): Message["toolCalls"] {
  // Handle flat array
  if (Array.isArray(raw)) {
    return raw.map(mapPersistedToolCall);
  }
  // Handle {"calls": [...]} wrapper from _persist_assistant_message
  if (raw && typeof raw === "object" && Array.isArray((raw as any).calls)) {
    return (raw as any).calls.map(mapPersistedToolCall);
  }
  return [];
}

function mapPersistedToolCall(tc: any): NonNullable<Message["toolCalls"]>[number] {
  return {
    id: tc.id || tc.run_id || `tc-${Math.random().toString(36).slice(2)}`,
    name: tc.name || tc.tool_name || "unknown",
    args: tc.args || tc.tool_input || {},
    status: "completed" as const,
    result: tc.result,
    runId: tc.runId || tc.run_id,
  };
}

// ---------------------------------------------------------------------------
// SSE event processor
// ---------------------------------------------------------------------------

interface SSEHandlers {
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setCurrentThreadId: React.Dispatch<React.SetStateAction<string | null>>;
  setPendingApproval: React.Dispatch<
    React.SetStateAction<ApprovalRequest | null>
  >;
  setTasks: React.Dispatch<React.SetStateAction<AgentTask[]>>;
  setTodos: React.Dispatch<React.SetStateAction<TodoItem[]>>;
  setFileOps: React.Dispatch<React.SetStateAction<FileOperation[]>>;
  setArtifacts: React.Dispatch<React.SetStateAction<Map<string, Artifact>>>;
  setActiveArtifactId: React.Dispatch<React.SetStateAction<string | null>>;
  setSubAgents: React.Dispatch<React.SetStateAction<SubAgent[]>>;
  setMemoryUpdated: React.Dispatch<React.SetStateAction<boolean>>;
  /** Mutable map used to accumulate token text per subagent across progress events. */
  subAgentProgressMap: Map<string, string>;
  updateAssistantContent: (content: string) => void;
  updateToolCalls: (calls: Message["toolCalls"]) => void;
}

/** Static descriptions shown for each known subagent type. */
const SUBAGENT_DESCRIPTIONS: Record<string, string> = {
  researcher: "Specialist for web research, data gathering, and source citation.",
  coder: "Specialist for code generation, review, debugging, and technical implementation.",
  writer: "Specialist for content writing, editing, and document creation.",
};

function processSSEEvent(
  event: string,
  data: Record<string, unknown>,
  assistantMsgId: string,
  assistantContent: string,
  currentToolCalls: NonNullable<Message["toolCalls"]>,
  handlers: SSEHandlers
) {
  switch (event) {
    case "message_start": {
      const threadId = data.thread_id as string;
      if (threadId) {
        handlers.setCurrentThreadId(threadId);
      }
      break;
    }

    case "token": {
      const token = data.token as string;
      if (token) {
        const newContent = assistantContent + token;
        handlers.updateAssistantContent(newContent);
        handlers.setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId ? { ...msg, content: newContent } : msg
          )
        );
      }
      break;
    }

    case "tool_call": {
      const toolName = data.tool_name as string;
      const toolInput = data.tool_input as Record<string, unknown>;
      const runId = data.run_id as string;

      const newToolCall = {
        id: runId || `tc-${Date.now()}`,
        name: toolName,
        args: toolInput ?? {},
        status: "running" as const,
      };

      const updatedCalls = [...currentToolCalls, newToolCall];
      handlers.updateToolCalls(updatedCalls);
      handlers.setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? { ...msg, toolCalls: updatedCalls }
            : msg
        )
      );

      // Add to tasks
      handlers.setTasks((prev) => [
        ...prev,
        {
          id: newToolCall.id,
          name: `Execute ${toolName}`,
          description: toolInput
            ? JSON.stringify(toolInput).slice(0, 100)
            : undefined,
          status: "in_progress",
          toolName,
          toolArgs: toolInput,
          createdAt: new Date().toISOString(),
        },
      ]);

      // Track file operations for file-related tools
      if (isFileOperation(toolName, toolInput)) {
        handlers.setFileOps((prev) => [
          ...prev,
          extractFileOperation(toolName, toolInput, runId),
        ]);
      }

      break;
    }

    case "approval_required": {
      const approvalRequest: ApprovalRequest = {
        id: data.approval_id as string,
        threadId: data.thread_id as string,
        toolName: data.tool_name as string,
        toolArgs: (data.tool_args as Record<string, unknown>) ?? {},
        runId: data.run_id as string,
        createdAt: new Date().toISOString(),
      };

      handlers.setPendingApproval(approvalRequest);

      // Add tool call with awaiting_approval status
      const approvalToolCall = {
        id: approvalRequest.id,
        name: approvalRequest.toolName,
        args: approvalRequest.toolArgs,
        status: "awaiting_approval" as const,
        runId: approvalRequest.runId,
      };

      const updatedCalls = [...currentToolCalls, approvalToolCall];
      handlers.updateToolCalls(updatedCalls);
      handlers.setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? { ...msg, toolCalls: updatedCalls }
            : msg
        )
      );

      // Add to tasks
      handlers.setTasks((prev) => [
        ...prev,
        {
          id: approvalRequest.id,
          name: `Execute ${approvalRequest.toolName}`,
          description: JSON.stringify(approvalRequest.toolArgs).slice(0, 100),
          status: "awaiting_approval",
          toolName: approvalRequest.toolName,
          toolArgs: approvalRequest.toolArgs,
          createdAt: new Date().toISOString(),
        },
      ]);
      break;
    }

    case "approval_result": {
      const decision = data.decision as string;
      const approvalId = data.approval_id as string;
      const toolName = data.tool_name as string;

      const newStatus =
        decision === "approved"
          ? ("running" as const)
          : ("rejected" as const);

      // Update tool call status
      const updatedCalls = currentToolCalls.map((tc) =>
        tc.id === approvalId ? { ...tc, status: newStatus } : tc
      );
      handlers.updateToolCalls(updatedCalls);
      handlers.setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? { ...msg, toolCalls: updatedCalls }
            : msg
        )
      );

      // Update task status
      handlers.setTasks((prev) =>
        prev.map((t) =>
          t.id === approvalId
            ? {
                ...t,
                status:
                  decision === "approved"
                    ? ("in_progress" as const)
                    : ("failed" as const),
              }
            : t
        )
      );
      break;
    }

    case "tool_result": {
      const runId = data.run_id as string;
      const output = data.output as string;

      // Update the matching tool call with the result
      // Match by id, name, or runId (needed for approval-required tools whose id is the approval_id)
      const updatedCalls = currentToolCalls.map((tc) =>
        tc.id === runId || tc.name === runId || tc.runId === runId
          ? { ...tc, result: output, status: "completed" as const }
          : tc
      );
      handlers.updateToolCalls(updatedCalls);
      handlers.setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? { ...msg, toolCalls: updatedCalls }
            : msg
        )
      );

      // Update task — match by runId, approval_id, or first in-progress task with matching tool name
      const matchedToolCall = currentToolCalls.find((tc) => tc.runId === runId);
      const matchedApprovalId = matchedToolCall?.id;
      const matchedToolName = matchedToolCall?.name;
      handlers.setTasks((prev) => {
        let matched = false;
        const updated = prev.map((t) => {
          if (t.id === runId || t.id === matchedApprovalId) {
            matched = true;
            return { ...t, status: "completed" as const, result: output, completedAt: new Date().toISOString() };
          }
          return t;
        });
        if (matched) return updated;
        // Fallback: match first in-progress task with same tool name
        let fallbackMatched = false;
        return prev.map((t) => {
          if (!fallbackMatched && matchedToolName && t.toolName === matchedToolName &&
              (t.status === "in_progress" || t.status === "awaiting_approval")) {
            fallbackMatched = true;
            return { ...t, status: "completed" as const, result: output, completedAt: new Date().toISOString() };
          }
          return t;
        });
      });

      // Update file operation
      handlers.setFileOps((prev) =>
        prev.map((f) =>
          f.id === runId
            ? { ...f, status: "completed" as const, preview: output?.slice(0, 200) }
            : f
        )
      );

      break;
    }

    case "artifact_created": {
      const artifactRunId = data.run_id as string;
      const artifactFilePath = data.file_path as string;
      const artifactContent = data.content as string;
      const artifactToolName = data.tool_name as string;

      if (artifactFilePath && artifactContent) {
        const artifactId = `artifact-${artifactRunId || Date.now()}`;
        // Find the tool call that created this artifact
        const matchingToolCall = currentToolCalls.find(
          (tc) => tc.id === artifactRunId || tc.runId === artifactRunId
        );
        const artifact = createArtifactFromToolCall({
          id: artifactId,
          filePath: artifactFilePath,
          content: artifactContent,
          toolCallId: matchingToolCall?.id ?? artifactRunId,
        });
        handlers.setArtifacts((prev) => {
          // Update existing artifact for same file path, or create new
          const existing = Array.from(prev.values()).find(
            (a) => a.filePath === artifactFilePath
          );
          const next = new Map(prev);
          if (existing) {
            const updated = updateArtifactContent(
              existing,
              artifactContent,
              "agent"
            );
            updated.sourceToolCallId = matchingToolCall?.id ?? artifactRunId;
            next.set(existing.id, updated);
          } else {
            next.set(artifactId, artifact);
          }
          return next;
        });
        // Auto-open the artifact panel (only if nothing is open)
        handlers.setActiveArtifactId((prev) => prev ?? artifactId);
      }
      break;
    }

    case "message_end": {
      const content = data.content as string;
      // Runtime guard: only accept plain objects; reject strings, numbers, arrays, null.
      const rawStructured = data.structured_response;
      const structuredResponse =
        rawStructured !== null &&
        rawStructured !== undefined &&
        typeof rawStructured === "object" &&
        !Array.isArray(rawStructured)
          ? (rawStructured as Record<string, unknown>)
          : undefined;
      if (content) {
        handlers.updateAssistantContent(content);
        handlers.setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? {
                  ...msg,
                  content,
                  ...(structuredResponse !== undefined && { structuredResponse }),
                }
              : msg
          )
        );
      } else if (structuredResponse !== undefined) {
        // No text content but there is structured data — still update the message.
        handlers.setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? { ...msg, structuredResponse }
              : msg
          )
        );
      }
      break;
    }

    case "sub_agent_start": {
      // Backend V2 emits `subagent_name`; use it as both the stable id and type.
      const subagentName = (data.subagent_name as string) || (data.agent_name as string) || "";
      if (!subagentName) break;

      const subAgent: SubAgent = {
        id: subagentName,
        name: subagentName.charAt(0).toUpperCase() + subagentName.slice(1),
        type: subagentName,
        status: "running",
        description:
          (data.description as string | undefined) ??
          SUBAGENT_DESCRIPTIONS[subagentName],
        startedAt: new Date().toISOString(),
      };
      // Initialize accumulator for this subagent's token progress text.
      handlers.subAgentProgressMap.set(subagentName, "");
      // Deduplicate in case the same agent emits a second start event.
      handlers.setSubAgents((prev) =>
        prev.some((a) => a.id === subagentName) ? prev : [...prev, subAgent]
      );
      break;
    }

    case "sub_agent_progress": {
      // Backend V2 emits `subagent_name`; fall back to `agent_id` for compatibility.
      const subagentName =
        (data.subagent_name as string) || (data.agent_id as string);
      if (!subagentName) break;

      const innerEvent = data.inner_event as string | undefined;

      if (innerEvent === "token") {
        // Accumulate token chunks so the full progress text grows over time.
        const token = (data.token as string) ?? "";
        if (token) {
          const accumulated =
            (handlers.subAgentProgressMap.get(subagentName) ?? "") + token;
          handlers.subAgentProgressMap.set(subagentName, accumulated);

          handlers.setSubAgents((prev) =>
            prev.map((a) =>
              a.id === subagentName
                ? { ...a, progressText: accumulated }
                : a
            )
          );
        }
      }
      // tool_call / tool_result inner events are tracked via the main event
      // stream and do not modify progressText.
      break;
    }

    case "sub_agent_end": {
      // Backend V2 emits `subagent_name`; fall back to `agent_id` for compatibility.
      // The backend does not send a `status` field — default to "completed".
      const subagentName =
        (data.subagent_name as string) || (data.agent_id as string);
      const status: SubAgent["status"] =
        (data.status as string) === "error" ? "error" : "completed";
      if (subagentName) {
        handlers.setSubAgents((prev) =>
          prev.map((a) =>
            a.id === subagentName
              ? { ...a, status, completedAt: new Date().toISOString() }
              : a
          )
        );
      }
      break;
    }

    case "todo_update": {
      // Agent emits its current planning snapshot via the write_todos tool.
      // The payload contains a `todos` array that replaces the current list.
      const rawTodos = data.todos as Array<Record<string, unknown>> | undefined;
      if (Array.isArray(rawTodos)) {
        const parsedTodos: TodoItem[] = rawTodos.map((t, i) => {
          const content = String(t.content ?? t.description ?? "");
          if (process.env.NODE_ENV !== "production" && !content) {
            console.warn("[todo_update] Todo item at index", i, "has no content:", t);
          }
          return {
            id: String(t.id ?? `todo-${i}`),
            content,
            status: (["pending", "in_progress", "completed"].includes(t.status as string)
              ? t.status
              : "pending") as TodoItem["status"],
            priority: (["low", "medium", "high"].includes(t.priority as string)
              ? t.priority
              : undefined) as TodoItem["priority"],
          };
        });
        handlers.setTodos(parsedTodos);
      }
      break;
    }

    case "execute_result": {
      // Structured result from the execute tool — backend emits run_id, stdout, stderr, exit_code.
      const runId = data.run_id as string;
      const stdout = (data.stdout as string) ?? "";
      const stderr = (data.stderr as string) ?? "";
      // Use null as sentinel when exit_code is absent — do NOT default to 0 (success)
      const exitCode: number | null =
        data.exit_code != null ? (data.exit_code as number) : null;

      const updatedCalls = currentToolCalls.map((tc) =>
        tc.id === runId || tc.runId === runId
          ? {
              ...tc,
              status: "completed" as const,
              execution: {
                stdout,
                stderr,
                exitCode,
                runId,
                timestamp: new Date().toISOString(),
              },
            }
          : tc
      );
      handlers.updateToolCalls(updatedCalls);
      handlers.setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? { ...msg, toolCalls: updatedCalls }
            : msg
        )
      );

      // Update task to completed
      handlers.setTasks((prev) =>
        prev.map((t) =>
          t.id === runId
            ? {
                ...t,
                status: "completed" as const,
                result: stdout || stderr || "(no output)",
                completedAt: new Date().toISOString(),
              }
            : t
        )
      );
      break;
    }

    case "memory_updated": {
      // Agent saved new memories during this turn — light up the badge.
      handlers.setMemoryUpdated(true);
      break;
    }

    case "error": {
      const errorText = data.error as string;
      handlers.setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                content:
                  msg.content +
                  `\n\n**Error:** ${errorText || "An unknown error occurred."}`,
              }
            : msg
        )
      );
      break;
    }
  }
}

// ---------------------------------------------------------------------------
// File operation helpers
// ---------------------------------------------------------------------------

function isFileOperation(
  toolName: string,
  _toolInput: Record<string, unknown> | undefined
): boolean {
  const fileTools = [
    "read_file",
    "write_file",
    "create_file",
    "delete_file",
    "edit_file",
    "list_files",
  ];
  return fileTools.includes(toolName);
}

function extractFileOperation(
  toolName: string,
  toolInput: Record<string, unknown> | undefined,
  runId: string
): FileOperation {
  const opMap: Record<string, FileOperation["operation"]> = {
    read_file: "read",
    write_file: "write",
    create_file: "create",
    delete_file: "delete",
    edit_file: "write",
    list_files: "read",
  };

  return {
    id: runId || `file-${Date.now()}`,
    operation: opMap[toolName] ?? "read",
    filePath: (toolInput?.path as string) || (toolInput?.file_path as string) || "unknown",
    toolName,
    status: "pending",
    timestamp: new Date().toISOString(),
  };
}
