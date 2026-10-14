"""Content hashes that bind a release's manifest to the exact bytes it was built and validated with."""
from __future__ import annotations

import hashlib
from pathlib import Path

ARTIFACTS = ("units.json", "vectors.npy", "parents.json", "facts.sqlite", "policies.json", "sources.json",
             "extraction_report.json")


class IntegrityError(ValueError):
    pass


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def content_hashes(root: Path) -> dict[str, str]:
    return {name: file_hash(root / name) for name in ARTIFACTS if (root / name).exists()}


def content_digest(hashes: dict[str, str]) -> str:
    return hashlib.sha256("\n".join(f"{k}:{v}" for k, v in sorted(hashes.items())).encode()).hexdigest()


_VERIFIED: dict[tuple[str, str], bool] = {}


def verify(root: Path, manifest: dict, validation: dict | None = None) -> None:
    """Recompute every artifact hash.  Cached per (root, manifest hash) because vectors can be large."""
    root = Path(root)
    key = (str(root), file_hash(root / "release.json"))
    if _VERIFIED.get(key):
        return
    expected = manifest.get("content_sha256") or {}
    if not expected:
        raise IntegrityError("manifest has no content hashes")
    actual = content_hashes(root)
    if actual != expected:
        changed = sorted(k for k in set(actual) | set(expected) if actual.get(k) != expected.get(k))
        raise IntegrityError(f"release artifacts changed after build: {changed}")
    if validation is not None and validation.get("content_digest") != content_digest(expected):
        raise IntegrityError("validation was produced for different content")
    _VERIFIED[key] = True
