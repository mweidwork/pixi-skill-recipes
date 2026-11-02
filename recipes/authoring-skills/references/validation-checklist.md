# Validation Checklist

Run this checklist before distributing a skill. Then run:

```bash
python scripts/validate_skill.py path/to/skill --strict
```

## Metadata

- [ ] `SKILL.md` starts with YAML frontmatter delimited by `---`.
- [ ] `name` uses lowercase letters, numbers, and hyphens only.
- [ ] `name` is 64 characters or fewer.
- [ ] `name` contains no XML tags and no `anthropic` or `claude`.
- [ ] `description` is non-empty and 1,024 characters or fewer.
- [ ] `description` is written in the third person.
- [ ] `description` states what the skill does and when to use it.
- [ ] `description` includes specific trigger terms.

## Structure

- [ ] The `SKILL.md` body is under 500 lines.
- [ ] The body contains a clear workflow with ordered steps.
- [ ] Multi-step work includes a checklist.
- [ ] Quality-critical work includes a validate-and-fix loop.
- [ ] Detail that is not always needed lives in `references/`.
- [ ] Every bundled resource is linked directly from `SKILL.md`.
- [ ] No references are nested more than one level deep.
- [ ] File names describe their content.
- [ ] All paths use forward slashes.

## Scripts

- [ ] Each script has a module docstring.
- [ ] The skill says whether to run the script or read it.
- [ ] Expected failures produce actionable error messages.
- [ ] Exit codes are meaningful.
- [ ] Constants and thresholds are justified.
- [ ] Required packages are listed and available.
- [ ] Validation or verification exists for critical operations.
- [ ] Python scripts pass syntax checks.

## Context quality

- [ ] Instructions are concise and avoid general knowledge the agent already has.
- [ ] One recommended approach is provided where possible.
- [ ] Terminology is consistent.
- [ ] Examples are concrete.
- [ ] No time-sensitive statements remain.
- [ ] No Windows-style paths remain.

## Testing

- [ ] At least three evaluation scenarios exist.
- [ ] Expected behavior is recorded for each scenario.
- [ ] The skill was tested with a fresh agent.
- [ ] The skill was tested with the models it will support.
- [ ] Observed failures were used to refine the skill.
- [ ] The final version passes the validator with no errors.
