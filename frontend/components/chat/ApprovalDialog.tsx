"use client";

import * as React from "react";
import {
  ShieldCheck,
  ChevronRight,
  ChevronDown,
  Pencil,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import { getApprovalDescription } from "@/lib/toolLabels";
import type { ApprovalRequest } from "@/lib/types";

export interface ApprovalDialogProps {
  /** The approval request to display, or null if no pending approval */
  approval: ApprovalRequest | null;
  /** Called when user approves the tool call */
  onApprove: (approvalId: string) => void;
  /** Called when user rejects the tool call */
  onReject: (approvalId: string, reason?: string) => void;
  /** Called when user edits and approves the tool call with modified args */
  onEdit: (approvalId: string, modifiedArgs: Record<string, unknown>) => void;
  /** Whether the approval action is in progress */
  isSubmitting?: boolean;
  /** Additional class names */
  className?: string;
}

type DialogMode = "idle" | "editing" | "rejecting";

/**
 * ApprovalDialog — human-friendly modal shown when the agent needs permission.
 *
 * Shows a plain-language description of what the agent wants to do,
 * with Allow/Deny buttons. Technical details and editing are available
 * under an expandable section for power users.
 */
export function ApprovalDialog({
  approval,
  onApprove,
  onReject,
  onEdit,
  isSubmitting = false,
  className,
}: ApprovalDialogProps) {
  const [rejectReason, setRejectReason] = React.useState("");
  const [mode, setMode] = React.useState<DialogMode>("idle");
  const [editArgsText, setEditArgsText] = React.useState("");
  const [editArgsError, setEditArgsError] = React.useState<string | null>(null);
  const [showTechnical, setShowTechnical] = React.useState(false);

  // Reset state when approval changes
  React.useEffect(() => {
    setRejectReason("");
    setMode("idle");
    setEditArgsText("");
    setEditArgsError(null);
    setShowTechnical(false);
  }, [approval?.id]);

  if (!approval) return null;

  const { title, description, icon } = getApprovalDescription(
    approval.toolName,
    approval.toolArgs
  );

  const handleAllow = () => {
    onApprove(approval.id);
  };

  const handleDeny = () => {
    if (mode === "rejecting") {
      onReject(approval.id, rejectReason || undefined);
    } else {
      setMode("rejecting");
    }
  };

  const handleEditClick = () => {
    if (mode === "editing") {
      // Attempt to parse and submit
      try {
        const parsed = JSON.parse(editArgsText) as Record<string, unknown>;
        setEditArgsError(null);
        onEdit(approval.id, parsed);
      } catch {
        setEditArgsError("Invalid JSON — please fix the syntax and try again.");
      }
    } else {
      setEditArgsText(JSON.stringify(approval.toolArgs, null, 2));
      setEditArgsError(null);
      setMode("editing");
    }
  };

  return (
    <Dialog open={!!approval} onOpenChange={() => {}}>
      <DialogContent
        className={cn("sm:max-w-[480px]", className)}
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-amber-500" />
            <DialogTitle>🛡️ {title}</DialogTitle>
          </div>
          <DialogDescription className="text-sm mt-2">
            {description}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {/* Human-readable summary card */}
          <div className="rounded-lg border border-border bg-secondary/30 p-3">
            <div className="flex items-start gap-2">
              <span className="text-lg" role="img" aria-hidden>
                {icon}
              </span>
              <div className="text-sm text-foreground">
                {formatArgsAsText(approval.toolName, approval.toolArgs)}
              </div>
            </div>
          </div>

          {/* Additional tool calls in the same turn */}
          {approval.additionalTools && approval.additionalTools.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">
                + {approval.additionalTools.length} additional tool{approval.additionalTools.length > 1 ? "s" : ""} in this action:
              </p>
              {approval.additionalTools.map((tool, idx) => {
                const extraDesc = getApprovalDescription(tool.name, tool.args);
                return (
                  <div key={idx} className="rounded-lg border border-border bg-secondary/30 p-2">
                    <div className="flex items-start gap-2">
                      <span className="text-sm" role="img" aria-hidden>
                        {extraDesc.icon}
                      </span>
                      <div className="text-xs text-foreground">
                        <span className="font-medium">{extraDesc.title}:</span>{" "}
                        {formatArgsAsText(tool.name, tool.args)}
                      </div>
                    </div>
                  </div>
                );
              })}
              <p className="text-xs text-muted-foreground italic">
                Your decision will apply to all tools above.
              </p>
            </div>
          )}

          {/* Reject reason input */}
          {mode === "rejecting" && (
            <div>
              <label
                htmlFor="reject-reason"
                className="text-xs font-medium text-muted-foreground mb-1.5 block"
              >
                Reason for denying (optional)
              </label>
              <textarea
                id="reject-reason"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Why are you denying this action?"
                className="w-full rounded-lg border border-border bg-secondary p-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                rows={2}
              />
            </div>
          )}

          {/* Edit args textarea (inside technical details) */}
          {mode === "editing" && (
            <div>
              <label
                htmlFor="edit-args"
                className="text-xs font-medium text-muted-foreground mb-1.5 block"
              >
                Edit Arguments (JSON)
              </label>
              <textarea
                id="edit-args"
                value={editArgsText}
                onChange={(e) => {
                  setEditArgsText(e.target.value);
                  setEditArgsError(null);
                }}
                className="w-full rounded-lg border border-border bg-secondary p-2 text-xs font-mono resize-none focus:outline-none focus:ring-2 focus:ring-ring max-h-[200px] overflow-y-auto"
                rows={6}
                aria-label="Edit tool arguments"
              />
              {editArgsError && (
                <p className="text-xs text-destructive mt-1">{editArgsError}</p>
              )}
            </div>
          )}

          {/* Expandable technical details */}
          {mode === "idle" && (
            <button
              type="button"
              onClick={() => setShowTechnical((prev) => !prev)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {showTechnical ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              View technical details
            </button>
          )}

          {showTechnical && mode === "idle" && (
            <div className="space-y-2">
              {/* Raw tool name */}
              <div className="text-xs text-muted-foreground">
                <span className="font-medium">Tool:</span> {approval.toolName}
              </div>

              {/* Raw JSON args */}
              {approval.toolArgs &&
                Object.keys(approval.toolArgs).length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">
                      Arguments
                    </p>
                    <pre className="text-xs bg-secondary rounded-lg p-2 overflow-x-auto whitespace-pre-wrap break-all max-h-[200px] overflow-y-auto custom-scrollbar">
                      {JSON.stringify(approval.toolArgs, null, 2)}
                    </pre>
                  </div>
                )}

              {/* Edit button inside technical details */}
              <button
                type="button"
                onClick={handleEditClick}
                disabled={isSubmitting}
                className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
              >
                <Pencil className="h-3 w-3" />
                Edit arguments
              </button>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-2">
          {mode === "editing" ? (
            <>
              <Button
                variant="outline"
                onClick={() => setMode("idle")}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                onClick={handleEditClick}
                disabled={isSubmitting}
              >
                Confirm Edit
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                onClick={handleDeny}
                disabled={isSubmitting}
              >
                {mode === "rejecting" ? "Confirm Deny" : "Deny"}
              </Button>
              <Button
                onClick={handleAllow}
                disabled={isSubmitting}
              >
                {isSubmitting ? "Allowing..." : "Allow"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Helpers — format args as human-readable text
// ---------------------------------------------------------------------------

function formatArgsAsText(
  toolName: string,
  args: Record<string, unknown>
): React.ReactNode {
  switch (toolName) {
    case "web_search": {
      const query = args.query as string | undefined;
      const maxResults = args.max_results as number | undefined;
      return (
        <div>
          {query && <p>Search for <strong>&ldquo;{query}&rdquo;</strong></p>}
          {maxResults && (
            <p className="text-xs text-muted-foreground mt-1">
              Up to {maxResults} results
            </p>
          )}
        </div>
      );
    }
    case "execute": {
      const cmd = (args.command as string) || (args.cmd as string);
      return (
        <div>
          {cmd && (
            <p>
              Run command:{" "}
              <code className="text-xs bg-secondary rounded px-1 py-0.5">
                {cmd}
              </code>
            </p>
          )}
        </div>
      );
    }
    case "read_file":
    case "write_file":
    case "create_file":
    case "delete_file":
    case "edit_file": {
      const path = (args.path as string) || (args.file_path as string);
      const opLabels: Record<string, string> = {
        read_file: "Read",
        write_file: "Write to",
        create_file: "Create",
        delete_file: "Delete",
        edit_file: "Edit",
      };
      return (
        <div>
          <p>
            {opLabels[toolName] || "Access"} file:{" "}
            <code className="text-xs bg-secondary rounded px-1 py-0.5">
              {path || "unknown"}
            </code>
          </p>
        </div>
      );
    }
    default: {
      // Fallback: show key-value pairs as simple text
      const entries = Object.entries(args);
      if (entries.length === 0) return <p>No additional details</p>;
      return (
        <div className="space-y-1">
          {entries.slice(0, 5).map(([key, val]) => (
            <p key={key} className="text-xs">
              <span className="font-medium capitalize">{key.replace(/_/g, " ")}:</span>{" "}
              {String(val)}
            </p>
          ))}
          {entries.length > 5 && (
            <p className="text-xs text-muted-foreground">
              +{entries.length - 5} more fields
            </p>
          )}
        </div>
      );
    }
  }
}
