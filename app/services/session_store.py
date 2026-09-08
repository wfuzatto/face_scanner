import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VerificationSession:
    id: str
    created_at: float
    expires_at: float
    reservation_id: str | None
    name_status: str


class SessionStore:
    """Armazena apenas metadados temporários da verificação.

    Nenhuma imagem, documento ou embedding biométrico é persistido aqui.
    SQLite permite que uma sessão curta sobreviva a restart do container sem
    adicionar Redis/MySQL ao caminho crítico desta primeira versão.
    """

    def __init__(self, ttl_seconds: int = 600, db_path: str | Path = ":memory:"):
        self.ttl_seconds = ttl_seconds
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._db = sqlite3.connect(
            self.db_path,
            timeout=5.0,
            check_same_thread=False,
            isolation_level=None,
        )
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.execute("PRAGMA foreign_keys=ON")
        if self.db_path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_sessions (
                id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                reservation_id TEXT,
                name_status TEXT NOT NULL
            )
            """
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_verification_sessions_expires_at "
            "ON verification_sessions(expires_at)"
        )

    def _purge_locked(self, now: float | None = None) -> None:
        self._db.execute(
            "DELETE FROM verification_sessions WHERE expires_at <= ?",
            (now if now is not None else time.time(),),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> VerificationSession:
        return VerificationSession(
            id=row["id"],
            created_at=float(row["created_at"]),
            expires_at=float(row["expires_at"]),
            reservation_id=row["reservation_id"],
            name_status=row["name_status"],
        )

    def create(self, reservation_id: str | None, name_status: str) -> VerificationSession:
        now = time.time()
        item = VerificationSession(
            id=secrets.token_urlsafe(24),
            created_at=now,
            expires_at=now + self.ttl_seconds,
            reservation_id=reservation_id,
            name_status=name_status,
        )
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._purge_locked(now)
                self._db.execute(
                    """
                    INSERT INTO verification_sessions
                        (id, created_at, expires_at, reservation_id, name_status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        item.id,
                        item.created_at,
                        item.expires_at,
                        item.reservation_id,
                        item.name_status,
                    ),
                )
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise
        return item

    def consume(self, session_id: str) -> VerificationSession | None:
        """Consome a sessão atomicamente; uma sessão nunca pode ser usada duas vezes."""
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                now = time.time()
                self._purge_locked(now)
                row = self._db.execute(
                    "SELECT id, created_at, expires_at, reservation_id, name_status "
                    "FROM verification_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                if row is None:
                    self._db.execute("COMMIT")
                    return None
                self._db.execute(
                    "DELETE FROM verification_sessions WHERE id = ?", (session_id,)
                )
                self._db.execute("COMMIT")
                return self._from_row(row)
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def count(self) -> int:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._purge_locked()
                row = self._db.execute(
                    "SELECT COUNT(*) AS total FROM verification_sessions"
                ).fetchone()
                self._db.execute("COMMIT")
                return int(row["total"])
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def close(self) -> None:
        with self._lock:
            self._db.close()
