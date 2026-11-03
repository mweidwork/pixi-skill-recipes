"""Shared pytest fixtures and in-memory storage helpers."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from pixi_skill_recipes.channel import PackageRecord
from pixi_skill_recipes.config import ChannelSettings


class MemoryStorage:
    """In-memory implementation of the storage protocol for tests."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.uploads: list[tuple[str, bytes]] = []

    def get_bytes(self, key: str) -> bytes | None:
        """Return stored bytes for a key."""
        return self.objects.get(key)

    def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        cache_control: str | None = None,
    ) -> None:
        """Store bytes under a key."""
        self.objects[key] = data

    def exists(self, key: str) -> bool:
        """Return whether a key exists."""
        return key in self.objects

    def upload_file(
        self,
        path: Path,
        key: str,
        *,
        content_type: str | None = None,
        cache_control: str | None = None,
    ) -> None:
        """Read a local file into memory under a key."""
        data = path.read_bytes()
        self.objects[key] = data
        self.uploads.append((key, data))

    def download_file(self, key: str, path: Path) -> None:
        """Write a stored object to a local path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.objects[key])

    def delete_keys(self, keys: Sequence[str]) -> int:
        """Delete keys and return the number removed."""
        deleted = 0
        for key in set(keys):
            if self.objects.pop(key, None) is not None:
                deleted += 1
        return deleted

    def list_keys(self, prefix: str = "") -> list[str]:
        """List keys with a prefix."""
        return sorted(key for key in self.objects if key.startswith(prefix))

    def head(self, key: str) -> dict[str, object] | None:
        """Return metadata for an existing key."""
        if key not in self.objects:
            return None
        return {"ContentLength": len(self.objects[key])}

    def credentials_env(self) -> dict[str, str]:
        """Return no credentials for the in-memory backend."""
        return {}


def repodata_bytes(records: Sequence[PackageRecord]) -> bytes:
    """Render a minimal noarch repodata document.

    Args:
        records: Package records to include.

    Returns:
        JSON-encoded repodata bytes.
    """
    packages: dict[str, dict[str, object]] = {}
    for record in records:
        packages[record.filename] = {
            "name": record.name,
            "version": record.version,
            "build": record.build,
            "build_number": record.build_number,
            "subdir": record.subdir,
            "sha256": record.sha256,
            "size": record.size,
        }
    return json.dumps(
        {
            "info": {"subdir": "noarch"},
            "packages": {},
            "packages.conda": packages,
            "repodata_version": 2,
        }
    ).encode("utf-8")


def dev_settings(**overrides: object) -> ChannelSettings:
    """Create channel settings for tests.

    Args:
        **overrides: Fields that override the defaults.

    Returns:
        Channel settings for a ``dev`` channel.
    """
    values: dict[str, object] = {
        "name": "dev",
        "bucket": "test-bucket",
        "prefix": "conda",
        "endpoint_url": None,
        "region": "auto",
        "addressing_style": "path",
    }
    values.update(overrides)
    return ChannelSettings(**values)  # type: ignore[arg-type]
