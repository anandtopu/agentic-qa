"""Unit tests for the evidence store — Story 1.6.3."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from pathlib import Path

import pytest

from qaforge_api.evidence import (
    EvidenceStoreError,
    FilesystemEvidenceStore,
    HashMismatchError,
    InMemoryEvidenceStore,
)

TENANT = uuid.UUID("00000000-0000-0000-0000-00000000000a")
WS = uuid.UUID("00000000-0000-0000-0000-00000000000b")
RUN = uuid.UUID("00000000-0000-0000-0000-00000000000c")


def _put(store, body: bytes, *, declared_sha256: str | None = None, filename: str = "evidence.txt"):
    return asyncio.run(
        store.put(
            tenant_id=TENANT,
            workspace_id=WS,
            run_id=RUN,
            body=body,
            content_type="text/plain",
            original_filename=filename,
            declared_sha256=declared_sha256,
        )
    )


def test_in_memory_put_returns_content_addressed_key() -> None:
    store = InMemoryEvidenceStore()
    body = b"hello, evidence"
    expected_sha = hashlib.sha256(body).hexdigest()

    result = _put(store, body)

    assert result.metadata.sha256 == expected_sha
    assert result.metadata.size_bytes == len(body)
    assert expected_sha in result.storage_key
    assert "evidence.txt" in result.storage_key


def test_in_memory_signed_url_round_trip() -> None:
    store = InMemoryEvidenceStore()
    result = _put(store, b"hi")
    signed = asyncio.run(store.signed_url(storage_key=result.storage_key))
    assert "memory://" in signed.url


def test_in_memory_get_bytes_returns_original_body() -> None:
    store = InMemoryEvidenceStore()
    result = _put(store, b"original content")
    assert asyncio.run(store.get_bytes(storage_key=result.storage_key)) == b"original content"


def test_in_memory_signed_url_raises_for_unknown_key() -> None:
    store = InMemoryEvidenceStore()
    with pytest.raises(EvidenceStoreError, match="no object"):
        asyncio.run(store.signed_url(storage_key="bogus/key"))


def test_declared_sha_mismatch_rejected() -> None:
    store = InMemoryEvidenceStore()
    body = b"matters what's on the wire"
    wrong = "0" * 64
    with pytest.raises(HashMismatchError) as exc_info:
        _put(store, body, declared_sha256=wrong)
    assert exc_info.value.declared == wrong


def test_declared_sha_match_accepted() -> None:
    store = InMemoryEvidenceStore()
    body = b"abc"
    sha = hashlib.sha256(body).hexdigest()
    result = _put(store, body, declared_sha256=sha)
    assert result.metadata.sha256 == sha


def test_filesystem_store_persists_to_disk(tmp_path: Path) -> None:
    store = FilesystemEvidenceStore(tmp_path)
    body = b"on disk"
    result = _put(store, body)
    on_disk = tmp_path / result.storage_key
    assert on_disk.is_file()
    assert on_disk.read_bytes() == body


def test_filesystem_get_bytes_returns_body(tmp_path: Path) -> None:
    store = FilesystemEvidenceStore(tmp_path)
    result = _put(store, b"persisted")
    assert asyncio.run(store.get_bytes(storage_key=result.storage_key)) == b"persisted"


def test_filesystem_signed_url_points_at_file(tmp_path: Path) -> None:
    store = FilesystemEvidenceStore(tmp_path)
    result = _put(store, b"x")
    signed = asyncio.run(store.signed_url(storage_key=result.storage_key))
    assert signed.url.startswith("file://")


def test_filesystem_signed_url_raises_for_unknown_key(tmp_path: Path) -> None:
    store = FilesystemEvidenceStore(tmp_path)
    with pytest.raises(EvidenceStoreError):
        asyncio.run(store.signed_url(storage_key="missing/key"))
