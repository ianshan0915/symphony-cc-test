"use client";

import * as React from "react";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { cn } from "@/lib/utils";
import type { Message } from "@/lib/types";

export interface ChatInterfaceProps {
  /** Additional class names */
  className?: string;
}

/**
 * ChatInterface — the top-level container that composes all chat components.
 *
 * Manages local message state and a simulated loading state.
 * In production this will integrate with the useAgent hook and backend API;
 * for now it provides a self-contained demo that satisfies all acceptance criteria.
 */
export function ChatInterface({ className }: ChatInterfaceProps) {
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);

  /**
   * Handle sending a new user message.
   *
   * In the future this will call the backend streaming endpoint.
   * For now it appends the user message and simulates an assistant reply
   * so the component can be demonstrated end-to-end.
   */
  const handleSend = React.useCallback((content: string) => {
    const userMessage: Message = {
      id: `msg-${Date.now()}-user`,
      role: "user",
      content,
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    // Simulate assistant response after a short delay
    setTimeout(() => {
      const assistantMessage: Message = {
        id: `msg-${Date.now()}-assistant`,
        role: "assistant",
        content: getPlaceholderReply(content),
        toolCalls: getPlaceholderToolCalls(content),
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsLoading(false);
    }, 1500);
  }, []);

  return (
    <div
      className={cn(
        "flex flex-col h-full w-full max-w-3xl mx-auto bg-background",
        className
      )}
    >
      {/* Header */}
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h1 className="text-base font-semibold">Symphony Chat</h1>
          <p className="text-xs text-muted-foreground">
            Powered by LangChain Deep Agents
          </p>
        </div>
      </header>

      {/* Message list — takes up remaining vertical space */}
      <MessageList messages={messages} isLoading={isLoading} />

      {/* Input area */}
      <ChatInput onSend={handleSend} isLoading={isLoading} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Placeholder helpers — will be removed when real backend integration lands
// ---------------------------------------------------------------------------

function getPlaceholderReply(userContent: string): string {
  const lower = userContent.toLowerCase();
  if (lower.includes("hello") || lower.includes("hi")) {
    return "Hello! I'm the Symphony AI assistant. How can I help you today?";
  }
  if (lower.includes("help")) {
    return (
      "I can help you with a variety of tasks:\n\n" +
      "- **Answer questions** about any topic\n" +
      "- **Search the web** for up-to-date information\n" +
      "- **Plan complex tasks** and break them into steps\n" +
      "- **Write and edit code** across multiple languages\n\n" +
      "Just let me know what you need!"
    );
  }
  return (
    "Thanks for your message! I'm currently running in **demo mode**. " +
    "Once the backend is connected, I'll be able to provide real responses " +
    "powered by LangChain Deep Agents.\n\n" +
    "Your message was:\n\n> " +
    userContent
  );
}

function getPlaceholderToolCalls(
  userContent: string
): Message["toolCalls"] {
  const lower = userContent.toLowerCase();
  if (lower.includes("search") || lower.includes("find")) {
    return [
      {
        id: `tc-${Date.now()}`,
        name: "web_search",
        args: { query: userContent },
        result: "Found 3 relevant results for your query.",
        status: "completed",
      },
    ];
  }
  if (lower.includes("plan") || lower.includes("task")) {
    return [
      {
        id: `tc-${Date.now()}`,
        name: "write_todos",
        args: {
          todos: [
            "Research the topic",
            "Draft initial plan",
            "Review and refine",
          ],
        },
        result: "Created 3 tasks.",
        status: "completed",
      },
    ];
  }
  return undefined;
}
