---
name: debugging
description: Systematically diagnose and fix bugs in code. Use when the user reports an error, unexpected behavior, test failure, or needs help troubleshooting.
metadata:
  author: symphony
  version: "1.0"
---
# Debugging

## When to use this skill

Activate this skill when the user:
- Reports an error message or stack trace
- Describes unexpected behavior in their code
- Has failing tests they cannot diagnose
- Needs help understanding why code behaves a certain way

## Debugging methodology

Follow this systematic approach:

### 1. Gather information
- What is the expected behavior?
- What is the actual behavior?
- When did it start? What changed recently?
- Can you reproduce it consistently?
- What environment/version is affected?

### 2. Read the error carefully
- Parse the full stack trace from bottom to top
- Identify the exact line and file where the error originates
- Distinguish between the root cause and downstream effects
- Check if the error message suggests a fix

### 3. Form hypotheses
- List 2-3 most likely causes based on the error type
- Rank by probability: most common causes first
- Consider recent changes as prime suspects

### 4. Isolate the problem
- Narrow down to the smallest reproducible case
- Use binary search: comment out half the code, see if error persists
- Check inputs at each stage of the pipeline
- Add targeted logging/print statements

### 5. Fix and verify
- Apply the minimal correct fix (avoid fixing unrelated things)
- Explain WHY the fix works, not just what it changes
- Verify the fix resolves the original issue
- Check for regressions in related functionality

### 6. Prevent recurrence
- Suggest a test case that catches this specific bug
- Recommend guards or assertions for the failure mode
- Note if the bug reveals a systemic issue worth addressing

## Common bug patterns

### Python
- `None` where an object is expected (check return values)
- Mutable default arguments (`def f(items=[])`)
- Off-by-one in range/slice operations
- `asyncio` — forgetting `await`, event loop issues
- Import cycles causing `None` attributes

### JavaScript/TypeScript
- `undefined` vs `null` confusion
- `this` binding in callbacks
- Async/await missing, leading to unresolved promises
- Type coercion surprises (`==` vs `===`)
- Closure variable capture in loops

### General
- Race conditions in concurrent code
- Encoding issues (UTF-8 vs Latin-1)
- Timezone-naive datetime comparisons
- Cache invalidation bugs
- Environment variable not set or wrong

## Output format

```markdown
## Diagnosis

**Root cause**: [concise explanation]

**Evidence**: [what in the error/code points to this cause]

## Fix

[code change with explanation]

## Verification

[how to verify the fix works]

## Prevention

[suggested test or guard]
```
