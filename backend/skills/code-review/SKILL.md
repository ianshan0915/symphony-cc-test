---
name: code-review
description: Review code for bugs, security issues, performance problems, and style violations. Use when the user asks for a code review, submits code for feedback, or wants to improve code quality.
metadata:
  author: symphony
  version: "1.0"
---
# Code Review

## When to use this skill

Activate this skill when the user:
- Asks for a review of their code
- Submits a pull request or diff for feedback
- Wants to improve existing code quality
- Asks about best practices for specific code

## Review checklist

Work through each category systematically:

### 1. Correctness
- Does the code handle all expected inputs?
- Are edge cases covered (empty inputs, nulls, boundaries)?
- Are error conditions handled appropriately?
- Do loops terminate correctly?

### 2. Security
- Are user inputs validated and sanitized?
- Are SQL queries parameterized (no string interpolation)?
- Are secrets hardcoded? (flag immediately)
- Is authentication/authorization checked where needed?
- Are there potential injection vectors (SQL, XSS, command)?

### 3. Performance
- Are there unnecessary loops or redundant computations?
- Could any O(n^2) operations be optimized?
- Are database queries efficient (N+1 problems, missing indexes)?
- Is there unnecessary memory allocation?

### 4. Readability
- Are variable/function names descriptive?
- Is the code structure logical and well-organized?
- Are complex algorithms commented?
- Does the code follow the project's conventions?

### 5. Maintainability
- Is the code DRY (Don't Repeat Yourself)?
- Are functions/methods appropriately sized?
- Is there proper separation of concerns?
- Are there adequate tests for the changes?

## Output format

Structure your review as:

```markdown
## Code Review Summary

**Overall**: [Brief assessment — e.g., "Good with minor issues"]

### Critical Issues
- [Issue]: [explanation + fix]

### Suggestions
- [Suggestion]: [explanation + example]

### Positive Notes
- [What's done well]
```

## Severity levels

- **Critical**: Bugs, security vulnerabilities, data loss risks — must fix
- **Warning**: Performance issues, missing error handling — should fix
- **Suggestion**: Style improvements, refactoring ideas — nice to have
- **Note**: Observations, questions, alternative approaches — informational
