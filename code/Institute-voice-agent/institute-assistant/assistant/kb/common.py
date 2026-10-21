"""Keep release metadata deterministic and publish manifests with atomic file replacement."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_VERSION = "2.3"


def digest(value: bytes | str) -> str:
    """Identify source bytes and processing inputs without using mutable filenames."""
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def now() -> str:
    """Record observation time separately from a document's publication date."""
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default=None):
    """Read optional manifests without masking malformed existing files."""
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path: Path, value) -> None:
    """Publish complete JSON or retain its previous version on interruption."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def active_release(state_dir: Path) -> tuple[Path, dict] | None:
    """Resolve a single release pointer for both vector and structured evidence."""
    pointer = read_json(state_dir / "active.json")
    if not pointer:
        return None
    root = (state_dir / "releases" / pointer["release"]).resolve()
    if root.parent != (state_dir / "releases").resolve():
        raise ValueError("Invalid release path")
    manifest = read_json(root / "release.json")
    if not manifest or manifest.get("status") != "complete":
        raise ValueError("Active knowledge release is incomplete")
    if pointer.get("manifest_sha256"):
        from assistant.kb.integrity import file_hash
        if file_hash(root/"release.json") != pointer["manifest_sha256"] or file_hash(root/"validation.json") != pointer["validation_sha256"]:
            raise ValueError("Active release identity changed")
    return root, manifest
