import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { SkillForm } from "../SkillForm";

beforeEach(() => {
  jest.resetAllMocks();
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      id: "new-skill-id",
      user_id: "user-1",
      name: "test-skill",
      description: "A test skill",
      instructions: "Do the thing",
      metadata: {},
      is_active: true,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    }),
  });
});

describe("SkillForm", () => {
  it("renders create form when no skill is provided", () => {
    render(
      <SkillForm open={true} onOpenChange={jest.fn()} />,
    );

    // Title + submit button both say "Create Skill"
    expect(screen.getAllByText("Create Skill").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/instructions/i)).toBeInTheDocument();
  });

  it("renders edit form when skill is provided", () => {
    const skill = {
      id: "s1",
      user_id: "user-1",
      name: "my-skill",
      description: "My skill description",
      instructions: "Follow these steps...",
      metadata: {},
      is_active: true,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };

    render(
      <SkillForm skill={skill} open={true} onOpenChange={jest.fn()} />,
    );

    expect(screen.getByText("Edit Skill")).toBeInTheDocument();
    expect(screen.getByDisplayValue("my-skill")).toBeInTheDocument();
    expect(screen.getByDisplayValue("My skill description")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Follow these steps...")).toBeInTheDocument();
  });

  it("disables submit when required fields are empty", () => {
    render(
      <SkillForm open={true} onOpenChange={jest.fn()} />,
    );

    const submitButtons = screen.getAllByRole("button");
    const submitBtn = submitButtons.find(
      (b) => b.getAttribute("type") === "submit",
    );
    expect(submitBtn).toBeDisabled();
  });

  it("calls onOpenChange(false) when Cancel is clicked", async () => {
    const user = userEvent.setup();
    const onOpenChange = jest.fn();

    render(
      <SkillForm open={true} onOpenChange={onOpenChange} />,
    );

    await user.click(screen.getByText("Cancel"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("shows name format hint", () => {
    render(
      <SkillForm open={true} onOpenChange={jest.fn()} />,
    );

    expect(
      screen.getByText(/lowercase letters, digits, and hyphens/i),
    ).toBeInTheDocument();
  });
});
