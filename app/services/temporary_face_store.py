from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class _Entry:
    expires_at: float
    value: Any


class TemporaryFaceStore:
    """Thread-safe, in-memory, TTL and single-use store; no persistence or logs."""

    def __init__(self, ttl_seconds: int = 600, clock: Callable[[], float] = time.time) -> None:
        self.ttl_seconds = max(1, int(ttl_seconds))
        self._clock, self._items, self._lock = clock, {}, threading.RLock()

    def _purge_locked(self) -> None:
        now = self._clock()
        for key, entry in list(self._items.items()):
            if entry.expires_at <= now:
                del self._items[key]

    def put(self, verification_id: str, face: Any) -> None:
        with self._lock:
            self._purge_locked()
            self._items[verification_id] = _Entry(self._clock() + self.ttl_seconds, face)

    def purge_expired(self) -> None:
        with self._lock:
            self._purge_locked()

    def get(self, verification_id: str) -> Any | None:
        with self._lock:
            self._purge_locked()
            entry = self._items.get(verification_id)
            return None if entry is None else entry.value

    def consume(self, verification_id: str) -> Any | None:
        with self._lock:
            self._purge_locked()
            entry = self._items.pop(verification_id, None)
            return None if entry is None else entry.value
