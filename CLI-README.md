# CLI Reference: pixi-skill-recipes

This guide covers only the `pixi-skill-recipes` command-line interface:
configuration, commands, common workflows, safety behavior, and errors.

> **Terminology:** A *skill* is a local recipe under `recipes/<skill>/`. Its
> Conda package is named `agent-skill-<skill>` by default. `skill-forge`, in
> contrast, is a public Conda channel from which `update` mirrors packages. It
> is not itself a single skill package.

## Table of contents

- [Installation and usage](#installation-and-usage)
- [Configuration](#configuration)
- [Global options](#global-options)
- [Commands](#commands)
  - [`new`](#new--create-a-recipe)
  - [`bump`](#bump--change-a-version)
  - [`build`](#build--build-locally)
  - [`publish`](#publish--publish-to-s3)
  - [`promote`](#promote--copy-between-s3-channels)
  - [`update`](#update--mirror-skill-forge-packages)
  - [`list`](#list--list-packages)
  - [`delete`](#delete--delete-packages)
  - [`index`](#index--rebuild-the-channel-index)
- [Recommended release workflows](#recommended-release-workflows)
- [GitHub Pages](#github-pages)
- [Errors and exit codes](#errors-and-exit-codes)

## Installation and usage

In this repository, run the CLI through Pixi:

```shell
pixi install
pixi run pixi-skill-recipes --help
pixi run pixi-skill-recipes <COMMAND> --help
```

Alternatively, an installed package provides the `pixi-skill-recipes` and
`psr` commands:

```shell
pixi run psr --help
```

The general command syntax is:

```text
pixi run pixi-skill-recipes [GLOBAL OPTIONS] COMMAND [COMMAND OPTIONS]
```

Global options go **before** the subcommand. For example:

```shell
pixi run pixi-skill-recipes --profile company-aws publish my-skill --env dev
```

## Configuration

The CLI reads its configuration from `pixi-skill-recipes.toml` in the
repository directory. Supported filenames are:

1. `pixi-skill-recipes.toml`
2. `.pixi-skill-recipes.toml`
3. `skill-recipes.toml`

Here is an example setup with separate development and production channels:

```toml
[channels.dev]
bucket = "skill-publish-dev"
prefix = "conda"
endpoint_url = "https://<account-id>.r2.cloudflarestorage.com"
region = "auto"
addressing_style = "path"

[channels.prd]
bucket = "skill-publish-prd"
prefix = "conda"
endpoint_url = "https://<account-id>.r2.cloudflarestorage.com"
region = "auto"
addressing_style = "path"
```

Each `[channels.<name>]` entry describes an S3-compatible destination:

| Field | Meaning |
|---|---|
| `bucket` | Required bucket name |
| `prefix` | Optional key prefix; defaults to `conda` |
| `endpoint_url` | Optional S3-compatible endpoint, such as Cloudflare R2 |
| `region` | S3 region; defaults to `auto` |
| `addressing_style` | `auto`, `path`, or `virtual`; defaults to `virtual` |

For example, the `[channels.dev]` channel with the `conda` prefix corresponds
to `s3://skill-publish-dev/conda`. `--env dev` selects the `dev` name from this
table; `--env` is not a bucket name.

### Configuration file location

- `--root PATH` sets the repository directory. Without this option, the CLI
  searches upward from the current directory for `pixi.toml` or a known
  configuration file.
- `--config PATH` loads a specific configuration file. An explicitly specified
  path that does not exist is an error.
- `PIXI_SKILL_RECIPES_CONFIG` specifies a configuration file when `--config` is
  not used.
- `recipes_dir` is optional in the configuration file and defaults to
  `recipes`.

The precedence for locating the configuration file is `--config`, then
`PIXI_SKILL_RECIPES_CONFIG`, then searching the detected repository.

### Environment variables and credentials

Individual channel fields can be overridden with environment variables. The
schema is `PIXI_SKILL_RECIPES_<CHANNEL>_<FIELD>`; names are converted to
uppercase and punctuation is replaced with underscores:

```text
PIXI_SKILL_RECIPES_PRD_BUCKET=skill-publish-production
PIXI_SKILL_RECIPES_DEV_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
```

Environment variables override the corresponding file entry, but not other
channel fields. Do not put a secret in the configuration file or commit it to
version control.

S3 credentials are **not** read from the channel TOML file. The CLI uses the
standard AWS/Boto3 credential chain, for example:

- an AWS profile entry from `~/.aws/credentials` and `~/.aws/config`,
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`,
- temporary credentials together with `AWS_SESSION_TOKEN`,
- a role or environment identity supported by AWS/Boto3.

Select a profile globally before the command:

```shell
pixi run pixi-skill-recipes --profile r2-publisher publish my-skill --env dev
```

Grant the profile only the permissions it needs. The CLI needs no upstream
credentials for a publicly readable upstream repository; it needs appropriate
write permissions to upload, delete, and index the target channel.

## Global options

| Option | Effect |
|---|---|
| `--root PATH` | Specify the repository directory |
| `--config PATH` | Specify the configuration file |
| `--profile NAME` | Select the AWS profile for S3 access |
| `--verbose` | Show output from launched subprocesses |
| `--yes` | Skip confirmation prompts for `delete` and `promote` |
| `--rattler-build PATH` | Specify the path to the `rattler-build` executable |
| `--rattler-index PATH` | Specify the path to the `rattler-index` executable |

`--yes` is not a general-purpose "ignore errors" switch. It only confirms
operations that ask for confirmation. It does not bypass conflict checks or
package and credential validation.

## Commands

### `new` – create a recipe

```text
pixi run pixi-skill-recipes new SKILL [--description TEXT] [--force]
```

Creates starter versions of `recipes/<SKILL>/SKILL.md` and `recipe.yaml`.
Skill names may contain only lowercase letters, digits, and hyphens; they may
not start or end with a hyphen.

```shell
pixi run pixi-skill-recipes new api-guides --description "Internal API guides"
```

`--force` overwrites the generated `SKILL.md` and `recipe.yaml` in the skill
directory. It does not delete additional files or resources already in that
directory. Review any changes there before overwriting.

### `bump` – change a version

```text
pixi run pixi-skill-recipes bump SKILL (--part {major,minor,patch} | --rc | --version VERSION) [--dry-run]
```

Changes `package.version` in the local `recipe.yaml`. Versions are interpreted
according to PEP 440.

```shell
# 0.1.0 -> 0.1.1
pixi run pixi-skill-recipes bump api-guides --part patch

# 0.1.0 -> 0.2.0
pixi run pixi-skill-recipes bump api-guides --part minor

# 0.1.0 -> 0.1.0rc1; repeated calls increment rc1 to rc2, and so on.
pixi run pixi-skill-recipes bump api-guides --rc

# Set a specific version
pixi run pixi-skill-recipes bump api-guides --version 1.0.0

# Preview the change without writing it
pixi run pixi-skill-recipes bump api-guides --part patch --dry-run
```

For `major`, `minor`, and `patch`, the lower-order components are reset to
zero. `--version` cannot be combined with `--part` or `--rc`. The CLI reports
an error if none of these three version-changing options is specified. A
version that is already set is not written again.

Changing skill contents does **not** automatically increase the package
version. Change the version deliberately before building and publishing the
recipe.

### `build` – build locally

```text
pixi run pixi-skill-recipes build [SKILL ... | --all] [--output-dir PATH]
```

Runs `rattler-build` for the selected local recipes and shows the generated
package files.

```shell
# Build one recipe
pixi run pixi-skill-recipes build api-guides

# Build all recipes
pixi run pixi-skill-recipes build --all

# Use a different output directory
pixi run pixi-skill-recipes build api-guides --output-dir .\build-output
```

Without `--output-dir`, the output directory is
`<repository>/validation-output`. Specify either skill names or `--all`; using
both is invalid. `--all` includes local recipes, not upstream packages from
skill-forge.

### `publish` – publish to S3

```text
pixi run pixi-skill-recipes publish [SKILL ... | --all]
  [--env NAME] [--no-build --build-dir PATH] [--force] [--no-index] [--dry-run]
```

By default, `publish` temporarily builds the selected local recipes and uploads
the generated package files to the specified S3 channel. The default channel
is `dev`. After uploading, the CLI updates the channel index.

```shell
# Build, upload to dev, and update the index
pixi run pixi-skill-recipes publish api-guides --env dev

# Preview the publication without building or uploading
pixi run pixi-skill-recipes publish api-guides --env dev --dry-run

# Reuse previously built artifacts
pixi run pixi-skill-recipes publish api-guides --env dev --no-build --build-dir .\validation-output

# Publish all local recipes
pixi run pixi-skill-recipes publish --all --env dev
```

Important details:

- `--no-build` requires `--build-dir`. The CLI searches there for packages
  whose name and version match the local `recipe.yaml`.
- Before uploading, the CLI checks whether the destination channel already
  contains the same object keys. By default, overwriting is refused.
- `--force` allows existing objects at exactly the same package path to be
  overwritten. It does not increase the package version.
- `--dry-run` lists planned uploads; it does not upload packages or update the
  index.
- `--no-index` leaves the channel index unchanged. Use it only when you
  deliberately plan to update the index separately with `index`.
- The local `publish` command publishes to S3, not directly to GitHub Pages.

### `promote` – copy between S3 channels

```text
pixi run pixi-skill-recipes promote [SKILL ... | --all]
  [--source NAME] [--target NAME] [--version VERSION | --all-versions]
  [--force] [--no-index] [--dry-run]
```

Copies already-published packages from the source channel to the target
channel. The defaults are `--source dev` and `--target prd`; unless
`--version` or `--all-versions` is specified, the latest available version of
each package is copied.

```shell
# Copy the latest version to prd
pixi run pixi-skill-recipes promote api-guides

# Copy a specific version
pixi run pixi-skill-recipes promote api-guides --version 1.0.0

# Copy all versions of selected skills
pixi run pixi-skill-recipes promote api-guides --all-versions

# Preview which files would be copied
pixi run pixi-skill-recipes promote --all --dry-run
```

`--version` and `--all-versions` are mutually exclusive. The source and target
must be different. The CLI checks for existing destination files before
copying and refuses conflicts by default; `--force` allows them to be
overwritten. Without `--dry-run`, the CLI asks for confirmation before the
operation. Use `--yes` to skip this prompt, for example in a non-interactive
invocation:

```shell
pixi run pixi-skill-recipes --yes promote --all --source dev --target prd
```

After copying, the target channel index is updated unless `--no-index` is set.
Promotion does not change local recipes.

### `update` – mirror skill-forge packages

```text
pixi run pixi-skill-recipes update [SKILL ... | --all]
  [--env NAME] [--source-url HTTPS-URL] [--dry-run] [--no-index]
```

`update` gets package metadata and packages from the public
[`skill-forge` Conda channel](https://prefix.dev/skill-forge), provided by the
[`pavelzw/skill-forge`](https://github.com/pavelzw/skill-forge) repository. The
default source channel is `https://prefix.dev/skill-forge`.

The positional argument is the skill name **without** the package prefix:

```shell
# Check whether polars is newer than the version in dev
pixi run pixi-skill-recipes update polars --env dev --dry-run

# Mirror the newer version to dev
pixi run pixi-skill-recipes update polars --env dev

# Check and update every skill available upstream
pixi run pixi-skill-recipes update --all --env dev
```

For `polars`, for example, the CLI looks for the Conda package
`agent-skill-polars`. This command does **not** require a local recipe for the
skill. It mirrors packages; it does not copy upstream files into `recipes/` or
automatically modify a local recipe.

#### What `update` does, step by step

1. Reads `noarch/repodata.json` from the configured HTTPS source channel.
2. Finds available packages named `agent-skill-<skill>`.
3. Selects the highest upstream version for each skill according to PEP 440.
4. Reads package versions in the target channel (`--env`, defaulting to
   `dev`).
5. Skips skills whose highest target version is equal to or newer than the
   highest upstream version.
6. Downloads the package file(s) for the latest upstream version.
7. Compares file size and SHA-256 with the values in upstream repodata, if the
   upstream provides them.
8. Refuses to overwrite an existing identical package path, uploads the
   packages to S3, and then updates the index.

Downloads accept only HTTPS source URLs, and unsafe package paths are rejected.
An integrity mismatch results in an error; an invalid local download file is
removed. `--dry-run` performs selection and conflict checks but does not
download package files or change S3 or the index. `--no-index` uploads
packages but leaves the target index unchanged.

Here, `--all` means all upstream packages with the `agent-skill-` prefix, not
all local recipes. An explicitly named skill that is unknown upstream is an
error. If neither skill names nor `--all` are specified, the command does not
perform a blanket update.

**Choose the target carefully:** `update` writes only to the configured S3
channel selected by `--env`. The default, `dev`, is recommended for the usual
update-check workflow. This CLI invocation does not publish directly to GitHub
Pages.

### `list` – list packages

```text
pixi run pixi-skill-recipes list [--env NAME] [--skill SKILL] [--json]
```

Reads the channel index and displays the package files registered in it. The
default channel is `dev`.

```shell
pixi run pixi-skill-recipes list --env dev
pixi run pixi-skill-recipes list --env prd --skill polars
pixi run pixi-skill-recipes list --env dev --json
```

`--skill polars` filters for the `agent-skill-polars` package. `--json`
produces machine-readable records with the package name, version, build,
subchannel, filename, and—if present in repodata—checksum and file size. An
empty channel is a valid result and is reported as such.

### `delete` – delete packages

```text
pixi run pixi-skill-recipes delete SKILL [--env NAME]
  (--version VERSION | --all-versions) [--dry-run] [--no-index]
```

Removes package files from the selected S3 channel (default: `dev`). You must
specify exactly one version or `--all-versions`:

```shell
# Preview which file would be affected
pixi run pixi-skill-recipes delete polars --version 1.0.0 --dry-run

# Delete a version after confirmation
pixi run pixi-skill-recipes delete polars --env dev --version 1.0.0

# Delete all versions of a package without interaction
pixi run pixi-skill-recipes --yes delete polars --env dev --all-versions
```

Without `--dry-run`, the command requires confirmation. In a non-interactive
environment, you must explicitly put `--yes` before the subcommand.
`--version` and `--all-versions` cannot be combined. After deletion, the
channel index is forcibly rebuilt; use `--no-index` to skip this.

Deletion is destructive and cannot be undone. Check the channel, version, and
dry-run output before confirming.

### `index` – rebuild the channel index

```text
pixi run pixi-skill-recipes index [--env NAME] [--force]
```

Runs `rattler-index` for the selected channel. `--env` defaults to `dev`.
`--force` tells `rattler-index` to rebuild the index:

```shell
pixi run pixi-skill-recipes index --env dev
pixi run pixi-skill-recipes index --env dev --force
```

This command does not change package files; it only updates the channel's
repodata. The S3 profile and endpoint come from the same channel configuration
as `publish`.

## Recommended release workflows

### Develop a local skill recipe and publish it to `dev`

```shell
pixi run pixi-skill-recipes new api-guides --description "Internal API guides"
# Edit SKILL.md, recipe.yaml, and any resources
pixi run pixi-skill-recipes bump api-guides --part patch
pixi run pixi-skill-recipes build api-guides
pixi run pixi-skill-recipes publish api-guides --env dev --dry-run
pixi run pixi-skill-recipes publish api-guides --env dev
pixi run pixi-skill-recipes list --env dev --skill api-guides
```

You need to change the version if the skill's content has changed. The
`publish` command's conflict check prevents accidentally overwriting an
existing package file.

### Update an upstream skill in `dev` and promote it to `prd`

```shell
pixi run pixi-skill-recipes update polars --env dev --dry-run
pixi run pixi-skill-recipes update polars --env dev
pixi run pixi-skill-recipes list --env dev --skill polars
pixi run pixi-skill-recipes promote polars --source dev --target prd --dry-run
pixi run pixi-skill-recipes promote polars --source dev --target prd
```

This keeps the upstream update check limited to the development channel first.
Promotion copies only packages that are already registered in the source
channel.

## GitHub Pages

The CLI writes directly to S3. The existing GitHub Actions workflow then
publishes the complete R2 channel to GitHub Pages. After `update` uploads new
packages to `dev`:

1. Make sure the R2 target channel is configured correctly and accessible.
2. On the `main` branch, start **Actions → Publish skills → Run workflow** on
   GitHub.
3. The workflow builds and publishes the local recipes to R2, reindexes the
   complete R2 channel, and mirrors the complete channel to GitHub Pages.

Merging this workflow change into `main` also triggers the configured
main-branch publishing workflow. Later local `update` invocations do not
automatically trigger a GitHub workflow. `update --env prd` alone does not
update Pages either; the Pages pipeline mirrors the R2 channel configured for
the workflow.

## Errors and exit codes

- `--help` displays the options and arguments recognized by the command
  parser.
- Expected recipe, configuration, build, channel, and storage errors are
  printed to `stderr` with a non-zero exit code.
- An invalid CLI invocation (for example, missing required arguments or
  conflicting options) is rejected by the argument parser.
- `Ctrl+C` stops the running command with exit code `130`.
- An error in an upstream HTTPS request, repodata, download checksum,
  credentials, or S3 access prevents a success message.

Useful diagnostic commands:

```shell
pixi run pixi-skill-recipes --help
pixi run pixi-skill-recipes update --help
pixi run pixi-skill-recipes --verbose index --env dev
pixi run pixi-skill-recipes list --env dev --json
```

## Further documentation

- [Project overview and skill distribution](README.md)
- [Contribution and recipe conventions](CONTRIBUTE.md)
