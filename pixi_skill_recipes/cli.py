"""Command line interface for the pixi-skill-recipes channel tooling."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .builder import Builder, find_artifacts
from .channel import (
    PACKAGE_CACHE_CONTROL,
    PACKAGE_CONTENT_TYPE,
    ChannelSettings,
    PackageRecord,
    index_channel,
    latest_version_for_skill,
    load_packages,
    package_name_for_skill,
    select_records,
    versions_for_skill,
)
from .config import Config, load_config
from .errors import ChannelError, RecipeError, SkillRecipesError
from .recipes import (
    Recipe,
    list_skills,
    load_recipe,
    scaffold_skill,
    set_recipe_version,
)
from .storage import S3Storage, Storage
from .versioning import bump_version, parse_version


@dataclass
class Runtime:
    """Resolved runtime dependencies shared by command handlers."""

    config: Config
    profile: str | None = None
    assume_yes: bool = False
    verbose: bool = False
    rattler_build: str | None = None
    rattler_index: str | None = None

    def storage(self, channel_name: str) -> S3Storage:
        """Create an S3 storage adapter for a configured channel."""
        return S3Storage(self.config.channel(channel_name), profile=self.profile)

    def builder(self) -> Builder:
        """Create a recipe builder."""
        return Builder(self.rattler_build, verbose=self.verbose)

    def index(
        self,
        settings: ChannelSettings,
        storage: Storage,
        *,
        force: bool = False,
    ) -> None:
        """Regenerate the channel repodata for a configured channel."""
        index_channel(
            settings,
            force=force,
            verbose=self.verbose,
            executable=self.rattler_index,
            credentials=storage.credentials_env(),  # type: ignore[attr-defined]
        )


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="pixi-skill-recipes",
        description="Build and manage agent skills in a Pixi-compatible Conda channel.",
    )
    parser.add_argument("--root", type=Path, help="Repository root (defaults to auto-detect)")
    parser.add_argument("--config", type=Path, help="Path to pixi-skill-recipes.toml")
    parser.add_argument("--profile", help="AWS profile to use for S3 credentials")
    parser.add_argument("--verbose", action="store_true", help="Stream subprocess output")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts for destructive operations",
    )
    parser.add_argument("--rattler-build", help="Path to the rattler-build executable")
    parser.add_argument("--rattler-index", help="Path to the rattler-index executable")

    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="Scaffold a new skill recipe")
    new_parser.add_argument("skill", help="Skill name, for example data-engineering")
    new_parser.add_argument("--description", help="Short skill description")
    new_parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    new_parser.set_defaults(func=cmd_new)

    bump_parser = subparsers.add_parser("bump", help="Change a recipe version")
    bump_parser.add_argument("skill", help="Skill name")
    bump_parser.add_argument(
        "--part",
        choices=("major", "minor", "patch"),
        help="Release component to increment",
    )
    bump_parser.add_argument(
        "--rc",
        action="store_true",
        help="Create or increment a release candidate version",
    )
    bump_parser.add_argument("--version", help="Set an explicit version")
    bump_parser.add_argument("--dry-run", action="store_true", help="Print without writing")
    bump_parser.set_defaults(func=cmd_bump)

    build_parser = subparsers.add_parser("build", help="Build one or more recipes")
    build_parser.add_argument("skills", nargs="*", metavar="SKILL")
    build_parser.add_argument("--all", action="store_true", help="Build every recipe")
    build_parser.add_argument(
        "--output-dir",
        type=Path,
        help="Build output directory (defaults to validation-output)",
    )
    build_parser.set_defaults(func=cmd_build)

    publish_parser = subparsers.add_parser("publish", help="Upload built skills to a channel")
    publish_parser.add_argument("skills", nargs="*", metavar="SKILL")
    publish_parser.add_argument("--all", action="store_true", help="Publish every recipe")
    publish_parser.add_argument("--env", default="dev", help="Channel name (default: dev)")
    publish_parser.add_argument("--no-build", action="store_true", help="Reuse existing artifacts")
    publish_parser.add_argument(
        "--build-dir",
        type=Path,
        help="Build directory to use with --no-build",
    )
    publish_parser.add_argument("--force", action="store_true", help="Overwrite existing objects")
    publish_parser.add_argument("--no-index", action="store_true", help="Skip repodata generation")
    publish_parser.add_argument("--dry-run", action="store_true", help="Print without uploading")
    publish_parser.set_defaults(func=cmd_publish)

    delete_parser = subparsers.add_parser("delete", help="Delete skill packages from a channel")
    delete_parser.add_argument("skill", help="Skill name")
    delete_parser.add_argument("--env", default="dev", help="Channel name (default: dev)")
    delete_parser.add_argument("--version", help="Package version to delete")
    delete_parser.add_argument(
        "--all-versions",
        action="store_true",
        help="Delete every version of the skill",
    )
    delete_parser.add_argument("--dry-run", action="store_true", help="Print without deleting")
    delete_parser.add_argument("--no-index", action="store_true", help="Skip repodata generation")
    delete_parser.set_defaults(func=cmd_delete)

    promote_parser = subparsers.add_parser(
        "promote",
        help="Copy skill packages from one channel to another",
    )
    promote_parser.add_argument("skills", nargs="*", metavar="SKILL")
    promote_parser.add_argument("--all", action="store_true", help="Promote every recipe")
    promote_parser.add_argument("--source", default="dev", help="Source channel (default: dev)")
    promote_parser.add_argument("--target", default="prd", help="Target channel (default: prd)")
    promote_parser.add_argument("--version", help="Version to promote (defaults to latest)")
    promote_parser.add_argument(
        "--all-versions",
        action="store_true",
        help="Promote every version of each selected skill",
    )
    promote_parser.add_argument("--force", action="store_true", help="Overwrite existing objects")
    promote_parser.add_argument("--no-index", action="store_true", help="Skip repodata generation")
    promote_parser.add_argument("--dry-run", action="store_true", help="Print without copying")
    promote_parser.set_defaults(func=cmd_promote)

    list_parser = subparsers.add_parser("list", help="List packages in a channel")
    list_parser.add_argument("--env", default="dev", help="Channel name (default: dev)")
    list_parser.add_argument("--skill", help="Filter by skill name")
    list_parser.add_argument("--json", action="store_true", help="Emit JSON")
    list_parser.set_defaults(func=cmd_list)

    index_parser = subparsers.add_parser("index", help="Regenerate channel repodata")
    index_parser.add_argument("--env", default="dev", help="Channel name (default: dev)")
    index_parser.add_argument("--force", action="store_true", help="Rebuild repodata from scratch")
    index_parser.set_defaults(func=cmd_index)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line interface and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(root=args.root, config_path=args.config)
        runtime = Runtime(
            config=config,
            profile=args.profile,
            assume_yes=args.yes,
            verbose=args.verbose,
            rattler_build=args.rattler_build,
            rattler_index=args.rattler_index,
        )
        return int(args.func(runtime, args) or 0)
    except SkillRecipesError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("aborted", file=sys.stderr)
        return 130


def cmd_new(runtime: Runtime, args: argparse.Namespace) -> int:
    """Scaffold a new skill under the configured recipes directory."""
    skill_path, recipe_path = scaffold_skill(
        runtime.config.recipes_dir,
        args.skill,
        description=args.description,
        force=args.force,
    )
    print(f"created {skill_path}")
    print(f"created {recipe_path}")
    return 0


def cmd_bump(runtime: Runtime, args: argparse.Namespace) -> int:
    """Update the version in a recipe."""
    if args.version and (args.part or args.rc):
        raise RecipeError("--version cannot be combined with --part or --rc")
    if not args.version and not args.part and not args.rc:
        raise RecipeError("specify --part, --rc, or --version")

    recipe = load_recipe(runtime.config.recipes_dir, args.skill)
    if args.version:
        new_version = args.version
        parse_version(new_version)
    else:
        new_version = bump_version(recipe.version, part=args.part, rc=args.rc)

    if new_version == recipe.version:
        raise RecipeError(f"{recipe.skill} is already at version {new_version}")

    if args.dry_run:
        print(f"{recipe.skill}: {recipe.version} -> {new_version} (dry run)")
        return 0

    set_recipe_version(recipe.path, new_version)
    print(f"{recipe.skill}: {recipe.version} -> {new_version}")
    return 0


def cmd_build(runtime: Runtime, args: argparse.Namespace) -> int:
    """Build one or more skill recipes."""
    skills = _resolve_skills(runtime, args.skills, args.all)
    output_dir = args.output_dir or runtime.config.root / "validation-output"
    builder = runtime.builder()

    for skill in skills:
        recipe = load_recipe(runtime.config.recipes_dir, skill)
        result = builder.build(recipe, output_dir)
        for artifact in result.artifacts:
            print(_display_path(artifact, runtime.config.root))
    return 0


def cmd_publish(runtime: Runtime, args: argparse.Namespace) -> int:
    """Build and upload skill packages to a configured channel."""
    settings, storage = _load_channel(runtime, args.env)
    skills = _resolve_skills(runtime, args.skills, args.all)
    build_dir_argument = (
        args.build_dir.expanduser().resolve() if args.build_dir is not None else None
    )
    if args.no_build and build_dir_argument is None:
        raise ChannelError("--no-build requires --build-dir")

    builder = runtime.builder()
    uploads: list[tuple[Path, str]] = []

    with tempfile.TemporaryDirectory(prefix="pixi-skill-recipes-") as temporary:
        build_dir = build_dir_argument or Path(temporary)
        for skill in skills:
            recipe = load_recipe(runtime.config.recipes_dir, skill)
            if args.no_build:
                artifacts = find_artifacts(build_dir, recipe)
                if not artifacts:
                    raise ChannelError(
                        f"no artifacts found for {recipe.package_name} {recipe.version} "
                        f"in {build_dir}"
                    )
            else:
                artifacts = builder.build(recipe, build_dir).artifacts

            for artifact in artifacts:
                key = settings.key(artifact.parent.name, artifact.name)
                uploads.append((artifact, key))

        _check_conflicts(storage, uploads, force=args.force)

        if args.dry_run:
            for artifact, key in uploads:
                print(f"would upload {_display_path(artifact, runtime.config.root)} -> {key}")
            return 0

        for artifact, key in uploads:
            storage.upload_file(
                artifact,
                key,
                content_type=PACKAGE_CONTENT_TYPE,
                cache_control=PACKAGE_CACHE_CONTROL,
            )
            print(f"uploaded {artifact.name} -> {key}")

    if not args.no_index:
        runtime.index(settings, storage)

    print(f"published {len(uploads)} package file(s) to {args.env}")
    return 0


def cmd_delete(runtime: Runtime, args: argparse.Namespace) -> int:
    """Delete skill packages from a channel and refresh repodata."""
    if not args.version and not args.all_versions:
        raise ChannelError("specify --version or --all-versions")
    if args.version and args.all_versions:
        raise ChannelError("--version cannot be combined with --all-versions")

    settings, storage = _load_channel(runtime, args.env)
    records = load_packages(storage, settings)
    selected = select_records(records, skill=args.skill, version=args.version)
    if not selected:
        scope = args.version or "all versions"
        raise ChannelError(f"skill '{args.skill}' ({scope}) was not found in {args.env}")

    keys = sorted({record.key(settings) for record in selected})
    for key in keys:
        print(f"would delete {key}" if args.dry_run else f"deleting {key}")

    if args.dry_run:
        return 0

    _confirm(
        runtime,
        f"Delete {len(keys)} package file(s) for '{args.skill}' from {args.env}?",
    )
    storage.delete_keys(keys)

    if not args.no_index:
        runtime.index(settings, storage, force=True)

    print(f"deleted {len(keys)} package file(s) from {args.env}")
    return 0


def cmd_promote(runtime: Runtime, args: argparse.Namespace) -> int:
    """Copy skill packages from a source channel to a target channel."""
    if args.source == args.target:
        raise ChannelError("source and target channels must be different")
    if args.version and args.all_versions:
        raise ChannelError("--version cannot be combined with --all-versions")

    source_settings, source_storage = _load_channel(runtime, args.source)
    target_settings, target_storage = _load_channel(runtime, args.target)
    skills = _resolve_skills(runtime, args.skills, args.all, require_recipe=False)

    source_records = load_packages(source_storage, source_settings)
    copies: list[tuple[PackageRecord, str, str]] = []

    for skill in skills:
        if args.version:
            versions = [args.version]
        elif args.all_versions:
            versions = versions_for_skill(source_records, skill=skill)
            if not versions:
                raise ChannelError(f"skill '{skill}' has no packages in {args.source}")
        else:
            versions = [latest_version_for_skill(source_records, skill=skill)]

        for version in versions:
            records = select_records(source_records, skill=skill, version=version)
            if not records:
                raise ChannelError(
                    f"skill '{skill}' version '{version}' was not found in {args.source}"
                )
            for record in records:
                copies.append(
                    (
                        record,
                        record.key(source_settings),
                        record.key(target_settings),
                    )
                )

    _check_conflicts(target_storage, [(record, key) for record, _, key in copies], force=args.force)

    if args.dry_run:
        for record, source_key, target_key in copies:
            print(f"would copy {source_key} -> {target_key}")
        return 0

    _confirm(
        runtime,
        f"Promote {len(copies)} package file(s) from {args.source} to {args.target}?",
    )

    with tempfile.TemporaryDirectory(prefix="pixi-skill-recipes-promote-") as temporary:
        temporary_dir = Path(temporary)
        for record, source_key, target_key in copies:
            local_path = temporary_dir / record.subdir / record.filename
            source_storage.download_file(source_key, local_path)
            target_storage.upload_file(
                local_path,
                target_key,
                content_type=PACKAGE_CONTENT_TYPE,
                cache_control=PACKAGE_CACHE_CONTROL,
            )
            print(f"copied {source_key} -> {target_key}")

    if not args.no_index:
        runtime.index(target_settings, target_storage)

    print(f"promoted {len(copies)} package file(s) to {args.target}")
    return 0


def cmd_list(runtime: Runtime, args: argparse.Namespace) -> int:
    """List packages available in a channel."""
    settings, storage = _load_channel(runtime, args.env)
    records = load_packages(storage, settings)
    if args.skill:
        records = select_records(records, skill=args.skill)

    if args.json:
        print(json.dumps([asdict(record) for record in records], indent=2))
        return 0

    if not records:
        print(f"no packages found in {args.env}")
        return 0

    rows = [
        (
            record.name,
            record.version,
            record.build,
            record.subdir,
            record.filename,
        )
        for record in records
    ]
    _print_table(("NAME", "VERSION", "BUILD", "SUBDIR", "FILENAME"), rows)
    return 0


def cmd_index(runtime: Runtime, args: argparse.Namespace) -> int:
    """Regenerate channel repodata."""
    settings, storage = _load_channel(runtime, args.env)
    runtime.index(settings, storage, force=args.force)
    print(f"indexed {settings.s3_url}")
    return 0


def _load_channel(runtime: Runtime, name: str) -> tuple[ChannelSettings, S3Storage]:
    settings = runtime.config.channel(name)
    return settings, runtime.storage(name)


def _resolve_skills(
    runtime: Runtime,
    skills: Sequence[str],
    all_skills: bool,
    *,
    require_recipe: bool = True,
) -> list[str]:
    if all_skills and skills:
        raise RecipeError("pass either skill names or --all, not both")
    if all_skills:
        selected = list_skills(runtime.config.recipes_dir)
        if not selected:
            raise RecipeError(f"no recipes found in {runtime.config.recipes_dir}")
    elif skills:
        selected = list(dict.fromkeys(skills))
    else:
        raise RecipeError("specify at least one skill or --all")

    if require_recipe:
        for skill in selected:
            if not (runtime.config.recipes_dir / skill / "recipe.yaml").is_file():
                raise RecipeError(f"recipe not found: {skill}")
    return selected


def _check_conflicts(
    storage: Storage,
    items: Sequence[tuple[Any, str]],
    *,
    force: bool,
) -> None:
    if force:
        return
    conflicts = [key for _, key in items if storage.exists(key)]
    if conflicts:
        formatted = "\n  ".join(conflicts)
        raise ChannelError(
            "refusing to overwrite existing package files; bump the version or use --force:\n"
            f"  {formatted}"
        )


def _confirm(runtime: Runtime, message: str) -> None:
    if runtime.assume_yes:
        return
    if not sys.stdin.isatty():
        raise SkillRecipesError(f"{message} Re-run with --yes to confirm.")
    answer = input(f"{message} [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise SkillRecipesError("aborted")


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _print_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def _package_name_for_skill(skill: str) -> str:
    """Return the Conda package name for a skill (kept for API compatibility)."""
    return package_name_for_skill(skill)


if __name__ == "__main__":
    raise SystemExit(main())
