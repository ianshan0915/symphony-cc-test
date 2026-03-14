"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User, Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import { ToolCallCard } from "./ToolCallCard";
import type { Message } from "@/lib/types";

export interface MessageBubbleProps {
  /** The message to display */
  message: Message;
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
export function MessageBubble({ message, className }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";

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
        )}

        {/* Tool calls — shown below the message content */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="flex flex-col gap-2 w-full">
            {message.toolCalls.map((toolCall) => (
              <ToolCallCard key={toolCall.id} toolCall={toolCall} />
            ))}
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
