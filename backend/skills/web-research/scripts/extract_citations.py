#!/usr/bin/env python3
"""Extract and format citations from raw search results.

Usage:
    python extract_citations.py < raw_results.json

Reads JSON search results (list of dicts with 'title', 'url', 'snippet' keys)
and outputs formatted Markdown citations.
"""

from __future__ import annotations

import json
import sys
from datetime import date


def format_citations(results: list[dict[str, str]]) -> str:
    """Format search results as numbered Markdown citations."""
    lines = ["## Sources", ""]
    for i, result in enumerate(results, 1):
        title = result.get("title", "Untitled")
        url = result.get("url", "")
        snippet = result.get("snippet", "")
        accessed = date.today().isoformat()
        lines.append(f"{i}. [{title}]({url}) — accessed {accessed}")
        if snippet:
            lines.append(f"   > {snippet[:200]}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    """Read JSON from stdin and print formatted citations."""
    raw = sys.stdin.read()
    try:
        results = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Error parsing JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(results, list):
        print("Expected a JSON array of search results", file=sys.stderr)
        sys.exit(1)

    print(format_citations(results))


if __name__ == "__main__":
    main()
