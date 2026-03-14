"""Deep Agent factory — creates configured LangGraph ReAct agents."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.agents.prompts.general import GENERAL_SYSTEM_PROMPT
from app.config import settings

logger = logging.getLogger(__name__)


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
        return ChatAnthropic(
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
        api_key=settings.openai_api_key or None,
        streaming=True,
        **kwargs,
    )


def create_deep_agent(
    *,
    model_name: str | None = None,
    tools: Sequence[BaseTool] | None = None,
    system_prompt: str | None = None,
    checkpointer: Any | None = None,
    model_kwargs: dict[str, Any] | None = None,
) -> CompiledStateGraph:
    """Create a LangGraph ReAct agent with the given configuration.

    Parameters
    ----------
    model_name:
        LLM model identifier (e.g. ``"gpt-4o"``, ``"claude-3-sonnet-20240229"``).
        Defaults to ``settings.default_model``.
    tools:
        Sequence of LangChain tools available to the agent.
        Defaults to an empty list (pure conversational agent).
    system_prompt:
        System prompt for the agent. Defaults to the general-purpose prompt.
    checkpointer:
        LangGraph checkpointer for persisting thread state across invocations.
        Defaults to an in-memory ``MemorySaver``.
    model_kwargs:
        Additional keyword arguments forwarded to the chat model constructor.

    Returns
    -------
    CompiledStateGraph
        A compiled LangGraph agent ready for streaming invocation.
    """
    llm = _get_chat_model(model_name, **(model_kwargs or {}))
    prompt = system_prompt or GENERAL_SYSTEM_PROMPT
    agent_tools: list[BaseTool] = list(tools) if tools else []
    saver = checkpointer if checkpointer is not None else MemorySaver()

    logger.info(
        "Creating deep agent: model=%s, tools=%d, checkpointer=%s",
        model_name or settings.default_model,
        len(agent_tools),
        type(saver).__name__,
    )

    agent = create_react_agent(
        model=llm,
        tools=agent_tools,
        prompt=prompt,
        checkpointer=saver,
    )

    return agent
