"use client";

import * as React from "react";
import {
  Bot,
  ChevronDown,
  Check,
  Loader2,
  Sparkles,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { config } from "@/lib/config";
import { apiFetch } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Assistant configuration returned by the backend */
export interface AssistantConfig {
  id: string;
  name: string;
  description: string | null;
  model: string;
  tools_enabled: string[];
  is_active: boolean;
}

export interface AssistantSelectorProps {
  /** Currently selected assistant ID */
  selectedId: string | null;
  /** Callback when a new assistant is selected */
  onSelect: (assistant: AssistantConfig) => void;
  /** Disable the selector (e.g. while streaming) */
  disabled?: boolean;
  /** Additional class names */
  className?: string;
}

// ---------------------------------------------------------------------------
// Model → icon colour mapping (visual hint for model type)
// ---------------------------------------------------------------------------

function modelColor(model: string): string {
  if (model.includes("gpt-4")) return "text-violet-500";
  if (model.includes("gpt-3")) return "text-emerald-500";
  if (model.includes("claude")) return "text-orange-500";
  return "text-primary";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * AssistantSelector — dropdown/card UI to choose the assistant (agent type)
 * before chatting.
 *
 * Fetches the available assistants from the `/assistants` backend endpoint
 * and lets the user pick one. The selection persists for the current thread.
 */
export function AssistantSelector({
  selectedId,
  onSelect,
  disabled = false,
  className,
}: AssistantSelectorProps) {
  const [assistants, setAssistants] = React.useState<AssistantConfig[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [isOpen, setIsOpen] = React.useState(false);
  const dropdownRef = React.useRef<HTMLDivElement>(null);

  // Fetch assistants on mount
  React.useEffect(() => {
    let cancelled = false;

    async function fetchAssistants() {
      setIsLoading(true);
      setError(null);

      try {
        const res = await apiFetch(`/assistants?limit=50`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          const active: AssistantConfig[] = (data.assistants ?? []).filter(
            (a: AssistantConfig) => a.is_active,
          );
          setAssistants(active);

          // Auto-select the first assistant if nothing selected yet
          if (!selectedId && active.length > 0) {
            onSelect(active[0]);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load assistants",
          );
          // Provide a sensible fallback so the user can still chat
          const fallback: AssistantConfig = {
            id: config.assistantId,
            name: "Default Assistant",
            description: "General-purpose chat assistant",
            model: "gpt-4o",
            tools_enabled: [],
            is_active: true,
          };
          setAssistants([fallback]);
          if (!selectedId) onSelect(fallback);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    fetchAssistants();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Close dropdown on outside click
  React.useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Close on Escape
  React.useEffect(() => {
    function handleEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setIsOpen(false);
    }
    if (isOpen) {
      document.addEventListener("keydown", handleEsc);
      return () => document.removeEventListener("keydown", handleEsc);
    }
  }, [isOpen]);

  const selected = assistants.find((a) => a.id === selectedId) ?? null;

  return (
    <div ref={dropdownRef} className={cn("relative", className)}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen((o) => !o)}
        disabled={disabled || isLoading}
        className={cn(
          "flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2",
          "text-sm font-medium text-foreground shadow-sm transition-colors",
          "hover:bg-accent hover:text-accent-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          "disabled:pointer-events-none disabled:opacity-50",
        )}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        ) : (
          <Bot className={cn("h-4 w-4", selected ? modelColor(selected.model) : "text-muted-foreground")} />
        )}
        <span className="truncate max-w-[160px]">
          {isLoading
            ? "Loading…"
            : selected?.name ?? "Select assistant"}
        </span>
        <ChevronDown
          className={cn(
            "ml-auto h-3.5 w-3.5 text-muted-foreground transition-transform",
            isOpen && "rotate-180",
          )}
        />
      </button>

      {/* Error hint */}
      {error && (
        <p className="flex items-center gap-1 mt-1 text-[10px] text-amber-500">
          <AlertCircle className="h-3 w-3" />
          Using fallback — {error}
        </p>
      )}

      {/* Dropdown panel */}
      {isOpen && (
        <div
          role="listbox"
          className={cn(
            "absolute left-0 top-full z-50 mt-1 w-72 origin-top-left",
            "rounded-lg border border-border bg-card shadow-lg",
            "animate-in fade-in-0 zoom-in-95 duration-150",
          )}
        >
          <div className="p-1 max-h-64 overflow-y-auto">
            {assistants.length === 0 && !isLoading && (
              <p className="px-3 py-4 text-xs text-muted-foreground text-center">
                No assistants available
              </p>
            )}
            {assistants.map((assistant) => {
              const isSelected = assistant.id === selectedId;
              return (
                <button
                  key={assistant.id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => {
                    onSelect(assistant);
                    setIsOpen(false);
                  }}
                  className={cn(
                    "flex w-full items-start gap-3 rounded-md px-3 py-2.5 text-left",
                    "transition-colors hover:bg-accent",
                    isSelected && "bg-accent/50",
                  )}
                >
                  <Sparkles
                    className={cn(
                      "h-4 w-4 mt-0.5 shrink-0",
                      modelColor(assistant.model),
                    )}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate">
                        {assistant.name}
                      </span>
                      {isSelected && (
                        <Check className="h-3.5 w-3.5 text-primary shrink-0" />
                      )}
                    </div>
                    {assistant.description && (
                      <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                        {assistant.description}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] text-muted-foreground bg-secondary rounded px-1 py-0.5">
                        {assistant.model}
                      </span>
                      {assistant.tools_enabled.length > 0 && (
                        <span className="text-[10px] text-muted-foreground">
                          {assistant.tools_enabled.length} tool
                          {assistant.tools_enabled.length !== 1 ? "s" : ""}
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
