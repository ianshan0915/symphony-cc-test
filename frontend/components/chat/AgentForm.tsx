"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiJson, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/Dialog";
import { SkillSelector } from "./SkillSelector";
import type { AssistantConfig } from "@/lib/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SUPPORTED_MODELS = [
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4o-mini", label: "GPT-4o Mini" },
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
  { value: "claude-haiku-4-20250414", label: "Claude Haiku 4" },
  { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
] as const;

/** Common tools that can be enabled on an agent. */
const AVAILABLE_TOOLS = [
  { id: "web_search", label: "Web Search", description: "Search the internet" },
  { id: "file_tools", label: "File Tools", description: "Read and write files" },
  { id: "knowledge_base", label: "Knowledge Base", description: "Query knowledge base" },
] as const;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AgentFormProps {
  /** When set, the form operates in "edit" mode. */
  agent?: AssistantConfig | null;
  /** Controls dialog visibility. */
  open: boolean;
  /** Called when the dialog should close. */
  onOpenChange: (open: boolean) => void;
  /** Called after a successful create or update. */
  onSaved?: (agent: AssistantConfig) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * AgentForm — create or edit an agent (assistant) configuration.
 *
 * Fields: name, description, model (dropdown), skills (multi-select),
 * tools (multi-select), custom system prompt (optional textarea).
 */
export function AgentForm({ agent, open, onOpenChange, onSaved }: AgentFormProps) {
  const isEdit = !!agent;

  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [model, setModel] = React.useState("gpt-4o");
  const [skillIds, setSkillIds] = React.useState<string[]>([]);
  const [toolsEnabled, setToolsEnabled] = React.useState<string[]>([]);
  const [systemPrompt, setSystemPrompt] = React.useState("");
  const [isSaving, setIsSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Populate fields
  React.useEffect(() => {
    if (agent) {
      setName(agent.name);
      setDescription(agent.description ?? "");
      setModel(agent.model);
      setSkillIds(agent.skills.map((s) => s.id));
      setToolsEnabled(agent.tools_enabled);
      setSystemPrompt(agent.system_prompt ?? "");
    } else {
      setName("");
      setDescription("");
      setModel("gpt-4o");
      setSkillIds([]);
      setToolsEnabled([]);
      setSystemPrompt("");
    }
    setError(null);
  }, [agent, open]);

  const isValid = name.trim().length > 0;

  function toggleTool(toolId: string) {
    setToolsEnabled((prev) =>
      prev.includes(toolId) ? prev.filter((t) => t !== toolId) : [...prev, toolId],
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid || isSaving) return;

    setIsSaving(true);
    setError(null);

    try {
      const payload = {
        name: name.trim(),
        description: description.trim() || null,
        model,
        skill_ids: skillIds,
        tools_enabled: toolsEnabled,
        system_prompt: systemPrompt.trim() || null,
      };

      let saved: AssistantConfig;
      if (isEdit && agent) {
        saved = await apiJson<AssistantConfig>(`/assistants/${agent.id}`, {
          method: "PUT",
          json: payload,
        });
      } else {
        saved = await apiJson<AssistantConfig>("/assistants", {
          method: "POST",
          json: payload,
        });
      }

      onSaved?.(saved);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save agent");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Agent" : "Create Agent"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update this agent's configuration."
              : "Configure a new agent with skills, tools, and a model."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Name */}
          <div className="space-y-1.5">
            <label htmlFor="agent-name" className="text-sm font-medium">
              Name <span className="text-destructive">*</span>
            </label>
            <Input
              id="agent-name"
              placeholder="My Agent"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={255}
              disabled={isSaving}
            />
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <label htmlFor="agent-description" className="text-sm font-medium">
              Description
            </label>
            <Input
              id="agent-description"
              placeholder="What does this agent do?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={1000}
              disabled={isSaving}
            />
          </div>

          {/* Model */}
          <div className="space-y-1.5">
            <label htmlFor="agent-model" className="text-sm font-medium">
              Model
            </label>
            <select
              id="agent-model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={isSaving}
              className={cn(
                "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
                "ring-offset-background focus-visible:outline-none focus-visible:ring-2",
                "focus-visible:ring-ring focus-visible:ring-offset-2",
                "disabled:cursor-not-allowed disabled:opacity-50",
              )}
            >
              {SUPPORTED_MODELS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          {/* Skills */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Skills</label>
            <SkillSelector
              selectedIds={skillIds}
              onChange={setSkillIds}
              disabled={isSaving}
            />
          </div>

          {/* Tools */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Tools</label>
            <div className="space-y-1 rounded-md border p-2">
              {AVAILABLE_TOOLS.map((tool) => {
                const isChecked = toolsEnabled.includes(tool.id);
                return (
                  <button
                    key={tool.id}
                    type="button"
                    onClick={() => toggleTool(tool.id)}
                    disabled={isSaving}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left transition-colors",
                      "hover:bg-accent",
                      isChecked && "bg-accent/60",
                      isSaving && "opacity-50 cursor-not-allowed",
                    )}
                  >
                    <div
                      className={cn(
                        "flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                        isChecked
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-muted-foreground/40",
                      )}
                    >
                      {isChecked && (
                        <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
                          <path
                            d="M2 6l3 3 5-5"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                    </div>
                    <div>
                      <span className="text-sm font-medium">{tool.label}</span>
                      <p className="text-[11px] text-muted-foreground">
                        {tool.description}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* System Prompt */}
          <div className="space-y-1.5">
            <label htmlFor="agent-prompt" className="text-sm font-medium">
              Custom System Prompt{" "}
              <span className="text-muted-foreground font-normal">(optional)</span>
            </label>
            <textarea
              id="agent-prompt"
              placeholder="Additional instructions for this agent..."
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={4}
              disabled={isSaving}
              maxLength={10000}
              className={cn(
                "flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
                "ring-offset-background placeholder:text-muted-foreground",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                "disabled:cursor-not-allowed disabled:opacity-50 resize-y min-h-[80px]",
              )}
            />
          </div>

          {/* Error */}
          {error && <p className="text-sm text-destructive">{error}</p>}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSaving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!isValid || isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEdit ? "Save Changes" : "Create Agent"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
