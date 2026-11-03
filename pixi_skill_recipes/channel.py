"""Conda channel inspection and repodata generation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .config import ChannelSettings
from .errors import ChannelError
from .storage import Storage
from .versioning import latest_version, parse_version

DEFAULT_SUBDIRS = ("noarch",)
PACKAGE_EXTENSIONS = (".conda", ".tar.bz2")
PACKAGE_CONTENT_TYPE = "application/octet-stream"
PACKAGE_CACHE_CONTROL = "public, max-age=31536000, immutable"


@dataclass(frozen=True)
class PackageRecord:
    """A package entry from channel repodata.

    Args:
        name: Conda package name.
        version: Package version.
        build: Build string.
        build_number: Build number.
        subdir: Channel subdirectory such as ``noarch``.
        filename: Package filename.
        sha256: Optional SHA-256 from repodata.
        size: Optional size in bytes from repodata.
    """

    name: str
    version: str
    build: str
    build_number: int
    subdir: str
    filename: str
    sha256: str | None = None
    size: int | None = None

    def key(self, settings: ChannelSettings) -> str:
        """Return the object key for this package.

        Args:
            settings: Channel connection settings.

        Returns:
            The S3 object key for the package file.
        """
        return settings.key(self.subdir, self.filename)


def package_name_for_skill(skill: str) -> str:
    """Return the Conda package name for a skill.

    Args:
        skill: Skill directory name.

    Returns:
        The package name, for example ``agent-skill-code-review``.
    """
    return f"agent-skill-{skill}"


def read_repodata(
    storage: Storage,
    settings: ChannelSettings,
    subdir: str = "noarch",
) -> dict[str, Any]:
    """Read a channel subdirectory's ``repodata.json``.

    Args:
        storage: Object storage implementation.
        settings: Channel connection settings.
        subdir: Channel subdirectory, usually ``noarch``.

    Returns:
        Parsed repodata, or an empty mapping when the file is missing.

    Raises:
        ChannelError: If the repodata file is not valid JSON.
    """
    key = settings.key(subdir, "repodata.json")
    raw = storage.get_bytes(key)
    if raw is None:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ChannelError(f"invalid repodata JSON at {key}: {exc}") from exc
    if not isinstance(data, dict):
        raise ChannelError(f"repodata at {key} must be a JSON object")
    return data


def load_packages(
    storage: Storage,
    settings: ChannelSettings,
    *,
    subdirs: Sequence[str] = DEFAULT_SUBDIRS,
) -> list[PackageRecord]:
    """Load package records from channel repodata.

    Args:
        storage: Object storage implementation.
        settings: Channel connection settings.
        subdirs: Channel subdirectories to inspect.

    Returns:
        Package records sorted by name, version, and build.
    """
    records: list[PackageRecord] = []
    seen: set[tuple[str, str]] = set()

    for subdir in subdirs:
        data = read_repodata(storage, settings, subdir)
        for record in parse_repodata(data, subdir):
            identity = (record.subdir, record.filename)
            if identity not in seen:
                seen.add(identity)
                records.append(record)

    return sorted(records, key=lambda record: (record.name, record.version, record.build))


def parse_repodata(data: Mapping[str, Any], subdir: str) -> list[PackageRecord]:
    """Parse package records from one repodata document.

    Args:
        data: Parsed repodata mapping.
        subdir: Channel subdirectory containing the repodata.

    Returns:
        Package records listed in the document.
    """
    records: list[PackageRecord] = []
    for section in ("packages", "packages.conda"):
        entries = data.get(section) or {}
        if not isinstance(entries, dict):
            continue
        for filename, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            records.append(
                PackageRecord(
                    name=str(entry.get("name") or ""),
                    version=str(entry.get("version") or ""),
                    build=str(entry.get("build") or ""),
                    build_number=int(entry.get("build_number") or 0),
                    subdir=str(entry.get("subdir") or subdir),
                    filename=str(filename),
                    sha256=_optional_str(entry.get("sha256")),
                    size=_optional_int(entry.get("size")),
                )
            )
    return records


def select_records(
    records: Iterable[PackageRecord],
    *,
    skill: str,
    version: str | None = None,
) -> list[PackageRecord]:
    """Select package records for a skill and optional version.

    Args:
        records: Candidate package records.
        skill: Skill directory name.
        version: Optional exact version filter.

    Returns:
        Matching records sorted by version and build.
    """
    package_name = package_name_for_skill(skill)
    selected = [
        record
        for record in records
        if record.name == package_name and (version is None or record.version == version)
    ]
    return sorted(selected, key=lambda record: (record.version, record.build))


def versions_for_skill(records: Iterable[PackageRecord], *, skill: str) -> list[str]:
    """Return the versions available for a skill.

    Args:
        records: Candidate package records.
        skill: Skill directory name.

    Returns:
        Sorted versions using PEP 440 ordering.
    """
    package_name = package_name_for_skill(skill)
    return sorted(
        {record.version for record in records if record.name == package_name},
        key=parse_version,
    )


def latest_version_for_skill(records: Iterable[PackageRecord], *, skill: str) -> str:
    """Return the latest version available for a skill.

    Args:
        records: Candidate package records.
        skill: Skill directory name.

    Returns:
        The highest version.

    Raises:
        ChannelError: If the skill has no packages.
    """
    versions = versions_for_skill(records, skill=skill)
    if not versions:
        raise ChannelError(f"skill '{skill}' has no packages in the source channel")
    return latest_version(versions)


def index_channel(
    settings: ChannelSettings,
    *,
    force: bool = False,
    verbose: bool = False,
    executable: str | None = None,
    credentials: dict[str, str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    """Regenerate channel repodata with ``rattler-index``.

    Credentials are passed through environment variables instead of command line
    arguments so secrets do not appear in process listings.

    Args:
        settings: Channel connection settings.
        force: Rebuild repodata from scratch instead of updating it incrementally.
        verbose: Stream rattler-index output to the terminal.
        executable: Optional path to ``rattler-index``.
        credentials: Optional ``S3_*`` credential environment variables.
        runner: Subprocess runner, injectable for tests.

    Raises:
        ChannelError: If rattler-index is unavailable or fails.
    """
    exe = executable or shutil.which("rattler-index")
    if exe is None:
        raise ChannelError(
            "rattler-index was not found on PATH. Install it with 'pixi install' "
            "or pass --rattler-index."
        )

    command = [exe, "s3", settings.s3_url]
    if settings.endpoint_url:
        command.extend(["--endpoint-url", settings.endpoint_url])
    if settings.region:
        command.extend(["--region", settings.region])
    command.extend(
        [
            "--addressing-style",
            "path" if settings.addressing_style == "path" else "virtual-host",
        ]
    )
    if force:
        command.append("--force")

    env = os.environ.copy()
    if credentials:
        env.update(credentials)

    result = runner(
        command,
        check=False,
        capture_output=not verbose,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        output = (result.stderr or result.stdout or "").strip()
        raise ChannelError(
            f"rattler-index failed for {settings.s3_url}" + (f": {output}" if output else "")
        )


def _optional_str(value: object) -> str | None:
    """Convert an optional repodata value to a string.

    Args:
        value: Raw repodata value.

    Returns:
        The value as a string, or ``None``.
    """
    if value is None:
        return None
    return str(value)


def _optional_int(value: object) -> int | None:
    """Convert an optional repodata value to an integer.

    Args:
        value: Raw repodata value.

    Returns:
        The value as an integer, or ``None`` when it is absent or invalid.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    try:
        return int(value)
    except ValueError:
        return None
