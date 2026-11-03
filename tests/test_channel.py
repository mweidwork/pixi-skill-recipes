"""Tests for repodata parsing and channel indexing."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

import pytest
from pixi_skill_recipes.channel import (
    PackageRecord,
    index_channel,
    latest_version_for_skill,
    load_packages,
    select_records,
    versions_for_skill,
)
from pixi_skill_recipes.errors import ChannelError

from .conftest import MemoryStorage, dev_settings, repodata_bytes


def _records() -> list[PackageRecord]:
    """Create sample package records."""
    return [
        PackageRecord(
            name="agent-skill-code-review",
            version="0.1.0",
            build="h0_0",
            build_number=0,
            subdir="noarch",
            filename="agent-skill-code-review-0.1.0-h0_0.conda",
        ),
        PackageRecord(
            name="agent-skill-code-review",
            version="0.2.0rc1",
            build="h0_0",
            build_number=0,
            subdir="noarch",
            filename="agent-skill-code-review-0.2.0rc1-h0_0.conda",
        ),
        PackageRecord(
            name="agent-skill-python-development",
            version="0.1.0",
            build="h0_0",
            build_number=0,
            subdir="noarch",
            filename="agent-skill-python-development-0.1.0-h0_0.conda",
        ),
    ]


def _storage_with_records(records: Sequence[PackageRecord]) -> MemoryStorage:
    """Create an in-memory channel containing the supplied records."""
    storage = MemoryStorage()
    settings = dev_settings()
    storage.put_bytes(settings.key("noarch", "repodata.json"), repodata_bytes(records))
    for record in records:
        storage.put_bytes(record.key(settings), b"package")
    return storage


def test_load_packages_reads_repodata() -> None:
    """Package records are loaded from repodata.json."""
    storage = _storage_with_records(_records())

    packages = load_packages(storage, dev_settings())

    assert len(packages) == 3
    assert packages[0].name == "agent-skill-code-review"
    assert packages[0].key(dev_settings()) == (
        "conda/noarch/agent-skill-code-review-0.1.0-h0_0.conda"
    )


def test_select_records_filters_by_skill_and_version() -> None:
    """Record selection matches package name and exact version."""
    packages = load_packages(_storage_with_records(_records()), dev_settings())

    selected = select_records(packages, skill="code-review", version="0.1.0")

    assert [record.version for record in selected] == ["0.1.0"]


def test_versions_for_skill_uses_pep440_order() -> None:
    """Versions are ordered with release candidates before final releases."""
    packages = load_packages(_storage_with_records(_records()), dev_settings())

    assert versions_for_skill(packages, skill="code-review") == ["0.1.0", "0.2.0rc1"]
    assert latest_version_for_skill(packages, skill="code-review") == "0.2.0rc1"


def test_latest_version_for_missing_skill_raises() -> None:
    """Requesting a missing skill produces a channel error."""
    packages = load_packages(_storage_with_records(_records()), dev_settings())

    with pytest.raises(ChannelError, match="has no packages"):
        latest_version_for_skill(packages, skill="missing")


def test_index_channel_builds_expected_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """The indexer receives channel, endpoint, region, and credentials."""
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_runner(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs["env"]))  # type: ignore[arg-type]
        return subprocess.CompletedProcess(command, 0, "", "")

    index_channel(
        dev_settings(endpoint_url="https://r2.example"),
        force=True,
        credentials={"S3_ACCESS_KEY_ID": "key", "S3_SECRET_ACCESS_KEY": "secret"},
        executable="rattler-index",
        runner=fake_runner,
    )

    command, env = calls[0]
    assert command == [
        "rattler-index",
        "s3",
        "s3://test-bucket/conda",
        "--endpoint-url",
        "https://r2.example",
        "--region",
        "auto",
        "--addressing-style",
        "path",
        "--force",
    ]
    assert env["S3_ACCESS_KEY_ID"] == "key"
    assert env["S3_SECRET_ACCESS_KEY"] == "secret"


def test_index_channel_reports_failures() -> None:
    """A non-zero rattler-index exit becomes a ChannelError."""

    def failing_runner(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 2, "", "boom")

    with pytest.raises(ChannelError, match="boom"):
        index_channel(
            dev_settings(),
            executable="rattler-index",
            runner=failing_runner,
        )
