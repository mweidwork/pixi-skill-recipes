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

## Docstrings and Type Annotations

- Write docstrings in Google style. Use a concise summary followed, when useful,
  by `Args:`, `Returns:`, `Raises:`, and class `Attributes:` sections.
- Document every public module, class, and function. Add docstrings to private
  helpers when their behavior, side effects, or constraints are not obvious.
- Describe arguments by name and purpose; keep their types in Python
  annotations instead of duplicating types in the docstring.
- Add annotations to every function parameter and return value, including
  `None` for functions that do not return a value. Use precise types and
  standard collection types; avoid `Any` unless an external or dynamic
  boundary requires it.
- Annotate constants, module-level values, and class attributes when their type
  is not clear from the assignment or when they form part of a public API.
- Document meaningful behavior that annotations cannot express, including
  ordering, mutation, units, defaults, side effects, and expected exceptions.
  Do not repeat the function signature or add speculative exceptions.
- Keep examples and terminology consistent with the implementation. Prefer
  Google-style sections over Sphinx fields such as `:param:` and `:returns:`.

```python
def parse_version(value: str) -> Version:
    """Parse a package version using PEP 440 rules.

    Args:
        value: Version string to parse.

    Returns:
        The parsed version.

    Raises:
        RecipeError: If the value is not a valid PEP 440 version.
    """
```

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
