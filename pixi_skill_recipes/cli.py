"""Command line interface for the pixi-skill-recipes channel tooling."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from .builder import Builder, find_artifacts
from .channel import (
    PACKAGE_CACHE_CONTROL,
    PACKAGE_CONTENT_TYPE,
    ChannelSettings,
    PackageRecord,
    index_channel,
    latest_version_for_skill,
    load_packages,
    select_records,
    versions_for_skill,
)
from .config import Config, load_config
from .errors import ChannelError, RecipeError, SkillRecipesError
from .recipes import (
    list_skills,
    load_recipe,
    scaffold_skill,
    set_recipe_version,
)
from .storage import S3Storage, Storage
from .versioning import bump_version, parse_version


@dataclass
class Runtime:
    """Resolved runtime dependencies shared by command handlers.

    Args:
        config: Loaded repository configuration.
        profile: Optional AWS profile name.
        assume_yes: Whether destructive operations skip confirmation prompts.
        verbose: Whether subprocess output is streamed to the terminal.
        rattler_build: Optional path to ``rattler-build``.
        rattler_index: Optional path to ``rattler-index``.
    """

    config: Config
    profile: str | None = None
    assume_yes: bool = False
    verbose: bool = False
    rattler_build: str | None = None
    rattler_index: str | None = None

    def storage(self, channel_name: str) -> Storage:
        """Create an S3 storage adapter for a configured channel.

        Args:
            channel_name: Logical channel name such as ``dev`` or ``prd``.

        Returns:
            A storage implementation for the channel.
        """
        return S3Storage(self.config.channel(channel_name), profile=self.profile)

    def builder(self) -> Builder:
        """Create a recipe builder.

        Returns:
            A builder configured for this runtime.
        """
        return Builder(self.rattler_build, verbose=self.verbose)

    def index(
        self,
        settings: ChannelSettings,
        storage: Storage,
        *,
        force: bool = False,
    ) -> None:
        """Regenerate channel repodata.

        Args:
            settings: Channel connection settings.
            storage: Storage implementation used to resolve credentials.
            force: Whether to rebuild repodata from scratch.
        """
        index_channel(
            settings,
            force=force,
            verbose=self.verbose,
            executable=self.rattler_index,
            credentials=storage.credentials_env(),
        )


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level argument parser.

    Returns:
        A parser with every CLI command registered.
    """
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

    build_parser_command = subparsers.add_parser("build", help="Build one or more recipes")
    build_parser_command.add_argument("skills", nargs="*", metavar="SKILL")
    build_parser_command.add_argument("--all", action="store_true", help="Build every recipe")
    build_parser_command.add_argument(
        "--output-dir",
        type=Path,
        help="Build output directory (defaults to validation-output)",
    )
    build_parser_command.set_defaults(func=cmd_build)

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
    """Run the command line interface.

    Args:
        argv: Argument list. Defaults to ``sys.argv[1:]``.

    Returns:
        A process exit code.
    """
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
    """Scaffold a new skill under the configured recipes directory.

    Args:
        runtime: Shared command dependencies.
        args: Parsed command arguments.

    Returns:
        Process exit code ``0``.
    """
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
    """Update the version in a recipe.

    Args:
        runtime: Shared command dependencies.
        args: Parsed command arguments.

    Returns:
        Process exit code ``0``.

    Raises:
        RecipeError: If the arguments are ambiguous or the version is unchanged.
    """
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
    """Build one or more skill recipes.

    Args:
        runtime: Shared command dependencies.
        args: Parsed command arguments.

    Returns:
        Process exit code ``0``.
    """
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
    """Build and upload skill packages to a configured channel.

    Args:
        runtime: Shared command dependencies.
        args: Parsed command arguments.

    Returns:
        Process exit code ``0``.

    Raises:
        ChannelError: If build artifacts are missing or existing objects conflict.
    """
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
    """Delete skill packages from a channel and refresh repodata.

    Args:
        runtime: Shared command dependencies.
        args: Parsed command arguments.

    Returns:
        Process exit code ``0``.

    Raises:
        ChannelError: If the selection is ambiguous or no packages match.
    """
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

    if args.dry_run:
        for key in keys:
            print(f"would delete {key}")
        return 0

    _confirm(
        runtime,
        f"Delete {len(keys)} package file(s) for '{args.skill}' from {args.env}?",
    )
    for key in keys:
        print(f"deleting {key}")
    storage.delete_keys(keys)

    if not args.no_index:
        runtime.index(settings, storage, force=True)

    print(f"deleted {len(keys)} package file(s) from {args.env}")
    return 0


def cmd_promote(runtime: Runtime, args: argparse.Namespace) -> int:
    """Copy skill packages from a source channel to a target channel.

    Args:
        runtime: Shared command dependencies.
        args: Parsed command arguments.

    Returns:
        Process exit code ``0``.

    Raises:
        ChannelError: If the source package is missing or target objects conflict.
    """
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

    _check_conflicts(
        target_storage,
        [(record, target_key) for record, _, target_key in copies],
        force=args.force,
    )

    if args.dry_run:
        for _, source_key, target_key in copies:
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
    """List packages available in a channel.

    Args:
        runtime: Shared command dependencies.
        args: Parsed command arguments.

    Returns:
        Process exit code ``0``.
    """
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
    """Regenerate channel repodata.

    Args:
        runtime: Shared command dependencies.
        args: Parsed command arguments.

    Returns:
        Process exit code ``0``.
    """
    settings, storage = _load_channel(runtime, args.env)
    runtime.index(settings, storage, force=args.force)
    print(f"indexed {settings.s3_url}")
    return 0


def _load_channel(runtime: Runtime, name: str) -> tuple[ChannelSettings, Storage]:
    """Resolve a channel and create its storage adapter.

    Args:
        runtime: Shared command dependencies.
        name: Logical channel name.

    Returns:
        The channel settings and a matching storage implementation.
    """
    settings = runtime.config.channel(name)
    return settings, runtime.storage(name)


def _resolve_skills(
    runtime: Runtime,
    skills: Sequence[str],
    all_skills: bool,
    *,
    require_recipe: bool = True,
) -> list[str]:
    """Resolve the skill selection for a command.

    Args:
        runtime: Shared command dependencies.
        skills: Skill names supplied on the command line.
        all_skills: Whether ``--all`` was supplied.
        require_recipe: Whether every selected skill must have a local recipe.

    Returns:
        Deduplicated skill names in the requested order.

    Raises:
        RecipeError: If the selection is empty, ambiguous, or missing a recipe.
    """
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
    items: Sequence[tuple[object, str]],
    *,
    force: bool,
) -> None:
    """Reject overwrites unless the caller explicitly allows them.

    Args:
        storage: Target storage implementation.
        items: Pairs of local objects and target keys.
        force: Whether overwrites are allowed.

    Raises:
        ChannelError: If any target key already exists and ``force`` is false.
    """
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
    """Ask for confirmation before a destructive operation.

    Args:
        runtime: Shared command dependencies.
        message: Prompt shown to the user.

    Raises:
        SkillRecipesError: If the user declines or the session is non-interactive
            without ``--yes``.
    """
    if runtime.assume_yes:
        return
    if not sys.stdin.isatty():
        raise SkillRecipesError(f"{message} Re-run with --yes to confirm.")
    answer = input(f"{message} [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise SkillRecipesError("aborted")


def _display_path(path: Path, root: Path) -> str:
    """Format a path relative to the repository when possible.

    Args:
        path: Path to display.
        root: Repository root.

    Returns:
        A relative path when possible, otherwise the absolute path.
    """
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _print_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    """Print a simple aligned text table.

    Args:
        headers: Column headers.
        rows: Table rows with the same number of columns as ``headers``.
    """
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


if __name__ == "__main__":
    raise SystemExit(main())
