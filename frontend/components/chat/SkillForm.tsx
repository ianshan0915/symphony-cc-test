"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";
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
import { apiJson, ApiError } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Skill data returned by the backend. */
export interface SkillData {
  id: string;
  user_id: string | null;
  name: string;
  description: string;
  instructions: string;
  metadata: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SkillFormProps {
  /** When set, the form operates in "edit" mode. */
  skill?: SkillData | null;
  /** Controls dialog visibility. */
  open: boolean;
  /** Called when the dialog should close. */
  onOpenChange: (open: boolean) => void;
  /** Called after a successful create or update. */
  onSaved?: (skill: SkillData) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * SkillForm — create or edit a user-created skill.
 *
 * Renders inside a Dialog. Fields: name, description, instructions (markdown).
 */
export function SkillForm({ skill, open, onOpenChange, onSaved }: SkillFormProps) {
  const isEdit = !!skill;

  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [instructions, setInstructions] = React.useState("");
  const [isSaving, setIsSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Populate fields when editing
  React.useEffect(() => {
    if (skill) {
      setName(skill.name);
      setDescription(skill.description);
      setInstructions(skill.instructions);
    } else {
      setName("");
      setDescription("");
      setInstructions("");
    }
    setError(null);
  }, [skill, open]);

  const isValid = name.trim().length > 0 && description.trim().length > 0 && instructions.trim().length > 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid || isSaving) return;

    setIsSaving(true);
    setError(null);

    try {
      const payload = {
        name: name.trim(),
        description: description.trim(),
        instructions: instructions.trim(),
      };

      let saved: SkillData;
      if (isEdit && skill) {
        saved = await apiJson<SkillData>(`/skills/${skill.id}`, {
          method: "PUT",
          json: payload,
        });
      } else {
        saved = await apiJson<SkillData>("/skills", {
          method: "POST",
          json: payload,
        });
      }

      onSaved?.(saved);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save skill");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Skill" : "Create Skill"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update this skill's configuration."
              : "Define a reusable skill with markdown instructions for your agents."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name */}
          <div className="space-y-1.5">
            <label htmlFor="skill-name" className="text-sm font-medium">
              Name
            </label>
            <Input
              id="skill-name"
              placeholder="my-skill-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={64}
              disabled={isSaving}
            />
            <p className="text-[11px] text-muted-foreground">
              Lowercase letters, digits, and hyphens only (e.g. &quot;code-review&quot;).
            </p>
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <label htmlFor="skill-description" className="text-sm font-medium">
              Description
            </label>
            <Input
              id="skill-description"
              placeholder="What does this skill do?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={1024}
              disabled={isSaving}
            />
          </div>

          {/* Instructions */}
          <div className="space-y-1.5">
            <label htmlFor="skill-instructions" className="text-sm font-medium">
              Instructions
            </label>
            <textarea
              id="skill-instructions"
              placeholder="Markdown instructions for the agent when using this skill..."
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={8}
              disabled={isSaving}
              className={
                "flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm " +
                "ring-offset-background placeholder:text-muted-foreground " +
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 " +
                "disabled:cursor-not-allowed disabled:opacity-50 resize-y min-h-[120px]"
              }
            />
            <p className="text-[11px] text-muted-foreground">
              Supports Markdown. These instructions are injected into the agent&apos;s system prompt.
            </p>
          </div>

          {/* Error */}
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

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
              {isEdit ? "Save Changes" : "Create Skill"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
