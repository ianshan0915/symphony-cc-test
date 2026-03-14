import React from "react";
import { render, screen } from "@testing-library/react";
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

  it("shows empty state when no messages", () => {
    render(<MessageList messages={[]} />);
    expect(screen.getByText("Welcome to Symphony")).toBeInTheDocument();
    expect(
      screen.getByText("Start a conversation with the AI agent.")
    ).toBeInTheDocument();
  });

  it("shows loading indicator when isLoading is true", () => {
    render(<MessageList messages={messages} isLoading />);
    expect(screen.getByLabelText("Loading")).toBeInTheDocument();
  });

  it("hides empty state when loading", () => {
    render(<MessageList messages={[]} isLoading />);
    expect(screen.queryByText("Welcome to Symphony")).not.toBeInTheDocument();
  });

  it("calls scrollIntoView for auto-scroll", () => {
    render(<MessageList messages={messages} />);
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });
});
