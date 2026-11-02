---
name: code-review
description: >
  Review code changes, pull requests, and patches for bugs,
  security problems, regressions, and missing tests.
---

# Code Review

## Review priorities

1. Correctness
2. Security
3. Reliability
4. Performance
5. Maintainability

## Review workflow

1. Understand the purpose of the changes.
2. Read the complete diff.
3. Inspect related implementation and callers.
4. Identify concrete failure scenarios.
5. Check test coverage.
6. Report actionable findings.

## Finding format

For each finding provide:

- Severity: Critical, High, Medium, or Low.
- File and line number.
- Problem description.
- Reproduction scenario.
- Recommended correction.

## Rules

- Do not report speculative problems as confirmed bugs.
- Do not focus on stylistic preferences.
- Do not modify code unless explicitly requested.
- Never claim tests passed without executing them.