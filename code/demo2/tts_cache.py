"""Release-bound pre-synthesised audio cache (Task 07 A5).

Greetings, acknowledgements and verified frequently-repeated answers never change between
turns, yet re-synthesising them costs 2–4.5 s each on CPU VITS (``VALIDATION.md``). This
module turns that into a file read. It mirrors the SQLite + LFU pattern of
``institute-assistant/assistant/cache.py::RagCache`` and binds every entry to the knowledge
release and TTS model, exactly like the RAG/draft cache, so a KB-release or model change
makes old audio simply *not found* and regenerated — a stale answer can never be spoken
after a knowledge update.

Key = ``sha256(normalized_text | voice | speed | model_version | kb_release)``.

Audio bytes are stored base64-encoded in a TEXT column (SQLite-friendly, same table shape as
RagCache). Only approved audio should be written: the Hindi path writes ``prepare_speech``-
approved, verified-status text; fillers are pre-rendered at build time. Never cache
``insufficient``/``out-of-scope`` turns (enforced by the caller).
"""
import base64
import hashlib
import json
import logging
import sqlite3
import time
from contextlib import closing, contextmanager
from functools import lru_cache
from pathlib import Path

import settings as cfg

logger = logging.getLogger(__name__)
CACHE_VERSION = 1


@lru_cache(maxsize=4)
def active_kb_release() -> str:
    """Read the active KB release id cheaply, without loading models or verifying integrity.

    Falls back to ``"unknown"`` when no pointer is resolvable so caching degrades to a safe
    (always-miss-on-change) default rather than failing synthesis.
    """
    candidates = []
    kbb_active = cfg.KBB_ROOT / "data/kbb/serving/active.json"
    legacy_active = cfg.AGENT_ROOT / "kb_state/active.json"
    import os
    backend = os.getenv("DEMO2_KB_BACKEND", "kbb")
    # Prefer the backend demo2 actually serves; fall back to whichever pointer exists.
    if backend == "legacy":
        candidates = [legacy_active, kbb_active]
    else:
        candidates = [kbb_active, legacy_active]
    for pointer in candidates:
        try:
            if pointer.is_file():
                data = json.loads(pointer.read_text())
                release = data.get("release")
                if release:
                    return str(release)
        except (OSError, ValueError, TypeError):
            continue
    return "unknown"


@lru_cache(maxsize=1)
def model_version() -> str:
    """Identify the TTS model generation so a checkpoint or package change invalidates audio.

    Combines the installed Coqui ``TTS`` package version with a hash of each voice's
    ``config.json`` (architecture, sample rate, character set). Checkpoint weights are not
    hashed for cost; config + package version change on any intended model swap, and the
    key also includes the KB release, so this is a conservative-enough identity for Phase 0.
    """
    try:
        import importlib.metadata
        package = importlib.metadata.version("TTS")
    except Exception:
        package = "unknown"
    digest = hashlib.sha256()
    digest.update(package.encode())
    for voice in cfg.VOICES:
        config = cfg.TTS_ROOT / voice / "config.json"
        try:
            digest.update(config.read_bytes())
        except OSError:
            digest.update(b"missing")
    return f"vits-{package}-{digest.hexdigest()[:12]}"


def cache_key(normalized_text: str, voice: str, speed: float, language: str = "hindi") -> str:
    """Hash the complete effective inputs; release and model version bind the entry."""
    payload = json.dumps(
        [CACHE_VERSION, language, normalized_text, voice, round(float(speed), 3),
         model_version(), active_kb_release()],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


class AudioCache:
    """Short SQLite transactions and LFU eviction over rendered-audio entries."""

    def __init__(self, settings=cfg, clock=time.time):
        self.settings, self.clock = settings, clock
        self._counters = {"hit": 0, "miss": 0, "bypass": 0, "put": 0, "evict": 0, "error": 0}

    @contextmanager
    def _connection(self):
        path = Path(self.settings.TTS_CACHE_DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path, timeout=self.settings.TTS_CACHE_TIMEOUT_SECONDS)) as conn:
            with conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS tts_cache (
                    key TEXT PRIMARY KEY, audio TEXT NOT NULL, mime TEXT NOT NULL,
                    extension TEXT NOT NULL, spoken_text TEXT NOT NULL, provider TEXT NOT NULL,
                    expires REAL NOT NULL, hits INTEGER NOT NULL, accessed REAL NOT NULL)""")
                conn.execute("CREATE INDEX IF NOT EXISTS tts_cache_expiry ON tts_cache(expires)")
                yield conn

    def get(self, key: str):
        """Return the cached audio payload dict on hit, else None. Errors are normal misses."""
        if not self.settings.TTS_CACHE_ENABLED:
            self._counters["bypass"] += 1
            return None
        try:
            with self._connection() as conn:
                now = self.clock()
                conn.execute("DELETE FROM tts_cache WHERE expires <= ?", (now,))
                row = conn.execute(
                    "SELECT audio, mime, extension, spoken_text, provider FROM tts_cache WHERE key = ?",
                    (key,)).fetchone()
                if row is None:
                    self._counters["miss"] += 1
                    return None
                try:
                    data = base64.b64decode(row[0].encode())
                except (ValueError, TypeError):
                    conn.execute("DELETE FROM tts_cache WHERE key = ?", (key,))
                    self._counters["miss"] += 1
                    return None
                conn.execute("UPDATE tts_cache SET hits = hits + 1, accessed = ? WHERE key = ?", (now, key))
                self._counters["hit"] += 1
                return {"data": data, "mime": row[1], "extension": row[2],
                        "spoken_text": row[3], "provider": row[4], "cache_hit": True}
        except (sqlite3.Error, OSError, ValueError, TypeError) as error:
            logger.warning("tts cache read failed (%s)", type(error).__name__)
            self._counters["error"] += 1
            return None

    def put(self, key: str, payload: dict) -> None:
        """Store rendered audio, preserving frequent entries under byte and count bounds."""
        if not self.settings.TTS_CACHE_ENABLED:
            return
        try:
            data = payload["data"]
            if not isinstance(data, (bytes, bytearray)) or len(data) > self.settings.TTS_CACHE_MAX_ENTRY_BYTES:
                return
            encoded = base64.b64encode(bytes(data)).decode()
            with self._connection() as conn:
                now = self.clock()
                conn.execute("DELETE FROM tts_cache WHERE expires <= ?", (now,))
                exists = conn.execute("SELECT 1 FROM tts_cache WHERE key = ?", (key,)).fetchone()
                if exists:
                    conn.execute("UPDATE tts_cache SET audio = ?, accessed = ? WHERE key = ?",
                                 (encoded, now, key))
                else:
                    conn.execute("INSERT INTO tts_cache VALUES (?,?,?,?,?,?,?,0,?)",
                                 (key, encoded, payload.get("mime", "audio/wav"),
                                  payload.get("extension", "wav"), payload.get("spoken_text", ""),
                                  payload.get("provider", "Local VITS"),
                                  now + self.settings.TTS_CACHE_TTL_SECONDS, now))
                self._counters["put"] += 1
                rows = conn.execute(
                    "SELECT key, LENGTH(CAST(audio AS BLOB)) FROM tts_cache ORDER BY hits, accessed, key"
                ).fetchall()
                total, count = sum(r[1] for r in rows), len(rows)
                for old, size in rows:
                    if count <= self.settings.TTS_CACHE_MAX_ENTRIES and total <= self.settings.TTS_CACHE_MAX_BYTES:
                        break
                    conn.execute("DELETE FROM tts_cache WHERE key = ?", (old,))
                    self._counters["evict"] += 1
                    total, count = total - size, count - 1
        except (sqlite3.Error, OSError, ValueError, TypeError, KeyError) as error:
            logger.warning("tts cache write failed (%s)", type(error).__name__)
            self._counters["error"] += 1

    def delete(self, key: str) -> None:
        if not self.settings.TTS_CACHE_ENABLED:
            return
        try:
            with self._connection() as conn:
                conn.execute("DELETE FROM tts_cache WHERE key = ?", (key,))
        except (sqlite3.Error, OSError) as error:
            logger.warning("tts cache delete failed (%s)", type(error).__name__)
            self._counters["error"] += 1

    def telemetry(self) -> dict:
        hits, misses = self._counters["hit"], self._counters["miss"]
        total = hits + misses
        return {**self._counters, "hit_rate": round(hits / total, 4) if total else 0.0,
                "total_requests": total}


_CACHE = AudioCache()


def get_cache() -> AudioCache:
    """Return the process-wide audio cache (one SQLite file under DATA_ROOT)."""
    return _CACHE
