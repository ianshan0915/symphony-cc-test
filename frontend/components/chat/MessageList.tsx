"use client";

import * as React from "react";
import { MessageBubble } from "./MessageBubble";
import { WelcomeScreen } from "./WelcomeScreen";
import { LoadingIndicator } from "./LoadingIndicator";
import { MessageSkeleton } from "./MessageSkeleton";
import { SubAgentProgress } from "./SubAgentProgress";
import { ScrollArea } from "@/components/ui/ScrollArea";
import { cn } from "@/lib/utils";
import { config } from "@/lib/config";
import type { Message, Artifact, SubAgent } from "@/lib/types";

/** Time gap (ms) between messages before showing a new time-group divider */
const TIME_GROUP_GAP_MS = 5 * 60 * 1000; // 5 minutes

export interface MessageListProps {
  /** Messages to display */
  messages: Message[];
  /** Whether the agent is currently generating a response */
  isLoading?: boolean;
  /** Whether the thread is loading (show skeleton) */
  isThreadLoading?: boolean;
  /** The currently active tool name (for contextual loading indicator) */
  currentToolName?: string | null;
  /** Active sub-agents to display inline in the chat stream */
  subAgents?: SubAgent[];
  /** Map of artifact ID → Artifact for rendering inline artifact buttons */
  artifacts?: Map<string, Artifact>;
  /** Called when user clicks an artifact button */
  onOpenArtifact?: (artifactId: string) => void;
  /** The currently open artifact ID (for highlighting) */
  activeArtifactId?: string | null;
  /** Called when user clicks a starter prompt on the welcome screen */
  onSend?: (message: string) => void;
  /** Called when user clicks retry on an assistant message */
  onRetry?: (messageId: string) => void;
  /** Additional class names */
  className?: string;
}

/**
 * MessageList — a scrollable list of message bubbles with auto-scroll,
 * time-grouped timestamps, contextual loading, and welcome screen.
 */
export function MessageList({
  messages,
  isLoading = false,
  isThreadLoading = false,
  currentToolName,
  subAgents = [],
  artifacts,
  onOpenArtifact,
  activeArtifactId,
  onSend,
  onRetry,
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

  // Attach scroll listener to the Radix viewport (it's the element that scrolls)
  React.useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    viewport.addEventListener("scroll", checkAutoScroll, { passive: true });
    return () => viewport.removeEventListener("scroll", checkAutoScroll);
  }, [checkAutoScroll]);

  // Auto-scroll when messages change or loading state changes
  React.useEffect(() => {
    if (shouldAutoScroll) {
      scrollToBottom();
    }
  }, [messages, isLoading, shouldAutoScroll, scrollToBottom]);

  // Thread loading skeleton
  if (isThreadLoading) {
    return (
      <ScrollArea className={cn("flex-1", className)} viewportRef={viewportRef}>
        <MessageSkeleton />
        <div ref={bottomRef} />
      </ScrollArea>
    );
  }

  return (
    <ScrollArea
      className={cn("flex-1", className)}
      viewportRef={viewportRef}
    >
      <div className="flex flex-col gap-4 px-3 py-4 sm:px-4 max-w-2xl mx-auto w-full">
        {/* Empty state — welcome screen */}
        {messages.length === 0 && !isLoading && onSend && (
          <WelcomeScreen onSend={onSend} />
        )}

        {/* Fallback empty state when no onSend is available */}
        {messages.length === 0 && !isLoading && !onSend && (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <p className="text-lg font-medium">Welcome to Symphony</p>
            <p className="text-sm mt-1">
              Start a conversation with the AI agent.
            </p>
          </div>
        )}

        {/* Message bubbles with time-group dividers */}
        {messages.map((message, index) => {
          const showTimeDivider = shouldShowTimeDivider(messages, index);
          return (
            <React.Fragment key={message.id}>
              {showTimeDivider && message.createdAt && (
                <TimeDivider timestamp={message.createdAt} />
              )}
              <MessageBubble
                message={message}
                artifacts={artifacts}
                onOpenArtifact={onOpenArtifact}
                activeArtifactId={activeArtifactId}
                onRetry={onRetry}
                showTimestamp={false}
              />
            </React.Fragment>
          );
        })}

        {/* Sub-agent progress — inline in chat stream */}
        {subAgents.length > 0 && (
          <SubAgentProgress subAgents={subAgents} />
        )}

        {/* Contextual loading indicator (replaces bouncing dots) */}
        {isLoading && (
          <LoadingIndicator currentToolName={currentToolName} />
        )}

        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}

// ---------------------------------------------------------------------------
// Time-group divider helpers
// ---------------------------------------------------------------------------

/**
 * Determines if a time-group divider should be shown before the message at `index`.
 * Rules:
 * - Always show before the first message
 * - Show when the gap between consecutive messages exceeds TIME_GROUP_GAP_MS
 */
function shouldShowTimeDivider(messages: Message[], index: number): boolean {
  if (index === 0) return true;
  const current = messages[index].createdAt;
  const previous = messages[index - 1].createdAt;
  if (!current || !previous) return false;

  const gap = new Date(current).getTime() - new Date(previous).getTime();
  return Math.abs(gap) >= TIME_GROUP_GAP_MS;
}

/**
 * TimeDivider — centered timestamp separator between message groups.
 * Follows the iMessage/WhatsApp pattern.
 */
function TimeDivider({ timestamp }: { timestamp: string }) {
  const date = new Date(timestamp);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();

  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday = date.toDateString() === yesterday.toDateString();

  let label: string;
  if (isToday) {
    label = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } else if (isYesterday) {
    label = `Yesterday ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  } else {
    label = date.toLocaleDateString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return (
    <div className="flex items-center gap-3 py-2" data-testid="time-divider">
      <div className="flex-1 h-px bg-border" />
      <span
        className="text-[10px] text-muted-foreground font-medium px-2"
        title={date.toLocaleString()}
      >
        {label}
      </span>
      <div className="flex-1 h-px bg-border" />
    </div>
  );
}
