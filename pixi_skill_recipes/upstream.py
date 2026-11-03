"""Read and download packages from public Conda channels."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, urlopen

from .channel import PackageRecord, parse_repodata
from .errors import ChannelError

DEFAULT_SKILL_FORGE_CHANNEL_URL = "https://prefix.dev/skill-forge"
REQUEST_TIMEOUT_SECONDS = 30
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
SAFE_SUBDIR_RE = re.compile(r"^[a-z0-9-]+$")
SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.+-]+$")


class _URLResponse(Protocol):
    """Subset of an urllib response used by this module."""

    def read(self, size: int = -1) -> bytes: ...

    def geturl(self) -> str: ...

    def close(self) -> None: ...


def load_upstream_packages(
    channel_url: str = DEFAULT_SKILL_FORGE_CHANNEL_URL,
) -> list[PackageRecord]:
    """Load noarch package records from a public Conda channel.

    Args:
        channel_url: HTTPS URL of the channel root.

    Returns:
        Package records sorted by name, version, and build.

    Raises:
        ChannelError: If the channel URL, response, or repodata is invalid.
    """
    base_url = _channel_url(channel_url)
    raw = _read_url(urljoin(base_url, "noarch/repodata.json"))
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ChannelError(f"invalid upstream repodata JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ChannelError("upstream repodata must be a JSON object")
    return sorted(
        parse_repodata(data, "noarch"),
        key=lambda record: (record.name, record.version, record.build),
    )


def download_upstream_package(
    channel_url: str,
    record: PackageRecord,
    destination: Path,
) -> None:
    """Download and verify one package from a public Conda channel.

    Args:
        channel_url: HTTPS URL of the channel root.
        record: Repodata record describing the package.
        destination: Local file path for the downloaded package.

    Raises:
        ChannelError: If the record is unsafe, the request fails, or integrity
            metadata does not match the downloaded package.
    """
    base_url = _channel_url(channel_url)
    if not SAFE_SUBDIR_RE.fullmatch(record.subdir):
        raise ChannelError(f"invalid upstream package subdirectory: {record.subdir!r}")
    if not SAFE_FILENAME_RE.fullmatch(record.filename):
        raise ChannelError(f"invalid upstream package filename: {record.filename!r}")

    package_url = urljoin(
        base_url,
        f"{quote(record.subdir, safe='')}/{quote(record.filename, safe='')}",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    try:
        response = _open_url(package_url)
        try:
            _require_https_response(response.geturl(), package_url)
            with destination.open("wb") as output:
                while chunk := response.read(DOWNLOAD_CHUNK_SIZE):
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
        finally:
            response.close()
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise ChannelError(f"failed to write upstream package {destination}: {exc}") from exc
    except ChannelError:
        destination.unlink(missing_ok=True)
        raise

    if record.size is not None and size != record.size:
        destination.unlink(missing_ok=True)
        raise ChannelError(
            f"upstream package size mismatch for {record.filename}: "
            f"expected {record.size}, got {size}"
        )
    if record.sha256 is not None and digest.hexdigest().lower() != record.sha256.lower():
        destination.unlink(missing_ok=True)
        raise ChannelError(f"upstream package SHA-256 mismatch for {record.filename}")


def _channel_url(value: str) -> str:
    """Validate and normalize a public Conda channel URL."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ChannelError(f"invalid upstream channel URL: {exc}") from exc
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not parsed.hostname
        or (port is not None and not 1 <= port <= 65535)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ChannelError("upstream channel URL must be an HTTPS URL without query or fragment")
    return value.rstrip("/") + "/"


def _read_url(url: str) -> bytes:
    """Read an HTTPS response body."""
    response = _open_url(url)
    try:
        _require_https_response(response.geturl(), url)
        return response.read()
    except OSError as exc:
        raise ChannelError(f"failed to fetch upstream URL {url}: {exc}") from exc
    finally:
        response.close()


def _open_url(url: str) -> _URLResponse:
    """Open an HTTPS URL with a bounded timeout and a stable user agent."""
    request = Request(url, headers={"User-Agent": "pixi-skill-recipes/1.0"})
    try:
        return cast(_URLResponse, urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS))
    except HTTPError as exc:
        raise ChannelError(f"upstream request failed with HTTP {exc.code}: {url}") from exc
    except URLError as exc:
        raise ChannelError(f"failed to fetch upstream URL {url}: {exc.reason}") from exc


def _require_https_response(response_url: str, requested_url: str) -> None:
    """Reject redirects to non-HTTPS locations."""
    if urlsplit(response_url).scheme != "https":
        raise ChannelError(f"upstream redirected to a non-HTTPS URL: {requested_url}")
