"use client";

import * as React from "react";
import { ShieldAlert, CheckCircle2, XCircle, Wrench } from "lucide-react";
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
import type { ApprovalRequest } from "@/lib/types";

export interface ApprovalDialogProps {
  /** The approval request to display, or null if no pending approval */
  approval: ApprovalRequest | null;
  /** Called when user approves the tool call */
  onApprove: (approvalId: string) => void;
  /** Called when user rejects the tool call */
  onReject: (approvalId: string, reason?: string) => void;
  /** Whether the approval action is in progress */
  isSubmitting?: boolean;
  /** Additional class names */
  className?: string;
}

/**
 * ApprovalDialog — modal dialog shown when the agent encounters a tool call
 * that requires human approval before execution.
 *
 * Displays the tool name, arguments, and provides approve/reject buttons.
 */
export function ApprovalDialog({
  approval,
  onApprove,
  onReject,
  isSubmitting = false,
  className,
}: ApprovalDialogProps) {
  const [rejectReason, setRejectReason] = React.useState("");
  const [showRejectInput, setShowRejectInput] = React.useState(false);

  // Reset state when approval changes
  React.useEffect(() => {
    setRejectReason("");
    setShowRejectInput(false);
  }, [approval?.id]);

  if (!approval) return null;

  const handleApprove = () => {
    onApprove(approval.id);
  };

  const handleReject = () => {
    if (showRejectInput) {
      onReject(approval.id, rejectReason || undefined);
    } else {
      setShowRejectInput(true);
    }
  };

  return (
    <Dialog open={!!approval} onOpenChange={() => {}}>
      <DialogContent
        className={cn("sm:max-w-[520px]", className)}
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-amber-500" />
            <DialogTitle>Approval Required</DialogTitle>
          </div>
          <DialogDescription>
            The agent wants to execute a tool that requires your approval before
            proceeding.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Tool name */}
          <div className="flex items-center gap-2 rounded-lg border border-border bg-card p-3">
            <Wrench className="h-4 w-4 text-muted-foreground shrink-0" />
            <div>
              <p className="text-sm font-medium">{approval.toolName}</p>
              <p className="text-xs text-muted-foreground">Tool call</p>
            </div>
          </div>

          {/* Arguments */}
          {approval.toolArgs &&
            Object.keys(approval.toolArgs).length > 0 && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-1.5">
                  Arguments
                </p>
                <pre className="text-xs bg-secondary rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-all max-h-[200px] overflow-y-auto custom-scrollbar">
                  {JSON.stringify(approval.toolArgs, null, 2)}
                </pre>
              </div>
            )}

          {/* Reject reason input */}
          {showRejectInput && (
            <div>
              <label
                htmlFor="reject-reason"
                className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-1.5 block"
              >
                Reason for rejection (optional)
              </label>
              <textarea
                id="reject-reason"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Why are you rejecting this action?"
                className="w-full rounded-lg border border-border bg-secondary p-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                rows={2}
              />
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={handleReject}
            disabled={isSubmitting}
            className="gap-1.5"
          >
            <XCircle className="h-4 w-4" />
            {showRejectInput ? "Confirm Reject" : "Reject"}
          </Button>
          <Button
            onClick={handleApprove}
            disabled={isSubmitting}
            className="gap-1.5"
          >
            <CheckCircle2 className="h-4 w-4" />
            {isSubmitting ? "Approving..." : "Approve"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
