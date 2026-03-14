import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { ChatInterface } from "../ChatInterface";

// Mock scrollIntoView
beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn();
});

describe("ChatInterface", () => {
  it("renders the header, message list, and input", () => {
    render(<ChatInterface />);
    expect(screen.getByText("Symphony Chat")).toBeInTheDocument();
    expect(screen.getByLabelText("Message input")).toBeInTheDocument();
    expect(screen.getByText("Welcome to Symphony")).toBeInTheDocument();
  });

  it("sends a message and displays it", async () => {
    render(<ChatInterface />);

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Hello AI{Enter}");

    expect(screen.getByText("Hello AI")).toBeInTheDocument();
    // Empty state should be gone
    expect(screen.queryByText("Welcome to Symphony")).not.toBeInTheDocument();
  });

  it("shows loading state after sending message", async () => {
    render(<ChatInterface />);

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Hello{Enter}");

    // Should show loading spinners (one in message list, one in send button)
    const spinners = screen.getAllByLabelText("Loading");
    expect(spinners.length).toBeGreaterThanOrEqual(1);
  });
});
