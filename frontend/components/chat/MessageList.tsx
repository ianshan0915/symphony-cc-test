"use client";

import * as React from "react";
import { MessageBubble } from "./MessageBubble";
import { ScrollArea } from "@/components/ui/ScrollArea";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils";
import { config } from "@/lib/config";
import type { Message } from "@/lib/types";

export interface MessageListProps {
  /** Messages to display */
  messages: Message[];
  /** Whether the agent is currently generating a response */
  isLoading?: boolean;
  /** Additional class names */
  className?: string;
}

/**
 * MessageList — a scrollable list of message bubbles with auto-scroll.
 *
 * - Automatically scrolls to the bottom when new messages arrive
 * - Shows a typing indicator when the agent is loading
 * - Respects user scroll position (won't force-scroll if user scrolled up)
 */
export function MessageList({
  messages,
  isLoading = false,
  className,
}: MessageListProps) {
  const viewportRef = React.useRef<HTMLDivElement>(null);
  const bottomRef = React.useRef<HTMLDivElement>(null);
  const [shouldAutoScroll, setShouldAutoScroll] = React.useState(true);

  /** Check if the user is near the bottom of the scroll area */
  const checkAutoScroll = React.useCallback(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    const { scrollTop, scrollHeight, clientHeight } = viewport;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    setShouldAutoScroll(distanceFromBottom <= config.autoScrollThreshold);
  }, []);

  /** Scroll to the bottom */
  const scrollToBottom = React.useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Auto-scroll when messages change or loading state changes
  React.useEffect(() => {
    if (shouldAutoScroll) {
      scrollToBottom();
    }
  }, [messages, isLoading, shouldAutoScroll, scrollToBottom]);

  return (
    <ScrollArea
      className={cn("flex-1", className)}
      viewportRef={viewportRef}
    >
      <div
        className="flex flex-col gap-4 p-4"
        onScroll={checkAutoScroll}
      >
        {/* Empty state */}
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <p className="text-lg font-medium">Welcome to Symphony</p>
            <p className="text-sm mt-1">
              Start a conversation with the AI agent.
            </p>
          </div>
        )}

        {/* Message bubbles */}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary">
              <Spinner size="sm" />
            </div>
            <div className="rounded-2xl rounded-bl-md bg-card border border-border px-4 py-2.5">
              <div className="flex items-center gap-1.5">
                <div className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-bounce [animation-delay:-0.3s]" />
                <div className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-bounce [animation-delay:-0.15s]" />
                <div className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-bounce" />
              </div>
            </div>
          </div>
        )}

        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
