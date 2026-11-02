"""Version parsing and release candidate helpers.

The project uses PEP 440 style versions because Conda orders them predictably
for release candidates. A release candidate sorts before its final release, so
``0.2.0rc1`` is older than ``0.2.0``.
"""

from __future__ import annotations

from collections.abc import Iterable

from packaging.version import InvalidVersion, Version

from .errors import RecipeError

PART_INDEX = {"major": 0, "minor": 1, "patch": 2}


def parse_version(value: str) -> Version:
    """Parse and validate a package version.

    Args:
        value: Version string such as ``0.2.0`` or ``0.2.0rc1``.

    Returns:
        The parsed :class:`packaging.version.Version`.

    Raises:
        RecipeError: If the version is not PEP 440 compatible.
    """
    try:
        return Version(value)
    except InvalidVersion as exc:
        raise RecipeError(f"invalid version '{value}': {exc}") from exc


def bump_version(current: str, *, part: str | None = None, rc: bool = False) -> str:
    """Return the next version for a recipe.

    ``rc=True`` without a part promotes ``X.Y.Z`` to ``X.Y.Zrc1`` and increments
    an existing ``rcN``. Supplying both ``part`` and ``rc`` bumps the release
    first, so ``0.2.0`` with ``part="minor"`` becomes ``0.3.0rc1``.

    Args:
        current: Current version string.
        part: Release component to increment: ``major``, ``minor``, or ``patch``.
        rc: Whether to produce a release candidate version.

    Returns:
        The next version as a string.

    Raises:
        RecipeError: If the current version is invalid, no part is supplied, or
            an unsupported pre-release is converted to an rc.
    """
    version = parse_version(current)

    if rc:
        if part is not None:
            return f"{_bump_release(version, part)}rc1"
        if version.pre and version.pre[0] == "rc":
            return f"{version.base_version}rc{version.pre[1] + 1}"
        if version.pre:
            raise RecipeError(
                f"cannot create an rc from pre-release version '{current}'"
            )
        return f"{version.base_version}rc1"

    if part is None:
        raise RecipeError("a version part is required (major, minor, or patch)")
    return _bump_release(version, part)


def latest_version(versions: Iterable[str]) -> str:
    """Return the highest version from an iterable.

    Args:
        versions: Version strings to compare.

    Returns:
        The highest version using PEP 440 ordering.

    Raises:
        RecipeError: If the iterable is empty or contains an invalid version.
    """
    values = list(versions)
    if not values:
        raise RecipeError("no versions are available")
    return max(values, key=parse_version)


def _bump_release(version: Version, part: str) -> str:
    """Increment a release component and clear lower components.

    Args:
        version: Parsed current version.
        part: Release component to increment.

    Returns:
        A three-component version string without pre-release segments.

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
