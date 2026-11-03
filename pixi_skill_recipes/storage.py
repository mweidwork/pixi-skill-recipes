"""Object storage abstractions and an S3-compatible implementation.

The :class:`Storage` protocol keeps command handlers testable without network
access. :class:`S3Storage` works with AWS S3 and Cloudflare R2.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

if TYPE_CHECKING:
    from mypy_boto3_s3.type_defs import PutObjectRequestTypeDef

from .config import ChannelSettings
from .errors import StorageError

MISSING_CODES = {"404", "NoSuchKey", "NotFound"}
DELETE_BATCH_SIZE = 1000


class Storage(Protocol):
    """Minimal object storage interface used by the channel commands."""

    def get_bytes(self, key: str) -> bytes | None:
        """Return an object's bytes, or ``None`` when it does not exist."""
        ...

    def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        cache_control: str | None = None,
    ) -> None:
        """Write bytes to an object key."""
        ...

    def exists(self, key: str) -> bool:
        """Return whether an object exists."""
        ...

    def upload_file(
        self,
        path: Path,
        key: str,
        *,
        content_type: str | None = None,
        cache_control: str | None = None,
    ) -> None:
        """Upload a local file to an object key."""
        ...

    def download_file(self, key: str, path: Path) -> None:
        """Download an object key to a local file."""
        ...

    def delete_keys(self, keys: Sequence[str]) -> int:
        """Delete object keys and return the number removed."""
        ...

    def list_keys(self, prefix: str = "") -> list[str]:
        """List object keys under a prefix."""
        ...

    def head(self, key: str) -> dict[str, Any] | None:
        """Return object metadata, or ``None`` when the object is missing."""
        ...

    def credentials_env(self) -> dict[str, str]:
        """Return S3 credentials in rattler-index environment variable form."""
        ...


class S3Storage:
    """Thin S3 wrapper that works with Cloudflare R2 and AWS S3.

    Args:
        settings: Channel connection settings.
        profile: Optional AWS profile name.
        session: Optional preconfigured boto3 session, mainly for tests.
    """

    def __init__(
        self,
        settings: ChannelSettings,
        *,
        profile: str | None = None,
        session: boto3.Session | None = None,
    ) -> None:
        """Create an S3 client configured for the channel."""
        self.settings = settings
        self.session = session or boto3.Session(profile_name=profile)
        self._client = self.session.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            region_name=settings.region,
            config=BotoConfig(
                signature_version="s3v4",
                retries={"max_attempts": 5, "mode": "standard"},
                s3={"addressing_style": settings.addressing_style},
            ),
        )

    @property
    def bucket(self) -> str:
        """Return the configured bucket name."""
        return self.settings.bucket

    def get_bytes(self, key: str) -> bytes | None:
        """Return an object's bytes, or ``None`` when it does not exist.

        Args:
            key: Object key.

        Returns:
            The object body, or ``None`` for a missing object.

        Raises:
            StorageError: If the request fails for another reason.
        """
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            body: bytes = response["Body"].read()
            return body
        except ClientError as exc:
            if _is_missing(exc):
                return None
            raise StorageError(f"failed to read s3://{self.bucket}/{key}: {exc}") from exc
        except BotoCoreError as exc:
            raise StorageError(f"failed to read s3://{self.bucket}/{key}: {exc}") from exc

    def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        cache_control: str | None = None,
    ) -> None:
        """Write bytes to an object key.

        Args:
            key: Object key.
            data: Object body.
            content_type: Optional HTTP content type.
            cache_control: Optional HTTP cache control header.

        Raises:
            StorageError: If the request fails.
        """
        request: PutObjectRequestTypeDef = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": data,
        }
        if content_type:
            request["ContentType"] = content_type
        if cache_control:
            request["CacheControl"] = cache_control
        try:
            self._client.put_object(**request)
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"failed to write s3://{self.bucket}/{key}: {exc}") from exc

    def exists(self, key: str) -> bool:
        """Return whether an object exists.

        Args:
            key: Object key.

        Returns:
            ``True`` when the object exists.
        """
        return self.head(key) is not None

    def head(self, key: str) -> dict[str, Any] | None:
        """Return object metadata, or ``None`` when the object is missing.

        Args:
            key: Object key.

        Returns:
            A dictionary of response metadata, or ``None``.

        Raises:
            StorageError: If the request fails for another reason.
        """
        try:
            response = self._client.head_object(Bucket=self.bucket, Key=key)
            return dict(response)
        except ClientError as exc:
            if _is_missing(exc):
                return None
            raise StorageError(f"failed to stat s3://{self.bucket}/{key}: {exc}") from exc
        except BotoCoreError as exc:
            raise StorageError(f"failed to stat s3://{self.bucket}/{key}: {exc}") from exc

    def upload_file(
        self,
        path: Path,
        key: str,
        *,
        content_type: str | None = None,
        cache_control: str | None = None,
    ) -> None:
        """Upload a local file to an object key.

        Args:
            path: Local file path.
            key: Destination object key.
            content_type: Optional HTTP content type.
            cache_control: Optional HTTP cache control header.

        Raises:
            StorageError: If the upload fails.
        """
        extra: dict[str, str] = {}
        if content_type:
            extra["ContentType"] = content_type
        if cache_control:
            extra["CacheControl"] = cache_control
        try:
            self._client.upload_file(
                str(path),
                self.bucket,
                key,
                ExtraArgs=extra or None,
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"failed to upload {path} to {key}: {exc}") from exc

    def download_file(self, key: str, path: Path) -> None:
        """Download an object key to a local file.

        Args:
            key: Source object key.
            path: Local destination path.

        Raises:
            StorageError: If the download fails.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._client.download_file(self.bucket, key, str(path))
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"failed to download {key} to {path}: {exc}") from exc

    def delete_keys(self, keys: Sequence[str]) -> int:
        """Delete object keys in batches.

        Args:
            keys: Object keys to delete.

        Returns:
            The number of keys submitted for deletion.

        Raises:
            StorageError: If any delete request fails.
        """
        unique_keys = sorted(set(keys))
        deleted = 0
        for start in range(0, len(unique_keys), DELETE_BATCH_SIZE):
            batch = unique_keys[start : start + DELETE_BATCH_SIZE]
            try:
                response = self._client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
                )
            except (BotoCoreError, ClientError) as exc:
                raise StorageError(f"failed to delete objects: {exc}") from exc

            errors = response.get("Errors") or []
            if errors:
                details = ", ".join(
                    f"{error.get('Key')}: {error.get('Message')}" for error in errors
                )
                raise StorageError(f"failed to delete objects: {details}")
            deleted += len(batch)
        return deleted

    def list_keys(self, prefix: str = "") -> list[str]:
        """List object keys under a prefix.

        Args:
            prefix: Key prefix to list.

        Returns:
            Object keys in lexicographic order as returned by S3.

        Raises:
            StorageError: If listing fails.
        """
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        try:
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for item in page.get("Contents") or []:
                    keys.append(item["Key"])
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"failed to list s3://{self.bucket}/{prefix}: {exc}") from exc
        return keys

    def credentials_env(self) -> dict[str, str]:
        """Return resolved credentials in rattler-index environment variable form.

        Returns:
            A mapping of ``S3_*`` environment variables. The mapping is empty when
            no credentials are configured, which allows anonymous access.
        """
        credentials = self.session.get_credentials()
        if credentials is None:
            return {}
        frozen = credentials.get_frozen_credentials()
        if frozen.access_key is None or frozen.secret_key is None:
            raise StorageError("resolved S3 credentials are incomplete")
        env = {
            "S3_ACCESS_KEY_ID": frozen.access_key,
            "S3_SECRET_ACCESS_KEY": frozen.secret_key,
        }
        if frozen.token:
            env["S3_SESSION_TOKEN"] = frozen.token
        return env


def _is_missing(exc: ClientError) -> bool:
    """Return whether a boto3 error represents a missing object.

    Args:
        exc: boto3 client error.

    Returns:
        ``True`` when the error code indicates a missing object.
    """
    code = str(exc.response.get("Error", {}).get("Code", ""))
    return code in MISSING_CODES
