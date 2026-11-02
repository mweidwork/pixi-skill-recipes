# Company Skill Forge

[![Publish company skills](https://github.com/mweidwork/pixi-skill-recipes/actions/workflows/publish.yml/badge.svg?branch=main)](https://github.com/mweidwork/pixi-skill-recipes/actions/workflows/publish.yml)

A private Conda channel for distributing reusable AI agent skills. Skills are packaged with `rattler-build`, published to Cloudflare R2, and installed into Pixi projects.

## Overview

Company Skill Forge provides a simple workflow for authoring, versioning, publishing, and consuming AI agent skills.

### Architecture

```text
GitHub repository
       |
       v
GitHub Actions
       |
       v
rattler-build
       |
       v
Cloudflare R2
       |
       v
Private Conda channel
       |
       v
Pixi projects
       |
       v
pixi-skills / OpenCode
```

## Available skills

| Skill | Conda package | Purpose |
|---|---|---|
| Python Development | `agent-skill-python-development` | Python development practices, testing, and maintainability |
| Code Review | `agent-skill-code-review` | Structured code reviews and actionable findings |
| Data Engineering | `agent-skill-data-engineering` | Data pipelines, quality, performance, and reliability |

Each skill is distributed as an independent Conda package.

## Repository structure

```text
pixi-skill-recipes/
├── .github/
│   └── workflows/
│       └── publish.yml
├── recipes/
│   ├── python-development/
│   │   ├── recipe.yaml
│   │   └── SKILL.md
│   ├── code-review/
│   │   ├── recipe.yaml
│   │   └── SKILL.md
│   └── data-engineering/
│       ├── recipe.yaml
│       └── SKILL.md
├── pixi.toml
├── LICENSE
└── README.md
```

## Publishing pipeline

Publishing is automated through GitHub Actions.

### Workflow triggers

| Event | Behavior |
|---|---|
| Push to `main` | Validates recipes and publishes changed skills |
| Pull request to `main` | Validates recipes without publishing |
| Manual workflow dispatch | Validates and publishes all skills when run on `main` |

The workflow watches changes to:

- `recipes/**`
- `pixi.toml`
- `.github/workflows/publish.yml`

Changes to documentation alone do not trigger a build.

### Publishing process

1. GitHub Actions checks out the repository.
2. Pixi installs the project environment.
3. `rattler-build` validates and builds the skill recipes.
4. Changed recipes are published to Cloudflare R2.
5. Channel metadata is updated.

The Conda channel is published to:

```text
s3://skill-publish/conda
```

### GitHub Actions configuration

Configure the following repository variables under **Settings → Secrets and variables → Actions → Variables**:

| Variable | Description |
|---|---|
| `R2_BUCKET` | Cloudflare R2 bucket name: `skill-publish` |
| `R2_ENDPOINT` | Cloudflare R2 S3-compatible endpoint |

Configure these repository secrets under **Settings → Secrets and variables → Actions → Secrets**:

| Secret | Description |
|---|---|
| `R2_ACCESS_KEY_ID` | R2 publishing access key |
| `R2_SECRET_ACCESS_KEY` | R2 publishing secret key |

The publishing token should have **Object Read & Write** permissions restricted to the `skill-publish` bucket.

The workflow uses the following R2 publishing configuration:

```yaml
S3_BUCKET: ${{ vars.R2_BUCKET }}
S3_ENDPOINT_URL: ${{ vars.R2_ENDPOINT }}
S3_REGION: auto
S3_ADDRESSING_STYLE: path
S3_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}
S3_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
```

## Adding a new skill

Create a new directory under `recipes/`:

```text
recipes/
└── my-skill/
    ├── recipe.yaml
    └── SKILL.md
```

### 1. Create the skill instructions

Add a `SKILL.md` file with the skill name and description in its frontmatter:

```markdown
---
name: my-skill
description: Explains when and how to use this skill.
---

# My Skill

Instructions for the AI agent go here.
```

### 2. Create the Conda recipe

Add a `recipe.yaml` that packages the skill instructions.

The package should follow the existing recipe conventions:

- Package name: `agent-skill-my-skill`
- Package version: independently managed
- Architecture: `noarch`
- Installed skill file: `share/agent-skills/my-skill/SKILL.md`

Use an existing recipe as the starting point and adjust the package name, version, description, and installation path.

### 3. Publish

Commit and push your changes to `main`.

GitHub Actions will validate the recipes and publish the changed skill package to R2.

## Consuming skills

Skills are installed into a regular Pixi project using the private Conda channel.

### 1. Configure the private channel

Add the following to your project's `pixi.toml`:

```toml
[workspace]
channels = [
    "s3://skill-publish/conda",
    "conda-forge",
]
platforms = [
    "linux-64",
    "osx-64",
    "osx-arm64",
    "win-64",
]

[workspace.s3-options.skill-publish]
endpoint-url = "https://b9296accc515e61268cbc93ac4377240.eu.r2.cloudflarestorage.com"
region = "WEUR"
force-path-style = false

[dependencies]
agent-skill-python-development = "*"
agent-skill-code-review = "*"
agent-skill-data-engineering = "*"
```

The `WEUR` region is used for the Cloudflare R2 EU location.

### 2. Configure read-only access

Create a separate Cloudflare R2 API token for consumers.

Recommended permissions:

- Object Read
- Restricted to the `skill-publish` bucket

Authenticate Pixi using the read-only credentials:

```bash
pixi auth login \
  --s3-access-key-id YOUR_READ_ACCESS_KEY \
  --s3-secret-access-key YOUR_READ_SECRET_KEY \
  s3://skill-publish
```

Do not use the publishing credentials on developer machines.

### 3. Install the skills

Install the dependencies:

```bash
pixi install
```

For a complete project that installs a single skill, see [example/](example/).

The skill packages install their instructions into the Pixi environment under:

```text
share/agent-skills/
├── python-development/
│   └── SKILL.md
├── code-review/
│   └── SKILL.md
└── data-engineering/
    └── SKILL.md
```

### 4. Register skills with OpenCode

Install `pixi-skills`:

```bash
pixi global install pixi-skills
```

From your project directory, run:

```bash
pixi-skills manage --backend opencode --scope local
```

This configures the installed skills for the selected OpenCode backend and local project scope.

## Versioning

Each skill package has its own version in its `recipe.yaml`.

For example:

```yaml
package:
  name: agent-skill-python-development
  version: "0.2.0"
```

When changing a skill:

1. Update its `SKILL.md`.
2. Increment the package version in `recipe.yaml`.
3. Commit and push the changes.

Keep versions independent so that one skill can be updated without releasing all other skills.

The build number can be managed by `rattler-build` when it is omitted from the recipe.

## Security

- Publishing credentials are stored as GitHub Actions secrets.
- The publishing token is restricted to the designated R2 bucket.
- Consumers use separate read-only credentials.
- Pull requests can validate recipes but cannot publish packages.
- Credentials must never be committed to the repository or stored in `pixi.toml`.

## Troubleshooting

| Problem | Things to check |
|---|---|
| Authentication fails | Check the R2 access key, secret, and bucket permissions |
| Channel cannot be resolved | Verify the bucket name, channel path, endpoint, and S3 options |
| Package is not found | Check that the package was published and that Pixi has refreshed its environment |
| Workflow fails during build | Inspect the recipe and `SKILL.md` paths in the Actions logs |
| Skill is not available in OpenCode | Check that the package is installed and run `pixi-skills manage` again |

## License

See [LICENSE](LICENSE) for the repository license and applicable terms.