import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
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
        onEdit={jest.fn()}
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
        onEdit={jest.fn()}
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
        onEdit={jest.fn()}
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
        onEdit={jest.fn()}
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
        onEdit={jest.fn()}
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
        onEdit={jest.fn()}
        isSubmitting={true}
      />
    );

    const approveBtn = screen.getByRole("button", { name: /approv/i });
    const rejectBtn = screen.getByRole("button", { name: /reject/i });
    const editBtn = screen.getByRole("button", { name: /edit/i });
    expect(approveBtn).toBeDisabled();
    expect(rejectBtn).toBeDisabled();
    expect(editBtn).toBeDisabled();
  });

  it("shows 'Approving...' text when submitting", () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        onEdit={jest.fn()}
        isSubmitting={true}
      />
    );

    expect(screen.getByText("Approving...")).toBeInTheDocument();
  });

  it("shows Edit button in initial state", () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        onEdit={jest.fn()}
      />
    );

    expect(screen.getByRole("button", { name: /^edit$/i })).toBeInTheDocument();
  });

  it("shows editable JSON textarea when Edit is clicked", async () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        onEdit={jest.fn()}
      />
    );

    const editBtn = screen.getByRole("button", { name: /^edit$/i });
    await userEvent.click(editBtn);

    const editTextarea = screen.getByLabelText(/edit tool arguments/i);
    expect(editTextarea).toBeInTheDocument();
    // Should be pre-populated with the current args
    expect(editTextarea).toHaveValue(
      JSON.stringify(mockApproval.toolArgs, null, 2)
    );

    // Button should now say "Confirm Edit"
    expect(
      screen.getByRole("button", { name: /confirm edit/i })
    ).toBeInTheDocument();
  });

  it("calls onEdit with modified args when Confirm Edit is clicked", async () => {
    const onEdit = jest.fn();
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        onEdit={onEdit}
      />
    );

    // Enter edit mode
    const editBtn = screen.getByRole("button", { name: /^edit$/i });
    await userEvent.click(editBtn);

    // Modify the args (use fireEvent.change to avoid userEvent escaping curly braces)
    const editTextarea = screen.getByLabelText(/edit tool arguments/i);
    fireEvent.change(editTextarea, {
      target: { value: '{"query":"modified search","max_results":10}' },
    });

    // Confirm edit
    const confirmEditBtn = screen.getByRole("button", {
      name: /confirm edit/i,
    });
    await userEvent.click(confirmEditBtn);

    expect(onEdit).toHaveBeenCalledWith("approval-1", {
      query: "modified search",
      max_results: 10,
    });
  });

  it("shows an error message when Confirm Edit is clicked with invalid JSON", async () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        onEdit={jest.fn()}
      />
    );

    // Enter edit mode
    const editBtn = screen.getByRole("button", { name: /^edit$/i });
    await userEvent.click(editBtn);

    // Enter invalid JSON (use fireEvent.change to avoid userEvent escaping curly braces)
    const editTextarea = screen.getByLabelText(/edit tool arguments/i);
    fireEvent.change(editTextarea, { target: { value: "not valid json {" } });

    // Attempt confirm
    const confirmEditBtn = screen.getByRole("button", {
      name: /confirm edit/i,
    });
    await userEvent.click(confirmEditBtn);

    // Should show error, not call onEdit
    expect(screen.getByText(/invalid json/i)).toBeInTheDocument();
  });

  it("clicking Edit hides the reject reason input if it was shown", async () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        onEdit={jest.fn()}
      />
    );

    // Show reject input
    await userEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(
      screen.getByPlaceholderText(/why are you rejecting/i)
    ).toBeInTheDocument();

    // Switch to edit mode
    await userEvent.click(screen.getByRole("button", { name: /^edit$/i }));

    // Reject input should be gone, edit textarea should be shown
    expect(
      screen.queryByPlaceholderText(/why are you rejecting/i)
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText(/edit tool arguments/i)).toBeInTheDocument();
  });
});
