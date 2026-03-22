"use client";

import * as React from "react";
import { Check, Search, Shield, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiFetch } from "@/lib/api";
import { ScrollArea } from "@/components/ui/ScrollArea";
import type { SkillData } from "./SkillForm";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SkillSelectorProps {
  /** Currently selected skill IDs. */
  selectedIds: string[];
  /** Called when the selection changes. */
  onChange: (ids: string[]) => void;
  /** Disable the selector. */
  disabled?: boolean;
  /** Additional class names. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * SkillSelector — multi-select picker showing system + user skills.
 *
 * System skills (user_id = null) are visually distinguished from user skills.
 */
export function SkillSelector({
  selectedIds,
  onChange,
  disabled = false,
  className,
}: SkillSelectorProps) {
  const [skills, setSkills] = React.useState<SkillData[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [search, setSearch] = React.useState("");

  React.useEffect(() => {
    let cancelled = false;

    async function fetchSkills() {
      setIsLoading(true);
      try {
        const res = await apiFetch("/skills?limit=100");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          setSkills((data.skills ?? []).filter((s: SkillData) => s.is_active));
        }
      } catch {
        // Silently fail — no skills to display
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    fetchSkills();
    return () => { cancelled = true; };
  }, []);

  const filtered = React.useMemo(() => {
    if (!search.trim()) return skills;
    const q = search.toLowerCase();
    return skills.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q),
    );
  }, [skills, search]);

  const systemSkills = filtered.filter((s) => s.user_id === null);
  const userSkills = filtered.filter((s) => s.user_id !== null);

  function toggle(id: string) {
    if (disabled) return;
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((sid) => sid !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  }

  function renderSkill(skill: SkillData) {
    const isSelected = selectedIds.includes(skill.id);
    const isSystem = skill.user_id === null;

    return (
      <button
        key={skill.id}
        type="button"
        onClick={() => toggle(skill.id)}
        disabled={disabled}
        className={cn(
          "flex w-full items-start gap-3 rounded-md px-3 py-2 text-left transition-colors",
          "hover:bg-accent",
          isSelected && "bg-accent/60 ring-1 ring-primary/30",
          disabled && "opacity-50 cursor-not-allowed",
        )}
      >
        <div
          className={cn(
            "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
            isSelected
              ? "border-primary bg-primary text-primary-foreground"
              : "border-muted-foreground/40",
          )}
        >
          {isSelected && <Check className="h-3 w-3" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium truncate">{skill.name}</span>
            {isSystem ? (
              <Shield className="h-3 w-3 text-blue-500 shrink-0" aria-label="System skill" />
            ) : (
              <User className="h-3 w-3 text-muted-foreground shrink-0" aria-label="User skill" />
            )}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
            {skill.description}
          </p>
        </div>
      </button>
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search skills..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          disabled={disabled}
          className={cn(
            "flex h-9 w-full rounded-md border border-input bg-background pl-9 pr-3 py-2 text-sm",
            "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2",
            "focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
          )}
        />
      </div>

      <ScrollArea className="h-56 rounded-md border">
        <div className="p-1">
          {isLoading && (
            <p className="px-3 py-6 text-xs text-muted-foreground text-center">
              Loading skills...
            </p>
          )}

          {!isLoading && filtered.length === 0 && (
            <p className="px-3 py-6 text-xs text-muted-foreground text-center">
              {search ? "No skills match your search." : "No skills available."}
            </p>
          )}

          {/* System skills */}
          {systemSkills.length > 0 && (
            <>
              <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                System Skills
              </p>
              {systemSkills.map(renderSkill)}
            </>
          )}

          {/* User skills */}
          {userSkills.length > 0 && (
            <>
              <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mt-1">
                Your Skills
              </p>
              {userSkills.map(renderSkill)}
            </>
          )}
        </div>
      </ScrollArea>

      {selectedIds.length > 0 && (
        <p className="text-[11px] text-muted-foreground">
          {selectedIds.length} skill{selectedIds.length !== 1 ? "s" : ""} selected
        </p>
      )}
    </div>
  );
}
