"""Custom LangSmith evaluators for Symphony agent quality.

Each evaluator is a callable that receives a ``Run`` and an ``Example``
and returns an ``EvaluationResult``.  They are plugged into
``langsmith.evaluation.evaluate()`` via the ``evaluators`` parameter.
"""

from __future__ import annotations

from langsmith.schemas import Example, Run


def response_not_empty(run: Run, example: Example | None = None) -> dict:
    """Check that the agent produced a non-empty response."""
    output = (run.outputs or {}).get("output", "")
    score = 1.0 if output and len(str(output).strip()) > 0 else 0.0
    return {"key": "response_not_empty", "score": score}


def response_length_check(run: Run, example: Example | None = None) -> dict:
    """Penalise extremely short (<20 chars) or extremely long (>5000 chars) responses."""
    output = str((run.outputs or {}).get("output", ""))
    length = len(output.strip())
    if length < 20:
        score = 0.3
    elif length > 5000:
        score = 0.6
    else:
        score = 1.0
    return {"key": "response_length", "score": score}


def contains_expected_keyword(run: Run, example: Example | None = None) -> dict:
    """Check whether the response contains key terms from the expected output.

    This is a simple keyword-overlap heuristic; for deeper semantic
    comparison use an LLM-as-judge evaluator (see ``run_evals.py``).
    """
    if example is None or not example.outputs:
        return {"key": "contains_expected_keyword", "score": 1.0}

    expected = str(example.outputs.get("expected", "")).lower()
    output = str((run.outputs or {}).get("output", "")).lower()

    # Extract significant words (>4 chars) from expected output
    keywords = {w for w in expected.split() if len(w) > 4}
    if not keywords:
        return {"key": "contains_expected_keyword", "score": 1.0}

    matches = sum(1 for kw in keywords if kw in output)
    score = matches / len(keywords)
    return {"key": "contains_expected_keyword", "score": round(score, 3)}


def no_error_in_output(run: Run, example: Example | None = None) -> dict:
    """Flag runs whose output contains common error indicators."""
    output = str((run.outputs or {}).get("output", "")).lower()
    error_indicators = ["traceback", "error:", "exception:", "failed to"]
    has_error = any(indicator in output for indicator in error_indicators)
    return {"key": "no_error_in_output", "score": 0.0 if has_error else 1.0}
