"use client";

import * as React from "react";
import { FileText, Code2, FileSpreadsheet, Globe, FileJson } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Artifact, ArtifactType } from "@/lib/types";

export interface ArtifactButtonProps {
  artifact: Artifact;
  isActive?: boolean;
  onClick: () => void;
  className?: string;
}

const typeConfig: Record<ArtifactType, { icon: React.ElementType; color: string }> = {
  code: { icon: Code2, color: "text-blue-500 bg-blue-500/10 border-blue-500/20" },
  document: { icon: FileText, color: "text-purple-500 bg-purple-500/10 border-purple-500/20" },
  markdown: { icon: FileText, color: "text-purple-500 bg-purple-500/10 border-purple-500/20" },
  html: { icon: Globe, color: "text-orange-500 bg-orange-500/10 border-orange-500/20" },
  csv: { icon: FileSpreadsheet, color: "text-green-600 bg-green-600/10 border-green-600/20" },
  json: { icon: FileJson, color: "text-amber-500 bg-amber-500/10 border-amber-500/20" },
  text: { icon: FileText, color: "text-muted-foreground bg-secondary border-border" },
};

/**
 * ArtifactButton — compact inline button shown in the chat when the agent
 * creates or modifies a file/document.  Clicking opens it in the ArtifactPanel.
 */
export function ArtifactButton({
  artifact,
  isActive = false,
  onClick,
  className,
}: ArtifactButtonProps) {
  const config = typeConfig[artifact.type] ?? typeConfig.text;
  const Icon = config.icon;

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 rounded-lg border px-3 py-2 text-left",
        "transition-all hover:shadow-sm",
        config.color,
        isActive && "ring-2 ring-primary/50 shadow-sm",
        className
      )}
      aria-label={`Open artifact: ${artifact.title}`}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium truncate">{artifact.title}</p>
        <p className="text-[10px] opacity-70 truncate">
          {artifact.language ?? artifact.type}
          {artifact.versions.length > 1 &&
            ` · v${artifact.versions.length}`}
        </p>
      </div>
      <span className="text-[10px] opacity-50">→</span>
    </button>
  );
}
