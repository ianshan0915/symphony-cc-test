"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User, Bot, Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { ToolCallCard } from "./ToolCallCard";
import { StructuredResponseCard } from "./StructuredResponseCard";
import { CodeExecutionCard } from "./CodeExecutionCard";
import { ArtifactButton } from "@/components/artifacts/ArtifactButton";
import { isArtifactProducingTool } from "@/lib/artifacts";
import type { Message, ToolCall, Artifact } from "@/lib/types";

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
  /** Additional class names */
  className?: string;
}

/**
 * MessageBubble — renders a single chat message with role-appropriate styling.
 *
 * - User messages: right-aligned, primary color
 * - Assistant messages: left-aligned, card background, markdown rendered
 * - Tool call results displayed via ToolCallCard
 */
export function MessageBubble({
  message,
  artifacts,
  onOpenArtifact,
  activeArtifactId,
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

  return (
    <div
      className={cn(
        "flex gap-3 w-full",
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
        {/* Message content bubble */}
        {message.content && (
          <div className="relative group/bubble">
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
                <p className="whitespace-pre-wrap break-words">{message.content}</p>
              )}
            </div>
            {/* Copy button (P3-15) — shown on hover for assistant messages */}
            {isAssistant && message.content && (
              <button
                onClick={handleCopy}
                className="absolute -bottom-1 right-1 opacity-0 group-hover/bubble:opacity-100 transition-opacity p-1 rounded-md bg-background border border-border text-muted-foreground hover:text-foreground shadow-sm"
                title={copied ? "Copied!" : "Copy message"}
                aria-label={copied ? "Copied to clipboard" : "Copy message to clipboard"}
              >
                {copied ? (
                  <Check className="h-3 w-3 text-green-500" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </button>
            )}
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
            {message.toolCalls.map((toolCall) => {
              // Show artifact button for write/create tools that produced artifacts
              if (
                isArtifactProducingTool(toolCall.name) &&
                artifacts &&
                onOpenArtifact
              ) {
                // Find artifact linked to this tool call
                const artifact = Array.from(artifacts.values()).find(
                  (a) => a.sourceToolCallId === toolCall.id
                );
                if (artifact) {
                  return (
                    <ArtifactButton
                      key={toolCall.id}
                      artifact={artifact}
                      isActive={activeArtifactId === artifact.id}
                      onClick={() => onOpenArtifact(artifact.id)}
                    />
                  );
                }
              }

              return isExecuteToolCall(toolCall) ? (
                <CodeExecutionCard key={toolCall.id} toolCall={toolCall} />
              ) : (
                <ToolCallCard key={toolCall.id} toolCall={toolCall} />
              );
            })}
          </div>
        )}

        {/* Timestamp */}
        {message.createdAt && (
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
