#!/usr/bin/env python3
"""Scheduled evaluation runner for Symphony agent quality monitoring.

This script is designed to be invoked by an external scheduler (cron,
GitHub Actions, Kubernetes CronJob, etc.) on a regular cadence — e.g.
every 6 hours — to track agent quality over time.

Usage::

    # Run once (suitable for cron)
    python -m evals.schedule_evals

    # Example crontab entry — every 6 hours
    # 0 */6 * * * cd /app/backend && python -m evals.schedule_evals >> /var/log/evals.log 2>&1

    # Example GitHub Actions schedule (in .github/workflows/evals.yml):
    #   on:
    #     schedule:
    #       - cron: '0 */6 * * *'

Environment variables::

    LANGCHAIN_API_KEY       — required
    LANGCHAIN_TRACING_V2    — set to ``true``
    LANGCHAIN_PROJECT       — project name (default: symphony)
    OPENAI_API_KEY / ANTHROPIC_API_KEY — for LLM invocation
    EVAL_DATASET            — override dataset name (optional)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)


def main() -> None:
    """Run scheduled evaluation and log results as structured JSON."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    api_key = os.environ.get("LANGCHAIN_API_KEY")
    if not api_key:
        logger.error("LANGCHAIN_API_KEY is not set — skipping scheduled eval")
        sys.exit(1)

    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")

    dataset = os.environ.get("EVAL_DATASET")

    from evals.run_evals import run_evaluation

    try:
        summary = run_evaluation(dataset)
        record = {
            "event": "eval_run_completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **summary,
        }
        # Emit structured log for ingestion by log aggregators
        print(json.dumps(record))
    except Exception:
        logger.exception("Scheduled evaluation failed")
        record = {
            "event": "eval_run_failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(record))
        sys.exit(1)


if __name__ == "__main__":
    main()
