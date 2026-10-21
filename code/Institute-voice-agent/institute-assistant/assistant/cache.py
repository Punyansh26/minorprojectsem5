"""Persist disposable RAG results without making cache availability a dependency."""
import hashlib
import json
import logging
import sqlite3
import time
from contextlib import closing, contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)
CACHE_VERSION = 2


def cache_key(kind: str, inputs: dict) -> str:
    """Hash complete effective inputs; never persist raw conversational cache keys."""
    value = json.dumps([CACHE_VERSION, kind, inputs], ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(value.encode()).hexdigest()


class RagCache:
    """Use short SQLite transactions and LFU eviction across retrieval and draft entries."""

    def __init__(self, settings, clock=time.time):
        self.settings, self.clock = settings, clock
        self._counters = {"hit": 0, "miss": 0, "bypass": 0, "put": 0, "evict": 0, "error": 0}

    @contextmanager
    def _connection(self):
        path = Path(self.settings.RAG_CACHE_DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path, timeout=self.settings.RAG_CACHE_TIMEOUT_SECONDS)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            with conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS rag_cache (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL, expires REAL NOT NULL,
                    hits INTEGER NOT NULL, accessed REAL NOT NULL)""")
                conn.execute("CREATE INDEX IF NOT EXISTS rag_cache_expiry ON rag_cache(expires)")
                conn.execute("""CREATE TABLE IF NOT EXISTS cache_owners (
                    key TEXT NOT NULL REFERENCES rag_cache(key) ON DELETE CASCADE,
                    conversation_id TEXT NOT NULL, PRIMARY KEY(key,conversation_id))""")
                yield conn

    @staticmethod
    def _own(conn, key):
        from assistant.operations import current
        operation = current()
        if operation:
            conn.execute("INSERT OR IGNORE INTO cache_owners VALUES (?,?)", (key, operation.conversation_id))

    def get(self, key: str):
        """Treat unavailable, expired or malformed cached JSON as a normal miss."""
        if not self.settings.RAG_CACHE_ENABLED:
            self._counters["bypass"] += 1
            return None
        try:
            with self._connection() as conn:
                now = self.clock()
                conn.execute("DELETE FROM rag_cache WHERE expires <= ?", (now,))
                row = conn.execute("SELECT value FROM rag_cache WHERE key = ?", (key,)).fetchone()
                if row is None:
                    self._counters["miss"] += 1
                    return None
                if not isinstance(row[0], str) or len(row[0].encode()) > self.settings.RAG_CACHE_MAX_ENTRY_BYTES:
                    conn.execute("DELETE FROM rag_cache WHERE key = ?", (key,))
                    return None
                try:
                    value = json.loads(row[0])
                except (ValueError, TypeError):
                    conn.execute("DELETE FROM rag_cache WHERE key = ?", (key,))
                    return None
                conn.execute("UPDATE rag_cache SET hits = hits + 1, accessed = ? WHERE key = ?", (now, key))
                self._own(conn, key)
                self._counters["hit"] += 1
                return value
        except (sqlite3.Error, OSError, ValueError, TypeError) as error:
            logger.warning("cache read failed (%s)", type(error).__name__)
            self._counters["error"] += 1
            return None

    def put(self, key: str, value) -> None:
        """Bound storage, preserving frequent entries and expiry from initial insertion."""
        if not self.settings.RAG_CACHE_ENABLED:
            return
        try:
            data = json.dumps(value, ensure_ascii=False, allow_nan=False)
            if len(data.encode()) > self.settings.RAG_CACHE_MAX_ENTRY_BYTES:
                return
            with self._connection() as conn:
                now = self.clock()
                conn.execute("DELETE FROM rag_cache WHERE expires <= ?", (now,))
                exists = conn.execute("SELECT 1 FROM rag_cache WHERE key = ?", (key,)).fetchone()
                if exists:
                    conn.execute("UPDATE rag_cache SET value = ? WHERE key = ?", (data, key))
                else:
                    conn.execute("INSERT INTO rag_cache VALUES (?, ?, ?, 0, ?)",
                             (key, data, now + self.settings.RAG_CACHE_TTL_SECONDS, now))
                self._own(conn, key)
                self._counters["put"] += 1
                rows = conn.execute("SELECT key,LENGTH(CAST(value AS BLOB)) FROM rag_cache ORDER BY hits,accessed,key").fetchall()
                total, count = sum(r[1] for r in rows), len(rows)
                for old, size in rows:
                    if count <= self.settings.RAG_CACHE_MAX_ENTRIES and total <= getattr(self.settings, "RAG_CACHE_MAX_BYTES", 67108864):
                        break
                    conn.execute("DELETE FROM rag_cache WHERE key=?", (old,))
                    self._counters["evict"] += 1
                    total, count = total - size, count - 1
        except (sqlite3.Error, OSError, ValueError, TypeError) as error:
            logger.warning("cache write failed (%s)", type(error).__name__)
            self._counters["error"] += 1

    def delete(self, key: str) -> None:
        """Discard an entry that no longer passes schema or grounding checks."""
        if not self.settings.RAG_CACHE_ENABLED:
            return
        try:
            with self._connection() as conn:
                conn.execute("DELETE FROM rag_cache WHERE key = ?", (key,))
        except (sqlite3.Error, OSError) as error:
            logger.warning("cache delete failed (%s)", type(error).__name__)
            self._counters["error"] += 1

    def telemetry(self) -> dict:
        hits = self._counters["hit"]
        misses = self._counters["miss"]
        total = hits + misses
        hit_rate = round(hits / total, 4) if total > 0 else 0.0
        return {**self._counters, "hit_rate": hit_rate, "total_requests": total}

    def maintain(self) -> dict:
        """Expire unused entries independently of cache hits and expose storage-only metrics."""
        try:
            with self._connection() as conn:
                conn.execute("DELETE FROM rag_cache WHERE expires <= ?", (self.clock(),))
                row = conn.execute("SELECT COUNT(*),COALESCE(SUM(LENGTH(CAST(value AS BLOB))),0),COALESCE(SUM(hits),0) FROM rag_cache").fetchone()
                stats = dict(entries=row[0], payload_bytes=row[1], hits=row[2])
                stats["telemetry"] = self.telemetry()
                return stats
        except (sqlite3.Error, OSError):
            return {"error_code": "cache_unavailable", "telemetry": self.telemetry()}
