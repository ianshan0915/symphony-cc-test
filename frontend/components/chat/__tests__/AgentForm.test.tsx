import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { AgentForm } from "../AgentForm";

// Mock skills fetch for SkillSelector
const mockSkillsResponse = {
  skills: [
    {
      id: "sk1",
      user_id: null,
      name: "research",
      description: "Research skill",
      instructions: "Do research",
      metadata: {},
      is_active: true,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    },
  ],
  total: 1,
  offset: 0,
  limit: 100,
};

beforeEach(() => {
  jest.resetAllMocks();
  global.fetch = jest.fn().mockImplementation((url: string) => {
    if (url.includes("/skills")) {
      return Promise.resolve({
        ok: true,
        json: async () => mockSkillsResponse,
      });
    }
    // Default: agent creation
    return Promise.resolve({
      ok: true,
      json: async () => ({
        id: "new-agent-id",
        name: "Test Agent",
        description: "A test agent",
        model: "gpt-4o",
        system_prompt: null,
        tools_enabled: [],
        metadata: {},
        skills: [],
        is_active: true,
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      }),
    });
  });
});

describe("AgentForm", () => {
  it("renders create form when no agent is provided", () => {
    render(
      <AgentForm open={true} onOpenChange={jest.fn()} />,
    );

    // Title + submit button both say "Create Agent"
    expect(screen.getAllByText("Create Agent").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByLabelText(/^name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^description$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^model$/i)).toBeInTheDocument();
  });

  it("renders edit form when agent is provided", () => {
    const agent = {
      id: "a1",
      user_id: "user-1",
      name: "My Agent",
      description: "My description",
      model: "gpt-4o",
      system_prompt: "Be helpful",
      tools_enabled: ["web_search"],
      metadata: {},
      skills: [{ id: "sk1", name: "research", description: "Research" }],
      is_active: true,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };

    render(
      <AgentForm agent={agent} open={true} onOpenChange={jest.fn()} />,
    );

    expect(screen.getByText("Edit Agent")).toBeInTheDocument();
    expect(screen.getByDisplayValue("My Agent")).toBeInTheDocument();
    expect(screen.getByDisplayValue("My description")).toBeInTheDocument();
  });

  it("disables submit when name is empty", () => {
    render(
      <AgentForm open={true} onOpenChange={jest.fn()} />,
    );

    // The Create Agent button in the form footer (not the title)
    const submitButtons = screen.getAllByRole("button");
    const submitBtn = submitButtons.find(
      (b) => b.getAttribute("type") === "submit",
    );
    expect(submitBtn).toBeDisabled();
  });

  it("shows model selector with supported models", () => {
    render(
      <AgentForm open={true} onOpenChange={jest.fn()} />,
    );

    const modelSelect = screen.getByLabelText(/model/i);
    expect(modelSelect).toBeInTheDocument();
    expect(modelSelect.querySelectorAll("option").length).toBeGreaterThan(0);
  });

  it("shows tools checkboxes", () => {
    render(
      <AgentForm open={true} onOpenChange={jest.fn()} />,
    );

    expect(screen.getByText("Web Search")).toBeInTheDocument();
    expect(screen.getByText("File Tools")).toBeInTheDocument();
    expect(screen.getByText("Knowledge Base")).toBeInTheDocument();
  });

  it("calls onOpenChange(false) when Cancel is clicked", async () => {
    const user = userEvent.setup();
    const onOpenChange = jest.fn();

    render(
      <AgentForm open={true} onOpenChange={onOpenChange} />,
    );

    await user.click(screen.getByText("Cancel"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
