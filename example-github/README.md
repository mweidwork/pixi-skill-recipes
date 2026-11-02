# Example: install a skill package from GitHub

This example is a minimal Pixi project that installs skills from the public Conda
channel served by GitHub Pages:

```text
https://mweidwork.github.io/pixi-skill-recipes/conda
```

Unlike the R2-based [example](../example/), this channel is public and requires no
authentication.

## Prerequisites

- [Pixi](https://pixi.sh) installed
- The repository workflow has published the channel to GitHub Pages at least once

## 1. Install the skills

From this directory:

```bash
pixi install
```

Pixi resolves the `agent-skill-*` packages from the GitHub Pages channel and installs
them into the project environment.

## 2. Verify the installation

The skill instructions are installed into the environment under
`share/agent-skills/<skill>/SKILL.md`.

List the installed packages:

```bash
pixi list | grep agent-skill
```

```powershell
pixi list | Select-String agent-skill
```

Show the installed instructions (macOS/Linux):

```bash
cat .pixi/envs/default/share/agent-skills/code-review/SKILL.md
```

Show the installed instructions (Windows):

```powershell
Get-Content .pixi\envs\default\share\agent-skills\code-review\SKILL.md
```

## 3. Register the skills with OpenCode (optional)

Install `pixi-skills` and register the installed skills with OpenCode:

```bash
pixi global install pixi-skills
pixi-skills manage --backend opencode --scope local
```

## Use the channel in another project

Add the GitHub Pages channel to any Pixi project:

```toml
[workspace]
channels = [
    "https://mweidwork.github.io/pixi-skill-recipes/conda",
    "conda-forge",
]

[dependencies]
agent-skill-code-review = "*"
```

## Publishing requirements

The `publish-github` job in
[`.github/workflows/publish.yml`](../.github/workflows/publish.yml) deploys the built
channel to GitHub Pages. Enable Pages once in the repository settings:

1. Open **Settings → Pages**.
2. Set **Source** to **GitHub Actions**.
3. Run the **Publish company skills** workflow on `main`.

After the first successful deployment the channel is available at the URL above.
