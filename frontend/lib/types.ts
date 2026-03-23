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
  /** Structured execution result — populated for execute tool calls via execute_result SSE event */
  execution?: CodeExecution;
}

/** A chat message */
export interface Message {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  toolCalls?: ToolCall[];
  createdAt?: string;
  /** Structured response data from the backend `response_format` feature */
  structuredResponse?: Record<string, unknown>;
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

/**
 * A structured todo item from the agent's planning tool (write_todos).
 * The agent emits `todo_update` SSE events with the current snapshot of todos.
 */
export interface TodoItem {
  /** Stable identifier for this todo */
  id: string;
  /** Human-readable description of the task */
  content: string;
  /** Current execution status */
  status: "pending" | "in_progress" | "completed";
  /** Optional priority hint from the agent */
  priority?: "low" | "medium" | "high";
}

/**
 * Structured result from a code execution (execute tool).
 * Populated by the `execute_result` SSE event emitted by the backend.
 */
export interface CodeExecution {
  /** Standard output from the executed command */
  stdout: string;
  /** Standard error output from the executed command */
  stderr: string;
  /**
   * Process exit code — 0 means success, non-zero means failure.
   * `null` means the exit code was not provided (e.g. a partial/error payload).
   * Callers must not treat `null` as success.
   */
  exitCode: number | null;
  /** Backend run_id used to correlate with the originating tool call */
  runId?: string;
  /** ISO timestamp of when the execution completed */
  timestamp?: string;
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

// ---------------------------------------------------------------------------
// Artifacts
// ---------------------------------------------------------------------------

/** Content type of an artifact */
export type ArtifactType =
  | "code"
  | "document"
  | "markdown"
  | "html"
  | "csv"
  | "json"
  | "text";

/** A single version snapshot of an artifact's content */
export interface ArtifactVersion {
  content: string;
  timestamp: string;
  /** What produced this version: agent tool call or user edit */
  source: "agent" | "user";
}

/**
 * An artifact produced or modified by the agent (or user).
 *
 * Artifacts are created when the agent writes/creates files, generates
 * documents, or produces structured output.  They are displayed in a
 * dedicated panel alongside the chat for viewing and editing.
 */
export interface Artifact {
  /** Stable identifier (usually the tool-call run_id) */
  id: string;
  /** Display title — typically the filename or a generated title */
  title: string;
  /** Current content (latest version) */
  content: string;
  /** Detected or declared content type */
  type: ArtifactType;
  /** Programming language hint for syntax highlighting (e.g. "python", "typescript") */
  language?: string;
  /** Original file path when the artifact was created from a file tool */
  filePath?: string;
  /** Version history — latest version last */
  versions: ArtifactVersion[];
  /** ISO timestamp of creation */
  createdAt: string;
  /** ISO timestamp of last update */
  updatedAt: string;
  /** The tool-call ID that created this artifact */
  sourceToolCallId?: string;
}
