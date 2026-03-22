import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import "@testing-library/jest-dom";
import { CodeExecutionCard } from "../CodeExecutionCard";
import type { ToolCall } from "@/lib/types";

/** Helper: build a ToolCall with an execution result attached. */
function makeExecuteToolCall(overrides?: Partial<ToolCall>): ToolCall {
  return {
    id: "tc-exec-1",
    name: "execute",
    args: { command: "echo hello" },
    status: "completed",
    execution: {
      stdout: "hello\n",
      stderr: "",
      exitCode: 0,
    },
    ...overrides,
  };
}

describe("CodeExecutionCard", () => {
  // ---------------------------------------------------------------------------
  // Rendering basics
  // ---------------------------------------------------------------------------

  it("renders the tool name in the header", () => {
    render(<CodeExecutionCard toolCall={makeExecuteToolCall()} />);
    expect(screen.getByText("execute")).toBeInTheDocument();
  });

  it("renders the code-execution-card test id", () => {
    render(<CodeExecutionCard toolCall={makeExecuteToolCall()} />);
    expect(screen.getByTestId("code-execution-card")).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Exit code badge
  // ---------------------------------------------------------------------------

  it("shows a green exit-code badge for exit code 0", () => {
    render(<CodeExecutionCard toolCall={makeExecuteToolCall()} />);
    const badge = screen.getByTestId("exit-code-badge");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("exit 0");
    expect(badge.className).toMatch(/green/);
  });

  it("shows a red exit-code badge for non-zero exit code", () => {
    const toolCall = makeExecuteToolCall({
      execution: { stdout: "", stderr: "error\n", exitCode: 1 },
    });
    render(<CodeExecutionCard toolCall={toolCall} />);
    const badge = screen.getByTestId("exit-code-badge");
    expect(badge).toHaveTextContent("exit 1");
    expect(badge.className).toMatch(/red/);
  });

  // ---------------------------------------------------------------------------
  // Auto-expand for short output
  // ---------------------------------------------------------------------------

  it("auto-expands when output is short (≤ 500 chars)", async () => {
    await act(async () => {
      render(<CodeExecutionCard toolCall={makeExecuteToolCall()} />);
    });
    // Short stdout — should be visible without clicking
    expect(screen.getByTestId("stdout-section")).toBeInTheDocument();
    // Use a custom matcher because Testing Library normalises whitespace and
    // newline characters can split text across DOM nodes.
    expect(
      screen.getByText((content) => content.includes("hello"))
    ).toBeInTheDocument();
  });

  it("does NOT auto-expand when output exceeds the threshold", async () => {
    const longOutput = "x".repeat(501);
    const toolCall = makeExecuteToolCall({
      execution: { stdout: longOutput, stderr: "", exitCode: 0 },
    });
    await act(async () => {
      render(<CodeExecutionCard toolCall={toolCall} />);
    });
    // Output area should be hidden by default
    expect(screen.queryByTestId("stdout-section")).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Manual expand / collapse
  // ---------------------------------------------------------------------------

  it("expands output when the header button is clicked", async () => {
    const longOutput = "x".repeat(501);
    const toolCall = makeExecuteToolCall({
      execution: { stdout: longOutput, stderr: "", exitCode: 0 },
    });
    await act(async () => {
      render(<CodeExecutionCard toolCall={toolCall} />);
    });

    const button = screen.getByRole("button");
    fireEvent.click(button);
    expect(screen.getByTestId("stdout-section")).toBeInTheDocument();
  });

  it("collapses output when expanded header is clicked again", async () => {
    await act(async () => {
      render(<CodeExecutionCard toolCall={makeExecuteToolCall()} />);
    });

    const button = screen.getByRole("button");
    // Already expanded (short output) — click to collapse
    fireEvent.click(button);
    expect(screen.queryByTestId("stdout-section")).not.toBeInTheDocument();
  });

  it("sets aria-expanded correctly", async () => {
    await act(async () => {
      render(<CodeExecutionCard toolCall={makeExecuteToolCall()} />);
    });

    const button = screen.getByRole("button");
    // Auto-expanded
    expect(button).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "false");
  });

  // ---------------------------------------------------------------------------
  // stdout / stderr separation
  // ---------------------------------------------------------------------------

  it("renders stdout section when stdout is non-empty", async () => {
    await act(async () => {
      render(<CodeExecutionCard toolCall={makeExecuteToolCall()} />);
    });
    expect(screen.getByTestId("stdout-section")).toBeInTheDocument();
    expect(
      screen.getByText((content) => content.includes("hello"))
    ).toBeInTheDocument();
  });

  it("renders stderr section when stderr is non-empty", async () => {
    const toolCall = makeExecuteToolCall({
      execution: { stdout: "", stderr: "warning: something went wrong\n", exitCode: 2 },
    });
    await act(async () => {
      render(<CodeExecutionCard toolCall={toolCall} />);
    });
    // stderr is short — auto-expands
    expect(screen.getByTestId("stderr-section")).toBeInTheDocument();
    expect(
      screen.getByText((content) => content.includes("warning: something went wrong"))
    ).toBeInTheDocument();
  });

  it("renders both stdout and stderr sections when both are non-empty", async () => {
    const toolCall = makeExecuteToolCall({
      execution: {
        stdout: "normal output\n",
        stderr: "some warning\n",
        exitCode: 0,
      },
    });
    await act(async () => {
      render(<CodeExecutionCard toolCall={toolCall} />);
    });
    expect(screen.getByTestId("stdout-section")).toBeInTheDocument();
    expect(screen.getByTestId("stderr-section")).toBeInTheDocument();
  });

  it("shows '(no output)' when both stdout and stderr are empty", async () => {
    const toolCall = makeExecuteToolCall({
      execution: { stdout: "", stderr: "", exitCode: 0 },
    });
    await act(async () => {
      render(<CodeExecutionCard toolCall={toolCall} />);
    });
    // Component only auto-expands when output is non-empty; manually expand here.
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("(no output)")).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Running / pending state
  // ---------------------------------------------------------------------------

  it("shows a spinner when status is running", () => {
    const toolCall: ToolCall = {
      id: "tc-running",
      name: "execute",
      args: {},
      status: "running",
    };
    render(<CodeExecutionCard toolCall={toolCall} />);
    // Spinner svg should be present and have animate-spin
    const button = screen.getByRole("button");
    const svgs = button.querySelectorAll("svg");
    const hasSpinner = Array.from(svgs).some(
      (svg) =>
        svg.className.baseVal?.includes("animate-spin") ||
        svg.classList?.contains("animate-spin")
    );
    expect(hasSpinner).toBe(true);
  });

  it("shows a spinner when status is pending", () => {
    const toolCall: ToolCall = {
      id: "tc-pending",
      name: "execute",
      args: {},
      status: "pending",
    };
    render(<CodeExecutionCard toolCall={toolCall} />);
    const button = screen.getByRole("button");
    const svgs = button.querySelectorAll("svg");
    const hasSpinner = Array.from(svgs).some(
      (svg) =>
        svg.className.baseVal?.includes("animate-spin") ||
        svg.classList?.contains("animate-spin")
    );
    expect(hasSpinner).toBe(true);
  });

  it("does NOT show an exit-code badge while running", () => {
    const toolCall: ToolCall = {
      id: "tc-running",
      name: "execute",
      args: {},
      status: "running",
    };
    render(<CodeExecutionCard toolCall={toolCall} />);
    expect(screen.queryByTestId("exit-code-badge")).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Accessibility
  // ---------------------------------------------------------------------------

  it("has an accessible aria-label on the toggle button", () => {
    render(<CodeExecutionCard toolCall={makeExecuteToolCall()} />);
    expect(screen.getByRole("button")).toHaveAttribute(
      "aria-label",
      "Code execution: execute"
    );
  });

  it("has aria-label on exit-code badge", async () => {
    await act(async () => {
      render(<CodeExecutionCard toolCall={makeExecuteToolCall()} />);
    });
    expect(screen.getByTestId("exit-code-badge")).toHaveAttribute(
      "aria-label",
      "Exit code 0"
    );
  });

  // ---------------------------------------------------------------------------
  // className passthrough
  // ---------------------------------------------------------------------------

  it("applies the className prop to the root element", () => {
    const { container } = render(
      <CodeExecutionCard
        toolCall={makeExecuteToolCall()}
        className="my-custom-class"
      />
    );
    expect(container.firstChild).toHaveClass("my-custom-class");
  });
});
