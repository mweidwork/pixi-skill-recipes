"""Tests for the command-line workflows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pixi_skill_recipes import cli
from pixi_skill_recipes.channel import PackageRecord
from pixi_skill_recipes.config import ChannelSettings, load_config
from pixi_skill_recipes.recipes import scaffold_skill

from .conftest import MemoryStorage, repodata_bytes


def _write_project(root: Path) -> None:
    """Create a minimal repository with development and production channels."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pixi.toml").write_text("[workspace]\n", encoding="utf-8")
    (root / "pixi-skill-recipes.toml").write_text(
        "\n".join(
            [
                "[channels.dev]",
                'bucket = "dev-bucket"',
                "",
                "[channels.prd]",
                'bucket = "prd-bucket"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _record(version: str) -> PackageRecord:
    """Create a noarch record for a code-review skill package."""
    return PackageRecord(
        name="agent-skill-code-review",
        version=version,
        build="h0_0",
        build_number=0,
        subdir="noarch",
        filename=f"agent-skill-code-review-{version}-h0_0.conda",
    )


def _put_records(
    storage: MemoryStorage,
    records: list[PackageRecord],
    settings: ChannelSettings,
) -> None:
    """Populate an in-memory channel with repodata and package objects."""
    storage.put_bytes(settings.key("noarch", "repodata.json"), repodata_bytes(records))
    for record in records:
        storage.put_bytes(record.key(settings), b"package:" + record.version.encode())


def test_main_new_and_bump_rc(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The CLI scaffolds a skill and updates its recipe to an RC version."""
    _write_project(tmp_path)

    assert cli.main(
        [
            "--root",
            str(tmp_path),
            "new",
            "code-review",
            "--description",
            "Review code carefully.",
        ]
    ) == 0
    assert cli.main(["--root", str(tmp_path), "bump", "code-review", "--rc"]) == 0

    assert "version: \"0.1.0rc1\"" in (
        tmp_path / "recipes" / "code-review" / "recipe.yaml"
    ).read_text(encoding="utf-8")
    assert "0.1.0 -> 0.1.0rc1" in capsys.readouterr().out


def test_publish_dry_run_does_not_upload_or_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A publish dry run reports uploads without modifying storage."""
    _write_project(tmp_path)
    scaffold_skill(tmp_path / "recipes", "code-review")
    build_dir = tmp_path / "build" / "noarch"
    build_dir.mkdir(parents=True)
    artifact = build_dir / _record("0.1.0").filename
    artifact.write_bytes(b"package")
    storage = MemoryStorage()
    indexed: list[str] = []
    monkeypatch.setattr(cli.Runtime, "storage", lambda _self, _name: storage)
    monkeypatch.setattr(
        cli.Runtime,
        "index",
        lambda _self, _settings, _storage, **_kwargs: indexed.append("indexed"),
    )

    result = cli.main(
        [
            "--root",
            str(tmp_path),
            "publish",
            "code-review",
            "--no-build",
            "--build-dir",
            str(tmp_path / "build"),
            "--dry-run",
        ]
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "would upload " in output
    assert artifact.name in output
    assert storage.objects == {}
    assert indexed == []


def test_promote_copies_latest_package_between_channels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promote copies the highest available version to production."""
    _write_project(tmp_path)
    config = load_config(root=tmp_path)
    dev_storage = MemoryStorage()
    prd_storage = MemoryStorage()
    records = [_record("0.1.0"), _record("0.2.0rc1"), _record("0.2.0")]
    _put_records(dev_storage, records, config.channel("dev"))
    stores = {"dev": dev_storage, "prd": prd_storage}
    monkeypatch.setattr(
        cli.Runtime,
        "storage",
        lambda _self, name: stores[name],
    )

    result = cli.main(
        [
            "--root",
            str(tmp_path),
            "--yes",
            "promote",
            "code-review",
            "--no-index",
        ]
    )

    expected = config.channel("prd").key("noarch", _record("0.2.0").filename)
    assert result == 0
    assert prd_storage.objects[expected] == b"package:0.2.0"


def test_delete_all_versions_removes_packages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delete removes all selected package versions when confirmed."""
    _write_project(tmp_path)
    config = load_config(root=tmp_path)
    storage = MemoryStorage()
    records = [_record("0.1.0"), _record("0.2.0")]
    _put_records(storage, records, config.channel("dev"))
    monkeypatch.setattr(cli.Runtime, "storage", lambda _self, _name: storage)

    result = cli.main(
        [
            "--root",
            str(tmp_path),
            "--yes",
            "delete",
            "code-review",
            "--all-versions",
            "--no-index",
        ]
    )

    assert result == 0
    assert not any(key.endswith(".conda") for key in storage.objects)


def test_list_json_emits_package_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The list command emits machine-readable records as JSON."""
    _write_project(tmp_path)
    config = load_config(root=tmp_path)
    storage = MemoryStorage()
    _put_records(storage, [_record("0.1.0")], config.channel("dev"))
    monkeypatch.setattr(cli.Runtime, "storage", lambda _self, _name: storage)

    result = cli.main(["--root", str(tmp_path), "list", "--json"])

    records = json.loads(capsys.readouterr().out)
    assert result == 0
    assert records[0]["name"] == "agent-skill-code-review"
    assert records[0]["version"] == "0.1.0"
