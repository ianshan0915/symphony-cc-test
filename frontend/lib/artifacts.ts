/**
 * Artifact detection and extraction utilities.
 *
 * Determines when tool calls produce artifacts and extracts metadata
 * (type, language, title) from file paths and content.
 */

import type { Artifact, ArtifactType, ArtifactVersion } from "./types";

// ---------------------------------------------------------------------------
// File extension → artifact type / language mapping
// ---------------------------------------------------------------------------

const EXT_MAP: Record<string, { type: ArtifactType; language?: string }> = {
  // Code
  ".py": { type: "code", language: "python" },
  ".js": { type: "code", language: "javascript" },
  ".ts": { type: "code", language: "typescript" },
  ".tsx": { type: "code", language: "tsx" },
  ".jsx": { type: "code", language: "jsx" },
  ".java": { type: "code", language: "java" },
  ".go": { type: "code", language: "go" },
  ".rs": { type: "code", language: "rust" },
  ".rb": { type: "code", language: "ruby" },
  ".php": { type: "code", language: "php" },
  ".c": { type: "code", language: "c" },
  ".cpp": { type: "code", language: "cpp" },
  ".h": { type: "code", language: "c" },
  ".cs": { type: "code", language: "csharp" },
  ".swift": { type: "code", language: "swift" },
  ".kt": { type: "code", language: "kotlin" },
  ".sh": { type: "code", language: "bash" },
  ".bash": { type: "code", language: "bash" },
  ".zsh": { type: "code", language: "bash" },
  ".sql": { type: "code", language: "sql" },
  ".r": { type: "code", language: "r" },
  ".yaml": { type: "code", language: "yaml" },
  ".yml": { type: "code", language: "yaml" },
  ".toml": { type: "code", language: "toml" },
  ".xml": { type: "code", language: "xml" },
  ".css": { type: "code", language: "css" },
  ".scss": { type: "code", language: "scss" },
  ".less": { type: "code", language: "less" },
  ".vue": { type: "code", language: "vue" },
  ".svelte": { type: "code", language: "svelte" },
  ".dockerfile": { type: "code", language: "dockerfile" },

  // Documents
  ".md": { type: "markdown" },
  ".mdx": { type: "markdown" },
  ".txt": { type: "text" },
  ".rst": { type: "text" },

  // Data
  ".json": { type: "json", language: "json" },
  ".jsonl": { type: "json", language: "json" },
  ".csv": { type: "csv" },
  ".tsv": { type: "csv" },

  // Web
  ".html": { type: "html", language: "html" },
  ".htm": { type: "html", language: "html" },
  ".svg": { type: "html", language: "svg" },
};

// Tools that produce artifacts
const ARTIFACT_WRITE_TOOLS = new Set([
  "write_file",
  "create_file",
  "edit_file",
]);

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Returns true when a tool call should create or update an artifact.
 */
export function isArtifactProducingTool(toolName: string): boolean {
  return ARTIFACT_WRITE_TOOLS.has(toolName);
}

/**
 * Detect artifact type and language from a file path.
 */
export function detectArtifactType(
  filePath: string
): { type: ArtifactType; language?: string } {
  const lower = filePath.toLowerCase();
  const ext = "." + lower.split(".").pop();
  return EXT_MAP[ext] ?? { type: "text" };
}

/**
 * Extract a display title from a file path.
 */
export function titleFromPath(filePath: string): string {
  return filePath.split("/").pop() ?? filePath;
}

/**
 * Create an artifact from a tool call that writes a file.
 *
 * Called when we see a write_file / create_file / edit_file tool call
 * and have the content (either from args or from the tool result).
 */
export function createArtifactFromToolCall(opts: {
  id: string;
  filePath: string;
  content: string;
  toolCallId?: string;
}): Artifact {
  const { type, language } = detectArtifactType(opts.filePath);
  const now = new Date().toISOString();

  const version: ArtifactVersion = {
    content: opts.content,
    timestamp: now,
    source: "agent",
  };

  return {
    id: opts.id,
    title: titleFromPath(opts.filePath),
    content: opts.content,
    type,
    language,
    filePath: opts.filePath,
    versions: [version],
    createdAt: now,
    updatedAt: now,
    sourceToolCallId: opts.toolCallId,
  };
}

/**
 * Update an existing artifact with new content, pushing a new version.
 */
export function updateArtifactContent(
  artifact: Artifact,
  content: string,
  source: "agent" | "user"
): Artifact {
  const now = new Date().toISOString();
  const version: ArtifactVersion = { content, timestamp: now, source };

  return {
    ...artifact,
    content,
    versions: [...artifact.versions, version],
    updatedAt: now,
  };
}

/**
 * Try to extract file content from tool call args.
 *
 * Different tools use different arg names:
 * - write_file: { path, content } or { file_path, content }
 * - create_file: { path, content }
 * - edit_file: { path, new_content } or { path, content }
 */
export function extractContentFromArgs(
  args: Record<string, unknown>
): { filePath: string; content: string } | null {
  const filePath =
    (args.path as string) ||
    (args.file_path as string) ||
    (args.filename as string);
  const content =
    (args.content as string) ||
    (args.new_content as string) ||
    (args.text as string);

  if (filePath && content) {
    return { filePath, content };
  }
  return null;
}
