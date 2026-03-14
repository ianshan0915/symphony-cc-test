"use client";

import * as React from "react";
import {
  FileText,
  FilePlus,
  FileEdit,
  Trash2,
  Eye,
  FolderOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/utils";
import type { FileOperation } from "@/lib/types";

export interface FilesSidebarProps {
  /** List of file operations to display */
  files: FileOperation[];
  /** Additional class names */
  className?: string;
}

const operationConfig: Record<
  FileOperation["operation"],
  { icon: React.ElementType; color: string; label: string }
> = {
  read: { icon: Eye, color: "text-blue-500", label: "Read" },
  write: { icon: FileEdit, color: "text-amber-500", label: "Modified" },
  create: { icon: FilePlus, color: "text-green-600", label: "Created" },
  delete: { icon: Trash2, color: "text-destructive", label: "Deleted" },
};

/**
 * FilesSidebar — displays files the agent has read or written.
 *
 * Shows a list of file operations grouped by operation type,
 * with file paths, operation badges, and timestamps.
 */
export function FilesSidebar({ files, className }: FilesSidebarProps) {
  const readCount = files.filter((f) => f.operation === "read").length;
  const writeCount = files.filter(
    (f) => f.operation === "write" || f.operation === "create"
  ).length;

  return (
    <aside
      className={cn(
        "flex flex-col h-full w-72 border-l border-border bg-background",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <FolderOpen className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold">File Operations</h2>
        <span className="ml-auto text-xs text-muted-foreground">
          {files.length}
        </span>
      </div>

      {/* Summary badges */}
      {files.length > 0 && (
        <div className="flex gap-2 px-4 py-2 border-b border-border">
          {readCount > 0 && (
            <span className="inline-flex items-center gap-1 text-[10px] bg-blue-500/10 text-blue-500 rounded-full px-2 py-0.5">
              <Eye className="h-3 w-3" />
              {readCount} read
            </span>
          )}
          {writeCount > 0 && (
            <span className="inline-flex items-center gap-1 text-[10px] bg-amber-500/10 text-amber-500 rounded-full px-2 py-0.5">
              <FileEdit className="h-3 w-3" />
              {writeCount} written
            </span>
          )}
        </div>
      )}

      {/* File list */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
        {files.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <FileText className="h-8 w-8 mb-2 opacity-50" />
            <p className="text-xs">No file operations yet</p>
            <p className="text-[10px] mt-1">
              File reads and writes will appear here
            </p>
          </div>
        ) : (
          files.map((file) => <FileItem key={file.id} file={file} />)
        )}
      </div>
    </aside>
  );
}

function FileItem({ file }: { file: FileOperation }) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const config = operationConfig[file.operation];
  const OpIcon = config.icon;

  // Extract filename from path
  const fileName = file.filePath.split("/").pop() ?? file.filePath;
  const dirPath = file.filePath.slice(
    0,
    file.filePath.length - fileName.length
  );

  return (
    <div
      className={cn(
        "rounded-lg px-2 py-2 text-sm transition-colors hover:bg-accent/50 cursor-pointer",
        file.status === "failed" && "bg-destructive/5"
      )}
      onClick={() => setIsExpanded((prev) => !prev)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          setIsExpanded((prev) => !prev);
        }
      }}
    >
      <div className="flex items-start gap-2">
        <OpIcon className={cn("h-4 w-4 shrink-0 mt-0.5", config.color)} />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium truncate" title={file.filePath}>
            {fileName}
          </p>
          {dirPath && (
            <p
              className="text-[10px] text-muted-foreground truncate"
              title={dirPath}
            >
              {dirPath}
            </p>
          )}
          <div className="flex items-center gap-2 mt-0.5">
            <span
              className={cn(
                "text-[10px] rounded px-1 py-0.5",
                config.color,
                "bg-secondary"
              )}
            >
              {config.label}
            </span>
            <span className="text-[10px] text-muted-foreground">
              {formatRelativeTime(file.timestamp)}
            </span>
          </div>
        </div>
      </div>

      {/* Expanded preview */}
      {isExpanded && file.preview && (
        <div className="mt-2 ml-6">
          <pre className="text-[10px] bg-secondary rounded-md p-2 overflow-x-auto whitespace-pre-wrap break-all max-h-[100px] overflow-y-auto custom-scrollbar">
            {file.preview}
          </pre>
        </div>
      )}
    </div>
  );
}
