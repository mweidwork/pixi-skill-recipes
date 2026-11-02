# Example: install a skill package

This example is a minimal Pixi project that installs a single skill from the private
`skill-publish` Conda channel: `agent-skill-code-review`.

## Prerequisites

- [Pixi](https://pixi.sh) installed
- A read-only Cloudflare R2 API token with:
  - **Object Read** permission
  - Access restricted to the `skill-publish` bucket

## 1. Authenticate with Cloudflare R2

Pixi stores the S3 credentials for the channel in its auth store. Log in once per
machine:

```bash
pixi auth login \
  --s3-access-key-id YOUR_READ_ACCESS_KEY \
  --s3-secret-access-key YOUR_READ_SECRET_KEY \
  s3://skill-publish
```

Use the read-only consumer token, never the publishing credentials.

## 2. Install the skill

From this directory:

```bash
pixi install
```

Pixi resolves `agent-skill-code-review` from `s3://skill-publish/conda` and installs it
into the project environment.

## 3. Verify the installation

The skill instructions are installed into the environment under
`share/agent-skills/code-review/SKILL.md`.

List the installed package:

```bash
pixi list | grep agent-skill-code-review
```

```powershell
pixi list | Select-String agent-skill-code-review
```

Show the installed instructions (macOS/Linux):

```bash
cat .pixi/envs/default/share/agent-skills/code-review/SKILL.md
```

Show the installed instructions (Windows):

```powershell
Get-Content .pixi\envs\default\share\agent-skills\code-review\SKILL.md
```

## 4. Register the skill with OpenCode (optional)

Install `pixi-skills` and register the installed skill with OpenCode:

```bash
pixi global install pixi-skills
pixi-skills manage --backend opencode --scope local
```

## Install a different skill

Change the dependency in `pixi.toml` to another package from the channel, for example:

```toml
[dependencies]
agent-skill-python-development = "*"
```

Then run `pixi install` again. See the [main README](../README.md#available-skills) for
the available packages.
