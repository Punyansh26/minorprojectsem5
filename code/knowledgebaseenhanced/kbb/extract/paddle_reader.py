"""PaddleOCR-VL reader (Apache-2.0): scanned pages, photos, legacy-font pages, complex tables.

Two-stage model (PP-DocLayout → element-wise 0.9B VLM), Hindi supported.  Runs either
in-process (if ``paddleocr`` imports here) or — the recommended setup — via
``kbb/workers/paddle_worker.py`` inside a separate env pointed to by
``extract.paddle_python`` / ``$KBB_PADDLE_PYTHON``.  Paddle's CUDA wheels and the ``minor``
env's torch stack must not share site-packages (see AGENTS.md §Environment).

Results are cached per (image sha256, model options), so a page is recognised once ever.
"""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from ..config import Config
from ..models import Element
from ..store import KVCache
from ..tables import from_content, render_rows
from ..textnorm import clean, sha256
from . import mk

log = logging.getLogger(__name__)
WORKER = Path(__file__).resolve().parent.parent / "workers" / "paddle_worker.py"

LABEL_MAP = {
    "doc_title": ("heading", 1), "paragraph_title": ("heading", 2), "title": ("heading", 2),
    "text": ("paragraph", None), "content": ("paragraph", None), "abstract": ("paragraph", None),
    "reference": ("paragraph", None), "reference_content": ("paragraph", None),
    "aside_text": ("paragraph", None), "algorithm": ("code", None), "list": ("list_item", None),
    "table": ("table", None), "chart": ("figure", None), "image": ("figure", None),
    "figure": ("figure", None), "seal": ("figure", None), "header_image": ("page_header", None),
    "footer_image": ("page_footer", None), "figure_title": ("caption", None),
    "table_title": ("caption", None), "chart_title": ("caption", None), "figure_table_chart_title": ("caption", None),
    "header": ("page_header", None), "footer": ("page_footer", None), "number": ("page_footer", None),
    "footnote": ("footnote", None), "vision_footnote": ("footnote", None),
    "formula": ("formula", None), "display_formula": ("formula", None), "inline_formula": ("formula", None),
    "formula_number": ("formula", None),
}


def available(cfg: Config) -> bool:
    if cfg.extract.vlm_backend != "paddleocr_vl":
        return False
    if cfg.extract.paddle_python:
        return Path(cfg.extract.paddle_python).exists()
    try:
        import paddleocr  # noqa: F401
        return True
    except Exception:
        return False


def _options(cfg: Config) -> dict:
    return {"pipeline_version": cfg.extract.paddle_pipeline_version, "device": cfg.extract.paddle_device,
            "use_chart_recognition": cfg.extract.paddle_use_chart_recognition}


def _run_batch(cfg: Config, jobs: list[dict]) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="kbb-paddle-") as tmp:
        jobs_path, out_path = Path(tmp) / "jobs.json", Path(tmp) / "out.jsonl"
        jobs_path.write_text(json.dumps({"options": _options(cfg), "jobs": jobs}), encoding="utf-8")
        if cfg.extract.paddle_python:
            cmd = [cfg.extract.paddle_python, str(WORKER), str(jobs_path), str(out_path)]
            proc = subprocess.run(cmd, capture_output=True, timeout=max(600, 120 * len(jobs)))
            if proc.returncode != 0 and not out_path.exists():
                raise RuntimeError("paddle worker failed: " + proc.stderr.decode(errors="replace")[-800:])
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location("kbb_paddle_worker", WORKER)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.main(str(jobs_path), str(out_path))
        return [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def recognise(cfg: Config, cache: KVCache, images: dict[str, str]) -> dict[str, dict]:
    """``{key: image_path}`` → ``{key: raw worker row}`` with caching and batching."""
    opt_key = sha256(json.dumps(_options(cfg), sort_keys=True))[:12]
    results, todo = {}, []
    for key, img in images.items():
        ck = f"{sha256(Path(img).read_bytes())}:{opt_key}"
        hit = cache.get("vlm", ck)
        if hit is not None:
            results[key] = hit
        else:
            todo.append({"key": key, "image": img, "_ck": ck})
    for i in range(0, len(todo), cfg.extract.paddle_batch_pages):
        batch = todo[i:i + cfg.extract.paddle_batch_pages]
        log.info("PaddleOCR-VL: pages %d-%d of %d", i + 1, i + len(batch), len(todo))
        rows = {r["key"]: r for r in _run_batch(cfg, [{"key": j["key"], "image": j["image"]} for j in batch])}
        for j in batch:
            row = rows.get(j["key"], {"key": j["key"], "blocks": [], "error": "missing from worker output"})
            if "error" not in row:
                cache.put("vlm", j["_ck"], row)
            results[j["key"]] = row
    return results


def to_elements(row: dict, page: int, scale: float) -> list[Element]:
    """Worker row → Elements.  ``scale`` maps pixels → PDF points (72/dpi; 1 for images)."""
    out: list[Element] = []
    pending_caption = ""
    for b in sorted(row.get("blocks", []), key=lambda b: (b.get("order") is None, b.get("order") or 0)):
        etype, level = LABEL_MAP.get(str(b.get("label", "text")).lower(), ("paragraph", None))
        bbox = [round(v * scale, 2) for v in b["bbox"][:4]] if b.get("bbox") and len(b["bbox"]) >= 4 else None
        content = b.get("content") or ""
        if etype == "table":
            table = from_content(content, caption=pending_caption)
            pending_caption = ""
            if table is None:
                out.append(mk("paragraph", page, clean(content), bbox=bbox, reader="paddleocr-vl",
                              table_parse_failed=True))
                continue
            out.append(mk("table", page, render_rows(table), bbox=bbox, table=table, reader="paddleocr-vl"))
            continue
        text = clean(content)
        if etype == "figure":
            table = from_content(content) if "|" in content or "<table" in content.lower() else None
            out.append(mk("figure", page, text, bbox=bbox, table=table, reader="paddleocr-vl",
                          chart=b.get("label") == "chart"))
            continue
        if not text:
            continue
        if etype == "caption":
            pending_caption = text
        out.append(mk(etype, page, text, bbox=bbox, level=level, reader="paddleocr-vl"))
    return out
