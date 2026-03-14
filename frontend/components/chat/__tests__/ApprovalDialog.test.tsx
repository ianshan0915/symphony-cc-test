import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { ApprovalDialog } from "../ApprovalDialog";
import type { ApprovalRequest } from "@/lib/types";

const mockApproval: ApprovalRequest = {
  id: "approval-1",
  threadId: "thread-1",
  toolName: "web_search",
  toolArgs: { query: "test search", max_results: 5 },
  runId: "run-1",
  createdAt: new Date().toISOString(),
};

describe("ApprovalDialog", () => {
  it("renders nothing when approval is null", () => {
    const { container } = render(
      <ApprovalDialog
        approval={null}
        onApprove={jest.fn()}
        onReject={jest.fn()}
      />
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders dialog with tool name when approval is provided", () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
      />
    );
    expect(screen.getByText("Approval Required")).toBeInTheDocument();
    expect(screen.getByText("web_search")).toBeInTheDocument();
  });

  it("shows tool arguments in the dialog", () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
      />
    );
    expect(screen.getByText(/test search/)).toBeInTheDocument();
  });

  it("calls onApprove when Approve button is clicked", async () => {
    const onApprove = jest.fn();
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={onApprove}
        onReject={jest.fn()}
      />
    );

    const approveBtn = screen.getByRole("button", { name: /approve/i });
    await userEvent.click(approveBtn);
    expect(onApprove).toHaveBeenCalledWith("approval-1");
  });

  it("shows reject reason input on first Reject click, then calls onReject on second", async () => {
    const onReject = jest.fn();
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={onReject}
      />
    );

    // First click reveals the reason input
    const rejectBtn = screen.getByRole("button", { name: /reject/i });
    await userEvent.click(rejectBtn);

    // Should now show the reason textarea
    const reasonInput = screen.getByPlaceholderText(
      /why are you rejecting/i
    );
    expect(reasonInput).toBeInTheDocument();

    // Type a reason
    await userEvent.type(reasonInput, "Not safe");

    // Click confirm reject
    const confirmBtn = screen.getByRole("button", {
      name: /confirm reject/i,
    });
    await userEvent.click(confirmBtn);

    expect(onReject).toHaveBeenCalledWith("approval-1", "Not safe");
  });

  it("disables buttons when isSubmitting is true", () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        isSubmitting={true}
      />
    );

    const approveBtn = screen.getByRole("button", { name: /approv/i });
    const rejectBtn = screen.getByRole("button", { name: /reject/i });
    expect(approveBtn).toBeDisabled();
    expect(rejectBtn).toBeDisabled();
  });

  it("shows 'Approving...' text when submitting", () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        isSubmitting={true}
      />
    );

    expect(screen.getByText("Approving...")).toBeInTheDocument();
  });
});
