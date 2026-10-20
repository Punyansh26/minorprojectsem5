#!/usr/bin/env python3
"""L0 — complete the BAAI/bge-reranker-v2-m3 download and prove it loads offline.

snapshot_download resumes the existing .incomplete blob. Afterwards the model is loaded exactly
as kbb.rerank loads it (CrossEncoder, local_files_only=True, CPU) and one relevant and one
irrelevant pair are scored. --check reports the cache state only (no network, no model load).
"""
import argparse, json, os, time
from pathlib import Path

MODEL = "BAAI/bge-reranker-v2-m3"
CACHE = Path(os.environ.get("HF_HUB_CACHE", Path.home() / ".cache/huggingface/hub")) / "models--BAAI--bge-reranker-v2-m3"


def cache_state():
    blobs = list((CACHE / "blobs").glob("*")) if (CACHE / "blobs").is_dir() else []
    incomplete = [b for b in blobs if b.name.endswith(".incomplete")]
    weights = list(CACHE.glob("snapshots/*/model.safetensors")) + list(CACHE.glob("snapshots/*/pytorch_model.bin"))
    return {"cache_dir": str(CACHE), "blobs": len(blobs), "incomplete_blobs": len(incomplete),
            "incomplete_bytes": sum(b.stat().st_size for b in incomplete),
            "weights_present": bool(weights), "complete": bool(weights) and not incomplete}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    if args.check:
        info = {"check": True, **cache_state()}
        json.dump(info, open(args.out, "w"), indent=2); print(json.dumps(info)); return
    from huggingface_hub import snapshot_download
    t0 = time.monotonic()
    path = snapshot_download(MODEL, allow_patterns=["*.json", "*.safetensors", "*.model", "*.txt", "tokenizer*"])
    fetch_s = time.monotonic() - t0
    os.environ["HF_HUB_OFFLINE"] = "1"
    from sentence_transformers import CrossEncoder
    t1 = time.monotonic()
    ce = CrossEncoder(MODEL, device="cpu", local_files_only=True, max_length=512)
    load_s = time.monotonic() - t1
    good, bad = ce.predict([("What is the hostel fee?", "Hostel fee per semester is Rs. 45,000."),
                            ("What is the hostel fee?", "The library opens at 9 am.")]).tolist()
    summary = {"model": MODEL, "snapshot": path, "fetch_s": round(fetch_s, 1), "load_s": round(load_s, 1),
               "relevant_score": round(good, 4), "irrelevant_score": round(bad, 4),
               "offline_load_ok": True, "sanity_ok": good > bad, **cache_state()}
    json.dump(summary, open(args.out, "w"), indent=2)
    print(json.dumps({k: summary[k] for k in ("complete", "offline_load_ok", "sanity_ok", "load_s")}))


if __name__ == "__main__":
    main()
