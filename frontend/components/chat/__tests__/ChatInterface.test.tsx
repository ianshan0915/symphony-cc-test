import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { ChatInterface } from "../ChatInterface";

// Mock scrollIntoView
beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn();
});

// Mock fetch for SSE streaming
beforeEach(() => {
  global.fetch = jest.fn();
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe("ChatInterface", () => {
  it("renders the header, message list, and input", () => {
    render(<ChatInterface />);
    expect(screen.getByText("Symphony Chat")).toBeInTheDocument();
    expect(screen.getByLabelText("Message input")).toBeInTheDocument();
    expect(screen.getByText("Welcome to Symphony")).toBeInTheDocument();
  });

  it("sends a message and displays it", async () => {
    // Mock fetch to return a minimal SSE stream
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      body: {
        getReader: () => ({
          read: jest
            .fn()
            .mockResolvedValueOnce({
              done: false,
              value: new TextEncoder().encode(
                'event: message_start\ndata: {"thread_id":"t1"}\n\n' +
                'event: message_end\ndata: {"thread_id":"t1","content":"Hello!","tool_calls":null}\n\n'
              ),
            })
            .mockResolvedValueOnce({ done: true, value: undefined }),
        }),
      },
    });

    render(<ChatInterface />);

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Hello AI{Enter}");

    expect(screen.getByText("Hello AI")).toBeInTheDocument();
    // Empty state should be gone
    expect(screen.queryByText("Welcome to Symphony")).not.toBeInTheDocument();
  });

  it("shows user message immediately when sent", async () => {
    // Mock fetch to simulate a slow response
    (global.fetch as jest.Mock).mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                ok: true,
                body: {
                  getReader: () => ({
                    read: jest
                      .fn()
                      .mockResolvedValueOnce({ done: true, value: undefined }),
                  }),
                },
              }),
            100
          )
        )
    );

    render(<ChatInterface />);

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Test message{Enter}");

    // User message should appear immediately
    expect(screen.getByText("Test message")).toBeInTheDocument();
  });

  it("displays error message on fetch failure", async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error("Network error"));

    render(<ChatInterface />);

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Hello{Enter}");

    await waitFor(() => {
      expect(screen.getByText(/Network error/)).toBeInTheDocument();
    });
  });

  it("renders sidebars on the page", () => {
    render(<ChatInterface />);
    expect(screen.getByText("Agent Tasks")).toBeInTheDocument();
    expect(screen.getByText("File Operations")).toBeInTheDocument();
  });
});
