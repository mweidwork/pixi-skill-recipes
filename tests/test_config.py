"""Tests for configuration loading and environment overrides."""

from __future__ import annotations

from pathlib import Path

import pytest

from pixi_skill_recipes.config import load_config
from pixi_skill_recipes.errors import ConfigError


def _write_config(root: Path) -> Path:
    """Write a minimal repository and configuration file."""
    (root / "pixi.toml").write_text("[workspace]\n", encoding="utf-8")
    config = root / "pixi-skill-recipes.toml"
    config.write_text(
        "\n".join(
            [
                'recipes_dir = "recipes"',
                "",
                "[channels.dev]",
                'bucket = "dev-bucket"',
                'prefix = "conda"',
                'endpoint_url = "https://dev.example"',
                'region = "auto"',
                'addressing_style = "path"',
                "",
                "[channels.prd]",
                'bucket = "prd-bucket"',
            ]
        ),
        encoding="utf-8",
    )
    return config


def test_load_config_reads_channels(tmp_path: Path) -> None:
    """Channel settings are loaded from the configuration file."""
    _write_config(tmp_path)

    config = load_config(root=tmp_path)

    assert config.root == tmp_path
    assert config.recipes_dir == tmp_path / "recipes"
    assert config.config_path is not None
    assert config.channel("dev").bucket == "dev-bucket"
    assert config.channel("dev").s3_url == "s3://dev-bucket/conda"
    assert config.channel("prd").addressing_style == "virtual"


def test_environment_overrides_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables override individual channel fields."""
    _write_config(tmp_path)
    monkeypatch.setenv("PIXI_SKILL_RECIPES_DEV_BUCKET", "override-bucket")
    monkeypatch.setenv("PIXI_SKILL_RECIPES_DEV_PREFIX", "channel")

    config = load_config(root=tmp_path)

    assert config.channel("dev").bucket == "override-bucket"
    assert config.channel("dev").s3_url == "s3://override-bucket/channel"


def test_unknown_channel_raises(tmp_path: Path) -> None:
    """Requesting an unconfigured channel fails with a helpful error."""
    _write_config(tmp_path)
    config = load_config(root=tmp_path)

    with pytest.raises(ConfigError, match="unknown channel"):
        config.channel("staging")


def test_missing_config_is_allowed(tmp_path: Path) -> None:
    """Commands that do not need S3 can run without a configuration file."""
    (tmp_path / "pixi.toml").write_text("[workspace]\n", encoding="utf-8")

    config = load_config(root=tmp_path)

    assert config.channels == {}
    assert config.recipes_dir == tmp_path / "recipes"


def test_explicit_missing_config_raises(tmp_path: Path) -> None:
    """An explicitly requested missing config file is an error."""
    (tmp_path / "pixi.toml").write_text("[workspace]\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="config file not found"):
        load_config(root=tmp_path, config_path=tmp_path / "missing.toml")
