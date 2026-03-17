import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { TasksSidebar } from "../TasksSidebar";
import type { AgentTask, TodoItem } from "@/lib/types";

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

const mockTodos: TodoItem[] = [
  {
    id: "todo-1",
    content: "Research the topic thoroughly",
    status: "completed",
  },
  {
    id: "todo-2",
    content: "Summarise key findings",
    status: "in_progress",
    priority: "high",
  },
  {
    id: "todo-3",
    content: "Write the final report",
    status: "pending",
    priority: "medium",
  },
];

// ---------------------------------------------------------------------------
// Existing task-only behaviour
// ---------------------------------------------------------------------------

describe("TasksSidebar — tasks only (backwards compatibility)", () => {
  it("renders empty state when no tasks and no todos", () => {
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

  it("shows progress bar with remaining tasks", () => {
    render(<TasksSidebar tasks={mockTasks} />);
    expect(screen.getByText("2 tasks remaining")).toBeInTheDocument();
  });

  it("shows all completed message when all tasks done", () => {
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

// ---------------------------------------------------------------------------
// Todo rendering
// ---------------------------------------------------------------------------

describe("TasksSidebar — structured todos", () => {
  it("renders the Agent Plan section when todos are provided", () => {
    render(<TasksSidebar tasks={[]} todos={mockTodos} />);
    expect(screen.getByText("Agent Plan")).toBeInTheDocument();
  });

  it("renders all todo content strings", () => {
    render(<TasksSidebar tasks={[]} todos={mockTodos} />);
    expect(screen.getByText("Research the topic thoroughly")).toBeInTheDocument();
    expect(screen.getByText("Summarise key findings")).toBeInTheDocument();
    expect(screen.getByText("Write the final report")).toBeInTheDocument();
  });

  it("shows correct progress count based on todo completion", () => {
    render(<TasksSidebar tasks={[]} todos={mockTodos} />);
    // 1 completed out of 3
    expect(screen.getByText("1/3")).toBeInTheDocument();
  });

  it("shows remaining count from pending/in_progress todos", () => {
    render(<TasksSidebar tasks={[]} todos={mockTodos} />);
    expect(screen.getByText("2 tasks remaining")).toBeInTheDocument();
  });

  it("shows all tasks completed when all todos are done", () => {
    const allDone: TodoItem[] = mockTodos.map((t) => ({
      ...t,
      status: "completed" as const,
    }));
    render(<TasksSidebar tasks={[]} todos={allDone} />);
    expect(screen.getByText("All tasks completed")).toBeInTheDocument();
  });

  it("renders priority badges for todos that have a priority", () => {
    render(<TasksSidebar tasks={[]} todos={mockTodos} />);
    // High priority badge
    expect(screen.getByText("High")).toBeInTheDocument();
    // Medium priority badge
    expect(screen.getByText("Med")).toBeInTheDocument();
  });

  it("does not render a priority badge for todos without priority", () => {
    const noPriority: TodoItem[] = [
      { id: "x", content: "No priority todo", status: "pending" },
    ];
    render(<TasksSidebar tasks={[]} todos={noPriority} />);
    expect(screen.queryByText("High")).not.toBeInTheDocument();
    expect(screen.queryByText("Med")).not.toBeInTheDocument();
    expect(screen.queryByText("Low")).not.toBeInTheDocument();
  });

  it("renders step numbers (1., 2., 3.) for ordered todos", () => {
    render(<TasksSidebar tasks={[]} todos={mockTodos} />);
    expect(screen.getByText("1.")).toBeInTheDocument();
    expect(screen.getByText("2.")).toBeInTheDocument();
    expect(screen.getByText("3.")).toBeInTheDocument();
  });

  it("shows Tool Calls section label when both todos and tasks are present", () => {
    render(<TasksSidebar tasks={mockTasks} todos={mockTodos} />);
    expect(screen.getByText("Agent Plan")).toBeInTheDocument();
    expect(screen.getByText("Tool Calls")).toBeInTheDocument();
  });

  it("does not show Tool Calls section label when only tasks are present (no todos)", () => {
    render(<TasksSidebar tasks={mockTasks} />);
    expect(screen.queryByText("Tool Calls")).not.toBeInTheDocument();
  });

  it("prefers todo progress over task progress when todos are present", () => {
    // 1 todo completed; 1 task completed — count should reflect todos (1/3), not tasks (1/3 coincidentally)
    // Use different counts to make the distinction testable
    const oneTodo: TodoItem[] = [
      { id: "a", content: "First step", status: "completed" },
      { id: "b", content: "Second step", status: "pending" },
    ];
    render(<TasksSidebar tasks={mockTasks} todos={oneTodo} />);
    // Progress should be 1/2 (todos) not 1/3 (tasks)
    expect(screen.getByText("1/2")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// todo_update event integration (via TasksSidebar prop updates)
// ---------------------------------------------------------------------------

describe("TasksSidebar — real-time todo status updates", () => {
  it("updates status indicator when todo transitions to in_progress", () => {
    const { rerender } = render(
      <TasksSidebar
        tasks={[]}
        todos={[{ id: "1", content: "Do something", status: "pending" }]}
      />
    );
    rerender(
      <TasksSidebar
        tasks={[]}
        todos={[{ id: "1", content: "Do something", status: "in_progress" }]}
      />
    );
    // Content still visible after transition
    expect(screen.getByText("Do something")).toBeInTheDocument();
    // 0 completed — counter stays at 0/1
    expect(screen.getByText("0/1")).toBeInTheDocument();
  });

  it("updates progress bar when todo completes", () => {
    const { rerender } = render(
      <TasksSidebar
        tasks={[]}
        todos={[{ id: "1", content: "Do something", status: "in_progress" }]}
      />
    );
    rerender(
      <TasksSidebar
        tasks={[]}
        todos={[{ id: "1", content: "Do something", status: "completed" }]}
      />
    );
    expect(screen.getByText("All tasks completed")).toBeInTheDocument();
    expect(screen.getByText("1/1")).toBeInTheDocument();
  });
});
