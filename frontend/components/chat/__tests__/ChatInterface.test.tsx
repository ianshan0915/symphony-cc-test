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

// ---------------------------------------------------------------------------
// Sub-agent SSE integration tests
// ---------------------------------------------------------------------------

/** Helper to build a one-shot SSE stream mock and return it. */
function sseStreamMock(events: string) {
  const encoded = new TextEncoder().encode(events);
  return {
    ok: true,
    body: {
      getReader: () => ({
        read: jest
          .fn()
          .mockResolvedValueOnce({ done: false, value: encoded })
          .mockResolvedValueOnce({ done: true, value: undefined }),
      }),
    },
  };
}

/** Build setupFetchMock that returns the given SSE events for /chat/stream. */
function setupSubAgentFetchMock(sseEvents: string) {
  setupFetchMock(async (url) => {
    if (url.includes("/chat/stream")) {
      return sseStreamMock(sseEvents);
    }
    // Other URLs (e.g. /auth/me on first render) get an empty successful response
    return { ok: true, json: async () => ({}) };
  });
}

// ---------------------------------------------------------------------------
// todo_update SSE integration tests
// ---------------------------------------------------------------------------

describe("ChatInterface todo_update SSE events", () => {
  it("renders Agent Plan section when todo_update event is received", async () => {
    const todos = [
      { id: "1", content: "Research the topic", status: "pending" },
      { id: "2", content: "Write the report", status: "pending" },
    ];
    setupSubAgentFetchMock(
      'event: message_start\ndata: {"thread_id":"t1"}\n\n' +
      `event: todo_update\ndata: ${JSON.stringify({ todos })}\n\n` +
      'event: message_end\ndata: {"thread_id":"t1","content":"Done","tool_calls":null}\n\n',
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Plan my project{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Agent Plan")).toBeInTheDocument();
      expect(screen.getByText("Research the topic")).toBeInTheDocument();
      expect(screen.getByText("Write the report")).toBeInTheDocument();
    });
  });

  it("updates existing todos when a subsequent todo_update arrives", async () => {
    const initialTodos = [
      { id: "1", content: "Research the topic", status: "in_progress" },
      { id: "2", content: "Write the report", status: "pending" },
    ];
    const updatedTodos = [
      { id: "1", content: "Research the topic", status: "completed" },
      { id: "2", content: "Write the report", status: "in_progress" },
    ];
    setupSubAgentFetchMock(
      'event: message_start\ndata: {"thread_id":"t1"}\n\n' +
      `event: todo_update\ndata: ${JSON.stringify({ todos: initialTodos })}\n\n` +
      `event: todo_update\ndata: ${JSON.stringify({ todos: updatedTodos })}\n\n` +
      'event: message_end\ndata: {"thread_id":"t1","content":"Done","tool_calls":null}\n\n',
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Do the work{Enter}");

    // After both events, progress should be 1/2 (1 completed)
    await waitFor(() => {
      expect(screen.getByText("1/2")).toBeInTheDocument();
    });
  });

  it("shows todo priority badges when priorities are set", async () => {
    const todos = [
      { id: "1", content: "High priority task", status: "pending", priority: "high" },
      { id: "2", content: "Low priority task", status: "pending", priority: "low" },
    ];
    setupSubAgentFetchMock(
      'event: message_start\ndata: {"thread_id":"t1"}\n\n' +
      `event: todo_update\ndata: ${JSON.stringify({ todos })}\n\n` +
      'event: message_end\ndata: {"thread_id":"t1","content":"Done","tool_calls":null}\n\n',
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Prioritize tasks{Enter}");

    await waitFor(() => {
      expect(screen.getByText("High")).toBeInTheDocument();
      expect(screen.getByText("Low")).toBeInTheDocument();
    });
  });
});

describe("ChatInterface sub-agent SSE events", () => {
  it("displays sub-agent panel when sub_agent_start event is received", async () => {
    setupSubAgentFetchMock(
      'event: message_start\ndata: {"thread_id":"t1"}\n\n' +
      'event: sub_agent_start\ndata: {"subagent_name":"researcher","thread_id":"t1"}\n\n' +
      'event: message_end\ndata: {"thread_id":"t1","content":"Done","tool_calls":null}\n\n',
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Research this{Enter}");

    // SubAgentProgress header and researcher agent should appear after SSE chain completes
    await waitFor(() => {
      expect(screen.getByText("Sub-Agents")).toBeInTheDocument();
      expect(screen.getByText("Researcher")).toBeInTheDocument();
    });
  });

  it("accumulates token progress text from sub_agent_progress events", async () => {
    setupSubAgentFetchMock(
      'event: message_start\ndata: {"thread_id":"t1"}\n\n' +
      'event: sub_agent_start\ndata: {"subagent_name":"researcher","thread_id":"t1"}\n\n' +
      'event: sub_agent_progress\ndata: {"subagent_name":"researcher","thread_id":"t1","inner_event":"token","token":"Searching "}\n\n' +
      'event: sub_agent_progress\ndata: {"subagent_name":"researcher","thread_id":"t1","inner_event":"token","token":"the web..."}\n\n' +
      'event: message_end\ndata: {"thread_id":"t1","content":"Done","tool_calls":null}\n\n',
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Research{Enter}");

    // Running agent is auto-expanded; accumulated tokens should be concatenated
    await waitFor(() => {
      expect(screen.getByText("Searching the web...")).toBeInTheDocument();
    });
  });

  it("marks sub-agent as Completed after sub_agent_end event", async () => {
    setupSubAgentFetchMock(
      'event: message_start\ndata: {"thread_id":"t1"}\n\n' +
      'event: sub_agent_start\ndata: {"subagent_name":"coder","thread_id":"t1"}\n\n' +
      'event: sub_agent_end\ndata: {"subagent_name":"coder","thread_id":"t1"}\n\n' +
      'event: message_end\ndata: {"thread_id":"t1","content":"Done","tool_calls":null}\n\n',
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Write code{Enter}");

    // Status label should have transitioned to "Completed"
    await waitFor(() => {
      expect(screen.getByText("Completed")).toBeInTheDocument();
    });
  });

  it("clears sub-agents from previous turn when a new message is sent", async () => {
    // First turn: researcher agent appears
    setupSubAgentFetchMock(
      'event: message_start\ndata: {"thread_id":"t1"}\n\n' +
      'event: sub_agent_start\ndata: {"subagent_name":"researcher","thread_id":"t1"}\n\n' +
      'event: message_end\ndata: {"thread_id":"t1","content":"Done","tool_calls":null}\n\n',
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "First message{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Researcher")).toBeInTheDocument();
    });

    // Second turn: no sub-agents — the panel should clear
    setupSubAgentFetchMock(
      'event: message_start\ndata: {"thread_id":"t1"}\n\n' +
      'event: message_end\ndata: {"thread_id":"t1","content":"Hi","tool_calls":null}\n\n',
    );

    await userEvent.type(input, "Second message{Enter}");

    // Sub-agent panel should be gone (SubAgentProgress renders null when list is empty)
    await waitFor(() => {
      expect(screen.queryByText("Researcher")).not.toBeInTheDocument();
    });
  });

  it("handles multiple sub-agents in one turn", async () => {
    setupSubAgentFetchMock(
      'event: message_start\ndata: {"thread_id":"t1"}\n\n' +
      'event: sub_agent_start\ndata: {"subagent_name":"researcher","thread_id":"t1"}\n\n' +
      'event: sub_agent_end\ndata: {"subagent_name":"researcher","thread_id":"t1"}\n\n' +
      'event: sub_agent_start\ndata: {"subagent_name":"writer","thread_id":"t1"}\n\n' +
      'event: sub_agent_end\ndata: {"subagent_name":"writer","thread_id":"t1"}\n\n' +
      'event: message_end\ndata: {"thread_id":"t1","content":"Done","tool_calls":null}\n\n',
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Write a researched article{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Researcher")).toBeInTheDocument();
      expect(screen.getByText("Writer")).toBeInTheDocument();
      // Both should be completed
      expect(screen.getAllByText("Completed")).toHaveLength(2);
    });
  });
});

// ---------------------------------------------------------------------------
// Structured response SSE integration tests
// ---------------------------------------------------------------------------

describe("ChatInterface structured_response in message_end", () => {
  it("renders StructuredResponseCard when structured_response is in message_end", async () => {
    const structuredData = { city: "Tokyo", population: 13960000 };
    setupSubAgentFetchMock(
      "event: message_start\ndata: {\"thread_id\":\"t1\"}\n\n" +
      `event: message_end\ndata: ${JSON.stringify({ thread_id: "t1", content: "Here is the data:", structured_response: structuredData, tool_calls: null })}\n\n`,
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "What is the population of Tokyo?{Enter}");

    await waitFor(() => {
      expect(screen.getByTestId("structured-response-card")).toBeInTheDocument();
    });
  });

  it("renders StructuredResponseCard with structured_response and no text content", async () => {
    const structuredData = { result: "success", count: 3 };
    setupSubAgentFetchMock(
      "event: message_start\ndata: {\"thread_id\":\"t1\"}\n\n" +
      `event: message_end\ndata: ${JSON.stringify({ thread_id: "t1", content: "", structured_response: structuredData, tool_calls: null })}\n\n`,
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Run the job{Enter}");

    await waitFor(() => {
      expect(screen.getByTestId("structured-response-card")).toBeInTheDocument();
    });
  });

  it("does not render StructuredResponseCard when no structured_response in message_end", async () => {
    setupSubAgentFetchMock(
      "event: message_start\ndata: {\"thread_id\":\"t1\"}\n\n" +
      "event: message_end\ndata: {\"thread_id\":\"t1\",\"content\":\"Hello!\",\"tool_calls\":null}\n\n",
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Say hello{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Hello!")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("structured-response-card")).not.toBeInTheDocument();
  });

  it("does not render StructuredResponseCard when structured_response is a non-object (runtime guard)", async () => {
    // Backend sends a string instead of an object — the runtime guard should reject it.
    setupSubAgentFetchMock(
      "event: message_start\ndata: {\"thread_id\":\"t1\"}\n\n" +
      "event: message_end\ndata: {\"thread_id\":\"t1\",\"content\":\"Done\",\"structured_response\":\"not an object\",\"tool_calls\":null}\n\n",
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Do something{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Done")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("structured-response-card")).not.toBeInTheDocument();
  });

  it("does not render StructuredResponseCard when structured_response is an array (runtime guard)", async () => {
    setupSubAgentFetchMock(
      "event: message_start\ndata: {\"thread_id\":\"t1\"}\n\n" +
      "event: message_end\ndata: {\"thread_id\":\"t1\",\"content\":\"Done\",\"structured_response\":[1,2,3],\"tool_calls\":null}\n\n",
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Do something{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Done")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("structured-response-card")).not.toBeInTheDocument();
  });
});
