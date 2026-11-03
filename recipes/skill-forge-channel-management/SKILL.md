---
name: skill-forge-channel-management
description: >
  Safely tests and operates the pixi-skill-recipes CLI when mirroring packages
  from the public skill-forge Conda channel to an S3-compatible channel. Use
  when configuring a dev channel, testing the update command, diagnosing
  channel or credential errors, or verifying mirrored package versions.
---

# SkillForge Channel Management

Use this skill when working with `pixi-skill-recipes update` or testing
packages mirrored from the public skill-forge Conda channel.

## Safety rules

- Confirm the target is a development/test channel before any upload, update,
  delete, or index operation. These commands change remote storage.
- Start with `--dry-run` when previewing an update. A dry run does not write
  packages or regenerate the index, but it still needs to read upstream
  metadata and inspect the configured target channel.
- Never request, print, commit, or write credentials to a config file.
- Do not assume the AWS CLI is installed. Prefer the CLI's S3 support or the
  project's Pixi-managed Python environment and its `boto3` dependency.
- Do not seed an older test package or mutate a remote channel unless the user
  explicitly requested that test.

## Configure the target channel

1. Inspect the repository's existing `skill-recipes.toml` or
   `pixi-skill-recipes.toml` before changing anything.
2. The CLI needs a declared channel table, such as `[channels.dev]`, with
   `bucket`, `prefix`, and `endpoint_url`. `--env dev` selects this table; it
   does not create a channel. Environment variables named
   `PIXI_SKILL_RECIPES_DEV_<FIELD>` override fields only for a channel already
   declared in the file.
3. For Cloudflare R2, `endpoint_url` is the account's S3 endpoint only, for
   example `https://<account-id>.r2.cloudflarestorage.com`. Configure the
   bucket separately and use `region = "auto"` and `addressing_style = "path"`.
4. Keep local channel configuration and credentials out of version control.
   The standard AWS/Boto3 credential chain accepts `AWS_ACCESS_KEY_ID`,
   `AWS_SECRET_ACCESS_KEY`, and, for temporary credentials,
   `AWS_SESSION_TOKEN`. Set them in the same shell session used for Pixi.
5. On Windows PowerShell, use `$env:NAME = ...` to set environment variables.
   Never paste credentials into a command argument or ask the user to disclose
   secret values.

If the CLI reports `unknown channel 'dev' (configured channels: none)`, check
that a discovered configuration file contains `[channels.dev]`. Credential
variables alone cannot define a channel.

## Test an upstream update

Use the skill slug without the `agent-skill-` package prefix. For example, the
package `agent-skill-grilling` is addressed as `grilling`.

1. Confirm the target channel and authorization to write to it.
2. List the current package versions:

   ```powershell
   pixi run pixi-skill-recipes list --env dev --skill grilling
   ```

3. Preview the update:

   ```powershell
   pixi run pixi-skill-recipes update grilling --env dev --dry-run
   ```

4. If the preview identifies the expected update and the user authorized the
   write, run:

   ```powershell
   pixi run pixi-skill-recipes update grilling --env dev
   ```

5. Verify the result:

   ```powershell
   pixi run pixi-skill-recipes list --env dev --skill grilling
   ```

The command selects the latest upstream version automatically. It does not
accept a requested source version. To test the version-comparison behavior
against an older target version, first confirm explicit authorization to modify
the test channel. Fetch package records from upstream repodata, choose an older
available version, verify the downloaded file against its advertised size and
SHA-256, upload only that package to the configured channel's `noarch/` path
using `boto3`, then rebuild the channel index:

```powershell
pixi run pixi-skill-recipes index --env dev --force
```

Do not assume `aws s3 cp` is available. If writing a helper command, use Pixi's
Python environment and `boto3`; do not log credentials. After verifying the
older version is listed, run the dry-run, perform the update only with
authorization, and confirm the newer version appears.

## Diagnose common failures

- **No configured channels:** verify the config file was discovered and
  includes the selected `[channels.<name>]` table.
- **Invalid R2 endpoint:** use the account endpoint without the bucket name or
  bucket path; set the bucket and object prefix in their own fields.
- **Credential length or access errors:** verify that the current shell has
  the correct R2 S3 access key and secret, and that they belong to the
  configured account. Never display their values.
- **AWS CLI not found:** use the project's Pixi environment with `boto3` for
  any manual package upload.
- **Update says already up to date:** the target's latest version is equal to
  or newer than the latest upstream version. Do not downgrade it to force an
  update test; use an authorized, isolated test channel.
- **Update fails during package verification:** stop. Do not bypass size or
  SHA-256 verification.

## Completion checklist

- [ ] The target is a development/test channel, not production.
- [ ] The channel is declared in config; no secrets are stored there.
- [ ] The update preview and target versions were checked.
- [ ] Remote writes were explicitly authorized.
- [ ] The final channel listing confirms the expected version.
