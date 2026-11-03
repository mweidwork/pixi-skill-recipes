"""Tests for version bumping and release candidate handling."""

from __future__ import annotations

import pytest

from pixi_skill_recipes.errors import RecipeError
from pixi_skill_recipes.versioning import bump_version, latest_version, parse_version


@pytest.mark.parametrize(
    ("current", "part", "expected"),
    [
        ("0.1.0", "patch", "0.1.1"),
        ("0.1.0", "minor", "0.2.0"),
        ("0.1.0", "major", "1.0.0"),
        ("1.2.3", "patch", "1.2.4"),
        ("1.2.3", "minor", "1.3.0"),
        ("1.2.3", "major", "2.0.0"),
    ],
)
def test_bump_release_component(current: str, part: str, expected: str) -> None:
    """Release bumps increment the requested component and reset lower ones."""
    assert bump_version(current, part=part) == expected


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        ("0.2.0", "0.2.0rc1"),
        ("0.2.0rc1", "0.2.0rc2"),
        ("0.2.0rc9", "0.2.0rc10"),
    ],
)
def test_bump_rc(current: str, expected: str) -> None:
    """RC bumps create or increment the release candidate number."""
    assert bump_version(current, rc=True) == expected


def test_bump_rc_with_release_part() -> None:
    """An RC combined with a release part bumps the base version first."""
    assert bump_version("0.2.0", part="minor", rc=True) == "0.3.0rc1"


def test_bump_requires_part() -> None:
    """A release bump without a part is rejected."""
    with pytest.raises(RecipeError):
        bump_version("0.2.0")


def test_invalid_version_is_rejected() -> None:
    """Invalid versions produce a RecipeError."""
    with pytest.raises(RecipeError):
        parse_version("not-a-version")


def test_latest_version_uses_pep440_ordering() -> None:
    """Release candidates sort before the final release."""
    assert latest_version(["0.1.0", "0.2.0rc1", "0.2.0"]) == "0.2.0"
    assert latest_version(["0.1.0", "0.2.0rc2", "0.2.0rc1"]) == "0.2.0rc2"
