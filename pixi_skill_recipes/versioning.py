"""Parse, compare, and increment package versions.

Versions follow PEP 440 ordering, where a release candidate sorts before its
final release. For example, ``0.2.0rc1`` is older than ``0.2.0``.
"""

from __future__ import annotations

from collections.abc import Iterable

from packaging.version import InvalidVersion, Version

from .errors import RecipeError

PART_INDEX: dict[str, int] = {"major": 0, "minor": 1, "patch": 2}


def parse_version(value: str) -> Version:
    """Parse a package version using PEP 440 rules.

    Args:
        value: Version string to parse.

    Returns:
        The parsed `Version`.

    Raises:
        RecipeError: If the value is not a valid PEP 440 version.
    """
    try:
        return Version(value)
    except InvalidVersion as exc:
        raise RecipeError(f"invalid version '{value}': {exc}") from exc


def bump_version(current: str, *, part: str | None = None, rc: bool = False) -> str:
    """Return the next recipe version after a release or release-candidate bump.

    With ``rc=True`` and no ``part``, a final version becomes its first release
    candidate and an existing release candidate advances by one. Supplying
    both ``part`` and ``rc`` increments the release component first, then
    starts at ``rc1`` (for example, ``0.2.0`` with ``part="minor"`` becomes
    ``0.3.0rc1``).

    Args:
        current: Version string to increment.
        part: Release component to increment, if any. Must be ``major``,
            ``minor``, or ``patch``.
        rc: Whether to return a release-candidate version.

    Returns:
        The incremented version string.

    Raises:
        RecipeError: If the current version is invalid, ``part`` is missing for
            a release bump, ``part`` is unsupported, or ``rc=True`` is used
            without ``part`` for a non-release-candidate pre-release version.
    """
    version = parse_version(current)

    if rc:
        if part is not None:
            return f"{_bump_release(version, part)}rc1"
        if version.pre and version.pre[0] == "rc":
            return f"{version.base_version}rc{version.pre[1] + 1}"
        if version.pre:
            raise RecipeError(f"cannot create an rc from pre-release version '{current}'")
        return f"{version.base_version}rc1"

    if part is None:
        raise RecipeError("a version part is required (major, minor, or patch)")
    return _bump_release(version, part)


def latest_version(versions: Iterable[str]) -> str:
    """Return the highest version from an iterable using PEP 440 ordering.

    Args:
        versions: Version strings to compare. The iterable is consumed once.

    Returns:
        The highest version string.

    Raises:
        RecipeError: If the iterable is empty or contains an invalid version.
    """
    values = list(versions)
    if not values:
        raise RecipeError("no versions are available")
    return max(values, key=parse_version)


def _bump_release(version: Version, part: str) -> str:
    """Increment a release component and reset all lower components.

    Args:
        version: Parsed version to increment.
        part: Component to increment: ``major``, ``minor``, or ``patch``.

    Returns:
        A three-component release string without pre-release segments.

    Raises:
        RecipeError: If ``part`` is not a supported release component.
    """
    try:
        index = PART_INDEX[part]
    except KeyError:
        allowed = ", ".join(PART_INDEX)
        raise RecipeError(f"invalid version part '{part}' (expected one of: {allowed})") from None

    release = list(version.release[:3])
    while len(release) < 3:
        release.append(0)

    release[index] += 1
    for position in range(index + 1, 3):
        release[position] = 0

    return ".".join(str(number) for number in release)
