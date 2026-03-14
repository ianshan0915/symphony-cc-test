import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { AssistantSelector } from "../AssistantSelector";

// Mock fetch
const mockAssistants = {
  assistants: [
    {
      id: "a1",
      name: "General Assistant",
      description: "General-purpose chat",
      model: "gpt-4o",
      tools_enabled: ["web_search", "code_exec"],
      is_active: true,
    },
    {
      id: "a2",
      name: "Code Assistant",
      description: "Specialized for coding tasks",
      model: "claude-3-opus",
      tools_enabled: ["code_exec"],
      is_active: true,
    },
    {
      id: "a3",
      name: "Inactive Bot",
      description: "Should not appear",
      model: "gpt-3.5-turbo",
      tools_enabled: [],
      is_active: false,
    },
  ],
  total: 3,
  offset: 0,
  limit: 50,
};

beforeEach(() => {
  jest.resetAllMocks();
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => mockAssistants,
  });
});

describe("AssistantSelector", () => {
  it("fetches and displays active assistants", async () => {
    const onSelect = jest.fn();
    render(<AssistantSelector selectedId={null} onSelect={onSelect} />);

    // Should auto-select the first active assistant
    await waitFor(() => {
      expect(onSelect).toHaveBeenCalledWith(
        expect.objectContaining({ id: "a1", name: "General Assistant" }),
      );
    });
  });

  it("renders the selected assistant name in the trigger", async () => {
    render(
      <AssistantSelector
        selectedId="a1"
        onSelect={jest.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("General Assistant")).toBeInTheDocument();
    });
  });

  it("opens dropdown on click and shows assistant options", async () => {
    const user = userEvent.setup();
    render(
      <AssistantSelector selectedId="a1" onSelect={jest.fn()} />,
    );

    await waitFor(() => {
      expect(screen.getByText("General Assistant")).toBeInTheDocument();
    });

    // Click trigger to open
    await user.click(screen.getByRole("button", { expanded: false }));

    // Should show active assistants only (not the inactive one)
    expect(screen.getByText("Code Assistant")).toBeInTheDocument();
    expect(screen.queryByText("Inactive Bot")).not.toBeInTheDocument();
  });

  it("calls onSelect when an assistant is clicked", async () => {
    const onSelect = jest.fn();
    const user = userEvent.setup();
    render(
      <AssistantSelector selectedId="a1" onSelect={onSelect} />,
    );

    await waitFor(() => {
      expect(screen.getByText("General Assistant")).toBeInTheDocument();
    });

    // Open dropdown
    await user.click(screen.getByRole("button", { expanded: false }));

    // Select the second assistant
    await user.click(screen.getByText("Code Assistant"));

    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ id: "a2", name: "Code Assistant" }),
    );
  });

  it("shows model badge for each assistant", async () => {
    const user = userEvent.setup();
    render(
      <AssistantSelector selectedId="a1" onSelect={jest.fn()} />,
    );

    await waitFor(() => {
      expect(screen.getByText("General Assistant")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { expanded: false }));

    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
    expect(screen.getByText("claude-3-opus")).toBeInTheDocument();
  });

  it("shows tool count for assistants with tools", async () => {
    const user = userEvent.setup();
    render(
      <AssistantSelector selectedId="a1" onSelect={jest.fn()} />,
    );

    await waitFor(() => {
      expect(screen.getByText("General Assistant")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { expanded: false }));

    expect(screen.getByText("2 tools")).toBeInTheDocument();
    expect(screen.getByText("1 tool")).toBeInTheDocument();
  });

  it("disables the trigger when disabled prop is true", async () => {
    render(
      <AssistantSelector
        selectedId="a1"
        onSelect={jest.fn()}
        disabled
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("General Assistant")).toBeInTheDocument();
    });

    const trigger = screen.getByRole("button");
    expect(trigger).toBeDisabled();
  });

  it("falls back gracefully on fetch error", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("Network error"));
    const onSelect = jest.fn();

    render(<AssistantSelector selectedId={null} onSelect={onSelect} />);

    await waitFor(() => {
      expect(onSelect).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Default Assistant" }),
      );
    });

    // Shows error hint
    expect(screen.getByText(/Network error/)).toBeInTheDocument();
  });
});
