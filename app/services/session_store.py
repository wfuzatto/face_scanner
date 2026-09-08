import secrets
import threading
import time
from dataclasses import dataclass

@dataclass
class VerificationSession:
    id: str
    created_at: float
    expires_at: float
    reservation_id: str | None
    name_status: str

class SessionStore:
    def __init__(self, ttl_seconds: int = 600):
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, VerificationSession] = {}
        self._lock = threading.Lock()
    def _purge(self) -> None:
        now = time.time()
        expired = [key for key, value in self._items.items() if value.expires_at <= now]
        for key in expired:
            self._items.pop(key, None)
    def create(self, reservation_id: str | None, name_status: str) -> VerificationSession:
        now = time.time()
        item = VerificationSession(id=secrets.token_urlsafe(24), created_at=now, expires_at=now + self.ttl_seconds, reservation_id=reservation_id, name_status=name_status)
        with self._lock:
            self._purge()
            self._items[item.id] = item
        return item
    def consume(self, session_id: str) -> VerificationSession | None:
        with self._lock:
            self._purge()
            return self._items.pop(session_id, None)
    def count(self) -> int:
        with self._lock:
            self._purge()
            return len(self._items)
