"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  X,
  FileText,
  Code2,
  Eye,
  Pencil,
  Copy,
  Check,
  Download,
  History,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import type { Artifact, ArtifactVersion } from "@/lib/types";

export interface ArtifactPanelProps {
  /** The artifact to display, or null to hide the panel */
  artifact: Artifact | null;
  /** Called when user edits the artifact content */
  onUpdate: (id: string, content: string) => void;
  /** Called when user closes the panel */
  onClose: () => void;
  /** Additional class names */
  className?: string;
}

type PanelMode = "preview" | "edit" | "history";

/**
 * ArtifactPanel — side panel that displays an artifact with preview, edit,
 * and version history modes.
 *
 * Inspired by Claude Artifacts and ChatGPT Canvas:
 * - Preview mode: rendered markdown/code with syntax highlighting
 * - Edit mode: full-height textarea for direct editing
 * - History mode: browse and restore previous versions
 */
export function ArtifactPanel({
  artifact,
  onUpdate,
  onClose,
  className,
}: ArtifactPanelProps) {
  const [mode, setMode] = React.useState<PanelMode>("preview");
  const [editContent, setEditContent] = React.useState("");
  const [copied, setCopied] = React.useState(false);
  const [historyIndex, setHistoryIndex] = React.useState(-1);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  // Reset state when artifact changes
  React.useEffect(() => {
    if (artifact) {
      setEditContent(artifact.content);
      setMode("preview");
      setHistoryIndex(-1);
    }
  }, [artifact?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync edit content when artifact content changes externally (agent updates)
  React.useEffect(() => {
    if (artifact && mode !== "edit") {
      setEditContent(artifact.content);
    }
  }, [artifact?.content]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!artifact) return null;

  const handleCopy = async () => {
    const content = mode === "edit" ? editContent : artifact.content;
    try {
      await navigator.clipboard.writeText(content);
    } catch {
      // fallback
      const ta = document.createElement("textarea");
      ta.value = content;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const content = mode === "edit" ? editContent : artifact.content;
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = artifact.title;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSaveEdit = () => {
    if (editContent !== artifact.content) {
      onUpdate(artifact.id, editContent);
    }
    setMode("preview");
  };

  const handleCancelEdit = () => {
    setEditContent(artifact.content);
    setMode("preview");
  };

  const handleStartEdit = () => {
    setEditContent(artifact.content);
    setMode("edit");
    // Focus textarea after render
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const handleRestoreVersion = (version: ArtifactVersion) => {
    onUpdate(artifact.id, version.content);
    setMode("preview");
    setHistoryIndex(-1);
  };

  const typeIcon = artifact.type === "code" ? Code2 : FileText;
  const TypeIcon = typeIcon;

  return (
    <aside
      className={cn(
        "flex flex-col h-full w-[480px] min-w-[380px] border-l border-border bg-background",
        "animate-in slide-in-from-right-4 duration-200",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-3 shrink-0">
        <TypeIcon className="h-4 w-4 text-muted-foreground shrink-0" />
        <div className="min-w-0 flex-1">
          <h2
            className="text-sm font-semibold truncate"
            title={artifact.title}
          >
            {artifact.title}
          </h2>
          {artifact.language && (
            <span className="text-[10px] text-muted-foreground">
              {artifact.language}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          aria-label="Close artifact panel"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-1 border-b border-border px-3 py-1.5 shrink-0">
        {/* Mode tabs */}
        <div className="flex items-center gap-0.5 bg-secondary rounded-md p-0.5">
          <button
            onClick={() => {
              if (mode === "edit") handleCancelEdit();
              else setMode("preview");
            }}
            className={cn(
              "flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors",
              mode === "preview"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Eye className="h-3 w-3" />
            Preview
          </button>
          <button
            onClick={handleStartEdit}
            className={cn(
              "flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors",
              mode === "edit"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Pencil className="h-3 w-3" />
            Edit
          </button>
          <button
            onClick={() => setMode(mode === "history" ? "preview" : "history")}
            className={cn(
              "flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors",
              mode === "history"
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <History className="h-3 w-3" />
            History
            {artifact.versions.length > 1 && (
              <span className="text-[10px] bg-primary/10 text-primary rounded-full px-1">
                {artifact.versions.length}
              </span>
            )}
          </button>
        </div>

        <div className="flex-1" />

        {/* Action buttons */}
        <button
          onClick={handleCopy}
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          title={copied ? "Copied!" : "Copy content"}
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-green-500" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </button>
        <button
          onClick={handleDownload}
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          title="Download file"
        >
          <Download className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-hidden">
        {mode === "preview" && (
          <div className="h-full overflow-y-auto p-4 custom-scrollbar">
            <ArtifactPreview artifact={artifact} />
          </div>
        )}

        {mode === "edit" && (
          <div className="flex flex-col h-full">
            <textarea
              ref={textareaRef}
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className={cn(
                "flex-1 w-full resize-none p-4 font-mono text-sm",
                "bg-background text-foreground",
                "focus:outline-none",
                "custom-scrollbar"
              )}
              spellCheck={artifact.type !== "code"}
            />
            <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-2 shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancelEdit}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleSaveEdit}
                disabled={editContent === artifact.content}
              >
                Save changes
              </Button>
            </div>
          </div>
        )}

        {mode === "history" && (
          <VersionHistory
            versions={artifact.versions}
            currentIndex={historyIndex}
            onSelect={setHistoryIndex}
            onRestore={handleRestoreVersion}
          />
        )}
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Renders the artifact content based on its type */
function ArtifactPreview({ artifact }: { artifact: Artifact }) {
  if (artifact.type === "markdown" || artifact.type === "document") {
    return (
      <div className="prose-chat">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {artifact.content}
        </ReactMarkdown>
      </div>
    );
  }

  if (artifact.type === "html") {
    return (
      <div className="rounded-lg border border-border overflow-hidden">
        <iframe
          srcDoc={artifact.content}
          title={artifact.title}
          className="w-full min-h-[600px] h-[calc(100vh-200px)] bg-white"
          sandbox="allow-scripts allow-same-origin"
        />
      </div>
    );
  }

  // code, json, csv, text — show as preformatted text
  return (
    <pre
      className={cn(
        "text-sm font-mono whitespace-pre-wrap break-words",
        "bg-secondary rounded-lg p-4",
        "overflow-x-auto"
      )}
    >
      <code>{artifact.content}</code>
    </pre>
  );
}

/** Browse and restore previous versions of the artifact */
function VersionHistory({
  versions,
  currentIndex,
  onSelect,
  onRestore,
}: {
  versions: ArtifactVersion[];
  currentIndex: number;
  onSelect: (i: number) => void;
  onRestore: (v: ArtifactVersion) => void;
}) {
  // Show versions newest first
  const reversedVersions = [...versions].reverse();
  const selectedIdx = currentIndex >= 0 ? currentIndex : 0;
  const selectedVersion = reversedVersions[selectedIdx];

  return (
    <div className="flex flex-col h-full">
      {/* Version list */}
      <div className="border-b border-border px-3 py-2 shrink-0">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onSelect(Math.min(selectedIdx + 1, reversedVersions.length - 1))}
            disabled={selectedIdx >= reversedVersions.length - 1}
            className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30"
            aria-label="Older version"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-xs text-muted-foreground flex-1 text-center">
            Version {reversedVersions.length - selectedIdx} of{" "}
            {reversedVersions.length}
            <span className="ml-2 text-[10px]">
              ({selectedVersion?.source === "user" ? "user edit" : "agent"})
            </span>
          </span>
          <button
            onClick={() => onSelect(Math.max(selectedIdx - 1, 0))}
            disabled={selectedIdx <= 0}
            className="p-1 rounded text-muted-foreground hover:text-foreground disabled:opacity-30"
            aria-label="Newer version"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
        {selectedVersion && (
          <p className="text-[10px] text-muted-foreground text-center mt-0.5">
            {new Date(selectedVersion.timestamp).toLocaleString()}
          </p>
        )}
      </div>

      {/* Version content preview */}
      <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
        {selectedVersion && (
          <pre className="text-xs font-mono whitespace-pre-wrap break-words bg-secondary rounded-lg p-3">
            {selectedVersion.content}
          </pre>
        )}
      </div>

      {/* Restore button */}
      {selectedIdx > 0 && selectedVersion && (
        <div className="border-t border-border px-4 py-2 shrink-0">
          <Button
            size="sm"
            variant="outline"
            className="w-full"
            onClick={() => onRestore(selectedVersion)}
          >
            Restore this version
          </Button>
        </div>
      )}
    </div>
  );
}
