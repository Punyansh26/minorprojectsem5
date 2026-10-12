"""Storage primitives: atomic files, a content-addressed KV cache, stage state, run lock.

Why SQLite instead of thousands of small cache files: at "hundreds of documents / thousands
of pages" the LLM, embedding and VLM caches reach 10^5 entries.  One WAL-mode SQLite file per
namespace gives O(log n) lookups, batched writes, safe concurrent readers, and trivial
backup — and avoids inode churn on the external drive this project lives on.
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import sqlite3
import tempfile
import threading
import time
import zlib
from pathlib import Path
from typing import Any, Iterable, Iterator

import orjson


# ---------------------------------------------------------------- atomic JSON / JSONL IO
def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def dumps(value: Any, *, indent: bool = False) -> bytes:
    opts = orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NON_STR_KEYS
    if indent:
        opts |= orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
    return orjson.dumps(value, option=opts)


def write_json(path: Path, value: Any, *, indent: bool = True) -> None:
    _atomic_write_bytes(path, dumps(value, indent=indent) + b"\n")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return orjson.loads(path.read_bytes())
    except FileNotFoundError:
        return default


def write_jsonl(path: Path, rows: Iterable[Any]) -> int:
    n = 0
    buf = bytearray()
    for row in rows:
        buf += dumps(row) + b"\n"
        n += 1
    _atomic_write_bytes(path, bytes(buf))
    return n


def read_jsonl(path: Path) -> Iterator[Any]:
    if not path.exists():
        return
    with path.open("rb") as fh:
        for line in fh:
            if line.strip():
                yield orjson.loads(line)


def write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


# ---------------------------------------------------------------- KV cache
class KVCache:
    """Content-addressed cache: ``key → bytes`` per namespace, zlib-compressed JSON values.

    Thread-safe (one connection per thread).  Writes are cheap; call ``flush`` rarely.
    """

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        with self._conn() as con:
            con.execute("CREATE TABLE IF NOT EXISTS kv (ns TEXT, k TEXT, v BLOB, t REAL, "
                        "PRIMARY KEY (ns, k)) WITHOUT ROWID")

    def _conn(self) -> sqlite3.Connection:
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(self.path, timeout=60, isolation_level=None,
                                  check_same_thread=False)
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=NORMAL")
            self._local.con = con
        return con

    def get(self, ns: str, key: str) -> Any | None:
        row = self._conn().execute("SELECT v FROM kv WHERE ns=? AND k=?", (ns, key)).fetchone()
        return orjson.loads(zlib.decompress(row[0])) if row else None

    def get_raw(self, ns: str, key: str) -> bytes | None:
        row = self._conn().execute("SELECT v FROM kv WHERE ns=? AND k=?", (ns, key)).fetchone()
        return row[0] if row else None

    def get_many_raw(self, ns: str, keys: list[str]) -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        con = self._conn()
        for i in range(0, len(keys), 900):           # SQLite variable limit
            chunk = keys[i:i + 900]
            q = f"SELECT k, v FROM kv WHERE ns=? AND k IN ({','.join('?' * len(chunk))})"
            out.update(dict(con.execute(q, (ns, *chunk)).fetchall()))
        return out

    def put(self, ns: str, key: str, value: Any) -> None:
        blob = zlib.compress(dumps(value), 3)
        self._conn().execute("INSERT OR REPLACE INTO kv VALUES (?,?,?,?)", (ns, key, blob, time.time()))

    def put_many_raw(self, ns: str, items: list[tuple[str, bytes]]) -> None:
        con = self._conn()
        now = time.time()
        con.execute("BEGIN")
        try:
            con.executemany("INSERT OR REPLACE INTO kv VALUES (?,?,?,?)",
                            [(ns, k, v, now) for k, v in items])
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

    def count(self, ns: str | None = None) -> int:
        q, args = ("SELECT COUNT(*) FROM kv WHERE ns=?", (ns,)) if ns else ("SELECT COUNT(*) FROM kv", ())
        return self._conn().execute(q, args).fetchone()[0]

    def purge(self, ns: str) -> int:
        return self._conn().execute("DELETE FROM kv WHERE ns=?", (ns,)).rowcount


# ---------------------------------------------------------------- stage state
class StageState:
    """Per-document stage bookkeeping → incremental, resumable runs.

    A stage is *fresh* when its recorded ``input_key`` equals the key computed now
    (upstream output hash + stage version + config fingerprint).  Anything else reruns.
    """

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        self.con = sqlite3.connect(path, timeout=60, isolation_level=None, check_same_thread=False)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("CREATE TABLE IF NOT EXISTS stage (doc_id TEXT, stage TEXT, input_key TEXT, "
                         "output_key TEXT, status TEXT, error TEXT, seconds REAL, updated REAL, "
                         "PRIMARY KEY (doc_id, stage))")

    def fresh(self, doc_id: str, stage: str, input_key: str) -> bool:
        row = self.con.execute("SELECT input_key, status FROM stage WHERE doc_id=? AND stage=?",
                               (doc_id, stage)).fetchone()
        return bool(row) and row[0] == input_key and row[1] == "ok"

    def output_key(self, doc_id: str, stage: str) -> str:
        row = self.con.execute("SELECT output_key FROM stage WHERE doc_id=? AND stage=?",
                               (doc_id, stage)).fetchone()
        return row[0] if row and row[0] else ""

    def record(self, doc_id: str, stage: str, input_key: str, output_key: str = "",
               status: str = "ok", error: str = "", seconds: float = 0.0) -> None:
        with self._lock:
            self.con.execute("INSERT OR REPLACE INTO stage VALUES (?,?,?,?,?,?,?,?)",
                             (doc_id, stage, input_key, output_key, status, error[:2000], seconds, time.time()))

    def summary(self) -> list[tuple]:
        return self.con.execute("SELECT stage, status, COUNT(*), ROUND(SUM(seconds),1) FROM stage "
                                "GROUP BY stage, status ORDER BY stage").fetchall()

    def errors(self) -> list[tuple]:
        return self.con.execute("SELECT doc_id, stage, error FROM stage WHERE status='error'").fetchall()


# ---------------------------------------------------------------- run lock
@contextlib.contextmanager
def run_lock(work: Path, name: str = "pipeline"):
    """Prevent two pipeline runs from writing the same work dir concurrently."""
    work.mkdir(parents=True, exist_ok=True)
    path = work / f".{name}.lock"
    fh = path.open("w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        fh.close()
        raise RuntimeError(f"Another KBB run holds {path}; wait for it or remove a stale lock.") from exc
    try:
        fh.write(str(os.getpid()))
        fh.flush()
        yield
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


class Stores:
    """Lazily opened shared stores for one work dir."""

    def __init__(self, work: Path):
        self.work = work
        self._cache: KVCache | None = None
        self._state: StageState | None = None

    @property
    def cache(self) -> KVCache:
        if self._cache is None:
            self._cache = KVCache(self.work / "cache" / "kv.sqlite")
        return self._cache

    @property
    def state(self) -> StageState:
        if self._state is None:
            self._state = StageState(self.work / "state.sqlite")
        return self._state
