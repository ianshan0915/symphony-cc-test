"use client";

import * as React from "react";
import {
  Bot,
  ChevronDown,
  Check,
  Loader2,
  Sparkles,
  AlertCircle,
  Plus,
  Shield,
  User,
  Pencil,
  Trash2,
  BookOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { config } from "@/lib/config";
import { apiFetch } from "@/lib/api";
import { AgentForm } from "./AgentForm";
import { SkillList } from "./SkillList";
import type { AssistantConfig } from "@/lib/types";

// ---------------------------------------------------------------------------
// Re-export for backward compatibility
// ---------------------------------------------------------------------------

export type { AssistantConfig } from "@/lib/types";

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
// Model icon colour mapping (visual hint for model type)
// ---------------------------------------------------------------------------

function modelColor(model: string): string {
  if (model.includes("gpt-4")) return "text-violet-500";
  if (model.includes("gpt-3")) return "text-emerald-500";
  if (model.includes("claude")) return "text-orange-500";
  return "text-primary";
}

// ---------------------------------------------------------------------------
// Helper: determine if an assistant is system-created
// ---------------------------------------------------------------------------

function isSystemAssistant(a: AssistantConfig): boolean {
  return a.user_id === undefined || a.user_id === null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * AssistantSelector — dropdown/card UI to choose the assistant (agent type)
 * before chatting.
 *
 * Fetches the available assistants from the `/assistants` backend endpoint
 * and lets the user pick one. Groups system agents vs user agents. Includes
 * "Create Agent" and "Manage Skills" actions.
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

  // Agent form state
  const [agentFormOpen, setAgentFormOpen] = React.useState(false);
  const [editingAgent, setEditingAgent] = React.useState<AssistantConfig | null>(null);

  // Skill list state
  const [skillListOpen, setSkillListOpen] = React.useState(false);

  // Delete confirmation state
  const [deletingAgent, setDeletingAgent] = React.useState<AssistantConfig | null>(null);

  // Fetch assistants
  const fetchAssistants = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const res = await apiFetch(`/assistants?limit=50`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const active: AssistantConfig[] = (data.assistants ?? []).filter(
        (a: AssistantConfig) => a.is_active,
      );
      setAssistants(active);

      // Auto-select the default assistant, falling back to the first one
      if (!selectedId && active.length > 0) {
        const defaultAssistant = active.find(
          (a) => a.metadata?.is_default === true,
        );
        onSelect(defaultAssistant ?? active[0]);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load assistants",
      );
      // Provide a sensible fallback so the user can still chat
      const fallback: AssistantConfig = {
        id: config.assistantId,
        name: "Default Assistant",
        description: "General-purpose chat assistant",
        model: "gpt-4o",
        system_prompt: null,
        tools_enabled: [],
        metadata: { is_default: true },
        skills: [],
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setAssistants([fallback]);
      if (!selectedId) onSelect(fallback);
    } finally {
      setIsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  React.useEffect(() => {
    fetchAssistants();
  }, [fetchAssistants]);

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

  // Group assistants
  const systemAgents = assistants.filter(isSystemAssistant);
  const userAgents = assistants.filter((a) => !isSystemAssistant(a));

  function handleCreateAgent() {
    setEditingAgent(null);
    setAgentFormOpen(true);
    setIsOpen(false);
  }

  function handleEditAgent(agent: AssistantConfig, e: React.MouseEvent) {
    e.stopPropagation();
    setEditingAgent(agent);
    setAgentFormOpen(true);
    setIsOpen(false);
  }

  function handleDeleteAgent(agent: AssistantConfig, e: React.MouseEvent) {
    e.stopPropagation();
    setDeletingAgent(agent);
    setIsOpen(false);
  }

  async function confirmDelete() {
    if (!deletingAgent) return;
    try {
      await apiFetch(`/assistants/${deletingAgent.id}`, { method: "DELETE" });
      // If deleted agent was selected, auto-select another
      if (deletingAgent.id === selectedId) {
        const remaining = assistants.filter((a) => a.id !== deletingAgent.id);
        if (remaining.length > 0) onSelect(remaining[0]);
      }
      fetchAssistants();
    } catch {
      // Silently fail
    } finally {
      setDeletingAgent(null);
    }
  }

  function handleAgentSaved() {
    fetchAssistants();
  }

  function renderAssistantItem(assistant: AssistantConfig) {
    const isSelected = assistant.id === selectedId;
    const isSystem = isSystemAssistant(assistant);
    const skillCount = assistant.skills?.length ?? 0;
    const toolCount = assistant.tools_enabled?.length ?? 0;

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
          "flex w-full items-start gap-3 rounded-md px-3 py-2.5 text-left group/item",
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
            {isSystem ? (
              <Shield className="h-3 w-3 text-blue-500 shrink-0" aria-label="System agent" />
            ) : (
              <User className="h-3 w-3 text-muted-foreground shrink-0" aria-label="Your agent" />
            )}
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
            {skillCount > 0 && (
              <span className="text-[10px] text-muted-foreground">
                {skillCount} skill{skillCount !== 1 ? "s" : ""}
              </span>
            )}
            {toolCount > 0 && (
              <span className="text-[10px] text-muted-foreground">
                {toolCount} tool{toolCount !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </div>
        {/* Edit/delete actions for user-owned agents */}
        {!isSystem && (
          <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover/item:opacity-100 transition-opacity">
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => handleEditAgent(assistant, e)}
              onKeyDown={(e) => { if (e.key === "Enter") handleEditAgent(assistant, e as unknown as React.MouseEvent); }}
              className="p-1 rounded hover:bg-background/80 text-muted-foreground hover:text-foreground transition-colors"
              aria-label={`Edit ${assistant.name}`}
            >
              <Pencil className="h-3 w-3" />
            </span>
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => handleDeleteAgent(assistant, e)}
              onKeyDown={(e) => { if (e.key === "Enter") handleDeleteAgent(assistant, e as unknown as React.MouseEvent); }}
              className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
              aria-label={`Delete ${assistant.name}`}
            >
              <Trash2 className="h-3 w-3" />
            </span>
          </div>
        )}
      </button>
    );
  }

  return (
    <>
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
              ? "Loading\u2026"
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
              "absolute left-0 top-full z-50 mt-1 w-80 origin-top-left",
              "rounded-lg border border-border bg-card shadow-lg",
              "animate-in fade-in-0 zoom-in-95 duration-150",
            )}
          >
            <div className="p-1 max-h-80 overflow-y-auto">
              {assistants.length === 0 && !isLoading && (
                <p className="px-3 py-4 text-xs text-muted-foreground text-center">
                  No assistants available
                </p>
              )}

              {/* System agents group */}
              {systemAgents.length > 0 && (
                <>
                  <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    System Agents
                  </p>
                  {systemAgents.map(renderAssistantItem)}
                </>
              )}

              {/* User agents group */}
              {userAgents.length > 0 && (
                <>
                  <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mt-1">
                    Your Agents
                  </p>
                  {userAgents.map(renderAssistantItem)}
                </>
              )}
            </div>

            {/* Action buttons */}
            <div className="border-t border-border p-1">
              <button
                type="button"
                onClick={handleCreateAgent}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-left",
                  "transition-colors hover:bg-accent text-muted-foreground hover:text-foreground",
                )}
              >
                <Plus className="h-4 w-4" />
                Create Agent
              </button>
              <button
                type="button"
                onClick={() => {
                  setSkillListOpen(true);
                  setIsOpen(false);
                }}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-left",
                  "transition-colors hover:bg-accent text-muted-foreground hover:text-foreground",
                )}
              >
                <BookOpen className="h-4 w-4" />
                Manage Skills
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Agent create/edit form */}
      <AgentForm
        agent={editingAgent}
        open={agentFormOpen}
        onOpenChange={setAgentFormOpen}
        onSaved={handleAgentSaved}
      />

      {/* Skill management list */}
      <SkillList open={skillListOpen} onOpenChange={setSkillListOpen} />

      {/* Delete confirmation dialog */}
      {deletingAgent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="fixed inset-0 bg-black/80"
            onClick={() => setDeletingAgent(null)}
          />
          <div className="relative z-50 w-full max-w-sm rounded-lg border bg-background p-6 shadow-lg">
            <h3 className="text-lg font-semibold">Delete Agent</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Are you sure you want to delete &quot;{deletingAgent.name}&quot;? This action
              cannot be undone.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeletingAgent(null)}
                className={cn(
                  "inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium",
                  "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
                  "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDelete}
                className={cn(
                  "inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium",
                  "bg-destructive text-destructive-foreground hover:bg-destructive/90",
                  "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
