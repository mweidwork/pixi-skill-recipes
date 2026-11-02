# Authoring Guide

Detailed guidance for designing skills that activate reliably and stay cheap in
context. Adapted from Anthropic's "The Complete Guide to Building Skills for
Claude" and the public skill authoring best practices.

## Contents

- Skill anatomy
- Progressive disclosure
- Metadata contract
- Writing the body
- Workflows and feedback loops
- Executable scripts
- Evaluation and iteration
- Anti-patterns
- Source

## Skill anatomy

A skill is a folder with one required file and optional resource directories:

```text
my-skill/
├── SKILL.md
├── scripts/
│   ├── process.py
│   └── validate.py
├── references/
│   ├── api-guide.md
│   └── examples.md
└── assets/
    └── report-template.md
```

- `SKILL.md` is required and contains YAML frontmatter plus instructions.
- `scripts/` contains executable code that an agent runs rather than reads.
- `references/` contains documentation loaded only when the task needs it.
- `assets/` contains files used in the output, not loaded into context.

Start with `SKILL.md` only. Add each directory only when it solves a concrete
problem. The main `SKILL.md` links directly to `resource-selection.md` for
decision rules.

## Progressive disclosure

Skills load in three levels:

1. **Metadata**: `name` and `description` are always available. They determine
   whether the skill activates.
2. **Body**: `SKILL.md` loads when the skill becomes relevant. It should contain
   the core workflow and navigation to deeper material.
3. **Resources**: files under `scripts/`, `references/`, and `assets/` load or
   execute only when needed.

This is why `SKILL.md` should read like a table of contents plus the essential
instructions, not like an entire manual.

Practical limits:

- Keep the body under 500 lines.
- Keep references one level deep from `SKILL.md`.
- Link every bundled reference directly from `SKILL.md`.
- Add a table of contents to reference files longer than 100 lines.
- Name files for their content: `form_validation_rules.md`, not `doc2.md`.

## Metadata contract

The frontmatter requires exactly the fields the runtime uses:

```yaml
---
name: processing-pdfs
description: >
  Extracts text and tables from PDF files and fills forms. Use when working
  with PDFs, forms, or document extraction.
---
```

### Name

- Lowercase letters, numbers, and hyphens only.
- Maximum 64 characters.
- No XML tags.
- No `anthropic` or `claude` reserved words.
- Prefer gerund or clear noun phrases: `analyzing-spreadsheets`,
  `pdf-processing`.
- Avoid vague names such as `helper`, `utils`, or `tools`.

### Description

- Non-empty, maximum 1,024 characters.
- No XML tags.
- Write in the third person: "Processes Excel files and generates reports", not
  "I can help you process Excel files".
- Include both what the skill does and when to use it.
- Include concrete trigger terms such as file types, user phrases, and domains.

The description is the discovery surface. A vague description causes missed
activations even when the body is excellent.

## Writing the body

- Assume the agent is already capable. Omit general knowledge and explanations
  that do not change behavior.
- Prefer one recommended approach. Offer alternatives only when the choice
  depends on the task.
- Use concrete examples and exact commands.
- Match specificity to fragility:
  - High freedom for judgment-heavy tasks such as reviews.
  - Medium freedom for parameterized scripts and templates.
  - Low freedom for fragile operations such as migrations, where the agent must
    run an exact command.
- Use consistent terminology throughout the skill.
- Avoid time-sensitive information. Move deprecated guidance into an "old
  patterns" section or a separate reference.

## Workflows and feedback loops

Break complex tasks into ordered steps. For multi-step work, provide a checklist
the agent can copy and mark as it progresses.

```text
Task progress:
- [ ] 1. Analyze the input
- [ ] 2. Create the plan
- [ ] 3. Validate the plan
- [ ] 4. Execute the plan
- [ ] 5. Verify the output
```

For quality-critical work, add a feedback loop:

1. Run the validator.
2. Fix every reported error.
3. Run the validator again.
4. Continue only when validation passes.

For destructive or batch operations, use plan-validate-execute: write the plan
to an intermediate file, validate it with a script, then apply it. This catches
mistakes before they touch the original data.

## Executable scripts

Prefer scripts for deterministic, repeated, or fragile operations. Scripts are
more reliable than regenerated code, save tokens, and enforce consistency.

- State whether the agent should run the script or read it as a reference.
  - Run: "Run `python scripts/analyze_form.py input.pdf`."
  - Read: "See `scripts/analyze_form.py` for the extraction algorithm."
- Handle expected failures inside the script with actionable messages.
- Avoid unexplained constants. Document why a timeout, retry count, or threshold
  has that value.
- List required packages and verify they are available in the target runtime.
- Return clear exit codes and print errors to standard error.
- Do not assume tools or packages are installed.

## Evaluation and iteration

Build evaluations before writing extensive documentation:

1. Run a representative task without the skill and note the failures.
2. Create at least three scenarios with expected behavior.
3. Record a baseline.
4. Write the minimum instructions that address the gaps.
5. Re-run the scenarios and compare against the baseline.

Test with the models you plan to support. Test with a fresh agent that only has
the skill loaded, then observe:

- Whether the skill activates when expected.
- Which files the agent reads and in what order.
- Whether any linked resource is ignored.
- Where the agent improvises instead of following the workflow.

Refine based on observed behavior, not assumptions.

## Anti-patterns

- Dumping an entire manual into `SKILL.md`.
- A description that says "Helps with documents" or "Processes data".
- Windows-style paths such as `scripts\helper.py`.
- Nested references that force the agent to follow `advanced.md` →
  `details.md` → the real answer.
- Offering many equivalent tools or approaches when one default is enough.
- Time-sensitive statements that will become wrong.
- Scripts that fail and leave the agent to guess the recovery step.
- Claiming validation passed without running it.
- Adding bundled resources that no instruction references.

## Source

- Anthropic, "The Complete Guide to Building Skills for Claude":
  https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf
- Anthropic, "Skill authoring best practices":
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
