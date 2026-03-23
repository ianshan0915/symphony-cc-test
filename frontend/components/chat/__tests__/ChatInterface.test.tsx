import React from "react";
import { render, screen, waitFor, act, within } from "@testing-library/react";
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
    expect(screen.getByTestId("welcome-screen")).toBeInTheDocument();
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
    expect(screen.queryByTestId("welcome-screen")).not.toBeInTheDocument();
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

  it("renders conversation sidebar", async () => {
    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });
    expect(screen.getByText("Conversations")).toBeInTheDocument();
    // TasksSidebar and FilesSidebar removed in UX redesign
    expect(screen.queryByText("Agent Tasks")).not.toBeInTheDocument();
    expect(screen.queryByText("File Operations")).not.toBeInTheDocument();
  });

  it("renders sidebar toggle button", async () => {
    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });
    expect(screen.getByLabelText("Collapse sidebar")).toBeInTheDocument();
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
  // Note: TasksSidebar removed in UX redesign Phase 1.
  // The SSE handler still processes todo_update events (state is preserved)
  // but no UI renders them directly. These tests verify the SSE handler
  // doesn't crash when todo_update events arrive.

  it("processes todo_update events without error", async () => {
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

    // The main message should still render correctly
    await waitFor(() => {
      expect(screen.getByText("Done")).toBeInTheDocument();
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

// ---------------------------------------------------------------------------
// execute_result SSE integration tests
// ---------------------------------------------------------------------------

describe("ChatInterface execute_result SSE events", () => {
  it("displays a CodeExecutionCard for an execute tool call", async () => {
    // tool_call followed by execute_result with stdout
    const toolCallPayload = JSON.stringify({
      tool_name: "execute",
      tool_input: { command: "echo hi" },
      run_id: "run-exec-1",
    });
    const execResultPayload = JSON.stringify({
      run_id: "run-exec-1",
      stdout: "hi\n",
      stderr: "",
      exit_code: 0,
    });

    setupSubAgentFetchMock(
      "event: message_start\ndata: {\"thread_id\":\"t1\"}\n\n" +
      `event: tool_call\ndata: ${toolCallPayload}\n\n` +
      `event: execute_result\ndata: ${execResultPayload}\n\n` +
      "event: message_end\ndata: {\"thread_id\":\"t1\",\"content\":\"Done\",\"tool_calls\":null}\n\n",
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Run a command{Enter}");

    await waitFor(() => {
      // CodeExecutionCard renders the tool name in its header
      expect(screen.getByTestId("code-execution-card")).toBeInTheDocument();
    });
  });

  it("shows stdout output after execute_result event", async () => {
    const toolCallPayload = JSON.stringify({
      tool_name: "execute",
      tool_input: { command: "echo hello world" },
      run_id: "run-exec-2",
    });
    const execResultPayload = JSON.stringify({
      run_id: "run-exec-2",
      stdout: "hello world\n",
      stderr: "",
      exit_code: 0,
    });

    setupSubAgentFetchMock(
      "event: message_start\ndata: {\"thread_id\":\"t1\"}\n\n" +
      `event: tool_call\ndata: ${toolCallPayload}\n\n` +
      `event: execute_result\ndata: ${execResultPayload}\n\n` +
      "event: message_end\ndata: {\"thread_id\":\"t1\",\"content\":\"Done\",\"tool_calls\":null}\n\n",
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Run echo{Enter}");

    await waitFor(() => {
      // Scope query to the stdout-section to avoid matching the tool args display.
      const stdoutSection = screen.getByTestId("stdout-section");
      expect(
        within(stdoutSection).getByText((content) =>
          content.includes("hello world")
        )
      ).toBeInTheDocument();
    });
  });

  it("shows a success exit-code badge (exit 0) after execute_result", async () => {
    const toolCallPayload = JSON.stringify({
      tool_name: "execute",
      tool_input: { command: "true" },
      run_id: "run-exec-3",
    });
    const execResultPayload = JSON.stringify({
      run_id: "run-exec-3",
      stdout: "",
      stderr: "",
      exit_code: 0,
    });

    setupSubAgentFetchMock(
      "event: message_start\ndata: {\"thread_id\":\"t1\"}\n\n" +
      `event: tool_call\ndata: ${toolCallPayload}\n\n` +
      `event: execute_result\ndata: ${execResultPayload}\n\n` +
      "event: message_end\ndata: {\"thread_id\":\"t1\",\"content\":\"Done\",\"tool_calls\":null}\n\n",
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Exit zero{Enter}");

    await waitFor(() => {
      const badge = screen.getByTestId("exit-code-badge");
      expect(badge).toHaveTextContent("exit 0");
    });
  });

  it("shows a failure exit-code badge for non-zero exit code", async () => {
    const toolCallPayload = JSON.stringify({
      tool_name: "execute",
      tool_input: { command: "false" },
      run_id: "run-exec-4",
    });
    const execResultPayload = JSON.stringify({
      run_id: "run-exec-4",
      stdout: "",
      stderr: "command failed\n",
      exit_code: 1,
    });

    setupSubAgentFetchMock(
      "event: message_start\ndata: {\"thread_id\":\"t1\"}\n\n" +
      `event: tool_call\ndata: ${toolCallPayload}\n\n` +
      `event: execute_result\ndata: ${execResultPayload}\n\n` +
      "event: message_end\ndata: {\"thread_id\":\"t1\",\"content\":\"Done\",\"tool_calls\":null}\n\n",
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Exit one{Enter}");

    await waitFor(() => {
      const badge = screen.getByTestId("exit-code-badge");
      expect(badge).toHaveTextContent("exit 1");
    });
  });

  it("shows an 'exit ?' badge when execute_result omits exit_code", async () => {
    const toolCallPayload = JSON.stringify({
      tool_name: "execute",
      tool_input: { command: "echo partial" },
      run_id: "run-exec-5",
    });
    // Intentionally omit exit_code — simulates a partial/error payload
    const execResultPayload = JSON.stringify({
      run_id: "run-exec-5",
      stdout: "partial\n",
      stderr: "",
    });

    setupSubAgentFetchMock(
      "event: message_start\ndata: {\"thread_id\":\"t1\"}\n\n" +
      `event: tool_call\ndata: ${toolCallPayload}\n\n` +
      `event: execute_result\ndata: ${execResultPayload}\n\n` +
      "event: message_end\ndata: {\"thread_id\":\"t1\",\"content\":\"Done\",\"tool_calls\":null}\n\n",
    );

    await act(async () => {
      render(<AuthProvider><ChatInterface /></AuthProvider>);
    });

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "Unknown exit{Enter}");

    await waitFor(() => {
      const badge = screen.getByTestId("exit-code-badge");
      expect(badge).toHaveTextContent("exit ?");
      expect(badge).toHaveAttribute("aria-label", "Exit code unknown");
    });
  });
});
