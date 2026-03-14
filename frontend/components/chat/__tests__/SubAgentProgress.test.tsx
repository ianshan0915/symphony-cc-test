import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { SubAgentProgress } from "../SubAgentProgress";
import type { SubAgent } from "../SubAgentProgress";

const now = new Date().toISOString();

const mockSubAgents: SubAgent[] = [
  {
    id: "sa-1",
    name: "Explore agent",
    type: "explore",
    status: "running",
    description: "Searching for relevant files",
    progressText: "Found 12 files matching pattern...",
    startedAt: now,
  },
  {
    id: "sa-2",
    name: "Plan agent",
    type: "plan",
    status: "completed",
    description: "Designed implementation strategy",
    startedAt: now,
    completedAt: now,
  },
  {
    id: "sa-3",
    name: "Test runner",
    type: "test",
    status: "error",
    description: "Running test suite",
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
    expect(screen.getByText("Explore agent")).toBeInTheDocument();
    expect(screen.getByText("Plan agent")).toBeInTheDocument();
    expect(screen.getByText("Test runner")).toBeInTheDocument();
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
      screen.getByText("Searching for relevant files"),
    ).toBeInTheDocument();
  });

  it("toggles expansion on click", async () => {
    const user = userEvent.setup();
    render(<SubAgentProgress subAgents={mockSubAgents} />);

    // Plan agent is not running, so collapsed by default. Click to expand.
    const planButton = screen.getByText("Plan agent").closest("button")!;
    await user.click(planButton);

    expect(
      screen.getByText("Designed implementation strategy"),
    ).toBeInTheDocument();

    // Click again to collapse
    await user.click(planButton);
    expect(
      screen.queryByText("Designed implementation strategy"),
    ).not.toBeInTheDocument();
  });

  it("shows agent type badge when expanded", async () => {
    const user = userEvent.setup();
    render(<SubAgentProgress subAgents={mockSubAgents} />);

    // Running agent auto-expanded
    expect(screen.getByText("explore")).toBeInTheDocument();

    // Expand completed agent
    const planButton = screen.getByText("Plan agent").closest("button")!;
    await user.click(planButton);
    expect(screen.getByText("plan")).toBeInTheDocument();
  });
});
