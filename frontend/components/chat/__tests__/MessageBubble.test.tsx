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

  // ---------------------------------------------------------------------------
  // Structured response rendering
  // ---------------------------------------------------------------------------

  it("renders StructuredResponseCard when structuredResponse is present", () => {
    const messageWithStructured: Message = {
      id: "msg-4",
      role: "assistant",
      content: "Here is your result:",
      structuredResponse: { name: "Alice", score: 95 },
    };

    render(<MessageBubble message={messageWithStructured} />);
    expect(screen.getByTestId("structured-response-card")).toBeInTheDocument();
  });

  it("renders structured response field values", () => {
    const messageWithStructured: Message = {
      id: "msg-5",
      role: "assistant",
      content: "Result:",
      structuredResponse: { city: "Tokyo", population: 13960000 },
    };

    render(<MessageBubble message={messageWithStructured} />);
    expect(screen.getByText("City")).toBeInTheDocument();
    expect(screen.getByText("Tokyo")).toBeInTheDocument();
  });

  it("does not render StructuredResponseCard when structuredResponse is absent", () => {
    render(<MessageBubble message={assistantMessage} />);
    expect(screen.queryByTestId("structured-response-card")).not.toBeInTheDocument();
  });

  it("renders both message content and structured response when both are present", () => {
    const messageWithBoth: Message = {
      id: "msg-6",
      role: "assistant",
      content: "Here is the weather:",
      structuredResponse: { temperature: 22, unit: "Celsius" },
    };

    render(<MessageBubble message={messageWithBoth} />);
    // The text content should still appear
    expect(screen.getByText(/Here is the weather/)).toBeInTheDocument();
    // And the structured card should also be present
    expect(screen.getByTestId("structured-response-card")).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // CodeExecutionCard routing
  // ---------------------------------------------------------------------------

  it("renders a CodeExecutionCard for an execute tool call", () => {
    const messageWithExecute: Message = {
      id: "msg-exec",
      role: "assistant",
      content: "",
      toolCalls: [
        {
          id: "tc-exec",
          name: "execute",
          args: { command: "ls -la" },
          status: "completed",
          execution: {
            stdout: "total 0\n",
            stderr: "",
            exitCode: 0,
          },
        },
      ],
    };

    render(<MessageBubble message={messageWithExecute} />);
    // CodeExecutionCard sets this test id on its root element
    expect(screen.getByTestId("code-execution-card")).toBeInTheDocument();
    // Generic ToolCallCard should NOT be rendered for execute tool calls
    expect(screen.queryByTestId("tool-call-card")).not.toBeInTheDocument();
  });

  it("renders a generic ToolCallCard for non-execute tool calls", () => {
    const messageWithTool: Message = {
      id: "msg-tool",
      role: "assistant",
      content: "",
      toolCalls: [
        {
          id: "tc-search",
          name: "web_search",
          args: { query: "hello" },
          status: "completed",
          result: "Some results",
        },
      ],
    };

    render(<MessageBubble message={messageWithTool} />);
    // CodeExecutionCard must NOT be rendered for non-execute tools
    expect(screen.queryByTestId("code-execution-card")).not.toBeInTheDocument();
    // ToolCallCard renders the tool name in its header
    expect(screen.getByText("web_search")).toBeInTheDocument();
  });
});
