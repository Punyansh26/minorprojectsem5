"""Bind logical evidence content and evaluation to immutable, portable releases."""
import hashlib
import json
import sqlite3
from pathlib import Path


def file_hash(path):
    """Hash artifacts in bounded memory, including large model files."""
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda:stream.read(1024*1024),b""):
            h.update(data)
    return h.hexdigest()


def content_hashes(root):
    """Use SQLite logical contents so harmless WAL/header changes do not invalidate evidence."""
    root = Path(root)
    result = {name:file_hash(root/name) for name in ("parents.json","sources.json")}
    if (root/"policies.json").exists():
        result["policies.json"] = file_hash(root/"policies.json")
    for name in ("facts.sqlite","chroma/chroma.sqlite3"):
        path = root/name
        if not path.exists():
            raise ValueError("Release store missing: "+name)
        with sqlite3.connect(f"file:{path}?mode=ro",uri=True) as conn:
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Release store corrupt")
            h = hashlib.sha256()
            for line in conn.iterdump():
                h.update(line.encode())
            result[name] = h.hexdigest()
    # Persisted HNSW content is part of the artifact, not just its SQL metadata.
    for path in sorted((root/"chroma").rglob("*")):
        if path.is_file() and path.suffix not in {".sqlite3"} and not path.name.endswith(("-wal","-shm")):
            result[path.relative_to(root).as_posix()] = file_hash(path)
    return result


def content_digest(hashes):
    return hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()


def verify(root, manifest, validation=None):
    """Reject modified candidates even when an old validation says passed."""
    expected = manifest.get("content_sha256")
    if not expected or expected != content_hashes(root):
        raise ValueError("Release content hash mismatch")
    if validation is not None and validation.get("content_digest") != content_digest(expected):
        raise ValueError("Validation does not match release contents")
    path = model_path(root,manifest)
    for name, checksum in manifest.get("model_sha256",{}).items():
        target = (path/name).resolve()
        if not target.is_relative_to(path.resolve()) or file_hash(target) != checksum:
            raise ValueError("Embedding artifact hash mismatch")


def model_path(root, manifest):
    """Prefer an explicit prepared model identifier over a machine-specific absolute path."""
    if manifest.get("model_artifact"):
        relative = Path(manifest["model_artifact"])
        state = Path(root).parent.parent.resolve()
        path = (state/relative).resolve()
        if not path.is_relative_to(state) or not path.is_dir():
            raise ValueError("Prepared embedding artifact missing")
        return path
    return Path(manifest["model_path"])
