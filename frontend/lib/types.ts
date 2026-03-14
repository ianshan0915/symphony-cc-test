/**
 * Shared type definitions for the chat UI.
 */

/** A single tool call made by the assistant */
export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status?: "pending" | "running" | "completed" | "error" | "awaiting_approval" | "rejected";
}

/** A chat message */
export interface Message {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  toolCalls?: ToolCall[];
  createdAt?: string;
}

/** Approval request sent by the backend when a sensitive tool call needs user confirmation */
export interface ApprovalRequest {
  /** Unique identifier for this approval request */
  id: string;
  /** The thread this approval belongs to */
  threadId: string;
  /** Name of the tool requiring approval */
  toolName: string;
  /** Arguments that will be passed to the tool */
  toolArgs: Record<string, unknown>;
  /** Run ID from the agent execution */
  runId: string;
  /** Timestamp of the request */
  createdAt: string;
}

/** User's decision on an approval request */
export interface ApprovalDecision {
  /** The approval request ID */
  approvalId: string;
  /** Thread ID */
  threadId: string;
  /** Whether the user approved or rejected */
  decision: "approve" | "reject";
  /** Optional reason for rejection */
  reason?: string;
}

/** A task tracked by the agent */
export interface AgentTask {
  id: string;
  name: string;
  description?: string;
  status: "planned" | "in_progress" | "completed" | "failed" | "awaiting_approval";
  toolName?: string;
  toolArgs?: Record<string, unknown>;
  result?: string;
  createdAt: string;
  completedAt?: string;
}

/** Assistant configuration (mirrors backend AssistantOut) */
export interface AssistantConfig {
  id: string;
  name: string;
  description: string | null;
  model: string;
  system_prompt: string | null;
  tools_enabled: string[];
  metadata: Record<string, unknown>;
  temperature: number | null;
  max_tokens: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Status of a sub-agent execution */
export type SubAgentStatus = "running" | "completed" | "error" | "waiting";

/** A sub-agent spawned by the main agent */
export interface SubAgent {
  id: string;
  name: string;
  type: string;
  status: SubAgentStatus;
  description?: string;
  progressText?: string;
  startedAt: string;
  completedAt?: string;
}

/** A file operation tracked by the agent */
export interface FileOperation {
  id: string;
  operation: "read" | "write" | "create" | "delete";
  filePath: string;
  toolName: string;
  status: "pending" | "completed" | "failed";
  timestamp: string;
  preview?: string;
}
