"""Evidence store implementations."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import UUID

DEFAULT_SIGNED_URL_TTL = timedelta(minutes=15)


class EvidenceStoreError(RuntimeError):
    """Base class for evidence-store failures."""


class HashMismatchError(EvidenceStoreError):
    """Caller declared a sha256 that doesn't match the body."""

    def __init__(self, declared: str, actual: str) -> None:
        super().__init__(f"sha256 mismatch: declared={declared} actual={actual}")
        self.declared = declared
        self.actual = actual


@dataclass(slots=True)
class EvidenceMetadata:
    sha256: str
    content_type: str
    size_bytes: int
    original_filename: str


@dataclass(slots=True)
class PutResult:
    storage_key: str
    metadata: EvidenceMetadata


@dataclass(slots=True)
class SignedFetchUrl:
    url: str
    expires_at: datetime


def _build_key(
    *, tenant_id: UUID, workspace_id: UUID, run_id: UUID, sha256: str, filename: str
) -> str:
    return f"t/{tenant_id}/w/{workspace_id}/r/{run_id}/{sha256}/{filename}"


def _compute_sha256(body: bytes) -> str:
    h = hashlib.sha256()
    h.update(body)
    return h.hexdigest()


def _verify_hash(body: bytes, declared_sha256: str | None) -> str:
    actual = _compute_sha256(body)
    if declared_sha256 is not None and declared_sha256.lower() != actual:
        raise HashMismatchError(declared=declared_sha256.lower(), actual=actual)
    return actual


class EvidenceStore(Protocol):
    async def put(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        run_id: UUID,
        body: bytes,
        content_type: str,
        original_filename: str,
        declared_sha256: str | None = None,
    ) -> PutResult: ...

    async def signed_url(
        self,
        *,
        storage_key: str,
        ttl: timedelta = DEFAULT_SIGNED_URL_TTL,
    ) -> SignedFetchUrl: ...

    async def get_bytes(self, *, storage_key: str) -> bytes: ...


class InMemoryEvidenceStore:
    """Test-only store backed by a dict."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, EvidenceMetadata]] = {}

    async def put(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        run_id: UUID,
        body: bytes,
        content_type: str,
        original_filename: str,
        declared_sha256: str | None = None,
    ) -> PutResult:
        sha = _verify_hash(body, declared_sha256)
        key = _build_key(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            run_id=run_id,
            sha256=sha,
            filename=original_filename,
        )
        metadata = EvidenceMetadata(
            sha256=sha,
            content_type=content_type,
            size_bytes=len(body),
            original_filename=original_filename,
        )
        existing = self._objects.get(key)
        if existing is not None and existing[1].sha256 != sha:
            # Should never happen: key contains sha. Belt-and-braces.
            raise EvidenceStoreError(f"key {key!r} already exists with different hash")
        self._objects[key] = (body, metadata)
        return PutResult(storage_key=key, metadata=metadata)

    async def signed_url(
        self,
        *,
        storage_key: str,
        ttl: timedelta = DEFAULT_SIGNED_URL_TTL,
    ) -> SignedFetchUrl:
        if storage_key not in self._objects:
            raise EvidenceStoreError(f"no object at {storage_key!r}")
        return SignedFetchUrl(
            url=f"memory://{storage_key}?expires={int(ttl.total_seconds())}",
            expires_at=datetime.now(UTC) + ttl,
        )

    async def get_bytes(self, *, storage_key: str) -> bytes:
        if storage_key not in self._objects:
            raise EvidenceStoreError(f"no object at {storage_key!r}")
        return self._objects[storage_key][0]

    def all_keys(self) -> list[str]:
        return list(self._objects.keys())


class FilesystemEvidenceStore:
    """Dev-loop store under a base directory.

    Used by ``make dev`` when MinIO is unavailable. Production uses an
    S3-backed implementation (Phase 3 hardening).
    """

    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir
        self._base.mkdir(parents=True, exist_ok=True)
        self._meta: dict[str, EvidenceMetadata] = {}

    async def put(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        run_id: UUID,
        body: bytes,
        content_type: str,
        original_filename: str,
        declared_sha256: str | None = None,
    ) -> PutResult:
        sha = _verify_hash(body, declared_sha256)
        key = _build_key(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            run_id=run_id,
            sha256=sha,
            filename=original_filename,
        )
        path = self._base / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        metadata = EvidenceMetadata(
            sha256=sha,
            content_type=content_type,
            size_bytes=len(body),
            original_filename=original_filename,
        )
        self._meta[key] = metadata
        return PutResult(storage_key=key, metadata=metadata)

    async def signed_url(
        self,
        *,
        storage_key: str,
        ttl: timedelta = DEFAULT_SIGNED_URL_TTL,
    ) -> SignedFetchUrl:
        path = self._base / storage_key
        if not path.is_file():
            raise EvidenceStoreError(f"no object at {storage_key!r}")
        return SignedFetchUrl(
            url=f"file://{path.resolve().as_posix()}",
            expires_at=datetime.now(UTC) + ttl,
        )

    async def get_bytes(self, *, storage_key: str) -> bytes:
        path = self._base / storage_key
        if not path.is_file():
            raise EvidenceStoreError(f"no object at {storage_key!r}")
        return path.read_bytes()


@dataclass(slots=True)
class StubSignedUrlConfig:
    """Used by tests to assert the URL TTL contract."""

    base_url: str = "https://signed.example"
    headers: Mapping[str, str] = field(default_factory=dict)
