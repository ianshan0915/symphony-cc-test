import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { ChatInterface } from "../ChatInterface";
import { AuthProvider } from "@/providers/AuthProvider";

// Mock scrollIntoView
beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn();
});

/** Helper: mock response for the /assistants endpoint */
function mockAssistantsResponse() {
  return {
    ok: true,
    json: async () => ({
      assistants: [
        {
          id: "default",
          name: "Default Assistant",
          description: "General-purpose",
          model: "gpt-4o",
          tools_enabled: [],
          is_active: true,
        },
      ],
      total: 1,
      offset: 0,
      limit: 50,
    }),
  };
}

/** Mock response for the /threads endpoint (conversation list) */
function mockThreadsResponse() {
  return {
    ok: true,
    json: async () => ({
      threads: [],
      total: 0,
      offset: 0,
      limit: 50,
    }),
  };
}

/** Route-aware fetch mock: assistants endpoint vs everything else */
function setupFetchMock(chatHandler?: (url: string, init?: RequestInit) => Promise<unknown>) {
  (global.fetch as jest.Mock).mockImplementation((url: string, init?: RequestInit) => {
    if (url.includes("/assistants")) {
      return Promise.resolve(mockAssistantsResponse());
    }
    if (url.includes("/threads")) {
      return Promise.resolve(mockThreadsResponse());
    }
    if (chatHandler) {
      return chatHandler(url, init);
    }
    // Default: return a minimal empty stream
    return Promise.resolve({
      ok: true,
      body: {
        getReader: () => ({
          read: jest.fn().mockResolvedValueOnce({ done: true, value: undefined }),
        }),
      },
    });
  });
}

// Mock fetch for SSE streaming
beforeEach(() => {
  global.fetch = jest.fn();
  // Clear persisted thread ID to avoid cross-test leakage
  localStorage.removeItem("symphony_current_thread_id");
  setupFetchMock();
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe("ChatInterface", () => {
  it("renders the header, message list, and input", async () => {
    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });
    expect(screen.getByText("Symphony Chat")).toBeInTheDocument();
    expect(screen.getByLabelText("Message input")).toBeInTheDocument();
    expect(screen.getByText("Welcome to Symphony")).toBeInTheDocument();
  });

  it("renders the assistant selector in the header", async () => {
    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    await waitFor(() => {
      expect(screen.getByText("Default Assistant")).toBeInTheDocument();
    });
  });

  it("sends a message and displays it", async () => {
    setupFetchMock(async (url) => {
      if (url.includes("/chat/stream")) {
        return {
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
        };
      }
    });

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Hello AI{Enter}");

    expect(screen.getByText("Hello AI")).toBeInTheDocument();
    // Empty state should be gone
    expect(screen.queryByText("Welcome to Symphony")).not.toBeInTheDocument();
  });

  it("shows user message immediately when sent", async () => {
    setupFetchMock(
      (url) =>
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
            100,
          ),
        ),
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Test message{Enter}");

    // User message should appear immediately
    expect(screen.getByText("Test message")).toBeInTheDocument();
  });

  it("displays error message on fetch failure", async () => {
    setupFetchMock(async (url) => {
      if (url.includes("/chat/stream")) {
        throw new Error("Network error");
      }
      // Fallback for other URLs
      return { ok: true, json: async () => ({}) };
    });

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Hello{Enter}");

    await waitFor(() => {
      expect(screen.getByText(/Network error/)).toBeInTheDocument();
    });
  });

  it("renders sidebars on the page", async () => {
    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });
    expect(screen.getByText("Agent Tasks")).toBeInTheDocument();
    expect(screen.getByText("File Operations")).toBeInTheDocument();
    expect(screen.getByText("Conversations")).toBeInTheDocument();
  });
});
