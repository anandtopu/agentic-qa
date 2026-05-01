"""Dead-letter queue — Epic 4.3.

A failed agent task is captured here so the alert pipeline (Epic
4.2) can fire a ``dlq_depth`` alert when the queue accumulates. The
in-memory impl is the test/dev default; a Redis / SQS impl drops in
by satisfying the :class:`DeadLetterQueue` Protocol.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclass(slots=True, frozen=True)
class DeadLetter:
    """One failed task held in the DLQ."""

    task_id: str
    workspace_id: str
    queued_at: datetime
    error_message: str
    payload: dict[str, Any] = field(default_factory=dict)
    attempts: int = 1


class DeadLetterQueue(Protocol):
    """Append + drain + count surface."""

    def append(self, letter: DeadLetter) -> None: ...
    def depth(self) -> int: ...
    def drain(self, limit: int = 100) -> list[DeadLetter]: ...


@dataclass(slots=True)
class InMemoryDeadLetterQueue:
    """Reference impl backed by a Python list. Thread-safe."""

    letters: list[DeadLetter] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, letter: DeadLetter) -> None:
        with self._lock:
            self.letters.append(letter)

    def depth(self) -> int:
        with self._lock:
            return len(self.letters)

    def drain(self, limit: int = 100) -> list[DeadLetter]:
        with self._lock:
            taken = self.letters[:limit]
            del self.letters[:limit]
            return taken

    def append_failure(
        self,
        *,
        task_id: str,
        workspace_id: str,
        error_message: str,
        payload: dict[str, Any] | None = None,
        attempts: int = 1,
    ) -> DeadLetter:
        letter = DeadLetter(
            task_id=task_id,
            workspace_id=workspace_id,
            queued_at=datetime.now(UTC),
            error_message=error_message,
            payload=payload or {},
            attempts=attempts,
        )
        self.append(letter)
        return letter

    # Test convenience.
    def snapshot(self) -> Iterable[DeadLetter]:
        with self._lock:
            return tuple(self.letters)


__all__ = ["DeadLetter", "DeadLetterQueue", "InMemoryDeadLetterQueue"]
