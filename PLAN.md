# Chat Platform Plan — LangChain Deep Agents

> **Linear Ticket:** [SYM-5](https://linear.app/symphony-cc/issue/SYM-5/create-a-plan-for-a-chat-platform-building-based-on-langchain-deep)
> **Date:** 2026-03-14
> **Status:** Research & Planning Complete

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technology Overview](#2-technology-overview)
3. [Proposed Architecture](#3-proposed-architecture)
4. [Backend Design](#4-backend-design)
5. [Frontend Design](#5-frontend-design)
6. [Agent Design](#6-agent-design)
7. [Data & Persistence Layer](#7-data--persistence-layer)
8. [Streaming & Real-Time Communication](#8-streaming--real-time-communication)
9. [Deployment & Infrastructure](#9-deployment--infrastructure)
10. [Implementation Phases](#10-implementation-phases)
11. [Risk & Mitigation](#11-risk--mitigation)
12. [References](#12-references)

---

## 1. Executive Summary

This plan outlines the architecture and implementation roadmap for an **agentic chat platform** built on **LangChain Deep Agents** — an open-source, production-ready agent harness built on LangChain and LangGraph. Deep Agents provides built-in planning, context management, sub-agent orchestration, and a virtual filesystem, making it an ideal foundation for a multi-purpose chatbot platform that can handle complex, long-running tasks.

The goal is to build a **simplified yet extensible** chat platform that:

- Provides a conversational chat interface backed by LLM-powered agents
- Supports multi-step task planning and execution
- Allows sub-agent delegation for parallel workloads
- Streams responses in real-time
- Persists conversations and agent memory across sessions
- Is provider-agnostic (works with Anthropic, OpenAI, Google, etc.)

---

## 2. Technology Overview

### 2.1 What Are LangChain Deep Agents?

Deep Agents is an opinionated, batteries-included agent harness (MIT licensed) that provides:

| Capability | Description |
|---|---|
| **Planning** | `write_todos` tool for task decomposition and progress tracking |
| **Filesystem** | `read_file`, `write_file`, `edit_file`, `ls`, `glob`, `grep` for context management |
| **Command Execution** | `execute` tool for sandboxed shell operations |
| **Sub-Agent Delegation** | `task` tool for spawning isolated sub-agents with their own context windows |
| **Context Management** | Automatic summarization middleware to handle long conversations |
| **Persistent Memory** | LangGraph Memory Store for cross-session knowledge retention |

### 2.2 Core Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Agent Framework** | `deepagents` (Python) | Batteries-included agent harness on LangGraph |
| **Backend API** | FastAPI | Async, high-performance, native streaming support |
| **Frontend** | Next.js + React 19 + TypeScript | SSR, App Router, excellent streaming support |
| **LLM Client** | `@langchain/langgraph-sdk` | Official SDK with `useChat` streaming hooks |
| **Database** | PostgreSQL + pgvector | Conversation persistence + vector search |
| **Cache/Queue** | Redis | Task queue, session caching, rate limiting |
| **Observability** | LangSmith | Agent tracing, evaluation, debugging |
| **Containerization** | Docker + Docker Compose | Consistent environments, easy deployment |

---

## 3. Proposed Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                     │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐ │
│  │ Chat UI  │  │ Thread   │  │ Tasks/Files Sidebar    │ │
│  │ Messages │  │ List     │  │ (agent artifacts)      │ │
│  │ Input    │  │ History  │  │                        │ │
│  └────┬─────┘  └──────────┘  └────────────────────────┘ │
│       │  useChat / useStream hooks (SSE/WebSocket)       │
└───────┼─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│                  Backend (FastAPI)                        │
│  ┌──────────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ /chat/stream  │  │ /threads │  │ /assistants      │  │
│  │ SSE endpoint  │  │ CRUD     │  │ management       │  │
│  └──────┬───────┘  └──────────┘  └──────────────────┘  │
│         │                                                │
│         ▼                                                │
│  ┌─────────────────────────────────────────────┐        │
│  │          Deep Agent Runtime                  │        │
│  │  ┌────────┐ ┌──────────┐ ┌───────────────┐ │        │
│  │  │Planning│ │Filesystem│ │  Sub-Agents    │ │        │
│  │  │Todos   │ │Backend   │ │  (task tool)   │ │        │
│  │  └────────┘ └──────────┘ └───────────────┘ │        │
│  │                                             │        │
│  │  Middleware Stack:                          │        │
│  │  TodoList → Memory → Skills → Filesystem   │        │
│  │  → SubAgents → Summarization               │        │
│  └─────────────────────────────────────────────┘        │
│         │                                                │
└─────────┼────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│                  Data Layer                               │
│  ┌──────────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ PostgreSQL   │  │ Redis    │  │ LangSmith        │  │
│  │ + pgvector   │  │ Queue    │  │ Tracing          │  │
│  │ Threads/Msgs │  │ Sessions │  │ Observability    │  │
│  └──────────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Backend Design

### 4.1 FastAPI Application Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI app, CORS, lifespan
│   ├── config.py               # Settings via pydantic-settings
│   ├── api/
│   │   ├── routes/
│   │   │   ├── chat.py         # /chat/stream - SSE streaming endpoint
│   │   │   ├── threads.py      # /threads - CRUD for conversations
│   │   │   └── assistants.py   # /assistants - agent config management
│   │   └── deps.py             # Dependency injection
│   ├── agents/
│   │   ├── factory.py          # create_deep_agent() wrappers
│   │   ├── tools/              # Custom tools (@tool decorated)
│   │   │   ├── web_search.py
│   │   │   ├── knowledge_base.py
│   │   │   └── __init__.py
│   │   ├── prompts/            # System prompts per assistant type
│   │   │   ├── general.py
│   │   │   └── researcher.py
│   │   └── middleware.py       # Custom middleware configuration
│   ├── models/                 # SQLAlchemy / Pydantic models
│   │   ├── thread.py
│   │   ├── message.py
│   │   └── user.py
│   ├── services/
│   │   ├── thread_service.py
│   │   └── agent_service.py
│   └── db/
│       ├── session.py          # Async SQLAlchemy session
│       └── migrations/         # Alembic migrations
├── tests/
├── Dockerfile
├── pyproject.toml
└── .env.example
```

### 4.2 Core Agent Factory

```python
# app/agents/factory.py
from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

def create_chat_agent(
    model_name: str = "anthropic:claude-sonnet-4-20250514",
    custom_tools: list | None = None,
    system_prompt: str | None = None,
):
    """Create a Deep Agent configured for the chat platform."""
    model = init_chat_model(model_name)

    agent = create_deep_agent(
        model=model,
        tools=custom_tools or [],
        system_prompt=system_prompt or DEFAULT_SYSTEM_PROMPT,
    )
    return agent
```

### 4.3 Streaming Chat Endpoint

```python
# app/api/routes/chat.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    agent = create_chat_agent()

    async def event_generator():
        async for event in agent.astream(
            {"messages": [{"role": "user", "content": request.message}]},
            stream_mode="messages",
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
```

### 4.4 Key API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat/stream` | Stream agent responses via SSE |
| `GET` | `/threads` | List conversation threads |
| `POST` | `/threads` | Create a new thread |
| `GET` | `/threads/{id}` | Get thread with messages |
| `DELETE` | `/threads/{id}` | Delete a thread |
| `GET` | `/threads/{id}/state` | Get agent state for a thread |
| `POST` | `/threads/{id}/resume` | Resume after human-in-the-loop interrupt |
| `GET` | `/assistants` | List available assistant configs |

---

## 5. Frontend Design

### 5.1 Project Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout, providers, fonts
│   ├── page.tsx                # Main chat page
│   └── globals.css             # Tailwind + custom CSS vars
├── components/
│   ├── chat/
│   │   ├── ChatInterface.tsx   # Main chat container
│   │   ├── MessageList.tsx     # Scrollable message display
│   │   ├── MessageBubble.tsx   # Individual message rendering
│   │   ├── ChatInput.tsx       # User input with submit
│   │   └── ToolCallCard.tsx    # Visualize tool executions
│   ├── threads/
│   │   ├── ThreadList.tsx      # Conversation sidebar
│   │   └── ThreadItem.tsx      # Single thread entry
│   ├── sidebar/
│   │   ├── TasksSidebar.tsx    # Agent task/todo tracking
│   │   └── FilesSidebar.tsx    # Agent-generated files
│   └── ui/                     # Shared UI primitives (Radix-based)
├── providers/
│   ├── ClientProvider.tsx      # LangGraph SDK client
│   └── ChatProvider.tsx        # Chat state context
├── hooks/
│   ├── useAgent.ts             # Agent interaction hook
│   └── useThreads.ts           # Thread management hook
├── lib/
│   ├── config.ts               # Configuration management
│   └── utils.ts                # Helpers
├── package.json
├── tailwind.config.ts
└── tsconfig.json
```

### 5.2 Key Frontend Dependencies

```json
{
  "dependencies": {
    "next": "^16.x",
    "react": "^19.x",
    "@langchain/langgraph-sdk": "^1.0.3",
    "@radix-ui/react-dialog": "^1.x",
    "@radix-ui/react-scroll-area": "^1.x",
    "tailwindcss": "^3.4",
    "react-markdown": "^9.x",
    "react-syntax-highlighter": "^15.x",
    "lucide-react": "^0.4",
    "sonner": "^1.x",
    "swr": "^2.3",
    "nuqs": "^2.4"
  }
}
```

### 5.3 Streaming Integration Pattern

```tsx
// hooks/useAgent.ts
import { useChat } from "@langchain/langgraph-sdk/react";

export function useAgent(threadId: string) {
  const chat = useChat({
    threadId,
    assistantId: process.env.NEXT_PUBLIC_ASSISTANT_ID,
    // Automatically handles streaming, sub-agent tracking,
    // interrupt detection, and message buffering
  });

  return {
    messages: chat.messages,
    submit: chat.submit,
    isStreaming: chat.isLoading,
    interrupt: chat.interrupt,
    resumeInterrupt: chat.resumeInterrupt,
  };
}
```

---

## 6. Agent Design

### 6.1 Simplified Agent Configuration

For the MVP, we start with a single general-purpose agent that leverages Deep Agents' built-in capabilities:

```python
from deepagents import create_deep_agent
from langchain_core.tools import tool

@tool
def search_knowledge_base(query: str) -> str:
    """Search the internal knowledge base for relevant information."""
    # pgvector similarity search
    ...

@tool
def web_search(query: str) -> str:
    """Search the web for up-to-date information."""
    # Tavily or similar search API
    ...

agent = create_deep_agent(
    model=init_chat_model("anthropic:claude-sonnet-4-20250514"),
    tools=[search_knowledge_base, web_search],
    system_prompt="""You are a helpful assistant for the Symphony platform.
    You can search the knowledge base, browse the web, plan complex tasks,
    and delegate subtasks to specialized sub-agents when needed.
    Always be concise and helpful.""",
)
```

### 6.2 Built-in Capabilities (No Extra Code Needed)

Deep Agents provides these out of the box:

- **Task Planning:** The agent automatically uses `write_todos` to break down complex requests
- **Sub-Agent Spawning:** The `task` tool creates isolated sub-agents for parallel work
- **File Management:** Agents can read/write files to persist context and artifacts
- **Context Summarization:** Middleware auto-summarizes long conversations to stay within token limits
- **Persistent Memory:** Cross-session memory via LangGraph Memory Store

### 6.3 Middleware Stack

```python
# Default middleware order (configurable):
# TodoList → Memory → Skills → Filesystem → SubAgents → Summarization
```

Each middleware layer is independently configurable. For the chat platform:

| Middleware | Purpose | Priority |
|---|---|---|
| **TodoList** | Track multi-step tasks | High |
| **Memory** | Persistent cross-session recall | High |
| **Filesystem** | Store artifacts, large outputs | Medium |
| **SubAgents** | Delegate parallel subtasks | Medium |
| **Summarization** | Compress long conversations | High |
| **Skills** | Load AGENTS.md / SKILL.md configs | Low (phase 2) |

### 6.4 Backend Selection

| Backend | Use Case | Phase |
|---|---|---|
| `StateBackend` | In-memory, for development/testing | Phase 1 |
| `StoreBackend` | Persistent store, for production | Phase 2 |
| `CompositeBackend` | Path-based routing to different backends | Phase 3 |

---

## 7. Data & Persistence Layer

### 7.1 Database Schema (PostgreSQL)

```sql
-- Conversation threads
CREATE TABLE threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    title VARCHAR(255),
    assistant_id VARCHAR(100) NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages within threads
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID REFERENCES threads(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'tool'
    content TEXT NOT NULL,
    tool_calls JSONB,          -- tool call metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent checkpoints (LangGraph state persistence)
CREATE TABLE checkpoints (
    thread_id UUID NOT NULL,
    checkpoint_id UUID NOT NULL,
    parent_id UUID,
    checkpoint JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_id)
);

-- Vector store for knowledge base (pgvector)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops);
```

### 7.2 Redis Usage

| Purpose | Key Pattern | TTL |
|---|---|---|
| Session cache | `session:{user_id}` | 24h |
| Rate limiting | `rate:{user_id}:{endpoint}` | 1m |
| Active streams | `stream:{thread_id}` | 30m |

---

## 8. Streaming & Real-Time Communication

### 8.1 Streaming Modes

Deep Agents supports three streaming modes:

| Mode | Description | Use Case |
|---|---|---|
| `"messages"` | Token-by-token message streaming | Chat UI real-time display |
| `"updates"` | State update events | Tool call visualization |
| `"values"` | Full state snapshots | Debugging, state inspection |

### 8.2 Event Types in the Stream

```
data: {"type": "message_start", "message": {...}}
data: {"type": "content_block_delta", "delta": {"text": "Hello"}}
data: {"type": "tool_use", "tool": "web_search", "input": {...}}
data: {"type": "tool_result", "output": "..."}
data: {"type": "subagent_start", "agent_id": "..."}
data: {"type": "subagent_end", "agent_id": "...", "result": "..."}
data: {"type": "interrupt", "reason": "approval_needed", ...}
data: {"type": "message_end"}
```

### 8.3 Human-in-the-Loop Flow

```
Agent detects sensitive operation
  → Emits "interrupt" event
    → Frontend shows approval dialog
      → User approves/rejects
        → POST /threads/{id}/resume with decision
          → Agent continues or aborts
```

---

## 9. Deployment & Infrastructure

### 9.1 Docker Compose (Development)

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/chatplatform
      - REDIS_URL=redis://redis:6379
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on: [db, redis]

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000

  db:
    image: pgvector/pgvector:pg16
    volumes: [pgdata:/var/lib/postgresql/data]
    environment:
      - POSTGRES_DB=chatplatform
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

### 9.2 Production Deployment Options

| Option | Pros | Cons |
|---|---|---|
| **LangGraph Cloud** | Managed, built-in persistence, easy scaling | Vendor lock-in, cost |
| **Self-hosted (Docker/K8s)** | Full control, cost-effective at scale | Operational overhead |
| **Hybrid** | Control plane managed, compute self-hosted | Moderate complexity |

### 9.3 Environment Variables

```bash
# LLM Provider
ANTHROPIC_API_KEY=sk-ant-...
# Alternative: OPENAI_API_KEY, GOOGLE_API_KEY, etc.

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/chatplatform

# Redis
REDIS_URL=redis://localhost:6379

# Observability
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=chat-platform

# Deep Agents
DEEPAGENTS_ALLOW_COMMANDS=python,node,curl
DEEPAGENTS_AUTO_APPROVE=false

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_ASSISTANT_ID=general-chat
```

---

## 10. Implementation Phases

### Phase 1 — MVP (Weeks 1–3)

**Goal:** Working chat interface with a single Deep Agent

| Task | Details | Est. |
|---|---|---|
| Project scaffolding | FastAPI backend + Next.js frontend + Docker Compose | 2d |
| Basic Deep Agent setup | `create_deep_agent()` with default config | 1d |
| Streaming endpoint | `POST /chat/stream` with SSE | 2d |
| Chat UI | Message list, input box, streaming display | 3d |
| Thread management | Create/list/delete conversations | 2d |
| PostgreSQL setup | Thread + message persistence | 2d |
| Basic auth | API key or simple JWT | 1d |
| **Testing & polish** | | 2d |

**Deliverable:** Users can chat with an agent that plans, uses tools, and streams responses.

### Phase 2 — Enhanced Features (Weeks 4–6)

**Goal:** Production-quality chat with memory and observability

| Task | Details | Est. |
|---|---|---|
| Persistent memory | LangGraph Memory Store integration | 2d |
| Knowledge base | pgvector document ingestion + search tool | 3d |
| Web search tool | Tavily/Brave search integration | 1d |
| Human-in-the-loop | Tool approval UI + interrupt/resume flow | 3d |
| LangSmith integration | Tracing, cost tracking, debugging | 1d |
| Thread sidebar | Task tracking, agent-generated files display | 2d |
| Rate limiting | Redis-based per-user rate limits | 1d |
| **Testing & polish** | | 2d |

**Deliverable:** Full-featured chat with memory, search, and observability.

### Phase 3 — Scale & Specialize (Weeks 7–10)

**Goal:** Multi-agent specialization and production hardening

| Task | Details | Est. |
|---|---|---|
| Multiple assistant types | Research agent, coding agent, writing agent | 3d |
| Sub-agent visualization | UI for sub-agent progress tracking | 2d |
| User management | Proper auth (OAuth/SSO), user profiles | 3d |
| StoreBackend migration | Persistent filesystem backend for production | 2d |
| Evaluation pipeline | LangSmith offline eval on test sets | 2d |
| Performance optimization | Prompt caching, connection pooling | 2d |
| Load testing | Concurrent user simulation | 1d |
| Documentation | API docs, deployment guide, user guide | 2d |
| **Testing & polish** | | 3d |

**Deliverable:** Production-ready platform with specialized agents and enterprise features.

---

## 11. Risk & Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| **LLM cost overruns** | High monthly bills from agent loops | Set token budgets, use summarization middleware, monitor via LangSmith |
| **Agent hallucination** | Incorrect or harmful responses | Implement guardrails, human-in-the-loop for sensitive actions, evaluation pipeline |
| **Context window overflow** | Agent loses track of conversation | Summarization middleware (built-in), sub-agent isolation |
| **Vendor lock-in** | Dependency on single LLM provider | Deep Agents is provider-agnostic; abstract model selection |
| **Deep Agents breaking changes** | Framework API changes | Pin versions, maintain integration tests, track releases |
| **Streaming reliability** | Dropped connections, partial responses | SSE retry logic, client-side reconnection, message deduplication |
| **Data privacy** | Sensitive data sent to LLM providers | Self-hosted models option, data classification, PII filtering |

---

## 12. References

- [LangChain Deep Agents — GitHub](https://github.com/langchain-ai/deepagents)
- [Deep Agents Documentation](https://docs.langchain.com/oss/python/deepagents/overview)
- [LangChain Deep Agents Product Page](https://www.langchain.com/deep-agents)
- [Deep Agents UI — GitHub](https://deepwiki.com/langchain-ai/deep-agents-ui/1-deep-agents-ui-overview)
- [LangGraph Agent Orchestration](https://www.langchain.com/langgraph)
- [FastAPI + LangGraph Production Template](https://github.com/wassim249/fastapi-langgraph-agent-production-ready-template)
- [Agent Service Toolkit (FastAPI + LangGraph + Streamlit)](https://github.com/JoshuaC215/agent-service-toolkit)
- [LangChain Deep Agents — Medium Overview](https://cobusgreyling.medium.com/langchain-deep-agents-a-meta-toolkit-for-building-long-horizon-ai-agents-e56ff4ac741f)
- [Deep Agents DataCamp Tutorial](https://www.datacamp.com/tutorial/deep-agents)
- [LangSmith Deployment Infrastructure](https://www.langchain.com/langsmith/deployment)
- [LangGraph Architecture Guide 2025](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-ai-framework-2025-complete-architecture-guide-multi-agent-orchestration-analysis)
- [Production Multi-Agent Communication (2026)](https://www.marktechpost.com/2026/03/01/how-to-design-a-production-grade-multi-agent-communication-system-using-langgraph-structured-message-bus-acp-logging-and-persistent-shared-state-architecture/)
- [State of AI Agents — LangChain](https://www.langchain.com/state-of-agent-engineering)
- [CopilotKit + Deep Agents Frontend Guide](https://www.copilotkit.ai/blog/how-to-build-a-frontend-for-langchain-deep-agents-with-copilotkit)
- [Official LangChain Blog — Deep Agents](https://blog.langchain.com/deep-agents/)
