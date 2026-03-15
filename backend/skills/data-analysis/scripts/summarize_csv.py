#!/usr/bin/env python3
"""Compute basic summary statistics from CSV data.

Usage:
    python summarize_csv.py data.csv
    python summarize_csv.py < data.csv

Outputs a Markdown table of summary statistics for each numeric column.
"""

from __future__ import annotations

import csv
import io
import statistics
import sys


def summarize(rows: list[dict[str, str]]) -> str:
    """Generate summary statistics for numeric columns in CSV data."""
    if not rows:
        return "No data to summarize."

    # Identify numeric columns
    numeric_cols: dict[str, list[float]] = {}
    for col in rows[0]:
        values: list[float] = []
        for row in rows:
            try:
                values.append(float(row[col]))
            except (ValueError, TypeError):
                continue
        if len(values) > len(rows) * 0.5:  # At least 50% numeric
            numeric_cols[col] = values

    if not numeric_cols:
        return "No numeric columns found."

    lines = ["| Column | Count | Mean | Median | Std Dev | Min | Max |"]
    lines.append("|--------|-------|------|--------|---------|-----|-----|")

    for col, values in numeric_cols.items():
        n = len(values)
        mean = statistics.mean(values)
        median = statistics.median(values)
        stdev = statistics.stdev(values) if n > 1 else 0.0
        lines.append(
            f"| {col} | {n} | {mean:.2f} | {median:.2f} | {stdev:.2f} "
            f"| {min(values):.2f} | {max(values):.2f} |"
        )

    return "\n".join(lines)


def main() -> None:
    """Read CSV from file argument or stdin and print summary."""
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    else:
        reader = csv.DictReader(io.StringIO(sys.stdin.read()))
        rows = list(reader)

    print(summarize(rows))


if __name__ == "__main__":
    main()
