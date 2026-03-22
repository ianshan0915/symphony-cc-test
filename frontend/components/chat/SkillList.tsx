"use client";

import * as React from "react";
import {
  Plus,
  Pencil,
  Trash2,
  Shield,
  User,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { apiFetch, apiJson, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { ScrollArea } from "@/components/ui/ScrollArea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/Dialog";
import { SkillForm, type SkillData } from "./SkillForm";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SkillListProps {
  /** Controls dialog visibility. */
  open: boolean;
  /** Called when the dialog should close. */
  onOpenChange: (open: boolean) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * SkillList — browse and manage skills.
 *
 * Shows system skills (read-only) and user skills (editable/deletable).
 * Includes a "Create Skill" button that opens the SkillForm.
 */
export function SkillList({ open, onOpenChange }: SkillListProps) {
  const [skills, setSkills] = React.useState<SkillData[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Skill form state
  const [formOpen, setFormOpen] = React.useState(false);
  const [editingSkill, setEditingSkill] = React.useState<SkillData | null>(null);

  // Delete confirmation state
  const [deletingSkill, setDeletingSkill] = React.useState<SkillData | null>(null);
  const [isDeleting, setIsDeleting] = React.useState(false);

  const fetchSkills = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/skills?limit=100");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSkills((data.skills ?? []).filter((s: SkillData) => s.is_active));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load skills");
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (open) fetchSkills();
  }, [open, fetchSkills]);

  function handleCreate() {
    setEditingSkill(null);
    setFormOpen(true);
  }

  function handleEdit(skill: SkillData) {
    setEditingSkill(skill);
    setFormOpen(true);
  }

  async function handleDelete() {
    if (!deletingSkill) return;
    setIsDeleting(true);
    try {
      await apiFetch(`/skills/${deletingSkill.id}`, { method: "DELETE" });
      setSkills((prev) => prev.filter((s) => s.id !== deletingSkill.id));
      setDeletingSkill(null);
    } catch {
      // Keep dialog open on error
    } finally {
      setIsDeleting(false);
    }
  }

  function handleSaved() {
    fetchSkills();
  }

  const systemSkills = skills.filter((s) => s.user_id === null);
  const userSkills = skills.filter((s) => s.user_id !== null);

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Skills</DialogTitle>
            <DialogDescription>
              Browse system skills and manage your custom skills.
            </DialogDescription>
          </DialogHeader>

          <div className="flex justify-end">
            <Button size="sm" onClick={handleCreate}>
              <Plus className="mr-1.5 h-3.5 w-3.5" />
              Create Skill
            </Button>
          </div>

          {error && (
            <p className="flex items-center gap-1 text-sm text-destructive">
              <AlertCircle className="h-4 w-4" />
              {error}
            </p>
          )}

          <ScrollArea className="h-80 rounded-md border">
            <div className="p-1">
              {isLoading && (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              )}

              {!isLoading && skills.length === 0 && (
                <p className="px-3 py-12 text-xs text-muted-foreground text-center">
                  No skills found. Create your first skill!
                </p>
              )}

              {/* System skills */}
              {systemSkills.length > 0 && (
                <>
                  <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    System Skills
                  </p>
                  {systemSkills.map((skill) => (
                    <div
                      key={skill.id}
                      className="flex items-start gap-3 rounded-md px-3 py-2.5"
                    >
                      <Shield className="h-4 w-4 mt-0.5 text-blue-500 shrink-0" />
                      <div className="min-w-0 flex-1">
                        <span className="text-sm font-medium">{skill.name}</span>
                        <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                          {skill.description}
                        </p>
                      </div>
                      <span className="text-[10px] text-muted-foreground bg-secondary rounded px-1.5 py-0.5 shrink-0">
                        read-only
                      </span>
                    </div>
                  ))}
                </>
              )}

              {/* User skills */}
              {userSkills.length > 0 && (
                <>
                  <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mt-1">
                    Your Skills
                  </p>
                  {userSkills.map((skill) => (
                    <div
                      key={skill.id}
                      className="flex items-start gap-3 rounded-md px-3 py-2.5 group"
                    >
                      <User className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
                      <div className="min-w-0 flex-1">
                        <span className="text-sm font-medium">{skill.name}</span>
                        <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                          {skill.description}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          type="button"
                          onClick={() => handleEdit(skill)}
                          className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                          aria-label={`Edit ${skill.name}`}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeletingSkill(skill)}
                          className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                          aria-label={`Delete ${skill.name}`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          </ScrollArea>
        </DialogContent>
      </Dialog>

      {/* Skill create/edit form */}
      <SkillForm
        skill={editingSkill}
        open={formOpen}
        onOpenChange={setFormOpen}
        onSaved={handleSaved}
      />

      {/* Delete confirmation */}
      <Dialog open={!!deletingSkill} onOpenChange={() => setDeletingSkill(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete Skill</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &quot;{deletingSkill?.name}&quot;? This action
              cannot be undone. Any agents using this skill will no longer have access to it.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeletingSkill(null)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
