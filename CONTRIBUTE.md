# Contributing

This repository uses a small, predictable workflow so that skill packages stay
reviewable and releases stay traceable. Follow the rules below for every change.

## Before you start

- Use [Pixi](https://pixi.sh) for all builds. Do not rely on a system Python or
  Conda installation.
- Install the build environment once:

  ```bash
  pixi install
  ```

- Never commit credentials, tokens, `.pixi/`, `channel/`, or
  `validation-output/`.

## Workflow

1. Create a short-lived branch from `main`:

   ```bash
   git switch main
   git pull --ff-only
   git switch -c feat/add-my-skill
   ```

2. Make one logical change and build the affected recipe:

   ```bash
   pixi run rattler-build build \
     --recipe recipes/<skill>/recipe.yaml \
     --output-dir validation-output
   ```

3. Commit with a Conventional Commit message (see below).
4. Rebase on the latest `main` before opening a pull request:

   ```bash
   git fetch origin
   git rebase origin/main
   ```

5. Open a pull request. Pull requests validate recipes but never publish.

## Official commit pattern

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Rules

- Write the description in the **imperative mood**: `add`, not `added` or `adds`.
- Use **lowercase** for the type and description; do not end the description
  with a period.
- Keep the subject line at **72 characters or fewer**.
- Use a scope when it adds clarity. Omit it for repository-wide changes.
- Leave one blank line between the subject and the body.
- Explain **why** the change is needed in the body; the diff explains **what**.
- Reference issues in the footer, for example `Closes #42`.
- Mark incompatible changes with `!` after the type/scope **and** a
  `BREAKING CHANGE:` footer.

### Types

| Type | Use for |
|---|---|
| `feat` | A new skill, example, or user-facing capability |
| `fix` | A bug fix in a recipe, workflow, or example |
| `docs` | Documentation-only changes |
| `ci` | Changes to `.github/workflows/` or publishing automation |
| `refactor` | Code or configuration changes that do not alter behavior |
| `test` | Adding or fixing recipe tests |
| `build` | Build system or dependency changes (`pixi.toml`, `pixi.lock`) |
| `chore` | Maintenance that does not fit the other types |
| `revert` | Reverting a previous commit |

### Scopes

Prefer a scope that matches the area you changed:

| Scope | Area |
|---|---|
| `recipes` | `recipes/**` |
| `ci` | `.github/workflows/**` |
| `docs` | `README.md`, `CONTRIBUTE.md`, other documentation |
| `example` | `example/**` |
| `example-github` | `example-github/**` |
| `agents` | `AGENTS.md`, `opencode.json` |
| `deps` | `pixi.toml`, `pixi.lock` |

### Examples

```text
feat(recipes): add data-engineering skill
fix(recipes): install SKILL.md into the correct prefix
docs: document the GitHub Pages channel
ci: mirror the Conda channel to GitHub Pages
build(deps): update rattler-build to 0.69
```

With a body and footer:

```text
fix(ci): publish only changed skills on main

The publish job previously rebuilt and uploaded every package, which made
release history hard to follow. Limit uploads to recipes that changed.

Closes #18
```

Breaking change:

```text
feat(recipes)!: move skill files under share/agent-skills

BREAKING CHANGE: consumers must update paths from share/skills to
share/agent-skills.
```

Avoid:

```text
updated stuff
Fixed bug.
feat: Added a new skill.
```

## Keep commits atomic

- One commit should represent one reviewable change.
- Do not mix recipe changes, workflow changes, and unrelated formatting in the
  same commit.
- Do not amend or force-push commits that others may already have based work on.
- Use `git rebase -i` locally to tidy your own branch before opening a pull
  request; do not rewrite `main`.

## Recipe changes

- Bump `package.version` in `recipe.yaml` whenever you change that skill's
  `SKILL.md`.
- Keep versions independent between skills.
- Add or update `tests.package_contents` for every installed file.
- Build the recipe locally before committing.

## Pull request checklist

- [ ] The change is focused and the commit messages follow this guide.
- [ ] `pixi run rattler-build build --recipe recipes/<skill>/recipe.yaml` passes.
- [ ] Workflow YAML was validated after editing.
- [ ] Documentation was updated when behavior or setup changed.
- [ ] No secrets, credentials, or generated directories are committed.

## Questions

Open an issue or start a discussion before large changes so the approach can be
agreed on before implementation.
