"use client";

import * as React from "react";
import { BookOpen, Loader2, Save, RotateCcw } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { apiJson } from "@/lib/api";
import type { MemoryResponse } from "@/lib/types";

/** Maximum content size in bytes (512 KiB — mirrors backend limit). */
const MAX_BYTES = 524_288;

export interface MemoryModalProps {
  /** Whether the modal is open. */
  open: boolean;
  /** Called when the modal should close. */
  onClose: () => void;
}

type Status = "idle" | "loading" | "saving" | "saved" | "error";

/**
 * MemoryModal — view and edit the persistent AGENTS.md memory.
 *
 * Fetches the user's current memory content on open, allows editing in a
 * textarea, and saves changes via `PUT /memory`.  Content size is validated
 * client-side before submission to match the backend 512 KiB limit.
 */
export function MemoryModal({ open, onClose }: MemoryModalProps) {
  const [content, setContent] = React.useState("");
  const [savedContent, setSavedContent] = React.useState("");
  const [status, setStatus] = React.useState<Status>("idle");
  const [errorMessage, setErrorMessage] = React.useState("");

  // Ref to track the "saved" auto-dismiss timer so it can be cancelled on
  // unmount, preventing a stale state update after the modal closes.
  const savedTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cancel any pending "saved" dismiss timer when the component unmounts.
  React.useEffect(() => {
    return () => {
      if (savedTimerRef.current !== null) {
        clearTimeout(savedTimerRef.current);
      }
    };
  }, []);

  // Fetch memory content when the modal opens.
  React.useEffect(() => {
    if (!open) return;

    let cancelled = false;

    async function fetchMemory() {
      // Explicitly reset to a clean slate before each load so stale content
      // from a previous open is never briefly visible on re-open.
      setContent("");
      setSavedContent("");
      setStatus("loading");
      setErrorMessage("");
      try {
        const data = await apiJson<MemoryResponse>("/memory");
        if (!cancelled) {
          setContent(data.content);
          setSavedContent(data.content);
          setStatus("idle");
        }
      } catch {
        if (!cancelled) {
          setErrorMessage("Failed to load memory. Please try again.");
          setStatus("error");
        }
      }
    }

    fetchMemory();
    return () => {
      cancelled = true;
    };
  }, [open]);

  const isDirty = content !== savedContent;

  const byteLength = React.useMemo(
    () => new Blob([content]).size,
    [content]
  );
  const isOverLimit = byteLength > MAX_BYTES;

  async function handleSave() {
    if (!isDirty || isOverLimit) return;

    setStatus("saving");
    setErrorMessage("");
    try {
      const data = await apiJson<MemoryResponse>("/memory", {
        method: "PUT",
        json: { content },
      });
      setContent(data.content);
      setSavedContent(data.content);
      setStatus("saved");
      // Auto-dismiss "saved" indicator after 2 s.  Cancel any previous timer
      // first to avoid duplicate dismissals when the user saves rapidly.
      if (savedTimerRef.current !== null) clearTimeout(savedTimerRef.current);
      savedTimerRef.current = setTimeout(() => {
        savedTimerRef.current = null;
        setStatus("idle");
      }, 2000);
      // Reset "saved" indicator after 2 s.
      setTimeout(() => setStatus("idle"), 2000);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to save memory.";
      setErrorMessage(message);
      setStatus("error");
    }
  }

  function handleReset() {
    setContent(savedContent);
    setStatus("idle");
    setErrorMessage("");
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      // Discard unsaved edits so the modal is clean on the next open.
      if (isDirty) handleReset();
      onClose();
    }
  }

  const kib = (byteLength / 1024).toFixed(1);
  const maxKib = (MAX_BYTES / 1024).toFixed(0);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="max-w-2xl h-[80vh] flex flex-col gap-0 p-0"
        data-testid="memory-modal"
      >
        {/* Header */}
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-muted-foreground" />
            <DialogTitle>Agent Memory</DialogTitle>
          </div>
          <DialogDescription>
            This content is loaded by the agent at the start of every
            conversation. Edit it to provide persistent context, preferences,
            or project conventions.
          </DialogDescription>
        </DialogHeader>

        {/* Body */}
        <div className="flex-1 overflow-hidden px-6 py-4 flex flex-col gap-3">
          {status === "loading" ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-muted-foreground">
              <Loader2 className="h-6 w-6 animate-spin" />
              <p className="text-sm">Loading memory…</p>
            </div>
          ) : (
            <>
              {/* Status banner */}
              {status === "error" && (
                <div
                  role="alert"
                  className="rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-sm text-destructive"
                >
                  {errorMessage}
                </div>
              )}
              {status === "saved" && (
                <div
                  role="status"
                  className="rounded-md bg-green-500/10 border border-green-500/30 px-3 py-2 text-sm text-green-700 dark:text-green-400"
                >
                  Memory saved successfully.
                </div>
              )}

              {/* Textarea */}
              <textarea
                aria-label="Agent memory content"
                value={content}
                onChange={(e) => {
                  setContent(e.target.value);
                  if (status === "saved" || status === "error") {
                    setStatus("idle");
                    setErrorMessage("");
                  }
                }}
                className={
                  "flex-1 w-full resize-none rounded-md border bg-background px-3 py-2 " +
                  "text-sm font-mono leading-relaxed text-foreground " +
                  "focus:outline-none focus:ring-2 focus:ring-ring " +
                  "placeholder:text-muted-foreground " +
                  (isOverLimit ? "border-destructive" : "border-input")
                }
                style={{ minHeight: 0, height: "100%" }}
                placeholder="# Agent Memory&#10;&#10;Add persistent context, preferences, or project conventions here…"
                disabled={status === "saving"}
                spellCheck={false}
              />

              {/* Byte counter */}
              <p
                className={
                  "text-right text-xs " +
                  (isOverLimit
                    ? "text-destructive font-medium"
                    : "text-muted-foreground")
                }
              >
                {kib} / {maxKib} KiB
                {isOverLimit && " — content exceeds the 512 KiB limit"}
              </p>
            </>
          )}
        </div>

        {/* Footer */}
        <DialogFooter className="px-6 pb-6 pt-4 border-t border-border shrink-0">
          <Button
            type="button"
            variant="ghost"
            onClick={handleReset}
            disabled={!isDirty || status === "loading" || status === "saving"}
          >
            <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
            Reset
          </Button>
          <Button
            type="button"
            onClick={handleSave}
            disabled={
              !isDirty ||
              isOverLimit ||
              status === "loading" ||
              status === "saving"
            }
          >
            {status === "saving" ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="mr-1.5 h-3.5 w-3.5" />
            )}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
