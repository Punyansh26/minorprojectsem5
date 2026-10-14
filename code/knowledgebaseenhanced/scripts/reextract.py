#!/usr/bin/env python3
"""Re-extract flagged documents ONE AT A TIME (no full-corpus batch; stop Ollama first for OCR runs).

    python scripts/reextract.py --doc general-campus_facilities_and_helpline
    python scripts/reextract.py --flagged-thin          # still sequential, one document per step
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kbb.config import get_config  # noqa: E402
from kbb.reextract import chrome_lines, reextract_document  # noqa: E402

PROCESSED = ROOT / "data" / "processed_knowledge_base"
SOURCES = ROOT / "data" / "knowledge_base"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", action="append", default=[])
    parser.add_argument("--flagged-thin", action="store_true", help="every document the audit reports as 'thin'")
    args = parser.parse_args()
    cfg = get_config()
    docs = list(args.doc)
    if args.flagged_thin:
        report = json.loads((cfg.work / "audit" / "quality_report.json").read_text())
        docs += [d["doc_id"] for d in report["details"] if any(i["code"] == "thin" for i in d["issues"])]
    html = sorted(SOURCES.rglob("*.html"))
    chrome = chrome_lines(html, cfg)
    print(f"{len(chrome)} navigation lines identified from {len(html)} HTML pages")
    for doc_id in dict.fromkeys(docs):
        try:
            print(json.dumps(reextract_document(cfg, PROCESSED, SOURCES, doc_id, chrome), ensure_ascii=False), flush=True)
        except Exception as error:  # report and continue with the next document
            print(json.dumps({"doc_id": doc_id, "error": f"{type(error).__name__}: {error}"}), flush=True)


if __name__ == "__main__":
    main()
