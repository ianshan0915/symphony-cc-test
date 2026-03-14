#!/usr/bin/env python3
"""Run the Symphony LangSmith evaluation pipeline.

Usage::

    # One-off run (uses the golden dataset)
    python -m evals.run_evals

    # Override dataset name
    python -m evals.run_evals --dataset my-custom-dataset

    # Scheduled via cron (see ``schedule_evals.py``)

Environment variables required::

    LANGCHAIN_API_KEY       — LangSmith API key
    LANGCHAIN_TRACING_V2    — must be ``true``
    LANGCHAIN_PROJECT       — project name (default: symphony)
    OPENAI_API_KEY          — (or ANTHROPIC_API_KEY) for the LLM
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

# Ensure the backend package is importable when running as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langsmith import Client
from langsmith.evaluation import evaluate

from evals.dataset import DATASET_NAME, ensure_dataset
from evals.evaluators import (
    contains_expected_keyword,
    no_error_in_output,
    response_length_check,
    response_not_empty,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Target function — invokes the Symphony agent
# ---------------------------------------------------------------------------


def _make_target() -> Any:
    """Build the target function that LangSmith will call for each example.

    We lazily import the agent factory here so environment variables
    (LangSmith, model keys) are already configured before any LangChain
    code is imported.
    """
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.store.memory import InMemoryStore

    from app.agents.factory import create_deep_agent

    # Create a lightweight agent for evaluation (in-memory backends are fine)
    agent = create_deep_agent(
        checkpointer=MemorySaver(),
        store=InMemoryStore(),
    )

    def target(inputs: dict[str, Any]) -> dict[str, Any]:
        """Invoke the agent synchronously for a single evaluation example."""
        user_input = inputs.get("input", "")
        config = {"configurable": {"thread_id": f"eval-{id(inputs)}"}}

        # Run the async agent in a new event loop (langsmith evaluate is sync)
        result = asyncio.run(
            agent.ainvoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
            )
        )

        # Extract the last AI message content
        messages = result.get("messages", [])
        if messages:
            last = messages[-1]
            content = getattr(last, "content", str(last))
        else:
            content = ""

        return {"output": content}

    return target


# ---------------------------------------------------------------------------
# Main evaluation runner
# ---------------------------------------------------------------------------


def run_evaluation(dataset_name: str | None = None) -> dict[str, Any]:
    """Execute the evaluation suite and return a summary dict.

    Parameters
    ----------
    dataset_name:
        LangSmith dataset to evaluate against.  Defaults to the golden
        dataset (created automatically if missing).

    Returns
    -------
    dict
        Summary with keys: ``dataset``, ``timestamp``, ``num_examples``,
        ``results``.
    """
    client = Client()
    ds_name = dataset_name or ensure_dataset(client)

    logger.info("Running evaluation against dataset '%s'", ds_name)

    target = _make_target()

    experiment_prefix = f"symphony-eval-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    results = evaluate(
        target,
        data=ds_name,
        evaluators=[
            response_not_empty,
            response_length_check,
            contains_expected_keyword,
            no_error_in_output,
        ],
        experiment_prefix=experiment_prefix,
        client=client,
    )

    summary = {
        "dataset": ds_name,
        "experiment_prefix": experiment_prefix,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "num_examples": len(list(results)),
    }

    logger.info("Evaluation complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for the evaluation runner."""
    parser = argparse.ArgumentParser(description="Run Symphony agent evaluations")
    parser.add_argument(
        "--dataset",
        default=None,
        help=f"LangSmith dataset name (default: {DATASET_NAME})",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Validate required env vars
    if not os.environ.get("LANGCHAIN_API_KEY"):
        logger.error("LANGCHAIN_API_KEY is not set — cannot run evaluations")
        sys.exit(1)

    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")

    summary = run_evaluation(args.dataset)
    print(f"\n✓ Evaluation complete — {summary['num_examples']} examples evaluated")
    print(f"  Experiment: {summary['experiment_prefix']}")
    print(f"  Dataset:    {summary['dataset']}")


if __name__ == "__main__":
    main()
