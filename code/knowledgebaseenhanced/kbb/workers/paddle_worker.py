"""Isolated PaddleOCR-VL worker.  Runs inside the *paddle* env, not the main ``minor`` env.

Usage (called by kbb.extract.paddle_reader):
    <paddle-python> paddle_worker.py jobs.json results.jsonl

jobs.json = {"options": {...PaddleOCRVL kwargs...}, "jobs": [{"key": str, "image": path}, ...]}
results.jsonl = one line per job:
    {"key", "width", "height", "blocks": [{"label","bbox","content","order"}], "error"?}

Standalone on purpose: imports nothing from ``kbb`` so it works with any Python that has
``paddleocr[doc-parser]`` installed.  The model loads once per launch and processes the
whole batch; results are flushed per page so a crash loses at most one page.
"""
import json
import sys
import traceback


def _to_list(v):
    try:
        return [float(x) for x in (v.tolist() if hasattr(v, "tolist") else v)]
    except Exception:
        return None


def main(jobs_path: str, out_path: str) -> int:
    with open(jobs_path, encoding="utf-8") as fh:
        spec = json.load(fh)
    from paddleocr import PaddleOCRVL
    options = {k: v for k, v in (spec.get("options") or {}).items() if v not in ("", None)}
    pipeline = PaddleOCRVL(**options)
    with open(out_path, "a", encoding="utf-8") as out:
        for job in spec["jobs"]:
            row = {"key": job["key"], "blocks": []}
            try:
                for res in pipeline.predict(job["image"]):
                    data = res.json if isinstance(res.json, dict) else {}
                    data = data.get("res", data)
                    row["width"], row["height"] = data.get("width"), data.get("height")
                    for i, b in enumerate(data.get("parsing_res_list", []) or []):
                        row["blocks"].append({
                            "label": b.get("block_label", "text"),
                            "bbox": _to_list(b.get("block_bbox")),
                            "content": b.get("block_content", "") or "",
                            "order": b.get("block_order") if b.get("block_order") is not None else i,
                        })
            except Exception as exc:          # one bad page must not kill the batch
                row["error"] = f"{type(exc).__name__}: {exc}"[:500]
                traceback.print_exc(file=sys.stderr)
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
