"""Tests for reading and verifying public Conda channel packages."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request

import pytest
from pixi_skill_recipes.channel import PackageRecord
from pixi_skill_recipes.errors import ChannelError
from pixi_skill_recipes.upstream import (
    download_upstream_package,
    load_upstream_packages,
)


class _Response(io.BytesIO):
    """Small HTTP response double used to test upstream requests."""

    def __init__(self, content: bytes, url: str) -> None:
        super().__init__(content)
        self.url = url

    def geturl(self) -> str:
        """Return the response URL after redirects."""
        return self.url


def _record(data: bytes) -> PackageRecord:
    """Create a package record matching the provided bytes."""
    return PackageRecord(
        name="agent-skill-polars",
        version="1.2.0",
        build="h0_0",
        build_number=0,
        subdir="noarch",
        filename="agent-skill-polars-1.2.0-h0_0.conda",
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
    )


def test_load_upstream_packages_reads_noarch_repodata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repodata is fetched from the configured channel's noarch directory."""
    repodata = {
        "packages.conda": {
            "agent-skill-polars-1.2.0-h0_0.conda": {
                "name": "agent-skill-polars",
                "version": "1.2.0",
                "build": "h0_0",
                "build_number": 0,
                "sha256": "abc123",
                "size": 42,
            }
        }
    }
    requests: list[tuple[str, float]] = []

    def fake_urlopen(request: Request, *, timeout: float) -> _Response:
        requests.append((request.full_url, timeout))
        return _Response(
            json.dumps(repodata).encode(),
            "https://packages.prefix.dev/skill-forge/noarch/repodata.json",
        )

    monkeypatch.setattr("pixi_skill_recipes.upstream.urlopen", fake_urlopen)

    records = load_upstream_packages("https://prefix.dev/skill-forge/")

    assert requests[0][0] == "https://prefix.dev/skill-forge/noarch/repodata.json"
    assert requests[0][1] > 0
    assert records == [
        PackageRecord(
            name="agent-skill-polars",
            version="1.2.0",
            build="h0_0",
            build_number=0,
            subdir="noarch",
            filename="agent-skill-polars-1.2.0-h0_0.conda",
            sha256="abc123",
            size=42,
        )
    ]


def test_load_upstream_packages_rejects_non_https_url() -> None:
    """Upstream URLs must use HTTPS."""
    with pytest.raises(ChannelError, match="HTTPS"):
        load_upstream_packages("http://prefix.dev/skill-forge")


def test_load_upstream_packages_reports_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed upstream metadata is reported as a channel error."""
    monkeypatch.setattr(
        "pixi_skill_recipes.upstream.urlopen",
        lambda *_args, **_kwargs: _Response(b"{invalid", "https://prefix.dev/channel"),
    )

    with pytest.raises(ChannelError, match="invalid upstream repodata JSON"):
        load_upstream_packages()


def test_download_upstream_package_verifies_hash_and_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Downloaded package bytes are checked against repodata integrity metadata."""
    package = b"conda package data"
    destination = tmp_path / "noarch" / "package.conda"
    monkeypatch.setattr(
        "pixi_skill_recipes.upstream.urlopen",
        lambda *_args, **_kwargs: _Response(
            package,
            "https://packages.prefix.dev/skill-forge/noarch/package.conda",
        ),
    )

    download_upstream_package(
        "https://prefix.dev/skill-forge",
        _record(package),
        destination,
    )

    assert destination.read_bytes() == package


def test_download_upstream_package_removes_invalid_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A package that fails hash verification is not left on disk."""
    destination = tmp_path / "package.conda"
    monkeypatch.setattr(
        "pixi_skill_recipes.upstream.urlopen",
        lambda *_args, **_kwargs: _Response(
            b"tampered",
            "https://packages.prefix.dev/skill-forge/noarch/package.conda",
        ),
    )

    with pytest.raises(ChannelError, match="SHA-256 mismatch"):
        download_upstream_package(
            "https://prefix.dev/skill-forge",
            _record(b"expected"),
            destination,
        )

    assert not destination.exists()


def test_download_upstream_package_rejects_path_traversal(tmp_path: Path) -> None:
    """Package metadata cannot escape the requested download directory."""
    record = PackageRecord(
        name="agent-skill-polars",
        version="1.2.0",
        build="h0_0",
        build_number=0,
        subdir="noarch",
        filename="../outside.conda",
    )

    with pytest.raises(ChannelError, match="invalid upstream package filename"):
        download_upstream_package("https://prefix.dev/skill-forge", record, tmp_path / "out")
