# Company Skill Forge

Private AI agent skill repository distributed through Pixi and Cloudflare R2.

## Architecture

GitHub → GitHub Actions → rattler-build → Cloudflare R2 → Pixi → OpenCode

## Skills

| Skill | Package |
|---|---|
| Python Development | agent-skill-python-development |
| Code Review | agent-skill-code-review |
| Data Engineering | agent-skill-data-engineering |

## Requirements

- Pixi
- GitHub repository
- Cloudflare R2 bucket
- R2 API token with Object Read & Write permissions

## Publishing

GitHub Actions automatically:

1. Validates and builds all recipes.
2. Publishes changed skills after merging into main.
3. Uploads packages to Cloudflare R2.
4. Updates Conda channel metadata.

Target:

s3://skill-publish/conda

## Adding a skill

Create:

recipes/my-skill/
├── recipe.yaml
└── SKILL.md

Use an independent package version in recipe.yaml.

Commit and push to main.

## Consuming skills

Add the private channel to your Pixi project:

```toml
[workspace]
channels = [
    "s3://skill-publish/conda",
    "conda-forge",
]
platforms = ["linux-64", "osx-arm64", "win-64"]

[workspace.s3-options.skill-publish]
endpoint-url = "https://b9296accc515e61268cbc93ac4377240.eu.r2.cloudflarestorage.com"
region = "WEUR"
force-path-style = false

[dependencies]
agent-skill-python-development = "*"
agent-skill-code-review = "*"
agent-skill-data-engineering = "*"