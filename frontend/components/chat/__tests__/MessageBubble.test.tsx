import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MessageBubble } from "../MessageBubble";
import type { Message } from "@/lib/types";

describe("MessageBubble", () => {
  const userMessage: Message = {
    id: "msg-1",
    role: "user",
    content: "Hello there",
    createdAt: "2026-01-01T12:00:00Z",
  };

  const assistantMessage: Message = {
    id: "msg-2",
    role: "assistant",
    content: "**Bold text** and a [link](https://example.com)",
    createdAt: "2026-01-01T12:01:00Z",
  };

  it("renders user message content", () => {
    render(<MessageBubble message={userMessage} />);
    expect(screen.getByText("Hello there")).toBeInTheDocument();
  });

  it("renders assistant message with markdown", () => {
    render(<MessageBubble message={assistantMessage} />);
    expect(screen.getByText("Bold text")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "link" })).toHaveAttribute(
      "href",
      "https://example.com"
    );
  });

  it("aligns user messages to the right", () => {
    const { container } = render(<MessageBubble message={userMessage} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("justify-end");
  });

  it("aligns assistant messages to the left", () => {
    const { container } = render(<MessageBubble message={assistantMessage} />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("justify-start");
  });

  it("renders tool calls when present", () => {
    const messageWithTools: Message = {
      id: "msg-3",
      role: "assistant",
      content: "Here are the results",
      toolCalls: [
        {
          id: "tc-1",
          name: "web_search",
          args: { query: "test" },
          result: "Found results",
          status: "completed",
        },
      ],
    };

    render(<MessageBubble message={messageWithTools} />);
    expect(screen.getByText("web_search")).toBeInTheDocument();
  });

  it("displays timestamp when createdAt is provided", () => {
    render(<MessageBubble message={userMessage} />);
    // The timestamp should be rendered (exact format depends on locale)
    const timeElements = screen.getAllByText(/\d{1,2}:\d{2}/);
    expect(timeElements.length).toBeGreaterThan(0);
  });
});
