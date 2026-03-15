---
name: web-research
description: Search the web for current information, verify facts across multiple sources, and compile cited research summaries. Use when the user asks factual questions, needs current data, or requests research on any topic.
metadata:
  author: symphony
  version: "1.0"
---
# Web Research

## When to use this skill

Activate this skill when the user:
- Asks factual questions that benefit from current information
- Requests research on a topic with source citations
- Needs to verify claims or cross-reference data
- Asks about recent events, statistics, or trends

## Research workflow

1. **Parse the query** — identify the core question and any constraints (date range, domain, geography).
2. **Plan searches** — break complex queries into 2-3 targeted sub-queries rather than one broad search.
3. **Execute searches** — use `web_search` for each sub-query. Prefer specific, keyword-rich queries.
4. **Evaluate sources** — assess credibility, recency, and relevance of each result.
5. **Cross-reference** — verify key facts across at least two independent sources.
6. **Synthesize** — combine findings into a coherent answer with inline citations.

## Citation format

Always cite sources using inline Markdown links:

```
According to [Source Title](url), the key finding is...
```

Include a **Sources** section at the end:

```markdown
## Sources
1. [Title](url) — accessed YYYY-MM-DD
2. [Title](url) — accessed YYYY-MM-DD
```

## Handling conflicting information

When sources disagree:
- Present both perspectives clearly
- Note which source is more authoritative or recent
- Let the user decide which interpretation to trust

## Edge cases

- **No results found**: Acknowledge the gap, suggest alternative search terms, and explain what you do know from training data (with a caveat about recency).
- **Paywalled content**: Note the paywall and extract what you can from the snippet. Suggest the user access the full article directly.
- **Rapidly changing topics**: Include the search date and warn that information may be outdated.

## Scripts

Use `scripts/extract_citations.py` to format raw search results into structured citations when processing large result sets.
