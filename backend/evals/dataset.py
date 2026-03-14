"""Evaluation dataset management for LangSmith.

Provides helpers to create and maintain golden datasets used by the
evaluation pipeline.  Datasets are stored in LangSmith so they can be
versioned, shared, and used in CI.
"""

from __future__ import annotations

from langsmith import Client

# ---------------------------------------------------------------------------
# Default dataset name
# ---------------------------------------------------------------------------

DATASET_NAME = "symphony-agent-golden"

# ---------------------------------------------------------------------------
# Golden examples — extend this list as the product evolves
# ---------------------------------------------------------------------------

GOLDEN_EXAMPLES: list[dict[str, str]] = [
    {
        "input": "What is the capital of France?",
        "expected": "Paris",
    },
    {
        "input": "Summarise the key benefits of connection pooling in PostgreSQL.",
        "expected": (
            "Connection pooling reduces the overhead of creating new database "
            "connections, improves response latency under concurrent load, and "
            "limits the total number of connections to the database server."
        ),
    },
    {
        "input": "Explain what a LangGraph checkpointer does in one sentence.",
        "expected": (
            "A LangGraph checkpointer persists the state of a graph execution "
            "so it can be resumed or replayed from any previous step."
        ),
    },
    {
        "input": "How do I reset my password?",
        "expected": (
            "The assistant should guide the user through the password reset "
            "process or indicate that the feature is available."
        ),
    },
    {
        "input": "Write a Python function that checks if a string is a palindrome.",
        "expected": (
            "A correct Python function that checks whether a given string "
            "reads the same forwards and backwards."
        ),
    },
]


def ensure_dataset(client: Client | None = None) -> str:
    """Create (or update) the golden dataset in LangSmith.

    Returns the dataset name.
    """
    client = client or Client()

    # Check if dataset already exists
    try:
        ds = client.read_dataset(dataset_name=DATASET_NAME)
    except Exception:
        ds = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Golden evaluation set for Symphony agent quality.",
        )

    # Upsert examples
    existing = list(client.list_examples(dataset_id=ds.id))
    existing_inputs = {ex.inputs.get("input") for ex in existing}

    for example in GOLDEN_EXAMPLES:
        if example["input"] not in existing_inputs:
            client.create_example(
                inputs={"input": example["input"]},
                outputs={"expected": example["expected"]},
                dataset_id=ds.id,
            )

    return DATASET_NAME
