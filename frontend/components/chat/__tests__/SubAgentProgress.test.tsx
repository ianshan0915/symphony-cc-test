import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { SubAgentProgress } from "../SubAgentProgress";
import type { SubAgent } from "../SubAgentProgress";

const now = new Date().toISOString();

/**
 * Mock sub-agents matching the real backend V2 event payload format:
 * - id equals subagent_name (the stable key from the backend)
 * - name is the capitalised form of subagent_name
 * - type equals subagent_name (used for icon lookup)
 */
const mockSubAgents: SubAgent[] = [
  {
    id: "researcher",
    name: "Researcher",
    type: "researcher",
    status: "running",
    description: "Specialist for web research, data gathering, and source citation.",
    progressText: "Found 12 files matching pattern...",
    startedAt: now,
  },
  {
    id: "coder",
    name: "Coder",
    type: "coder",
    status: "completed",
    description: "Specialist for code generation, review, debugging, and technical implementation.",
    startedAt: now,
    completedAt: now,
  },
  {
    id: "writer",
    name: "Writer",
    type: "writer",
    status: "error",
    description: "Specialist for content writing, editing, and document creation.",
    startedAt: now,
    completedAt: now,
  },
];

describe("SubAgentProgress", () => {
  it("renders nothing when subAgents is empty", () => {
    const { container } = render(<SubAgentProgress subAgents={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders all sub-agents", () => {
    render(<SubAgentProgress subAgents={mockSubAgents} />);
    expect(screen.getByText("Researcher")).toBeInTheDocument();
    expect(screen.getByText("Coder")).toBeInTheDocument();
    expect(screen.getByText("Writer")).toBeInTheDocument();
  });

  it("shows the active count badge", () => {
    render(<SubAgentProgress subAgents={mockSubAgents} />);
    expect(screen.getByText("1 active")).toBeInTheDocument();
  });

  it("shows completed count when no agents are active", () => {
    const completed = mockSubAgents.filter((a) => a.status !== "running");
    render(<SubAgentProgress subAgents={completed} />);
    expect(screen.getByText("2 completed")).toBeInTheDocument();
  });

  it("shows status labels for each agent", () => {
    render(<SubAgentProgress subAgents={mockSubAgents} />);
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("auto-expands running agents and shows progress text", () => {
    render(<SubAgentProgress subAgents={mockSubAgents} />);
    // Running agent should be auto-expanded, showing progress text
    expect(
      screen.getByText("Found 12 files matching pattern..."),
    ).toBeInTheDocument();
  });

  it("shows description when expanded", () => {
    render(<SubAgentProgress subAgents={mockSubAgents} />);
    // Running agent is auto-expanded
    expect(
      screen.getByText("Specialist for web research, data gathering, and source citation."),
    ).toBeInTheDocument();
  });

  it("toggles expansion on click", async () => {
    const user = userEvent.setup();
    render(<SubAgentProgress subAgents={mockSubAgents} />);

    // Coder is not running, so collapsed by default. Click to expand.
    const coderButton = screen.getByText("Coder").closest("button")!;
    await user.click(coderButton);

    expect(
      screen.getByText("Specialist for code generation, review, debugging, and technical implementation."),
    ).toBeInTheDocument();

    // Click again to collapse
    await user.click(coderButton);
    expect(
      screen.queryByText("Specialist for code generation, review, debugging, and technical implementation."),
    ).not.toBeInTheDocument();
  });

  it("shows agent type badge when expanded", async () => {
    const user = userEvent.setup();
    render(<SubAgentProgress subAgents={mockSubAgents} />);

    // Running agent auto-expanded
    expect(screen.getByText("researcher")).toBeInTheDocument();

    // Expand completed agent
    const coderButton = screen.getByText("Coder").closest("button")!;
    await user.click(coderButton);
    expect(screen.getByText("coder")).toBeInTheDocument();
  });

  it("shows progressText for completed agents when expanded", async () => {
    const user = userEvent.setup();
    const completedWithProgress: SubAgent = {
      id: "researcher",
      name: "Researcher",
      type: "researcher",
      status: "completed",
      progressText: "Completed research summary text.",
      startedAt: now,
      completedAt: now,
    };
    render(<SubAgentProgress subAgents={[completedWithProgress]} />);

    // Expand the completed agent
    const button = screen.getByText("Researcher").closest("button")!;
    await user.click(button);

    // progressText should be visible even though agent is completed
    expect(
      screen.getByText("Completed research summary text."),
    ).toBeInTheDocument();
  });

  it("renders type-specific icon for researcher (no crash)", () => {
    const researcher: SubAgent = {
      id: "researcher",
      name: "Researcher",
      type: "researcher",
      status: "running",
      startedAt: now,
    };
    // Should render without throwing (Search icon replaces generic Bot icon)
    const { container } = render(<SubAgentProgress subAgents={[researcher]} />);
    expect(container.firstChild).not.toBeNull();
    expect(screen.getByText("Researcher")).toBeInTheDocument();
  });

  it("renders type-specific icon for coder (no crash)", () => {
    const coder: SubAgent = {
      id: "coder",
      name: "Coder",
      type: "coder",
      status: "running",
      startedAt: now,
    };
    const { container } = render(<SubAgentProgress subAgents={[coder]} />);
    expect(container.firstChild).not.toBeNull();
    expect(screen.getByText("Coder")).toBeInTheDocument();
  });

  it("renders type-specific icon for writer (no crash)", () => {
    const writer: SubAgent = {
      id: "writer",
      name: "Writer",
      type: "writer",
      status: "running",
      startedAt: now,
    };
    const { container } = render(<SubAgentProgress subAgents={[writer]} />);
    expect(container.firstChild).not.toBeNull();
    expect(screen.getByText("Writer")).toBeInTheDocument();
  });

  it("falls back to Bot icon for unknown type (no crash)", () => {
    const unknown: SubAgent = {
      id: "custom-agent",
      name: "Custom",
      type: "unknown_type",
      status: "running",
      startedAt: now,
    };
    const { container } = render(<SubAgentProgress subAgents={[unknown]} />);
    expect(container.firstChild).not.toBeNull();
    expect(screen.getByText("Custom")).toBeInTheDocument();
  });
});
