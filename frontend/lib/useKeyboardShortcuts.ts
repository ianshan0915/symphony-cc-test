"use client";

import { useEffect } from "react";

export interface KeyboardShortcutOptions {
  /** Called when Cmd/Ctrl+K is pressed — focus conversation search */
  onFocusSearch?: () => void;
  /** Called when Cmd/Ctrl+N is pressed — new conversation */
  onNewConversation?: () => void;
  /** Called when Escape is pressed — close any open modal/drawer/panel */
  onEscape?: () => void;
}

/**
 * useKeyboardShortcuts — registers global keyboard shortcuts for the chat UI.
 *
 * Shortcuts:
 * - Cmd/Ctrl+K → focus conversation search
 * - Cmd/Ctrl+N → new conversation
 * - Escape → close modal/drawer/artifact panel
 */
export function useKeyboardShortcuts({
  onFocusSearch,
  onNewConversation,
  onEscape,
}: KeyboardShortcutOptions) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const isMod = e.metaKey || e.ctrlKey;

      // Cmd/Ctrl+K — focus search
      if (isMod && e.key === "k") {
        e.preventDefault();
        onFocusSearch?.();
      }

      // Cmd/Ctrl+N — new conversation
      if (isMod && e.key === "n") {
        e.preventDefault();
        onNewConversation?.();
      }

      // Escape — close
      if (e.key === "Escape") {
        // Don't intercept if user is in an input/textarea (let default behavior work)
        const target = e.target as HTMLElement;
        if (
          target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable
        ) {
          return;
        }
        onEscape?.();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onFocusSearch, onNewConversation, onEscape]);
}
