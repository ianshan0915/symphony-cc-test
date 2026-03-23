"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User, Bot, Copy, Check, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import { ToolCallCard } from "./ToolCallCard";
import { ToolCallGroup } from "./ToolCallGroup";
import { StructuredResponseCard } from "./StructuredResponseCard";
import { CodeExecutionCard } from "./CodeExecutionCard";
import { ArtifactButton } from "@/components/artifacts/ArtifactButton";
import { isArtifactProducingTool } from "@/lib/artifacts";
import type { Message, ToolCall, Artifact } from "@/lib/types";

/** Threshold: if there are more than this many tool calls, group them */
const GROUP_THRESHOLD = 3;

/** Returns true when a tool call should be rendered as a CodeExecutionCard. */
function isExecuteToolCall(toolCall: ToolCall): boolean {
  return toolCall.name === "execute";
}

export interface MessageBubbleProps {
  /** The message to display */
  message: Message;
  /** Map of artifact ID → Artifact for rendering inline artifact buttons */
  artifacts?: Map<string, Artifact>;
  /** Called when user clicks an artifact button */
  onOpenArtifact?: (artifactId: string) => void;
  /** The currently open artifact ID (for highlighting) */
  activeArtifactId?: string | null;
  /** Called when user clicks retry on an assistant message */
  onRetry?: (messageId: string) => void;
  /** Whether to show the per-message timestamp (default: true for backward compat) */
  showTimestamp?: boolean;
  /** Additional class names */
  className?: string;
}

/**
 * MessageBubble — renders a single chat message with role-appropriate styling.
 *
 * - User messages: right-aligned, primary color
 * - Assistant messages: left-aligned, card background, markdown rendered
 * - Hover toolbar with copy + retry actions (above the message)
 * - Tool call results displayed via ToolCallCard / ToolCallGroup
 */
export function MessageBubble({
  message,
  artifacts,
  onOpenArtifact,
  activeArtifactId,
  onRetry,
  showTimestamp = true,
  className,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const [copied, setCopied] = React.useState(false);

  const handleCopy = React.useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = message.content;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [message.content]);

  const handleRetry = React.useCallback(() => {
    onRetry?.(message.id);
  }, [onRetry, message.id]);

  return (
    <div
      className={cn(
        "flex gap-3 w-full group/message",
        isUser ? "justify-end" : "justify-start",
        className
      )}
    >
      {/* Avatar — shown on the left for assistant messages */}
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary">
          <Bot className="h-4 w-4 text-secondary-foreground" />
        </div>
      )}

      <div
        className={cn(
          "flex flex-col gap-1.5 max-w-[80%]",
          isUser ? "items-end" : "items-start"
        )}
      >
        {/* Message content bubble with hover action toolbar */}
        {message.content && (
          <div className="relative group/bubble">
            {/* Hover action toolbar — floats above the message */}
            {isAssistant && message.content && (
              <div
                className={cn(
                  "absolute -top-8 right-0 flex items-center gap-1 opacity-0 group-hover/message:opacity-100",
                  "transition-opacity bg-background border border-border rounded-lg shadow-sm px-1 py-0.5 z-10"
                )}
              >
                <button
                  onClick={handleCopy}
                  className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                  title={copied ? "Copied!" : "Copy"}
                  aria-label={copied ? "Copied to clipboard" : "Copy message to clipboard"}
                >
                  {copied ? (
                    <Check className="h-3.5 w-3.5 text-green-500" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                </button>
                {onRetry && (
                  <button
                    onClick={handleRetry}
                    className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                    title="Retry"
                    aria-label="Retry this response"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            )}

            <div
              className={cn(
                "rounded-2xl px-4 py-2.5 text-sm",
                isUser
                  ? "bg-primary text-primary-foreground rounded-br-md"
                  : "bg-card border border-border text-card-foreground rounded-bl-md"
              )}
            >
              {isAssistant ? (
                <div className="prose-chat">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="whitespace-pre-wrap break-words overflow-wrap-anywhere">{message.content}</p>
              )}
            </div>
          </div>
        )}

        {/* Structured response — shown below text content when present */}
        {message.structuredResponse && (
          <StructuredResponseCard
            data={message.structuredResponse}
            className="w-full"
          />
        )}

        {/* Tool calls — shown below the message content */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="flex flex-col gap-2 w-full">
            {renderToolCalls(message.toolCalls, artifacts, onOpenArtifact, activeArtifactId)}
          </div>
        )}

        {/* Timestamp — only shown when showTimestamp is true (backward compat) */}
        {showTimestamp && message.createdAt && (
          <span className="text-[10px] text-muted-foreground px-1">
            {new Date(message.createdAt).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        )}
      </div>

      {/* Avatar — shown on the right for user messages */}
      {isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary">
          <User className="h-4 w-4 text-primary-foreground" />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tool call rendering with grouping
// ---------------------------------------------------------------------------

/**
 * Renders tool calls, grouping consecutive non-artifact calls when there
 * are more than GROUP_THRESHOLD. Artifact-producing tools always get their
 * own ArtifactButton. Execute tool calls are shown individually when ungrouped.
 */
function renderToolCalls(
  toolCalls: ToolCall[],
  artifacts?: Map<string, Artifact>,
  onOpenArtifact?: (artifactId: string) => void,
  activeArtifactId?: string | null
): React.ReactNode[] {
  const elements: React.ReactNode[] = [];

  // Separate artifact tool calls from regular ones
  const artifactToolCallIds = new Set<string>();
  if (artifacts && onOpenArtifact) {
    for (const tc of toolCalls) {
      if (isArtifactProducingTool(tc.name)) {
        const artifact = Array.from(artifacts.values()).find(
          (a) => a.sourceToolCallId === tc.id
        );
        if (artifact) {
          artifactToolCallIds.add(tc.id);
        }
      }
    }
  }

  // Split into artifact calls and regular calls
  const regularCalls: ToolCall[] = [];
  for (const tc of toolCalls) {
    if (artifactToolCallIds.has(tc.id)) {
      // Flush any accumulated regular calls as a group first
      if (regularCalls.length > 0) {
        elements.push(...renderRegularToolCalls([...regularCalls]));
        regularCalls.length = 0;
      }
      // Render artifact button
      const artifact = Array.from(artifacts!.values()).find(
        (a) => a.sourceToolCallId === tc.id
      )!;
      elements.push(
        <ArtifactButton
          key={tc.id}
          artifact={artifact}
          isActive={activeArtifactId === artifact.id}
          onClick={() => onOpenArtifact!(artifact.id)}
        />
      );
    } else {
      regularCalls.push(tc);
    }
  }

  // Flush remaining regular calls
  if (regularCalls.length > 0) {
    elements.push(...renderRegularToolCalls(regularCalls));
  }

  return elements;
}

function renderRegularToolCalls(toolCalls: ToolCall[]): React.ReactNode[] {
  // Group if above threshold
  if (toolCalls.length > GROUP_THRESHOLD) {
    return [
      <ToolCallGroup
        key={`group-${toolCalls[0].id}`}
        toolCalls={toolCalls}
      />,
    ];
  }

  // Render individually
  return toolCalls.map((tc) =>
    tc.name === "execute" ? (
      <CodeExecutionCard key={tc.id} toolCall={tc} />
    ) : (
      <ToolCallCard key={tc.id} toolCall={tc} />
    )
  );
}
