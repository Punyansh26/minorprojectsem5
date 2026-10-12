"""Format normalisation: turn "anything" into one of the formats the readers handle.

* ``office_convert`` (doc/ppt/xls/odt/ods/odp/rtf/epub) → PDF via headless LibreOffice.
* docx/pptx/xlsx → Docling directly (style-based headings) or → PDF when configured /
  when Docling is unavailable.  PDF conversion gives page numbers for citations.

Conversions are cached by source SHA-256, so each file is converted once ever.
LibreOffice is run with a private user profile per call so parallel conversions do not
fight over ``~/.config/libreoffice`` locks (a classic headless-soffice failure).
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import Config

log = logging.getLogger(__name__)


def docling_available() -> bool:
    try:
        import docling  # noqa: F401
        return True
    except Exception:
        return False


def soffice_available(cfg: Config) -> bool:
    return shutil.which(cfg.intake.soffice) is not None


def converted_pdf_path(cfg: Config, sha256: str) -> Path:
    return cfg.work / "cache" / "converted" / f"{sha256[:16]}.pdf"


def to_pdf(cfg: Config, src: str, sha256: str) -> Path:
    """Convert an office-like file to PDF once (cached)."""
    out = converted_pdf_path(cfg, sha256)
    if out.exists() and out.stat().st_size > 0:
        return out
    if not soffice_available(cfg):
        raise RuntimeError("LibreOffice (soffice) not found; cannot convert " + src)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kbb-soffice-") as tmp:
        tmp_path = Path(tmp)
        # Copy to an ASCII name: soffice mishandles some unicode/newline filenames.
        suffix = Path(src).suffix or ".bin"
        staged = tmp_path / f"input{suffix}"
        shutil.copyfile(src, staged)
        cmd = [cfg.intake.soffice, f"-env:UserInstallation=file://{tmp_path}/profile", "--headless",
               "--norestore", "--convert-to", "pdf", "--outdir", str(tmp_path), str(staged)]
        proc = subprocess.run(cmd, capture_output=True, timeout=cfg.intake.soffice_timeout_s)
        produced = tmp_path / "input.pdf"
        if proc.returncode != 0 or not produced.exists():
            raise RuntimeError(f"soffice failed ({proc.returncode}): {proc.stderr.decode(errors='replace')[:300]}")
        shutil.move(str(produced), out)
    return out


def effective_format(cfg: Config, doc) -> tuple[str, str]:
    """Return ``(format, path)`` the extraction stage should actually read.

    Office formats become ``pdf`` when converted; everything else passes through.
    """
    fmt = doc.format
    if fmt == "office_convert":
        return "pdf", str(to_pdf(cfg, doc.path, doc.sha256))
    if fmt in {"docx", "pptx", "xlsx"}:
        use_pdf = cfg.intake.office_strategy == "pdf" or not docling_available()
        if use_pdf and soffice_available(cfg):
            return "pdf", str(to_pdf(cfg, doc.path, doc.sha256))
        if not docling_available():
            # Last resort: stdlib OOXML text extraction (paragraphs/tables, no layout).
            return f"{fmt}_xml", doc.path
    return fmt, doc.path
