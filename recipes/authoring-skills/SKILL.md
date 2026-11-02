---
name: authoring-skills
description: >
  Creates, reviews, and refactors reusable AI agent skills built from SKILL.md,
  scripts, references, and assets. Use when adding a new skill, deciding which
  bundled resources a skill needs, validating skill structure, or preparing a
  skill for distribution.
---

# Authoring Skills

A skill is a folder, not only a Markdown file. The metadata tells an agent when
to load the skill, the `SKILL.md` body carries the core workflow, and bundled
resources provide depth only when the task needs it.

## Workflow

Copy this checklist and track your progress:

```text
Skill progress:
- [ ] 1. Define the trigger and success criteria
- [ ] 2. Draft three evaluation scenarios
- [ ] 3. Choose the minimal resource layout
- [ ] 4. Write the frontmatter and SKILL.md
- [ ] 5. Add scripts, references, or assets only where they reduce ambiguity
- [ ] 6. Run the validator
- [ ] 7. Test with real tasks and iterate
```

### 1. Define the trigger and success criteria

Write down what the agent should do, when the skill should activate, and what a
successful result looks like. If the skill cannot be distinguished from a
general-purpose agent, it is not ready.

### 2. Draft three evaluation scenarios

Create at least three representative requests before writing extensive
documentation. Record the expected behavior for each. Use the scenarios to find
real gaps instead of documenting imagined ones.

### 3. Choose the minimal resource layout

Start with `SKILL.md` alone. Add a resource only when it removes a concrete
ambiguity:

| Resource | Use it for |
|---|---|
| `scripts/` | Deterministic, repeated, or fragile operations that should be executed instead of regenerated |
| `references/` | Detailed documentation, domain variants, examples, or schemas that should load only when relevant |
| `assets/` | Templates, icons, fonts, or other files copied into the output rather than read into context |

See [resource-selection.md](references/resource-selection.md) for decision rules
and layouts.

### 4. Write the frontmatter and SKILL.md

Required frontmatter:

```yaml
---
name: authoring-skills
description: >
  Creates and validates agent skills. Use when building or reviewing a skill.
---
```

- `name`: lowercase letters, numbers, and hyphens only; maximum 64 characters;
  no XML tags; never include `anthropic` or `claude`.
- `description`: non-empty, maximum 1,024 characters; third person; state both
  what the skill does and when to use it.
- Keep the `SKILL.md` body under 500 lines.
- Write file paths with forward slashes, even on Windows.

See [authoring-guide.md](references/authoring-guide.md) for naming,
description, and progressive-disclosure patterns.

### 5. Add the bundled resources

Reference every bundled file directly from `SKILL.md`. Keep references one level
deep so an agent does not have to follow a chain of files.

Use templates as a starting point:

- [SKILL.md.template](assets/SKILL.md.template)
- [reference.md.template](assets/reference.md.template)
- [script.py.template](assets/script.py.template)
- [asset.txt.template](assets/asset.txt.template)

### 6. Run the validator

Run the validator from the skill directory:

```bash
python scripts/validate_skill.py .
```

It checks the frontmatter contract, body length, resource links, Windows-style
paths, referenced-file existence, and Python script syntax.

Useful options:

```bash
python scripts/validate_skill.py path/to/skill --strict
python scripts/validate_skill.py path/to/skill --json
```

Fix errors before distributing the skill. Treat warnings as signals to simplify
or clarify the skill.

### 7. Test with real tasks and iterate

Run the evaluation scenarios with a fresh agent that has only the skill loaded.
Watch for:

- The skill not activating when expected.
- The agent missing a linked resource.
- The agent reading files in an unexpected order.
- Instructions that are too long or too vague.

Update the skill based on observed behavior. Repeat the validate-and-test loop.

## Scaffold a new skill

Create a skill directory from the bundled templates:

```bash
python scripts/scaffold_skill.py my-skill --dir path/to/skills --with-scripts --with-references --with-assets
```

The scaffold validates the name, creates the directory, and renders the
templates. Omit the resource flags to start with `SKILL.md` only.

## Design rules

- Prefer concise instructions over explanations the agent already knows.
- Provide one recommended approach, not a menu of equivalent options.
- Use a checklist for multi-step workflows and a validation loop for quality.
- State whether the agent should run a script or read it as a reference.
- List required packages and verify they exist when a skill depends on them.
- Never use Windows-style paths in instructions or links.
- Avoid time-sensitive statements; put historical context in an "old patterns"
  section.
- Test the skill with real usage before publishing.

## Validation

Run the full checklist in
[validation-checklist.md](references/validation-checklist.md) before sharing a
skill. It covers metadata, progressive disclosure, scripts, and testing.
