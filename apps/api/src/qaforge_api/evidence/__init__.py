"""Evidence store — Story 1.6.3.

Content-addressed (SHA-256) write-once storage for run artifacts. Per
ADR-0005, evidence URLs are stable and tamper-evident: the storage key
is keyed off the hash, not a free-form filename, so any mutation
changes the address.

Phase 1 ships an in-memory store (tests) and a filesystem store (dev).
The S3 implementation is wired but tested only through stubs — Phase 3
hardens deployment + KMS.
"""

from qaforge_api.evidence.factory import (
    get_evidence_store,
    reset_evidence_store_cache,
)
from qaforge_api.evidence.store import (
    EvidenceMetadata,
    EvidenceStore,
    EvidenceStoreError,
    FilesystemEvidenceStore,
    HashMismatchError,
    InMemoryEvidenceStore,
    PutResult,
    SignedFetchUrl,
)

__all__ = [
    "EvidenceMetadata",
    "EvidenceStore",
    "EvidenceStoreError",
    "FilesystemEvidenceStore",
    "HashMismatchError",
    "InMemoryEvidenceStore",
    "PutResult",
    "SignedFetchUrl",
    "get_evidence_store",
    "reset_evidence_store_cache",
]
