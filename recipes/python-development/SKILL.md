---
name: python-development
description: >
  Python development best practices. Use when writing, reviewing,
  debugging, refactoring, or testing Python applications.
---

# Python Development

## Principles

- Follow existing project conventions.
- Prefer readable, maintainable Python.
- Use type hints for public interfaces.
- Avoid unnecessary dependencies.
- Handle errors explicitly.
- Keep functions focused and small.

## Workflow

1. Inspect the existing project.
2. Understand requirements and edge cases.
3. Implement the smallest appropriate change.
4. Add or update tests.
5. Run relevant tests and linters.
6. Document important changes.

## Testing

- Prefer pytest when already used by the project.
- Test normal and exceptional cases.
- Avoid flaky tests.
- Never claim tests passed without running them.

## Security

- Never commit secrets.
- Validate external input.
- Avoid logging sensitive information.