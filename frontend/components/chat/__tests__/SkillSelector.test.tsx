import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { SkillSelector } from "../SkillSelector";

// Mock ResizeObserver for Radix ScrollArea
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof ResizeObserver;

const mockSkillsResponse = {
  skills: [
    {
      id: "sk1",
      user_id: null,
      name: "research",
      description: "Research the web",
      instructions: "Search and summarize",
      metadata: {},
      is_active: true,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    },
    {
      id: "sk2",
      user_id: "user-123",
      name: "code-review",
      description: "Review code changes",
      instructions: "Review carefully",
      metadata: {},
      is_active: true,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    },
    {
      id: "sk3",
      user_id: null,
      name: "inactive-skill",
      description: "Should not appear",
      instructions: "N/A",
      metadata: {},
      is_active: false,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    },
  ],
  total: 3,
  offset: 0,
  limit: 100,
};

beforeEach(() => {
  jest.resetAllMocks();
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => mockSkillsResponse,
  });
});

describe("SkillSelector", () => {
  it("fetches and displays active skills grouped by type", async () => {
    render(
      <SkillSelector selectedIds={[]} onChange={jest.fn()} />,
    );

    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });

    expect(screen.getByText("code-review")).toBeInTheDocument();
    expect(screen.queryByText("inactive-skill")).not.toBeInTheDocument();

    expect(screen.getByText("System Skills")).toBeInTheDocument();
    expect(screen.getByText("Your Skills")).toBeInTheDocument();
  });

  it("calls onChange when a skill is toggled on", async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();

    render(
      <SkillSelector selectedIds={[]} onChange={onChange} />,
    );

    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });

    await user.click(screen.getByText("research"));
    expect(onChange).toHaveBeenCalledWith(["sk1"]);
  });

  it("calls onChange when a skill is toggled off", async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();

    render(
      <SkillSelector selectedIds={["sk1"]} onChange={onChange} />,
    );

    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });

    await user.click(screen.getByText("research"));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("shows selected count", async () => {
    render(
      <SkillSelector selectedIds={["sk1", "sk2"]} onChange={jest.fn()} />,
    );

    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });

    expect(screen.getByText("2 skills selected")).toBeInTheDocument();
  });

  it("filters skills by search query", async () => {
    const user = userEvent.setup();

    render(
      <SkillSelector selectedIds={[]} onChange={jest.fn()} />,
    );

    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("Search skills..."), "code");

    expect(screen.getByText("code-review")).toBeInTheDocument();
    expect(screen.queryByText("research")).not.toBeInTheDocument();
  });
});
