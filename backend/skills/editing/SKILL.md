---
name: editing
description: Edit and improve existing text for clarity, tone, grammar, and structure. Use when the user submits text for review, asks to improve writing, or needs proofreading.
metadata:
  author: symphony
  version: "1.0"
---
# Editing

## When to use this skill

Activate this skill when the user:
- Submits existing text and asks for improvements
- Requests proofreading or grammar checking
- Wants to change the tone or style of text
- Asks to shorten, expand, or restructure content

## Editing levels

### 1. Proofreading (light touch)
Fix only:
- Spelling and typos
- Grammar errors
- Punctuation mistakes
- Obvious formatting issues

### 2. Copy editing (moderate)
Everything in proofreading, plus:
- Sentence clarity and flow
- Word choice improvements
- Consistent terminology
- Parallel structure in lists
- Removing redundancy

### 3. Substantive editing (heavy)
Everything in copy editing, plus:
- Reorganizing structure and flow
- Strengthening arguments
- Adding transitions
- Rewriting unclear passages
- Adjusting tone and voice

## Editing workflow

1. **Read the full text** before making any changes
2. **Identify the editing level** the user needs (ask if unclear)
3. **Make changes** with explanations for each significant edit
4. **Present results** showing before/after or using tracked changes

## Output format

For small edits (under 100 words), show before/after:

```markdown
**Before**: The system was very slow and it had a lot of bugs that were causing problems.
**After**: The system suffered from poor performance and numerous bugs.
**Why**: Removed filler words; combined redundant phrases.
```

For larger edits, provide the revised text with a summary of changes:

```markdown
## Revised Text
[full revised text]

## Changes Made
1. Restructured opening paragraph for stronger hook
2. Removed redundant sentences in section 2
3. Fixed subject-verb agreement throughout
4. Tightened conclusion to focus on call to action
```

## Common issues to catch

- **Passive voice** (when active is better): "The report was written by the team" → "The team wrote the report"
- **Nominalization**: "made a decision" → "decided"
- **Filler words**: very, really, just, quite, basically, actually
- **Redundancy**: "past history", "future plans", "end result"
- **Jargon**: replace with plain language unless the audience is technical
- **Long sentences**: break up sentences over 30 words
- **Inconsistency**: mixed tense, voice, or terminology
