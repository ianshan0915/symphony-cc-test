"""Knowledge-base similarity search tool for LangGraph agents.

Uses pgvector cosine similarity to find relevant documents in the
knowledge base.  The tool generates an embedding for the user query via
OpenAI's ``text-embedding-3-small`` model and then runs an approximate
nearest-neighbour search against the ``documents`` table.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool
from sqlalchemy import text

from app.config import settings
from app.db.session import async_session_factory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding helper
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


async def _get_embedding(query: str) -> list[float]:
    """Generate an embedding vector for *query* using OpenAI's API.

    Falls back to a zero vector if the API call fails so that the tool
    can degrade gracefully rather than crash the agent.
    """
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": EMBEDDING_MODEL,
                    "input": query,
                    "dimensions": EMBEDDING_DIMENSIONS,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
    except Exception:
        logger.exception("Failed to generate embedding for query: %s", query[:100])
        raise


# ---------------------------------------------------------------------------
# Similarity search
# ---------------------------------------------------------------------------


async def _similarity_search(
    embedding: list[float],
    *,
    top_k: int = 5,
    score_threshold: float = 0.0,
) -> list[dict[str, Any]]:
    """Run cosine similarity search against the documents table.

    Parameters
    ----------
    embedding:
        The query embedding vector.
    top_k:
        Maximum number of results to return.
    score_threshold:
        Minimum cosine similarity score (0-1).  Results below this
        threshold are discarded.

    Returns
    -------
    list[dict]
        Matching documents with their similarity scores.
    """
    # Use 1 - cosine distance as the similarity score.
    query = text(
        """
        SELECT
            id,
            title,
            content,
            source,
            metadata_ AS metadata,
            1 - (embedding <=> :embedding::vector) AS score
        FROM documents
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> :embedding::vector
        LIMIT :top_k
        """
    )

    async with async_session_factory() as session:
        result = await session.execute(
            query,
            {
                "embedding": str(embedding),
                "top_k": top_k,
            },
        )
        rows = result.mappings().all()

    results = []
    for row in rows:
        score = float(row["score"])
        if score >= score_threshold:
            results.append(
                {
                    "id": str(row["id"]),
                    "title": row["title"],
                    "content": row["content"],
                    "source": row["source"],
                    "score": round(score, 4),
                    "metadata": row["metadata"] or {},
                }
            )

    return results


# ---------------------------------------------------------------------------
# LangChain tool
# ---------------------------------------------------------------------------


@tool
async def search_knowledge_base(query: str, top_k: int = 5) -> str:
    """Search the knowledge base for documents relevant to the query.

    Use this tool when you need to find information from the organisation's
    knowledge base, documentation, or previously stored context.  The search
    uses semantic similarity so you don't need exact keyword matches — just
    describe what you're looking for.

    Args:
        query: Natural language description of the information you need.
        top_k: Maximum number of results to return (default 5).

    Returns:
        Formatted string of matching documents with their relevance scores.
    """
    try:
        embedding = await _get_embedding(query)
        results = await _similarity_search(embedding, top_k=top_k, score_threshold=0.3)
    except Exception:
        logger.exception("Knowledge base search failed for query: %s", query[:100])
        return "Error: Unable to search the knowledge base at this time. Please try again later."

    if not results:
        return f"No relevant documents found for: {query}"

    parts = [f"Found {len(results)} relevant document(s):\n"]
    for i, doc in enumerate(results, 1):
        title = doc["title"] or "Untitled"
        source = f" (source: {doc['source']})" if doc["source"] else ""
        parts.append(
            f"---\n**[{i}] {title}**{source}  \nRelevance: {doc['score']:.0%}\n\n{doc['content']}\n"
        )

    return "\n".join(parts)
