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
  /** LangGraph run_id — used to correlate tool_result events for approval-required tools */
  runId?: string;
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
  /** Whether the user approved, rejected, or edited */
  decision: "approve" | "reject" | "edit";
  /** Optional reason for rejection */
  reason?: string;
  /** Modified tool arguments when decision is "edit" */
  modifiedArgs?: Record<string, unknown>;
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

/** Brief skill info embedded in assistant configuration */
export interface SkillBrief {
  id: string;
  name: string;
  description: string;
}

/** Assistant configuration (mirrors backend AssistantOut) */
export interface AssistantConfig {
  id: string;
  user_id?: string | null;
  name: string;
  description: string | null;
  model: string;
  system_prompt: string | null;
  tools_enabled: string[];
  metadata: Record<string, unknown>;
  skills: SkillBrief[];
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

/** Thread detail returned by GET /threads/{id} */
export interface ThreadDetail {
  id: string;
  title: string | null;
  assistant_id: string;
  metadata: Record<string, unknown>;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  messages: ThreadMessage[];
}

/** Message as stored on the backend */
export interface ThreadMessage {
  id: string;
  thread_id: string;
  role: string;
  content: string;
  tool_calls?: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

/** Response from GET /memory and PUT /memory */
export interface MemoryResponse {
  /** Current AGENTS.md Markdown content */
  content: string;
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
