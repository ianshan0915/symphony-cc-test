import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MessageList } from "../MessageList";
import type { Message } from "@/lib/types";

// Mock scrollIntoView since jsdom doesn't implement it
beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn();
});

describe("MessageList", () => {
  const messages: Message[] = [
    { id: "1", role: "user", content: "Hello" },
    { id: "2", role: "assistant", content: "Hi there!" },
    { id: "3", role: "user", content: "How are you?" },
  ];

  it("renders all messages", () => {
    render(<MessageList messages={messages} />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("Hi there!")).toBeInTheDocument();
    expect(screen.getByText("How are you?")).toBeInTheDocument();
  });

  it("shows welcome screen when no messages and onSend provided", () => {
    render(<MessageList messages={[]} onSend={jest.fn()} />);
    expect(screen.getByTestId("welcome-screen")).toBeInTheDocument();
  });

  it("shows fallback empty state when no messages and no onSend", () => {
    render(<MessageList messages={[]} />);
    expect(screen.getByText("Welcome to Symphony")).toBeInTheDocument();
    expect(
      screen.getByText("Start a conversation with the AI agent.")
    ).toBeInTheDocument();
  });

  it("shows contextual loading indicator when isLoading is true", () => {
    render(<MessageList messages={messages} isLoading />);
    expect(screen.getByTestId("loading-indicator")).toBeInTheDocument();
    expect(screen.getByText("Thinking…")).toBeInTheDocument();
  });

  it("shows tool-specific loading indicator when currentToolName is set", () => {
    render(
      <MessageList messages={messages} isLoading currentToolName="web_search" />
    );
    expect(screen.getByText(/Searching the web/)).toBeInTheDocument();
  });

  it("hides empty state when loading", () => {
    render(<MessageList messages={[]} isLoading />);
    expect(screen.queryByTestId("welcome-screen")).not.toBeInTheDocument();
    expect(screen.queryByText("Welcome to Symphony")).not.toBeInTheDocument();
  });

  it("calls scrollIntoView for auto-scroll", () => {
    render(<MessageList messages={messages} />);
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it("shows skeleton when isThreadLoading is true", () => {
    render(<MessageList messages={[]} isThreadLoading />);
    expect(screen.getByTestId("message-skeleton")).toBeInTheDocument();
  });

  it("renders time dividers between message groups", () => {
    const messagesWithGap: Message[] = [
      { id: "1", role: "user", content: "First", createdAt: "2026-01-01T12:00:00Z" },
      { id: "2", role: "assistant", content: "Response", createdAt: "2026-01-01T12:01:00Z" },
      // 10 minute gap — should trigger a new divider
      { id: "3", role: "user", content: "Later", createdAt: "2026-01-01T12:11:00Z" },
    ];
    render(<MessageList messages={messagesWithGap} />);
    const dividers = screen.getAllByTestId("time-divider");
    expect(dividers.length).toBe(2); // first message + after gap
  });

  it("sends starter prompt when welcome card is clicked", () => {
    const onSend = jest.fn();
    render(<MessageList messages={[]} onSend={onSend} />);
    // Click the first starter card
    const cards = screen.getByTestId("welcome-screen").querySelectorAll("button");
    expect(cards.length).toBe(4);
    fireEvent.click(cards[0]);
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith(expect.any(String));
  });

  it("renders SubAgentProgress inline when subAgents are provided", () => {
    const subAgents = [
      {
        id: "researcher",
        name: "Researcher",
        type: "researcher",
        status: "running" as const,
        startedAt: new Date().toISOString(),
      },
    ];
    render(<MessageList messages={messages} subAgents={subAgents} />);
    expect(screen.getByText("Researcher")).toBeInTheDocument();
    expect(screen.getByText("Sub-Agents")).toBeInTheDocument();
  });
});
