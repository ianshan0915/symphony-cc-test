"use client";

import * as React from "react";
import { SendHorizontal } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils";
import { config } from "@/lib/config";

export interface ChatInputProps {
  /** Called when the user submits a message */
  onSend: (message: string) => void;
  /** Whether the agent is currently processing */
  isLoading?: boolean;
  /** Placeholder text for the input */
  placeholder?: string;
  /** Whether the input is disabled */
  disabled?: boolean;
  /** Additional class names */
  className?: string;
}

/**
 * ChatInput — a text input with send button, keyboard submit (Enter),
 * and loading state indicator.
 *
 * - Press Enter to send (Shift+Enter for newline)
 * - Send button shows spinner when loading
 * - Input is disabled while agent is responding
 */
export function ChatInput({
  onSend,
  isLoading = false,
  placeholder = "Type a message\u2026",
  disabled = false,
  className,
}: ChatInputProps) {
  const [value, setValue] = React.useState("");
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  const isDisabled = disabled || isLoading;
  const canSend = value.trim().length > 0 && !isDisabled;

  /** Auto-resize the textarea to fit content */
  const adjustHeight = React.useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  React.useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);

  const handleSend = React.useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isDisabled) return;
    onSend(trimmed);
    setValue("");
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, isDisabled, onSend]);

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  return (
    <div
      className={cn(
        "flex items-end gap-2 border-t border-border bg-background px-4 py-3",
        className
      )}
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => {
          if (e.target.value.length <= config.maxMessageLength) {
            setValue(e.target.value);
          }
        }}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isDisabled}
        rows={1}
        aria-label="Message input"
        className={cn(
          "flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2.5 text-sm",
          "ring-offset-background placeholder:text-muted-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "min-h-[42px] max-h-[200px]"
        )}
      />
      <Button
        onClick={handleSend}
        disabled={!canSend}
        size="icon"
        aria-label={isLoading ? "Agent is responding" : "Send message"}
        className="shrink-0"
      >
        {isLoading ? (
          <Spinner size="sm" className="text-primary-foreground" />
        ) : (
          <SendHorizontal className="h-4 w-4" />
        )}
      </Button>
    </div>
  );
}
