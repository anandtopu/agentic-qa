"""Process-wide evidence-store singleton + reset helper.

Phase 1 dev loop uses :class:`InMemoryEvidenceStore`; tests inject their
own. Production deployments swap to a filesystem or S3-backed store
once the cloud Helm values are wired (Phase 3).
"""

from __future__ import annotations

from functools import lru_cache

from aqao_api.evidence.store import EvidenceStore, InMemoryEvidenceStore


@lru_cache(maxsize=1)
def get_evidence_store() -> EvidenceStore:
    return InMemoryEvidenceStore()


def reset_evidence_store_cache() -> None:
    get_evidence_store.cache_clear()
