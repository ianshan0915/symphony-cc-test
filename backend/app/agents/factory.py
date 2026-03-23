"""Deep Agent factory — creates configured deep agents via the ``deepagents`` package.

Supports specialized agent types (researcher, coder, writer) via
``assistant_type`` parameter, with prompt caching for repeat invocations.

Long-conversation support
--------------------------
``deepagents`` automatically includes ``SummarizationMiddleware`` in every
agent with model-aware defaults (85 % fraction trigger / 10 % fraction keep
for profiled models).  Symphony adds an *explicit* second instance so that:

* thresholds are visible and documented in ``app.config.Settings``,
* a message-count safety net fires even for models without profile data,
* the ``keep`` policy is always the same predictable "last N messages"
  regardless of model context-window size.

Configuration knobs (all settable via environment variables):

``SUMMARIZATION_TRIGGER_FRACTION`` (default 0.85)
    Fraction of the model's context window that activates summarisation.
``SUMMARIZATION_TRIGGER_MESSAGES`` (default 200)
    Message-count fallback trigger (models without profile data).
``SUMMARIZATION_KEEP_MESSAGES`` (default 20)
    Number of recent messages preserved verbatim after summarisation.
``SUMMARIZATION_SUMMARY_PROMPT`` (default "")
    Optional custom prompt for the summarisation LLM call; empty → deepagents
    default prompt.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from deepagents import create_deep_agent as _deepagents_create
from deepagents.backends import BackendContext, CompositeBackend, StateBackend, StoreBackend
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from app.agents.middleware import get_checkpointer, get_memory_store
from app.agents.prompts import (
    GENERAL_SYSTEM_PROMPT,
    get_prompt_for_agent_type,
    get_tools_for_agent_type,
)
from app.agents.sandbox import create_sandbox_backend, sandbox_manager
from app.agents.skills import resolve_skill_paths
from app.agents.subagents import build_subagent_configs
from app.agents.tools import TOOL_REGISTRY
from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Runtime context schema — carries per-request data (e.g. user_id) into the
# agent's LangGraph runtime so backend factories can resolve user-scoped
# namespaces without coupling to LangGraph config internals.
# ---------------------------------------------------------------------------


@dataclass
class UserContext:
    """Runtime context for deep agents, carrying the authenticated user's ID.

    Passed as ``context=UserContext(user_id=...)`` when invoking the agent.
    The ``_user_ns_factory`` below reads ``ctx.runtime.context.user_id`` to
    resolve the per-user ``("filesystem", user_id)`` store namespace so that
    ``StoreBackend`` reads/writes to the correct user's AGENTS.md.
    """

    user_id: str | None = None


def _user_ns_factory(ctx: BackendContext) -> tuple[str, ...]:
    """Resolve the LangGraph store namespace for a backend operation.

    When a ``user_id`` is present in the runtime context the namespace is
    scoped to that user: ``("filesystem", user_id)``.  This matches exactly
    the namespace written by ``set_agents_md(content, user_id=...)`` in
    ``middleware.py``, so the agent reads the same data the API writes.

    Falls back to the global ``("filesystem",)`` namespace when no user
    context is available (e.g. background jobs, tests without auth context).
    """
    context = getattr(ctx.runtime, "context", None)
    user_id = getattr(context, "user_id", None) if context is not None else None
    if user_id:
        return ("filesystem", str(user_id))
    return ("filesystem",)


# ---------------------------------------------------------------------------
# Prompt cache — avoids repeated string processing for frequent prompts
# ---------------------------------------------------------------------------

_prompt_cache: dict[str, str] = {}


def _get_cached_prompt(prompt: str) -> str:
    """Return the prompt from cache (by content hash), populating if needed.

    This is a content-addressable cache: identical prompt strings share
    a single cached entry regardless of how they were constructed.
    """
    key = hashlib.sha256(prompt.encode()).hexdigest()[:16]
    if key not in _prompt_cache:
        _prompt_cache[key] = prompt
        logger.debug("Prompt cached (key=%s, length=%d)", key, len(prompt))
    return _prompt_cache[key]


@lru_cache(maxsize=16)
def _get_agent_type_prompt(agent_type: str) -> str:
    """Return and cache the system prompt for a given agent type.

    Uses ``functools.lru_cache`` so lookups after the first call for each
    agent type are O(1) with no hashing overhead.
    """
    return get_prompt_for_agent_type(agent_type)


def clear_prompt_cache() -> None:
    """Clear all prompt caches. Useful for testing or dynamic prompt updates."""
    _prompt_cache.clear()
    _get_agent_type_prompt.cache_clear()
    logger.debug("Prompt caches cleared")


# ---------------------------------------------------------------------------
# LangSmith configuration
# ---------------------------------------------------------------------------


def _configure_langsmith() -> None:
    """Set LangSmith environment variables from application settings.

    LangChain reads tracing configuration from environment variables.
    This function bridges our Pydantic settings to those env vars so
    tracing activates automatically when configured.
    """
    if settings.langchain_tracing_v2 and settings.langchain_api_key:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langchain_api_key)
        os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)
        if settings.langchain_endpoint:
            os.environ.setdefault("LANGCHAIN_ENDPOINT", settings.langchain_endpoint)
        logger.info(
            "LangSmith tracing enabled for project '%s'",
            settings.langchain_project,
        )
    else:
        logger.debug("LangSmith tracing not configured — skipping")


# ---------------------------------------------------------------------------
# Chat model instantiation
# ---------------------------------------------------------------------------


def _get_chat_model(model_name: str | None = None, **kwargs: Any) -> BaseChatModel:
    """Instantiate the appropriate chat model based on model name.

    Supports OpenAI (gpt-*) and Anthropic (claude-*) model families.
    Falls back to ``settings.default_model`` when *model_name* is ``None``.
    """
    model = model_name or settings.default_model

    if model.startswith("claude"):
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise ImportError(
                "langchain-anthropic is required for Anthropic models. "
                "Install it with: pip install langchain-anthropic"
            ) from exc
        anthropic_kwargs: dict[str, Any] = {
            "model": model,
            "anthropic_api_key": settings.anthropic_api_key or None,
            "streaming": True,
        }
        if settings.anthropic_base_url:
            anthropic_kwargs["anthropic_api_url"] = settings.anthropic_base_url
        return ChatAnthropic(**(anthropic_kwargs | kwargs))  # type: ignore[no-any-return, unused-ignore]

    # Default to OpenAI-compatible models
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise ImportError(
            "langchain-openai is required for OpenAI models. "
            "Install it with: pip install langchain-openai"
        ) from exc
    openai_kwargs: dict[str, Any] = {
        "model": model,
        "api_key": settings.openai_api_key or None,  # type: ignore[arg-type, unused-ignore]
        "streaming": True,
    }
    if settings.openai_base_url:
        openai_kwargs["base_url"] = settings.openai_base_url
    return ChatOpenAI(**(openai_kwargs | kwargs))


# ---------------------------------------------------------------------------
# Tool resolution
# ---------------------------------------------------------------------------


def _resolve_tools(
    tools: Sequence[BaseTool] | None,
    assistant_type: str | None,
) -> list[BaseTool]:
    """Resolve the tool list for an agent.

    Priority:
    1. Explicitly provided ``tools`` sequence.
    2. Tool names from the agent type's recommended list.
    3. All registered tools (fallback).
    """
    if tools is not None:
        return list(tools)

    # If an assistant type specifies recommended tools, filter the registry
    if assistant_type:
        recommended = get_tools_for_agent_type(assistant_type)
        if recommended is not None:
            resolved = []
            for tool_name in recommended:
                if tool_name in TOOL_REGISTRY:
                    resolved.append(TOOL_REGISTRY[tool_name])
                else:
                    logger.warning(
                        "Tool '%s' recommended for agent type '%s' not found in registry",
                        tool_name,
                        assistant_type,
                    )
            if resolved:
                return resolved
            # Fall through to all tools if none of the recommended tools exist
            logger.warning(
                "No recommended tools found for agent type '%s'; using all tools",
                assistant_type,
            )

    return list(TOOL_REGISTRY.values())


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


def _make_default_backend() -> Any:
    """Create the default CompositeBackend factory for deep agents.

    Returns a callable ``(ToolRuntime) -> CompositeBackend`` that routes:

    * ``/memories/`` paths → ``StoreBackend`` (persistent, cross-thread storage)
    * All other paths → sandbox backend when configured, otherwise
      ``StateBackend`` (ephemeral, checkpointed per-thread)

    When ``SANDBOX_BACKEND`` is set to ``LOCAL_SHELL`` (the default),
    :class:`~deepagents.backends.LocalShellBackend` is used as the default
    backend.  This provides both native filesystem operations *and* the
    ``execute`` tool so agents can run shell commands in addition to reading
    and writing files.

    Setting ``SANDBOX_BACKEND=NONE`` disables the sandbox and falls back
    to :class:`~deepagents.backends.StateBackend` (no ``execute`` tool).

    ``StoreBackend`` resolves the LangGraph store from the runtime at call
    time (via ``rt.store``), so no store reference is needed at factory
    construction time.

    Sandbox lifecycle
    -----------------
    When a ``thread_id`` is available in the LangGraph runtime config (the
    normal case for all agent invocations), the backend is obtained via
    :data:`~app.agents.sandbox.sandbox_manager` so that:

    * The same backend instance is reused for all turns in a session.
    * :meth:`~app.agents.sandbox.SandboxManager.cleanup_all` called at
      shutdown can terminate all active cloud sandboxes.

    When no ``thread_id`` is present (e.g. unit tests or direct
    ``_backend_factory`` calls without LangGraph config), the factory
    falls back to :func:`~app.agents.sandbox.create_sandbox_backend` and
    creates a fresh, untracked instance — acceptable because
    ``LocalShellBackend`` in virtual mode is stateless.
    """

    def _backend_factory(rt: Any) -> CompositeBackend:
        # Extract thread_id from the LangGraph runtime config so the same
        # sandbox backend is reused for all turns in a session and can be
        # properly cleaned up at session end / shutdown.
        config = getattr(rt, "config", None)
        thread_id: str | None = None
        if isinstance(config, dict):
            thread_id = config.get("configurable", {}).get("thread_id")

        if thread_id:
            sandbox = sandbox_manager.get_or_create(thread_id)
        else:
            # No thread_id available (e.g. tests): create a fresh, untracked
            # instance.  LocalShellBackend is stateless so this is safe.
            sandbox = create_sandbox_backend()

        default: Any = sandbox if sandbox is not None else StateBackend(rt)

        return CompositeBackend(
            default=default,
            # Pass an explicit namespace factory so StoreBackend resolves the
            # per-user namespace ("filesystem", user_id) instead of the legacy
            # global ("filesystem",).  This ensures the agent reads from the
            # same namespace the API writes to via set_agents_md(user_id=...).
            routes={"/memories/": StoreBackend(rt, namespace=_user_ns_factory)},
        )

    return _backend_factory


def create_deep_agent(
    *,
    model_name: str | None = None,
    tools: Sequence[BaseTool] | None = None,
    system_prompt: str | None = None,
    custom_system_prompt: str | None = None,
    assistant_type: str | None = None,
    skills: list[str] | None = None,
    extra_skill_dirs: list[str] | None = None,
    checkpointer: Any | None = None,
    store: Any | None = None,
    backend: Any | None = None,
    model_kwargs: dict[str, Any] | None = None,
    subagents: list[dict[str, Any]] | None = None,
    enable_subagents: bool = True,
    interrupt_on: dict[str, Any] | list[str] | None = None,
    response_format: type[BaseModel] | None = None,
) -> CompiledStateGraph:  # type: ignore[type-arg]
    """Create a deep agent via the ``deepagents`` package.

    Parameters
    ----------
    model_name:
        LLM model identifier (e.g. ``"gpt-4o"``, ``"claude-3-sonnet-20240229"``).
        Defaults to ``settings.default_model``.
    tools:
        Sequence of LangChain tools available to the agent.
        Defaults to tools recommended for the ``assistant_type``, or all
        registered tools if no type is specified.
    system_prompt:
        Explicit system prompt override. Takes precedence over ``assistant_type``.
    custom_system_prompt:
        User-provided custom system prompt. Layered on top of (not replacing)
        the resolved system prompt from skills/assistant_type. Appended after
        the main prompt.
    assistant_type:
        Agent specialization type (``"researcher"``, ``"coder"``, ``"writer"``,
        or ``"general"``). Determines the system prompt and default tool set.
        Ignored when ``system_prompt`` is provided.
    skills:
        Explicit list of skill names to load. Takes precedence over
        ``assistant_type`` skill resolution. Skill directories are resolved
        from the system-wide skills directory and any ``extra_skill_dirs``.
    extra_skill_dirs:
        Additional directories to scan for skills beyond the system-wide
        skills directory. Useful for project-level or user-level skills.
    checkpointer:
        LangGraph checkpointer for persisting thread state across invocations.
        Defaults to the shared checkpointer (``AsyncPostgresSaver`` when
        available, otherwise ``MemorySaver``).
    store:
        LangGraph memory store for cross-turn context persistence.
        Defaults to the shared store (``AsyncPostgresStore`` when available,
        otherwise ``InMemoryStore``).
    backend:
        Filesystem backend (or factory callable ``(ToolRuntime) -> Backend``)
        for native filesystem tools. Defaults to a ``CompositeBackend`` with
        ``StateBackend`` for general files and ``StoreBackend`` for
        ``/memories/`` paths (persistent cross-thread storage).
    model_kwargs:
        Additional keyword arguments forwarded to the chat model constructor.
    subagents:
        Explicit list of subagent configuration dicts to pass to the
        ``deepagents`` framework.  Each dict should have ``name``,
        ``model``, ``system_prompt``, and ``tools`` keys.  When ``None``
        (default) and *enable_subagents* is ``True``, default subagent
        configs for researcher, coder, and writer are built automatically.
    enable_subagents:
        Whether to attach subagent configurations to the supervisor agent.
        Defaults to ``True``.  Set to ``False`` to create a standalone
        agent without delegation capabilities (backwards-compatible mode).
    interrupt_on:
        Tool names that should trigger a human-in-the-loop interrupt before
        execution.  Accepts either a list of tool name strings for simple
        approve/reject, or a dict mapping tool names to interrupt config
        dicts (e.g. ``{"allowed_decisions": ["approve", "edit", "reject"]}``).
        When ``None`` (default) no interrupts are configured and the agent
        runs autonomously.
    response_format:
        Optional Pydantic model class for structured output.  When provided,
        the agent constrains its final response to the given schema and
        returns the validated instance in ``result["structured_response"]``
        (via ``ainvoke()``) or in the ``structured_response`` key of the
        final state update (via ``astream()``).  Use predefined formats from
        :mod:`app.agents.response_formats` or supply a custom Pydantic class.
        When ``None`` (default) the agent returns unstructured text as usual.

    Returns
    -------
    CompiledStateGraph
        A compiled deep agent ready for streaming invocation.

    Notes
    -----
    **Summarization / long-conversation support**

    ``deepagents`` includes ``SummarizationMiddleware`` automatically with
    model-aware defaults (fraction-based trigger for profiled models).
    Symphony adds an *explicit* second instance (appended to the middleware
    stack via the ``middleware`` kwarg) so that:

    * Thresholds are surfaced in application config and logs.
    * A message-count safety net applies even for models without profile data.
    * The ``keep`` policy is a predictable "last N messages" (configurable via
      ``settings.summarization_keep_messages``) rather than a fraction.

    The middleware is positioned *after* the deepagents default, meaning the
    default model-aware summarisation fires first; the explicit one provides a
    secondary safety net for cases where the fraction-based trigger does not
    apply (e.g. custom/unlisted models).
    """
    # Ensure LangSmith tracing env vars are configured
    _configure_langsmith()

    llm = _get_chat_model(model_name, **(model_kwargs or {}))

    # Resolve system prompt: explicit > assistant_type > general default
    if system_prompt:
        prompt = _get_cached_prompt(system_prompt)
    elif assistant_type:
        prompt = _get_agent_type_prompt(assistant_type)
    else:
        prompt = GENERAL_SYSTEM_PROMPT

    # Layer custom system prompt on top of the resolved prompt
    if custom_system_prompt:
        prompt = prompt + "\n\n" + custom_system_prompt

    # Resolve tools
    agent_tools = _resolve_tools(tools, assistant_type)

    # Resolve skills via progressive disclosure
    skill_paths = resolve_skill_paths(
        skills=skills,
        assistant_type=assistant_type,
        extra_skill_dirs=extra_skill_dirs,  # type: ignore[arg-type]
    )

    saver = checkpointer if checkpointer is not None else get_checkpointer()
    memory_store = store if store is not None else get_memory_store()

    # Resolve backend: explicit > default CompositeBackend factory
    agent_backend = backend if backend is not None else _make_default_backend()

    # Resolve subagent configurations
    resolved_subagents: list[dict[str, Any]] | None = None
    if subagents is not None:
        resolved_subagents = subagents
    elif enable_subagents:
        resolved_subagents = build_subagent_configs(
            model_name=model_name,
            model_kwargs=model_kwargs,
        )

    logger.info(
        "Creating deep agent: model=%s, type=%s, tools=%d, skills=%d, subagents=%d, "
        "checkpointer=%s, store=%s, backend=%s, sandbox=%s, response_format=%s",
        model_name or settings.default_model,
        assistant_type or "general",
        len(agent_tools),
        len(skill_paths),
        len(resolved_subagents) if resolved_subagents else 0,
        type(saver).__name__,
        type(memory_store).__name__,
        "factory" if callable(agent_backend) else type(agent_backend).__name__,
        settings.sandbox_backend,
        response_format.__name__ if response_format is not None else None,
    )

    create_kwargs: dict[str, Any] = {
        "model": llm,
        "tools": agent_tools,
        "system_prompt": prompt,
        "checkpointer": saver,
        "store": memory_store,
        "backend": agent_backend,
        # context_schema=UserContext allows the LangGraph runtime to accept a
        # UserContext instance at invocation time (passed as
        # context=UserContext(user_id=...)).  The _user_ns_factory above reads
        # ctx.runtime.context.user_id to resolve the per-user store namespace
        # so the agent loads the correct user's AGENTS.md.
        "context_schema": UserContext,
        # Load persistent memory from the store-backed /memories/ path.
        # The CompositeBackend routes /memories/ to StoreBackend so the file
        # survives across all threads.  The same path is used when seeding
        # (middleware._seed_agents_md_if_missing) and the API endpoints
        # (GET/PUT /memory), ensuring agents always see the latest content.
        "memory": ["/memories/AGENTS.md"],
    }

    # Pass skills to deepagents if any were resolved
    if skill_paths:
        create_kwargs["skills"] = skill_paths

    # Pass subagent configs — the framework automatically provides a `task` tool
    # to the supervisor agent for delegating work to subagents
    if resolved_subagents:
        create_kwargs["subagents"] = resolved_subagents

    # Pass interrupt_on when provided (human-in-the-loop tool approval)
    if interrupt_on is not None:
        create_kwargs["interrupt_on"] = interrupt_on

    # Pass response_format when provided (structured output via Pydantic schema)
    if response_format is not None:
        create_kwargs["response_format"] = response_format

    agent = _deepagents_create(**create_kwargs)

    return agent
