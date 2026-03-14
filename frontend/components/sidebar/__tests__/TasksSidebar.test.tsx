import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { TasksSidebar } from "../TasksSidebar";
import type { AgentTask } from "@/lib/types";

const mockTasks: AgentTask[] = [
  {
    id: "t1",
    name: "Search the web",
    description: "Searching for: test query",
    status: "completed",
    toolName: "web_search",
    createdAt: new Date().toISOString(),
    completedAt: new Date().toISOString(),
  },
  {
    id: "t2",
    name: "Execute knowledge_base search",
    status: "in_progress",
    toolName: "search_knowledge_base",
    createdAt: new Date().toISOString(),
  },
  {
    id: "t3",
    name: "Execute file_write",
    status: "awaiting_approval",
    toolName: "file_write",
    createdAt: new Date().toISOString(),
  },
];

describe("TasksSidebar", () => {
  it("renders empty state when no tasks", () => {
    render(<TasksSidebar tasks={[]} />);
    expect(screen.getByText("No tasks yet")).toBeInTheDocument();
    expect(
      screen.getByText("Tasks will appear as the agent plans actions")
    ).toBeInTheDocument();
  });

  it("renders task list with correct count", () => {
    render(<TasksSidebar tasks={mockTasks} />);
    expect(screen.getByText("Agent Tasks")).toBeInTheDocument();
    expect(screen.getByText("1/3")).toBeInTheDocument(); // 1 completed out of 3
  });

  it("shows task names", () => {
    render(<TasksSidebar tasks={mockTasks} />);
    expect(screen.getByText("Search the web")).toBeInTheDocument();
    expect(
      screen.getByText("Execute knowledge_base search")
    ).toBeInTheDocument();
  });

  it("shows tool name badges", () => {
    render(<TasksSidebar tasks={mockTasks} />);
    expect(screen.getByText("web_search")).toBeInTheDocument();
    expect(screen.getByText("search_knowledge_base")).toBeInTheDocument();
  });

  it("shows progress bar", () => {
    render(<TasksSidebar tasks={mockTasks} />);
    expect(screen.getByText("2 tasks remaining")).toBeInTheDocument();
  });

  it("shows all completed message when all done", () => {
    const completedTasks: AgentTask[] = [
      {
        id: "t1",
        name: "Done task",
        status: "completed",
        createdAt: new Date().toISOString(),
        completedAt: new Date().toISOString(),
      },
    ];
    render(<TasksSidebar tasks={completedTasks} />);
    expect(screen.getByText("All tasks completed")).toBeInTheDocument();
  });
});
