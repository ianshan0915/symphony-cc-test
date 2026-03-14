import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ToolCallCard } from "../ToolCallCard";
import type { ToolCall } from "@/lib/types";

describe("ToolCallCard", () => {
  const toolCall: ToolCall = {
    id: "tc-1",
    name: "web_search",
    args: { query: "test query" },
    result: "Found 3 results",
    status: "completed",
  };

  it("renders tool name", () => {
    render(<ToolCallCard toolCall={toolCall} />);
    expect(screen.getByText("web_search")).toBeInTheDocument();
  });

  it("is collapsed by default", () => {
    render(<ToolCallCard toolCall={toolCall} />);
    expect(screen.queryByText("Arguments")).not.toBeInTheDocument();
    expect(screen.queryByText("Result")).not.toBeInTheDocument();
  });

  it("expands to show details when clicked", () => {
    render(<ToolCallCard toolCall={toolCall} />);
    fireEvent.click(screen.getByRole("button"));

    expect(screen.getByText("Arguments")).toBeInTheDocument();
    expect(screen.getByText("Result")).toBeInTheDocument();
    expect(screen.getByText("Found 3 results")).toBeInTheDocument();
  });

  it("collapses again when clicked twice", () => {
    render(<ToolCallCard toolCall={toolCall} />);
    const button = screen.getByRole("button");

    fireEvent.click(button);
    expect(screen.getByText("Arguments")).toBeInTheDocument();

    fireEvent.click(button);
    expect(screen.queryByText("Arguments")).not.toBeInTheDocument();
  });

  it("shows running status with animation", () => {
    const runningTool: ToolCall = {
      ...toolCall,
      status: "running",
    };
    render(<ToolCallCard toolCall={runningTool} />);
    // The status icon should have animate-spin class
    const button = screen.getByRole("button");
    const svgs = button.querySelectorAll("svg");
    const hasAnimated = Array.from(svgs).some((svg) =>
      svg.className.baseVal?.includes("animate-spin") ||
      svg.classList?.contains("animate-spin")
    );
    expect(hasAnimated).toBe(true);
  });

  it("has correct aria-expanded attribute", () => {
    render(<ToolCallCard toolCall={toolCall} />);
    const button = screen.getByRole("button");

    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
  });
});
