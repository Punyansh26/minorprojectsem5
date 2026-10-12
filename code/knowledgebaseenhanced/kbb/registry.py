"""Stage 0 — intake registry: discover files, fingerprint, dedupe, attach metadata.

Output: ``work/registry.json`` → ``{"docs": [DocRecord...], "skipped": [...], "duplicates": [...]}``.

* Format is detected from **magic bytes**, not extensions (the corpus has a PDF whose name
  contains a newline and no ``.pdf`` suffix, and browser ``view-source_`` HTML dumps).
* ``doc_id = <category>-<slug(title)>-<sha256[:8]>``: stable across renames, changes when
  content changes (so stale artefacts are never reused for new bytes).
* Metadata precedence: defaults ← ``kb_sources.json``/``sources_meta.yaml`` ← sidecar
  ``<file>.meta.yaml``.
"""
from __future__ import annotations

import fnmatch
import hashlib
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import Config
from .store import read_json, write_json
from .textnorm import slug

log = logging.getLogger(__name__)

MAGIC = [(b"%PDF", "pdf"), (b"\x89PNG", "image"), (b"\xff\xd8\xff", "image"), (b"GIF8", "image"),
         (b"II*\x00", "image"), (b"MM\x00*", "image"), (b"BM", "image"), (b"RIFF", "image"),
         (b"{\\rtf", "office_convert")]
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"          # legacy .doc/.ppt/.xls
OFFICE = {".docx": "docx", ".pptx": "pptx", ".xlsx": "xlsx"}
CONVERT_EXT = {".doc", ".ppt", ".xls", ".odt", ".ods", ".odp", ".rtf", ".epub"}
TEXT_FORMATS = {".csv": "csv", ".tsv": "csv", ".json": "json", ".jsonl": "json", ".xml": "xml",
                ".yaml": "yaml", ".yml": "yaml", ".txt": "text", ".md": "text", ".rst": "text",
                ".eml": "email"}


def sniff_format(path: Path) -> str | None:
    """Detect the reader to use.  Bytes win over extensions; extensions break ties.

    Returns one of: pdf | image | html | docx | pptx | xlsx | office_convert | csv | json |
    xml | yaml | text | email | None (unsupported).
    """
    suffix = path.suffix.lower()
    with path.open("rb") as fh:
        head = fh.read(4096)
    if head.startswith(b"PK\x03\x04"):                      # zip container
        import zipfile
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
        except zipfile.BadZipFile:
            return None
        if "word/document.xml" in names:
            return "docx"
        if "ppt/presentation.xml" in names:
            return "pptx"
        if "xl/workbook.xml" in names:
            return "xlsx"
        if "mimetype" in names or "META-INF/container.xml" in names:   # ODF / EPUB
            return "office_convert"
        return None
    if head.startswith(OLE_MAGIC):
        return "office_convert"
    for magic, fmt in MAGIC:
        if head.startswith(magic):
            if magic == b"RIFF" and head[8:12] != b"WEBP":
                return None
            return fmt
    if suffix in CONVERT_EXT:
        return "office_convert"
    lowered = head.lower().lstrip()
    if suffix == ".mhtml" or lowered.startswith(b"mime-version") and b"multipart/related" in lowered:
        return "html"
    if b"<html" in lowered or b"<!doctype html" in lowered or suffix in {".html", ".htm", ".xhtml"}:
        return "html"
    if suffix in TEXT_FORMATS:
        return TEXT_FORMATS[suffix]
    if re.match(rb"(?i)(received|from|return-path|message-id|date|subject):", lowered):
        return "email"
    if b"\x00" not in head:                                 # unknown extension, plain text bytes
        try:
            head.decode("utf-8")
            return "text"
        except UnicodeDecodeError:
            return None
    return None


@dataclass
class DocRecord:
    doc_id: str
    path: str                  # absolute path
    rel_path: str              # relative to its source root (metadata key)
    format: str                # pdf | image | html | docx | pptx | xlsx | text
    sha256: str
    bytes: int
    title: str
    category: str = "general"
    topic: str = "general"
    years: list[int] = field(default_factory=list)
    period: str = ""
    programme: str = ""
    historical: bool = False
    published_at: str = ""
    source_url: str = ""
    source_status: str = "active"      # active | retired
    superseded_by: str = ""
    language_hint: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def meta(self) -> dict:
        """Metadata copied onto every parent / unit (provenance + filters)."""
        return {"doc_id": self.doc_id, "title": self.title, "source_file": self.rel_path,
                "source_sha256": self.sha256, "source_url": self.source_url, "category": self.category,
                "topic": self.topic, "years": self.years, "period": self.period,
                "programme": self.programme, "historical": self.historical,
                "published_at": self.published_at, "source_status": self.source_status,
                "superseded_by": self.superseded_by, "format": self.format}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _load_metadata(cfg: Config) -> dict[str, dict]:
    meta: dict[str, dict] = {}
    for path in cfg.paths.metadata_files:
        if not path.exists():
            continue
        data = read_json(path) if path.suffix == ".json" else yaml.safe_load(path.read_text("utf-8"))
        if not data:
            continue
        for key, value in (data.get("local_sources") or data.get("files") or {}).items():
            meta.setdefault(key, {}).update(value or {})
    return meta


def _title_from_name(path: Path) -> str:
    name = re.sub(r"\s+", " ", path.stem.replace("_", " ")).strip()
    name = re.sub(r"^view-source\s*https?\s*", "", name, flags=re.I)
    return name or path.name


def _skip_reason(cfg: Config, path: Path, fmt: str) -> str:
    if any(re.search(p, path.name) for p in cfg.intake.skip_name_patterns):
        return "name matches skip pattern"
    if path.stat().st_size > cfg.intake.max_file_mb * 1024 * 1024:
        return "file too large"
    if fmt == "image":
        try:
            from PIL import Image
            with Image.open(path) as im:
                if min(im.size) < cfg.intake.min_image_side_px:
                    return f"image too small {im.size} (icon/logo)"
        except Exception as exc:     # unreadable image is reported, not fatal
            return f"unreadable image: {type(exc).__name__}"
    return ""


def discover(cfg: Config) -> dict:
    """Walk source roots → registry dict (also written to ``work/registry.json``)."""
    metadata = _load_metadata(cfg)
    previous = {d["sha256"]: d for d in (read_json(cfg.work / "registry.json", {}) or {}).get("docs", [])}
    docs: list[DocRecord] = []
    skipped, duplicates = [], []
    seen: dict[str, str] = {}
    for root in cfg.paths.sources:
        if not root.exists():
            log.warning("source root missing: %s", root)
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = path.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(path.name, g.split("/")[-1])
                   for g in cfg.intake.ignore_globs):
                continue
            fmt = sniff_format(path)
            if fmt is None:
                skipped.append({"path": rel, "reason": "unsupported format"})
                continue
            reason = _skip_reason(cfg, path, fmt)
            if reason:
                skipped.append({"path": rel, "reason": reason})
                continue
            sha = file_sha256(path)
            if sha in seen:
                duplicates.append({"path": rel, "duplicate_of": seen[sha]})
                continue
            seen[sha] = rel
            # Metadata keys may be written with a normalised path (newlines → spaces).
            m = dict(metadata.get(rel) or metadata.get(re.sub(r"\s+", " ", rel)) or {})
            sidecar = path.with_name(path.name + ".meta.yaml")
            if sidecar.exists():
                m.update(yaml.safe_load(sidecar.read_text("utf-8")) or {})
            category = m.get("category") or (rel.split("/")[0] if "/" in rel else "general")
            title = m.get("title") or _title_from_name(path)
            doc_id = f"{slug(category, 20)}-{slug(title, 40)}-{sha[:8]}"
            rec = DocRecord(
                doc_id=doc_id, path=str(path), rel_path=rel, format=fmt, sha256=sha,
                bytes=path.stat().st_size, title=title, category=category,
                topic=m.get("topic", category), years=[int(y) for y in m.get("years", [])],
                period=m.get("period", ""), programme=m.get("programme", ""),
                historical=bool(m.get("historical", False)), published_at=str(m.get("published_at", "")),
                source_url=m.get("url", m.get("source_url", "")),
                source_status=m.get("source_status", "active"), superseded_by=m.get("superseded_by", ""),
                language_hint=m.get("language", ""),
                extra={k: v for k, v in m.items() if k not in DocRecord.__dataclass_fields__})
            if not rec.years:
                rec.years = sorted({int(y) for y in re.findall(r"(?<!\d)(20[0-4]\d)(?!\d)", rel)})
            docs.append(rec)
    registry = {"docs": [asdict(d) for d in docs], "skipped": skipped, "duplicates": duplicates,
                "new": [d.doc_id for d in docs if d.sha256 not in previous],
                "removed": [p["doc_id"] for s, p in previous.items() if s not in seen]}
    write_json(cfg.work / "registry.json", registry)
    log.info("registry: %d docs (%d new, %d removed), %d skipped, %d duplicates",
             len(docs), len(registry["new"]), len(registry["removed"]), len(skipped), len(duplicates))
    return registry


def load_registry(cfg: Config) -> list[DocRecord]:
    data = read_json(cfg.work / "registry.json", {}) or {}
    return [DocRecord(**d) for d in data.get("docs", [])]
