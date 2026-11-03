"""Repository and channel configuration.

Configuration is read from ``pixi-skill-recipes.toml`` (or one of its fallback
names). Secrets are never stored in the file; S3 credentials come from the
standard boto3 credential chain, including environment variables, profiles, and
instance roles.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .errors import ConfigError

CONFIG_FILENAMES = (
    "pixi-skill-recipes.toml",
    ".pixi-skill-recipes.toml",
    "skill-recipes.toml",
)
DEFAULT_PREFIX = "conda"
AddressingStyle = Literal["auto", "path", "virtual"]
ADDRESSING_STYLES: frozenset[AddressingStyle] = frozenset({"auto", "path", "virtual"})


@dataclass(frozen=True)
class ChannelSettings:
    """Connection settings for one Conda channel stored in S3.

    Args:
        name: Logical channel name such as ``dev`` or ``prd``.
        bucket: S3 bucket that stores the channel.
        prefix: Key prefix inside the bucket. Defaults to ``conda``.
        endpoint_url: Optional S3-compatible endpoint, for example Cloudflare R2.
        region: S3 region. Defaults to ``auto`` for R2.
        addressing_style: boto3 addressing style: ``auto``, ``path``, or ``virtual``.

    Raises:
        ConfigError: If the bucket is missing or the addressing style is invalid.
    """

    name: str
    bucket: str
    prefix: str = DEFAULT_PREFIX
    endpoint_url: str | None = None
    region: str = "auto"
    addressing_style: AddressingStyle = "virtual"

    def __post_init__(self) -> None:
        """Validate required settings and normalize the object prefix."""
        if not self.bucket or not str(self.bucket).strip():
            raise ConfigError(f"channel '{self.name}' is missing a bucket")
        if self.addressing_style not in ADDRESSING_STYLES:
            allowed = ", ".join(sorted(ADDRESSING_STYLES))
            raise ConfigError(
                f"channel '{self.name}' has invalid addressing_style "
                f"'{self.addressing_style}' (expected one of: {allowed})"
            )
        object.__setattr__(self, "prefix", str(self.prefix).strip("/"))

    @property
    def s3_url(self) -> str:
        """Return the channel URL in ``s3://bucket/prefix`` form."""
        if self.prefix:
            return f"s3://{self.bucket}/{self.prefix}"
        return f"s3://{self.bucket}"

    def key(self, *parts: str) -> str:
        """Build an object key below the channel prefix.

        Args:
            *parts: Path components such as ``"noarch"`` and a package filename.

        Returns:
            A POSIX-style S3 object key with duplicate slashes removed.
        """
        cleaned = [str(part).strip("/") for part in parts if str(part).strip("/")]
        if self.prefix:
            cleaned.insert(0, self.prefix)
        return "/".join(cleaned)


@dataclass(frozen=True)
class Config:
    """Repository configuration resolved from disk and environment variables.

    Args:
        root: Repository root directory.
        recipes_dir: Directory containing skill recipes.
        channels: Configured channels keyed by logical name.
        config_path: Configuration file that was loaded, if any.
    """

    root: Path
    recipes_dir: Path
    channels: dict[str, ChannelSettings] = field(default_factory=dict)
    config_path: Path | None = None

    def channel(self, name: str) -> ChannelSettings:
        """Return a configured channel by name.

        Args:
            name: Logical channel name.

        Returns:
            The matching channel settings.

        Raises:
            ConfigError: If the channel is not configured.
        """
        try:
            return self.channels[name]
        except KeyError:
            available = ", ".join(sorted(self.channels)) or "none"
            raise ConfigError(
                f"unknown channel '{name}' (configured channels: {available})"
            ) from None


def find_root(start: Path | None = None) -> Path:
    """Find the repository root by walking up to a workspace or config file.

    Args:
        start: Directory to start from. Defaults to the current working directory.

    Returns:
        The nearest ancestor containing ``pixi.toml`` or a configuration file.
        If no marker is found, the resolved start directory is returned.
    """
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        has_workspace = (candidate / "pixi.toml").is_file()
        has_config = any((candidate / name).is_file() for name in CONFIG_FILENAMES)
        if has_workspace or has_config:
            return candidate
    return current


def load_config(
    *,
    root: Path | None = None,
    config_path: Path | None = None,
) -> Config:
    """Load repository and channel configuration.

    Environment variables named ``PIXI_SKILL_RECIPES_<CHANNEL>_<FIELD>`` override
    values from the configuration file. For example,
    ``PIXI_SKILL_RECIPES_PRD_BUCKET`` overrides ``channels.prd.bucket``.

    Args:
        root: Repository root. Auto-detected when omitted.
        config_path: Explicit configuration file. When omitted, the environment
            variable ``PIXI_SKILL_RECIPES_CONFIG`` and standard filenames are used.

    Returns:
        The resolved configuration.

    Raises:
        ConfigError: If the file is invalid or a channel is missing required values.
    """
    repo_root = find_root(root)
    path = _resolve_config_path(repo_root, config_path)
    data: dict[str, Any] = {}
    if path is not None:
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"invalid TOML in {path}: {exc}") from exc

    recipes_dir = repo_root / str(data.get("recipes_dir", "recipes"))
    raw_channels = data.get("channels") or {}
    if not isinstance(raw_channels, dict):
        raise ConfigError("'channels' must be a table in the configuration file")

    channels: dict[str, ChannelSettings] = {}
    for name, raw in raw_channels.items():
        if not isinstance(raw, dict):
            raise ConfigError(f"channel '{name}' must be a table")
        channels[str(name)] = ChannelSettings(
            name=str(name),
            bucket=_env_override(name, "bucket", raw.get("bucket")),
            prefix=_env_override(name, "prefix", raw.get("prefix", DEFAULT_PREFIX)),
            endpoint_url=_env_override(name, "endpoint_url", raw.get("endpoint_url")),
            region=_env_override(name, "region", raw.get("region", "auto")),
            addressing_style=_env_override(
                name, "addressing_style", raw.get("addressing_style", "virtual")
            ),
        )

    return Config(
        root=repo_root,
        recipes_dir=recipes_dir,
        channels=channels,
        config_path=path,
    )


def _resolve_config_path(root: Path, explicit: Path | None) -> Path | None:
    """Resolve the configuration file path.

    Args:
        root: Repository root used for filename discovery.
        explicit: User-provided configuration path.

    Returns:
        The resolved file path, or ``None`` when no configuration exists.

    Raises:
        ConfigError: If an explicitly requested file does not exist.
    """
    if explicit is not None:
        path = explicit.expanduser().resolve()
        if not path.is_file():
            raise ConfigError(f"config file not found: {path}")
        return path

    env_path = os.environ.get("PIXI_SKILL_RECIPES_CONFIG")
    if env_path:
        path = Path(env_path).expanduser().resolve()
        if not path.is_file():
            raise ConfigError(f"config file not found: {path}")
        return path

    for name in CONFIG_FILENAMES:
        path = root / name
        if path.is_file():
            return path
    return None


def _env_override(channel: str, field: str, default: Any) -> Any:
    """Return an environment override for a channel field.

    Args:
        channel: Logical channel name.
        field: Field name such as ``bucket`` or ``endpoint_url``.
        default: Value from the configuration file.

    Returns:
        The environment value when present, otherwise ``default``.
    """
    name = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        f"PIXI_SKILL_RECIPES_{channel}_{field}",
    ).upper()
    value = os.environ.get(name)
    return value if value is not None else default
