"""Deep Agent factory — creates configured LangGraph ReAct agents.

Supports specialized agent types (researcher, coder, writer) via
``assistant_type`` parameter, with prompt caching for repeat invocations.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.agents.middleware import get_checkpointer, get_memory_store
from app.agents.prompts import (
    GENERAL_SYSTEM_PROMPT,
    get_prompt_for_agent_type,
    get_tools_for_agent_type,
)
from app.agents.tools import TOOL_REGISTRY
from app.config import settings

logger = logging.getLogger(__name__)


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
        return ChatAnthropic(  # type: ignore[no-any-return]
            model=model,
            anthropic_api_key=settings.anthropic_api_key or None,
            streaming=True,
            **kwargs,
        )

    # Default to OpenAI-compatible models
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise ImportError(
            "langchain-openai is required for OpenAI models. "
            "Install it with: pip install langchain-openai"
        ) from exc
    return ChatOpenAI(
        model=model,
        api_key=settings.openai_api_key or None,  # type: ignore[arg-type]
        streaming=True,
        **kwargs,
    )


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


def create_deep_agent(
    *,
    model_name: str | None = None,
    tools: Sequence[BaseTool] | None = None,
    system_prompt: str | None = None,
    assistant_type: str | None = None,
    checkpointer: Any | None = None,
    store: Any | None = None,
    model_kwargs: dict[str, Any] | None = None,
) -> CompiledStateGraph:  # type: ignore[type-arg]
    """Create a LangGraph ReAct agent with the given configuration.

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
    assistant_type:
        Agent specialization type (``"researcher"``, ``"coder"``, ``"writer"``,
        or ``"general"``). Determines the system prompt and default tool set.
        Ignored when ``system_prompt`` is provided.
    checkpointer:
        LangGraph checkpointer for persisting thread state across invocations.
        Defaults to the shared checkpointer (``AsyncPostgresSaver`` when
        available, otherwise ``MemorySaver``).
    store:
        LangGraph memory store for cross-turn context persistence.
        Defaults to the shared store (``AsyncPostgresStore`` when available,
        otherwise ``InMemoryStore``).
    model_kwargs:
        Additional keyword arguments forwarded to the chat model constructor.

    Returns
    -------
    CompiledStateGraph
        A compiled LangGraph agent ready for streaming invocation.
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

    # Resolve tools
    agent_tools = _resolve_tools(tools, assistant_type)

    saver = checkpointer if checkpointer is not None else get_checkpointer()
    memory_store = store if store is not None else get_memory_store()

    logger.info(
        "Creating deep agent: model=%s, type=%s, tools=%d, checkpointer=%s, store=%s",
        model_name or settings.default_model,
        assistant_type or "general",
        len(agent_tools),
        type(saver).__name__,
        type(memory_store).__name__,
    )

    agent = create_react_agent(
        model=llm,
        tools=agent_tools,
        prompt=prompt,
        checkpointer=saver,
        store=memory_store,
    )

    return agent
