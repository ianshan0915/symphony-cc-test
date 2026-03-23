/**
 * Human-readable labels, icons, and summary extractors for tool calls.
 *
 * Replaces raw tool names like "read_file" with user-friendly labels
 * like "Reading a file..." / "Read a file".
 */

export interface ToolLabelConfig {
  /** Emoji icon for this tool */
  icon: string;
  /** Label shown while the tool is running */
  runningLabel: string;
  /** Label shown after the tool completes */
  completedLabel: string;
  /** Extract a human-readable summary from tool args */
  summarize?: (args: Record<string, unknown>) => string | null;
}

const toolConfigs: Record<string, ToolLabelConfig> = {
  web_search: {
    icon: "🔍",
    runningLabel: "Searching the web…",
    completedLabel: "Searched the web",
    summarize: (args) => {
      const query = args.query as string | undefined;
      return query ? `"${query}"` : null;
    },
  },
  execute: {
    icon: "▶",
    runningLabel: "Running a command…",
    completedLabel: "Ran a command",
    summarize: (args) => {
      const cmd = (args.command as string | undefined) || (args.cmd as string | undefined);
      if (!cmd) return null;
      // Show first 60 chars of command
      return cmd.length > 60 ? `\`${cmd.slice(0, 60)}…\`` : `\`${cmd}\``;
    },
  },
  read_file: {
    icon: "📄",
    runningLabel: "Reading a file…",
    completedLabel: "Read a file",
    summarize: (args) => {
      const path = (args.path as string) || (args.file_path as string) || null;
      if (!path) return null;
      // Show just the filename
      const parts = path.split("/");
      return parts[parts.length - 1];
    },
  },
  write_file: {
    icon: "✏️",
    runningLabel: "Writing a file…",
    completedLabel: "Wrote a file",
    summarize: (args) => {
      const path = (args.path as string) || (args.file_path as string) || null;
      if (!path) return null;
      const parts = path.split("/");
      return parts[parts.length - 1];
    },
  },
  create_file: {
    icon: "➕",
    runningLabel: "Creating a file…",
    completedLabel: "Created a file",
    summarize: (args) => {
      const path = (args.path as string) || (args.file_path as string) || null;
      if (!path) return null;
      const parts = path.split("/");
      return parts[parts.length - 1];
    },
  },
  delete_file: {
    icon: "🗑️",
    runningLabel: "Deleting a file…",
    completedLabel: "Deleted a file",
    summarize: (args) => {
      const path = (args.path as string) || (args.file_path as string) || null;
      if (!path) return null;
      const parts = path.split("/");
      return parts[parts.length - 1];
    },
  },
  edit_file: {
    icon: "✏️",
    runningLabel: "Editing a file…",
    completedLabel: "Edited a file",
    summarize: (args) => {
      const path = (args.path as string) || (args.file_path as string) || null;
      if (!path) return null;
      const parts = path.split("/");
      return parts[parts.length - 1];
    },
  },
  list_files: {
    icon: "📂",
    runningLabel: "Listing files…",
    completedLabel: "Listed files",
    summarize: (args) => {
      const path = (args.path as string) || (args.directory as string) || null;
      return path || null;
    },
  },
};

const defaultConfig: ToolLabelConfig = {
  icon: "🔧",
  runningLabel: "Working…",
  completedLabel: "Done",
};

/**
 * Get the label config for a tool name.
 */
export function getToolLabel(toolName: string): ToolLabelConfig {
  return toolConfigs[toolName] ?? {
    ...defaultConfig,
    completedLabel: `Used ${toolName}`,
  };
}

/**
 * Get a human-readable summary line for a tool call.
 * Returns e.g. '📄 Read a file · config.py' or '🔍 Searching the web… · "AI agents"'
 */
export function getToolSummary(
  toolName: string,
  args: Record<string, unknown>,
  status: string
): { icon: string; label: string; detail: string | null } {
  const config = getToolLabel(toolName);
  const isRunning = status === "running" || status === "pending";
  const label = isRunning ? config.runningLabel : config.completedLabel;
  const detail = config.summarize?.(args) ?? null;
  return { icon: config.icon, label, detail };
}

/**
 * Group tool names for display in summary cards.
 * Returns counts by category, e.g. { "📄 files read": 12, "▶ commands run": 5 }
 */
export function groupToolCounts(
  toolNames: string[]
): Array<{ icon: string; count: number; label: string }> {
  const groups: Record<string, { icon: string; count: number; label: string }> = {};

  const groupLabels: Record<string, string> = {
    read_file: "files read",
    write_file: "files written",
    create_file: "files created",
    delete_file: "files deleted",
    edit_file: "files edited",
    list_files: "directories listed",
    execute: "commands run",
    web_search: "web searches",
  };

  for (const name of toolNames) {
    const config = getToolLabel(name);
    const groupKey = groupLabels[name] || `${name} calls`;
    if (!groups[groupKey]) {
      groups[groupKey] = { icon: config.icon, count: 0, label: groupKey };
    }
    groups[groupKey].count++;
  }

  return Object.values(groups);
}

/**
 * Generate a human-readable approval description.
 * e.g. "Symphony wants to search the web for "AI agents""
 */
export function getApprovalDescription(
  toolName: string,
  args: Record<string, unknown>
): { title: string; description: string; icon: string } {
  const config = getToolLabel(toolName);
  const detail = config.summarize?.(args);

  const descriptions: Record<string, string> = {
    web_search: `search the web${detail ? ` for ${detail}` : ""}`,
    execute: `run a command${detail ? `: ${detail}` : ""}`,
    read_file: `read a file${detail ? `: ${detail}` : ""}`,
    write_file: `write to a file${detail ? `: ${detail}` : ""}`,
    create_file: `create a file${detail ? `: ${detail}` : ""}`,
    delete_file: `delete a file${detail ? `: ${detail}` : ""}`,
    edit_file: `edit a file${detail ? `: ${detail}` : ""}`,
  };

  const desc = descriptions[toolName] || `use ${toolName}${detail ? `: ${detail}` : ""}`;

  return {
    title: "Permission Required",
    description: `Symphony wants to ${desc}`,
    icon: config.icon,
  };
}
