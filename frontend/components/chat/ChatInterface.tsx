"use client";

import * as React from "react";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { ApprovalDialog } from "./ApprovalDialog";
import { AssistantSelector } from "./AssistantSelector";
import { SubAgentProgress } from "./SubAgentProgress";
import { TasksSidebar } from "@/components/sidebar/TasksSidebar";
import { FilesSidebar } from "@/components/sidebar/FilesSidebar";
import { cn } from "@/lib/utils";
import { config } from "@/lib/config";
import type {
  Message,
  ApprovalRequest,
  AgentTask,
  FileOperation,
  SubAgent,
} from "@/lib/types";
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
export function ChatInterface({ className }: ChatInterfaceProps) {
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [currentThreadId, setCurrentThreadId] = React.useState<string | null>(
    null
  );

  // Approval state
  const [pendingApproval, setPendingApproval] =
    React.useState<ApprovalRequest | null>(null);
  const [isApprovalSubmitting, setIsApprovalSubmitting] = React.useState(false);

  // Sidebar state
  const [tasks, setTasks] = React.useState<AgentTask[]>([]);
  const [fileOps, setFileOps] = React.useState<FileOperation[]>([]);

  // Assistant selector state
  const [selectedAssistant, setSelectedAssistant] =
    React.useState<AssistantConfig | null>(null);

  // Sub-agent tracking
  const [subAgents, setSubAgents] = React.useState<SubAgent[]>([]);

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

      // Clear sub-agents from previous turn
      setSubAgents([]);

      // Build the streaming URL
      const url = new URL(`${config.apiUrl}/chat/stream`);
      if (currentThreadId) {
        url.searchParams.set("thread_id", currentThreadId);
      }
      if (selectedAssistant) {
        url.searchParams.set("assistant_id", selectedAssistant.id);
      }

      try {
        const response = await fetch(url.toString(), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: content }),
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

          // Parse SSE events from buffer
          const lines = buffer.split("\n");
          buffer = "";

          let currentEvent = "";
          let currentData = "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              currentData = line.slice(6);
            } else if (line === "" && currentEvent && currentData) {
              // Process complete event
              try {
                const data = JSON.parse(currentData);
                processSSEEvent(
                  currentEvent,
                  data,
                  assistantMsgId,
                  assistantContent,
                  currentToolCalls ?? [],
                  {
                    setMessages,
                    setCurrentThreadId,
                    setPendingApproval,
                    setTasks,
                    setFileOps,
                    setSubAgents,
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
              currentEvent = "";
              currentData = "";
            } else if (currentEvent || currentData) {
              // Incomplete event, put back in buffer
              buffer =
                (currentEvent ? `event: ${currentEvent}\n` : "") +
                (currentData ? `data: ${currentData}\n` : "") +
                line +
                "\n";
            }
          }
        }
      } catch (error) {
        const errorMsg: Message = {
          id: `msg-${Date.now()}-error`,
          role: "assistant",
          content: `Sorry, an error occurred: ${error instanceof Error ? error.message : "Unknown error"}`,
          createdAt: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
      }
    },
    [currentThreadId, selectedAssistant]
  );

  /**
   * Handle approval of a pending tool call.
   */
  const handleApprove = React.useCallback(
    async (approvalId: string) => {
      if (!pendingApproval) return;
      setIsApprovalSubmitting(true);

      try {
        const response = await fetch(`${config.apiUrl}/chat/approval`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            thread_id: pendingApproval.threadId,
            decision: "approve",
          }),
        });

        if (!response.ok) {
          throw new Error(`Approval failed: ${response.statusText}`);
        }

        // Update task status
        setTasks((prev) =>
          prev.map((t) =>
            t.id === approvalId
              ? { ...t, status: "in_progress" as const }
              : t
          )
        );

        setPendingApproval(null);
      } catch (error) {
        console.error("Failed to submit approval:", error);
      } finally {
        setIsApprovalSubmitting(false);
      }
    },
    [pendingApproval]
  );

  /**
   * Handle rejection of a pending tool call.
   */
  const handleReject = React.useCallback(
    async (approvalId: string, reason?: string) => {
      if (!pendingApproval) return;
      setIsApprovalSubmitting(true);

      try {
        const response = await fetch(`${config.apiUrl}/chat/approval`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            thread_id: pendingApproval.threadId,
            decision: "reject",
            reason,
          }),
        });

        if (!response.ok) {
          throw new Error(`Rejection failed: ${response.statusText}`);
        }

        // Update task status
        setTasks((prev) =>
          prev.map((t) =>
            t.id === approvalId ? { ...t, status: "failed" as const } : t
          )
        );

        // Update tool call status in messages
        setMessages((prev) =>
          prev.map((msg) => {
            if (!msg.toolCalls) return msg;
            return {
              ...msg,
              toolCalls: msg.toolCalls.map((tc) =>
                tc.id === approvalId
                  ? { ...tc, status: "rejected" as const, result: reason ?? "Rejected by user" }
                  : tc
              ),
            };
          })
        );

        setPendingApproval(null);
      } catch (error) {
        console.error("Failed to submit rejection:", error);
      } finally {
        setIsApprovalSubmitting(false);
      }
    },
    [pendingApproval]
  );

  return (
    <div
      className={cn("flex h-full w-full bg-background", className)}
    >
      {/* Tasks sidebar */}
      <TasksSidebar tasks={tasks} className="hidden lg:flex" />

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
          {pendingApproval && (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-500 bg-amber-500/10 rounded-full px-2.5 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
              Approval pending
            </span>
          )}
        </header>

        {/* Message list — takes up remaining vertical space */}
        <MessageList messages={messages} isLoading={isLoading} />

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

      {/* Files sidebar */}
      <FilesSidebar files={fileOps} className="hidden lg:flex" />

      {/* Approval dialog */}
      <ApprovalDialog
        approval={pendingApproval}
        onApprove={handleApprove}
        onReject={handleReject}
        isSubmitting={isApprovalSubmitting}
      />
    </div>
  );
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
  setFileOps: React.Dispatch<React.SetStateAction<FileOperation[]>>;
  setSubAgents: React.Dispatch<React.SetStateAction<SubAgent[]>>;
  updateAssistantContent: (content: string) => void;
  updateToolCalls: (calls: Message["toolCalls"]) => void;
}

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

    case "message_end": {
      const content = data.content as string;
      if (content) {
        handlers.updateAssistantContent(content);
        handlers.setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId ? { ...msg, content } : msg
          )
        );
      }
      break;
    }

    case "sub_agent_start": {
      const subAgent: SubAgent = {
        id: (data.agent_id as string) || `sub-${Date.now()}`,
        name: (data.agent_name as string) || "Sub-Agent",
        type: (data.agent_type as string) || "unknown",
        status: "running",
        description: data.description as string | undefined,
        startedAt: new Date().toISOString(),
      };
      handlers.setSubAgents((prev) => [...prev, subAgent]);
      break;
    }

    case "sub_agent_progress": {
      const agentId = data.agent_id as string;
      const progressText = data.progress_text as string;
      if (agentId) {
        handlers.setSubAgents((prev) =>
          prev.map((a) =>
            a.id === agentId
              ? { ...a, progressText: progressText ?? a.progressText }
              : a
          )
        );
      }
      break;
    }

    case "sub_agent_end": {
      const agentId = data.agent_id as string;
      const status = (data.status as string) === "error" ? "error" : "completed";
      if (agentId) {
        handlers.setSubAgents((prev) =>
          prev.map((a) =>
            a.id === agentId
              ? {
                  ...a,
                  status: status as SubAgent["status"],
                  completedAt: new Date().toISOString(),
                }
              : a
          )
        );
      }
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
