---
name: data-analysis
description: Analyze datasets, identify patterns, compute statistics, and generate summary reports. Use when the user provides data to analyze, asks about trends, or needs statistical insights.
metadata:
  author: symphony
  version: "1.0"
---
# Data Analysis

## When to use this skill

Activate this skill when the user:
- Provides a dataset or table to analyze
- Asks about trends, patterns, or correlations
- Needs statistical summaries or comparisons
- Requests data-driven recommendations

## Analysis workflow

1. **Understand the data** — identify columns, data types, and the unit of analysis.
2. **Clarify the question** — determine what specific insight the user needs.
3. **Assess data quality** — check for missing values, outliers, and inconsistencies.
4. **Analyze** — apply appropriate statistical methods or aggregations.
5. **Interpret** — translate findings into plain-language insights.
6. **Present** — use tables, summaries, and recommendations.

## Output format

### Summary statistics
Present key metrics in a table:

```markdown
| Metric   | Value    |
|----------|----------|
| Mean     | 42.5     |
| Median   | 38.0     |
| Std Dev  | 12.3     |
| Count    | 150      |
```

### Comparisons
Use side-by-side tables for group comparisons.

### Trends
Describe trends in natural language with supporting data points.

## Statistical methods

- **Descriptive**: mean, median, mode, std dev, quartiles
- **Comparative**: percentage change, ratios, rankings
- **Correlation**: note when variables appear related, but always caveat that correlation does not imply causation
- **Aggregation**: group-by summaries, pivot-style analysis

## Edge cases

- **Small sample sizes**: Warn about limited statistical power
- **Missing data**: Report the extent and how it affects conclusions
- **Outliers**: Identify and explain their impact; present results with and without outliers when significant

## Scripts

Use `scripts/summarize_csv.py` to compute basic summary statistics from CSV data.
