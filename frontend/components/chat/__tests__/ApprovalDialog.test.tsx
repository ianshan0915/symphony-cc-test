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

  it("renders dialog with human-readable description when approval is provided", () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        onEdit={jest.fn()}
      />
    );
    expect(screen.getByText(/Permission Required/)).toBeInTheDocument();
    // Should show human-readable description, not raw tool name
    expect(screen.getByText(/Symphony wants to search the web/)).toBeInTheDocument();
  });

  it("shows tool args formatted as readable text", () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        onEdit={jest.fn()}
      />
    );
    // Should show the query in a readable format (appears in both description and summary)
    expect(screen.getAllByText(/test search/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Up to 5 results/)).toBeInTheDocument();
  });

  it("calls onApprove when Allow button is clicked", async () => {
    const onApprove = jest.fn();
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={onApprove}
        onReject={jest.fn()}
        onEdit={jest.fn()}
      />
    );

    const allowBtn = screen.getByRole("button", { name: /allow/i });
    await userEvent.click(allowBtn);
    expect(onApprove).toHaveBeenCalledWith("approval-1");
  });

  it("shows deny reason input on first Deny click, then calls onReject on second", async () => {
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
    const denyBtn = screen.getByRole("button", { name: /^deny$/i });
    await userEvent.click(denyBtn);

    // Should now show the reason textarea
    const reasonInput = screen.getByPlaceholderText(
      /why are you denying/i
    );
    expect(reasonInput).toBeInTheDocument();

    // Type a reason
    await userEvent.type(reasonInput, "Not safe");

    // Click confirm deny
    const confirmBtn = screen.getByRole("button", {
      name: /confirm deny/i,
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

    const allowBtn = screen.getByRole("button", { name: /allow/i });
    const denyBtn = screen.getByRole("button", { name: /deny/i });
    expect(allowBtn).toBeDisabled();
    expect(denyBtn).toBeDisabled();
  });

  it("shows 'Allowing...' text when submitting", () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        onEdit={jest.fn()}
        isSubmitting={true}
      />
    );

    expect(screen.getByText("Allowing...")).toBeInTheDocument();
  });

  it("has a 'View technical details' expandable section", async () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        onEdit={jest.fn()}
      />
    );

    const detailsBtn = screen.getByText(/View technical details/);
    expect(detailsBtn).toBeInTheDocument();

    // Click to expand
    await userEvent.click(detailsBtn);

    // Should show raw tool name and JSON args
    expect(screen.getByText("web_search")).toBeInTheDocument();
    expect(screen.getByText(/Edit arguments/)).toBeInTheDocument();
  });

  it("shows editable JSON textarea when Edit arguments is clicked in technical details", async () => {
    render(
      <ApprovalDialog
        approval={mockApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        onEdit={jest.fn()}
      />
    );

    // Expand technical details
    await userEvent.click(screen.getByText(/View technical details/));

    // Click edit
    await userEvent.click(screen.getByText(/Edit arguments/));

    const editTextarea = screen.getByLabelText(/edit tool arguments/i);
    expect(editTextarea).toBeInTheDocument();
    // Should be pre-populated with the current args
    expect(editTextarea).toHaveValue(
      JSON.stringify(mockApproval.toolArgs, null, 2)
    );

    // Footer should show Confirm Edit + Cancel
    expect(
      screen.getByRole("button", { name: /confirm edit/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /cancel/i })
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

    // Enter edit mode via technical details
    await userEvent.click(screen.getByText(/View technical details/));
    await userEvent.click(screen.getByText(/Edit arguments/));

    // Modify the args
    const editTextarea = screen.getByLabelText(/edit tool arguments/i);
    fireEvent.change(editTextarea, {
      target: { value: '{"query":"modified search","max_results":10}' },
    });

    // Confirm edit
    await userEvent.click(
      screen.getByRole("button", { name: /confirm edit/i })
    );

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
    await userEvent.click(screen.getByText(/View technical details/));
    await userEvent.click(screen.getByText(/Edit arguments/));

    // Enter invalid JSON
    const editTextarea = screen.getByLabelText(/edit tool arguments/i);
    fireEvent.change(editTextarea, { target: { value: "not valid json {" } });

    // Attempt confirm
    await userEvent.click(
      screen.getByRole("button", { name: /confirm edit/i })
    );

    // Should show error
    expect(screen.getByText(/invalid json/i)).toBeInTheDocument();
  });

  it("renders human-readable summary for execute tool", () => {
    const execApproval: ApprovalRequest = {
      id: "approval-2",
      threadId: "thread-1",
      toolName: "execute",
      toolArgs: { command: "rm -rf /tmp/test" },
      runId: "run-2",
      createdAt: new Date().toISOString(),
    };
    render(
      <ApprovalDialog
        approval={execApproval}
        onApprove={jest.fn()}
        onReject={jest.fn()}
        onEdit={jest.fn()}
      />
    );
    expect(screen.getByText(/Symphony wants to run a command/)).toBeInTheDocument();
    expect(screen.getAllByText(/rm -rf \/tmp\/test/).length).toBeGreaterThanOrEqual(1);
  });
});
