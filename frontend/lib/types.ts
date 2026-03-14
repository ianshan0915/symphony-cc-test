/**
 * Shared type definitions for the chat UI.
 */

/** A single tool call made by the assistant */
export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status?: "pending" | "running" | "completed" | "error";
}

/** A chat message */
export interface Message {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  toolCalls?: ToolCall[];
  createdAt?: string;
}
