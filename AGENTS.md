# AGENTS.md

Guidance for coding agents working in this repository.

## What this repository is

A Conda channel that packages reusable AI agent skills. Each skill is authored in
`recipes/<skill>/`, built with `rattler-build`, and published to Cloudflare R2 and
GitHub Pages.

## Layout

```text
recipes/<skill>/SKILL.md      Skill instructions (YAML frontmatter + markdown)
recipes/<skill>/recipe.yaml   Conda recipe that installs SKILL.md
pixi.toml                     Build environment (rattler-build)
.github/workflows/publish.yml Build and publish pipeline
examples/s3/                  Consume skills from the private R2 channel
examples/github/              Consume skills from the public GitHub Pages channel
```

The repo's own skills are registered for opencode via `opencode.json`
(`skills.paths: ["./recipes"]`), so they are available while working here.

## Commands

Use Pixi for everything. Do not assume system Python or Conda.

```bash
pixi install
pixi run rattler-build build --recipe recipes/<skill>/recipe.yaml --output-dir validation-output
```

To build the full channel locally:

```bash
for recipe in recipes/*/recipe.yaml; do
  pixi run rattler-build build --recipe "$recipe" --output-dir channel
done
```

## Recipe conventions

- Package name: `agent-skill-<skill>`.
- Build: `noarch: generic`.
- Installed file: `share/agent-skills/<skill>/SKILL.md`.
- Copy instructions from `${RECIPE_DIR}/SKILL.md` in the build script.
- Each package has its own version; bump `package.version` in `recipe.yaml` when
  changing its `SKILL.md`.
- Add a `tests.package_contents` entry for every installed file.
- Keep `about.summary` and `about.license` set.

## Adding a skill

1. Create `recipes/<skill>/SKILL.md` with `name` and `description` frontmatter.
2. Copy an existing `recipe.yaml` and adjust name, version, summary, and paths.
3. Build the recipe locally before committing.
4. Push to `main`; the workflow validates and publishes changed skills.

## Publishing

- Push to `main` or run `workflow_dispatch` to build and publish.
- Cloudflare R2 channel: `s3://skill-publish/conda` (private, requires auth).
- GitHub Pages channel: `https://mweidwork.github.io/pixi-skill-recipes/conda`
  (public, no auth).
- Never commit credentials, tokens, `.pixi/`, `channel/`, or `validation-output/`.

## Workflow changes

- Validate YAML before committing.
- Publishing jobs must only run on `main`.
- Keep pull requests validate-only; they must not publish.
- The Pages job requires **Settings → Pages → Source → GitHub Actions**.

## Commit style

Follow [CONTRIBUTE.md](CONTRIBUTE.md). Use Conventional Commits, for example:

```text
feat(recipes): add data-engineering skill
fix(ci): correct R2 destination path
docs: document the GitHub Pages channel
```

Only commit when explicitly asked.
