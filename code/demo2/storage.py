"""Own local conversation retention, durable request results and consistent backups."""
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
import time
import fcntl
from uuid import uuid4

import settings as cfg

DATABASES = ("conversations.sqlite", "tickets.sqlite", "rag_cache.sqlite", "sessions.sqlite")


@contextmanager
def connection(path):
    """Bound essential store contention and close handles on every failure path."""
    conn = sqlite3.connect(path, timeout=.25)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        with conn:
            yield conn
    finally:
        conn.close()


def tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


class Store:
    """Keep session ownership independent of self-reported student identity."""

    def __init__(self, root=None, retention=None, clock=time.time):
        self.root = Path(root or cfg.DATA_ROOT)
        self.retention = retention if retention is not None else cfg.RETENTION_SECONDS
        self.clock = clock
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "sessions.sqlite"
        with connection(self.path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, created REAL NOT NULL, expires REAL NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS requests(session_id TEXT NOT NULL, turn_id TEXT NOT NULL, fingerprint TEXT NOT NULL, result TEXT, PRIMARY KEY(session_id,turn_id));
                CREATE TABLE IF NOT EXISTS storage_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS deletions(id TEXT PRIMARY KEY, deleted_at REAL NOT NULL);
            """)
            conn.execute("INSERT OR IGNORE INTO storage_meta VALUES ('legacy_grace_until',?)", (str(self.clock() + self.retention),))

    def register(self, session_id):
        """Give newly encountered conversations a fixed, disclosed retention lifetime."""
        with connection(self.path) as conn:
            if conn.execute("SELECT 1 FROM deletions WHERE id=?", (session_id,)).fetchone():
                raise ValueError("conversation_deleted")
            conn.execute("INSERT OR IGNORE INTO sessions VALUES (?,?,?,0)",
                         (session_id, self.clock(), self.clock() + self.retention))
            row = conn.execute("SELECT expires,deleted FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row[1] or row[0] <= self.clock():
                raise ValueError("conversation_expired")

    def session_ids(self):
        with connection(self.path) as conn:
            return {r[0] for r in conn.execute("SELECT id FROM sessions WHERE deleted=0 AND expires>?",(self.clock(),))}

    def acquire_runtime(self):
        """Ensure one app or offline maintenance owner spans all four SQLite stores."""
        handle=(self.root/'runtime.lock').open('a')
        try:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            raise ValueError('storage_in_use') from None
        return handle

    def request(self, session_id, turn_id, payload):
        """Reserve a request identity; only exactly matching submissions may reuse it."""
        self.register(session_id)
        fingerprint = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        with connection(self.path) as conn:
            conn.execute("INSERT OR IGNORE INTO requests VALUES (?,?,?,NULL)", (session_id, turn_id, fingerprint))
            row = conn.execute("SELECT fingerprint,result FROM requests WHERE session_id=? AND turn_id=?", (session_id, turn_id)).fetchone()
            if row[0] != fingerprint:
                raise ValueError("request_conflict")
            return json.loads(row[1]) if row[1] else None

    def complete(self, session_id, turn_id, result):
        """Persist reviewed text only; raw recordings and generated audio remain transient."""
        with connection(self.path) as conn:
            alive = conn.execute("SELECT 1 FROM sessions WHERE id=? AND deleted=0 AND expires>?", (session_id,self.clock())).fetchone()
            if not alive:
                return
            safe = {k: v for k, v in result.items() if k not in {"audio", "audio_data"}}
            conn.execute("UPDATE requests SET result=? WHERE session_id=? AND turn_id=?",
                         (json.dumps(safe, ensure_ascii=False), session_id, turn_id))

    def _erase_rows(self, session_id):
        """Repeatable deletion tolerates an interrupted cleanup across separate stores."""
        for name in DATABASES[:3]:
            path = self.root / name
            if not path.exists():
                continue
            with connection(path) as conn:
                available = tables(conn)
                for table in ("checkpoints", "writes"):
                    if table in available:
                        conn.execute(f"DELETE FROM {table} WHERE thread_id=?", (session_id,))
                if "action_requests" in available:
                    for kind, table in (("ticket", "tickets"), ("reminder", "reminders")):
                        if table in available:
                            conn.execute(f"DELETE FROM {table} WHERE id IN (SELECT action_id FROM action_requests WHERE conversation_id=? AND kind=?)", (session_id,kind))
                    conn.execute("DELETE FROM action_requests WHERE conversation_id=?", (session_id,))
                if "cache_owners" in available:
                    conn.execute("DELETE FROM rag_cache WHERE key IN (SELECT key FROM cache_owners WHERE conversation_id=?)", (session_id,))
                    conn.execute("DELETE FROM cache_owners WHERE conversation_id=?", (session_id,))
        with connection(self.path) as conn:
            conn.execute("DELETE FROM requests WHERE session_id=?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))

    def delete(self, session_id):
        """Persist a tombstone before cleanup so managed restores cannot resurrect data."""
        with connection(self.path) as conn:
            conn.execute("INSERT OR REPLACE INTO deletions VALUES (?,?)", (session_id, self.clock()))
            conn.execute("UPDATE sessions SET deleted=1 WHERE id=?", (session_id,))
        # Existing managed backups may contain this conversation: remove those bundles.
        self._expire_backups(all_backups=True)
        self._erase_rows(session_id)

    def compact(self, session_id):
        """Keep the newest two complete checkpoints only after a successful idle turn."""
        path = self.root / "conversations.sqlite"
        if not path.exists():
            return
        with connection(path) as conn:
            if not {"checkpoints", "writes"}.issubset(tables(conn)):
                return
            old = [r[0] for r in conn.execute("SELECT checkpoint_id FROM checkpoints WHERE thread_id=? ORDER BY checkpoint_id DESC LIMIT -1 OFFSET 2", (session_id,))]
            conn.executemany("DELETE FROM writes WHERE thread_id=? AND checkpoint_id=?", [(session_id, key) for key in old])
            conn.executemany("DELETE FROM checkpoints WHERE thread_id=? AND checkpoint_id=?", [(session_id, key) for key in old])

    def _expire_backups(self, all_backups=False):
        root = self.root / "backups"
        if root.exists():
            for folder in root.iterdir():
                manifest = folder / "backup.json"
                if folder.is_dir() and manifest.is_file():
                    if all_backups or json.loads(manifest.read_text())["expires"] <= self.clock():
                        shutil.rmtree(folder)

    def maintain(self, active=()):
        """Sweep inactive expired sessions; defer active jobs rather than racing writes."""
        with connection(self.path) as conn:
            expired = [r[0] for r in conn.execute("SELECT id FROM sessions WHERE expires<=? OR deleted=1", (self.clock(),)) if r[0] not in active]
            retries = [r[0] for r in conn.execute("SELECT id FROM deletions") if r[0] not in active]
            grace = float(conn.execute("SELECT value FROM storage_meta WHERE key='legacy_grace_until'").fetchone()[0])
            known = {r[0] for r in conn.execute("SELECT id FROM sessions")}
        for session_id in expired:
            self.delete(session_id)
        for session_id in set(retries) - set(expired):
            self._erase_rows(session_id)
        if self.clock() >= grace:
            # Legacy conversations have no ownership mapping: expire them after migration grace.
            path = self.root / "conversations.sqlite"
            if path.exists():
                with connection(path) as conn:
                    orphaned = [r[0] for r in conn.execute("SELECT DISTINCT thread_id FROM checkpoints")] if "checkpoints" in tables(conn) else []
                for session_id in set(orphaned) - known - set(active):
                    self.delete(session_id)
            path = self.root / "tickets.sqlite"
            if path.exists():
                with connection(path) as conn:
                    available = tables(conn)
                    for kind, table, column in (("ticket","tickets","timestamp"),("reminder","reminders","created_at")):
                        if table in available:
                            clause = " AND id NOT IN (SELECT action_id FROM action_requests WHERE kind=?)" if "action_requests" in available else ""
                            conn.execute(f"DELETE FROM {table} WHERE julianday({column}) < julianday(?,'unixepoch'){clause}",
                                         (self.clock()-self.retention,kind) if clause else (self.clock()-self.retention,))
        path = self.root / "rag_cache.sqlite"
        if path.exists():
            with connection(path) as conn:
                if "rag_cache" in tables(conn):
                    conn.execute("DELETE FROM rag_cache WHERE expires<=?", (self.clock(),))
        self._expire_backups()
        # Tombstones outlive every valid managed backup, then cease being identifiers.
        with connection(self.path) as conn:
            conn.execute("DELETE FROM deletions WHERE deleted_at<?", (self.clock()-self.retention,))
        return {"expired_sessions": len(expired)}

    def backup(self):
        """Call under the job-manager gate while idle for a consistent multi-store snapshot."""
        folder = self.root / "backups" / str(uuid4())
        folder.mkdir(parents=True)
        manifest = {"created": self.clock(), "expires": self.clock()+self.retention, "sha256": {}}
        for name in DATABASES:
            source = self.root / name
            if source.exists():
                with connection(source) as src, connection(folder / name) as dst:
                    src.backup(dst)
                manifest["sha256"][name] = sha256((folder/name).read_bytes()).hexdigest()
        (folder / "backup.json").write_text(json.dumps(manifest, indent=2))
        return folder

    def restore_into(self, backup, destination):
        """Validate into an empty recovery directory, never overwrite running databases."""
        backup, destination = Path(backup), Path(destination)
        manifest = json.loads((backup / "backup.json").read_text())
        if manifest["expires"] <= self.clock() or (destination.exists() and any(destination.iterdir())):
            raise ValueError("Backup expired or restore destination is not empty")
        for name, expected in manifest["sha256"].items():
            if name not in DATABASES or sha256((backup/name).read_bytes()).hexdigest() != expected:
                raise ValueError("backup_integrity_error")
            with connection(backup/name) as conn:
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("backup_integrity_error")
        destination.mkdir(parents=True, exist_ok=True)
        for name in manifest["sha256"]:
            shutil.copy2(backup/name, destination/name)
        restored = Store(destination, self.retention, self.clock)
        with connection(self.path) as conn:
            deleted = [r[0] for r in conn.execute("SELECT id FROM deletions")]
        for session_id in deleted:
            restored.delete(session_id)
        restored.maintain()
        return restored
