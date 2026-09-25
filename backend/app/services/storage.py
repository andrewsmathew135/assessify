"""File storage abstraction.

Two interchangeable backends implement the same interface:

* ``LocalStorage`` writes to disk (default for development / tests).
* ``R2Storage`` talks to Cloudflare R2 via its S3-compatible API (boto3).

Switching is controlled by ``STORAGE_BACKEND`` in the environment.
"""
from __future__ import annotations

import os
import shutil
import uuid
from abc import ABC, abstractmethod
from functools import lru_cache

from app.config import get_settings
from app.core.errors import NotFoundError, StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)


def make_object_key(prefix: str, filename: str) -> str:
    """Build a collision-resistant, path-safe object key."""
    safe_name = os.path.basename(filename).replace("\\", "_").replace("/", "_")
    return f"{prefix.strip('/')}/{uuid.uuid4().hex}_{safe_name}"


class Storage(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str | None = None) -> str: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...


class LocalStorage(Storage):
    """Disk-backed storage used for local development and tests."""

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        # Prevent path traversal: the resolved path must stay under base_dir.
        full = os.path.abspath(os.path.join(self.base_dir, key))
        if os.path.commonpath([full, self.base_dir]) != self.base_dir:
            raise StorageError("Invalid storage key.")
        return full

    def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        return key

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not os.path.exists(path):
            raise NotFoundError("File not found in storage.")
        with open(path, "rb") as fh:
            return fh.read()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.exists(path):
            os.remove(path)

    def exists(self, key: str) -> bool:
        return os.path.exists(self._path(key))


class R2Storage(Storage):
    """Cloudflare R2 storage via the S3-compatible API."""

    def __init__(self):
        import boto3  # imported lazily so local dev needs no AWS deps loaded
        from botocore.config import Config

        settings = get_settings()
        if not settings.r2_endpoint_url:
            raise StorageError("R2 endpoint URL is not configured.")
        self.bucket = settings.r2_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name=settings.r2_region,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        try:
            extra = {"ContentType": content_type} if content_type else {}
            self._client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)
            return key
        except Exception as exc:  # noqa: BLE001 - convert to clean domain error
            logger.error("R2 put failed: %s", exc)
            raise StorageError("Failed to store file.") from exc

    def get(self, key: str) -> bytes:
        from botocore.exceptions import ClientError

        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404"):
                raise NotFoundError("File not found in storage.") from exc
            logger.error("R2 get failed: %s", exc)
            raise StorageError("Failed to read file.") from exc

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001
            logger.error("R2 delete failed: %s", exc)
            raise StorageError("Failed to delete file.") from exc

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "r2" and settings.r2_endpoint_url:
        logger.info("Using R2 storage backend")
        return R2Storage()
    logger.info("Using local storage backend at %s", settings.local_storage_dir)
    return LocalStorage(settings.local_storage_dir)
