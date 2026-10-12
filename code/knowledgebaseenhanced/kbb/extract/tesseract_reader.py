"""Tesseract word-level reader: fallback second read and last-resort primary OCR.

``OMP_THREAD_LIMIT=1`` per process is essential when many pages run in parallel; otherwise
each Tesseract spawns all-core OpenMP threads and throughput collapses.
"""
from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
from pathlib import Path

from ..config import Config
from ..models import Element
from ..textnorm import clean
from . import mk


def available() -> bool:
    return shutil.which("tesseract") is not None


def _langs(cfg: Config) -> tuple[list[str], dict]:
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    args: list[str] = []
    td = cfg.paths.tessdata
    if td and Path(td, "hin.traineddata").exists():
        args += ["--tessdata-dir", str(td)]
    langs = cfg.extract.tesseract_langs
    if td and not Path(td, "hin.traineddata").exists() and "hin" in langs:
        langs = "eng"
    return args + ["-l", langs], env


def ocr_words(cfg: Config, image_path: str, scale: float = 1.0, psm: int = 3) -> tuple[str, list[dict]]:
    """Return (text with line breaks, words[{text, bbox(points), conf}])."""
    lang_args, env = _langs(cfg)
    cmd = ["tesseract", str(image_path), "stdout", "--psm", str(psm), *lang_args, "-c", "tessedit_create_tsv=1"]
    proc = subprocess.run(cmd, capture_output=True, timeout=300, env=env, check=True)
    words, lines = [], {}
    reader = csv.DictReader(io.StringIO(proc.stdout.decode("utf-8", "replace")), delimiter="\t",
                            quoting=csv.QUOTE_NONE)
    for row in reader:
        text = (row.get("text") or "").strip()
        if row.get("level") != "5" or not text:
            continue
        x, y, w, h = (int(row[k]) for k in ("left", "top", "width", "height"))
        words.append({"text": text, "bbox": [round(x * scale, 2), round(y * scale, 2),
                                             round((x + w) * scale, 2), round((y + h) * scale, 2)],
                      "conf": float(row.get("conf") or -1)})
        key = (row["block_num"], row["par_num"], row["line_num"])
        lines.setdefault(key, []).append(text)
    return "\n".join(" ".join(v) for v in lines.values()), words


def words_to_elements(words: list[dict], page: int) -> list[Element]:
    """Group words into line-paragraph elements (no structure; used only when nothing better)."""
    if not words:
        return []
    heights = sorted(w["bbox"][3] - w["bbox"][1] for w in words)
    lh = heights[len(heights) // 2] or 10
    rows: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["bbox"][1], w["bbox"][0])):
        if rows and abs(w["bbox"][1] - rows[-1][0]["bbox"][1]) < lh * 0.6:
            rows[-1].append(w)
        else:
            rows.append([w])
    paras, cur, last_y = [], [], None
    for row in rows:
        y = row[0]["bbox"][1]
        if cur and last_y is not None and y - last_y > lh * 1.8:
            paras.append(cur)
            cur = []
        cur.append(row)
        last_y = y
    if cur:
        paras.append(cur)
    out = []
    for para in paras:
        ws = [w for row in para for w in sorted(row, key=lambda w: w["bbox"][0])]
        text = "\n".join(" ".join(w["text"] for w in sorted(row, key=lambda w: w["bbox"][0])) for row in para)
        bbox = [min(w["bbox"][0] for w in ws), min(w["bbox"][1] for w in ws),
                max(w["bbox"][2] for w in ws), max(w["bbox"][3] for w in ws)]
        conf = sum(w["conf"] for w in ws) / len(ws)
        out.append(mk("paragraph", page, clean(text), bbox=bbox, reader="tesseract", confidence=round(conf, 1)))
    return out
