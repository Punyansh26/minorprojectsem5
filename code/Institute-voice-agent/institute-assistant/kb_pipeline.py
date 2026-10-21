"""Refresh, inspect, build, evaluate and activate the shared verified knowledge base."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from assistant.config import settings
from assistant.kb.common import read_json, write_json


def merge_records(state: Path):
    """Merge approved JoSAA rows without modifying the manually maintained records file."""
    blocks = read_json(state / "blocks.json", [])
    extra = read_json(state / "josaa_blocks.json", [])
    merged = {b["id"]: b for b in blocks + extra}
    write_json(state / "blocks.json", list(merged.values()))
    manual = read_json(state / "manual_records.json", [])
    write_json(state / "records.json", manual + read_json(state / "josaa_records.json", []))
    manifest = read_json(state / "sources.json", {"sources": []})
    by_id = {s["id"]: s for s in manifest["sources"]}
    for audit in read_json(state / "josaa_audit.json", []):
        if audit.get("source"):
            source = {**audit["source"], "fetch_method": "public_form"}
            by_id[source["id"]] = source
    manifest["sources"] = list(by_id.values())
    write_json(state / "sources.json", manifest)


def main():
    """Keep acquisition and release activation explicit, repeatable operations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=Path(settings.KB_STATE_DIR))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap", help="Download pinned embedding weights and official Hindi OCR data")
    refresh = sub.add_parser("refresh")
    refresh.add_argument("--registry", type=Path, default=Path(__file__).with_name("kb_sources.json"))
    refresh.add_argument("--discover", action="store_true")
    refresh.add_argument("--only-new", action="store_true")
    ranks = sub.add_parser("ranks")
    ranks.add_argument("--years", nargs="+", type=int, default=[2026, 2025, 2024, 2023, 2022])
    sub.add_parser("extract")
    sub.add_parser("build")
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--release")
    evaluate.add_argument("--cases", type=Path, default=Path(__file__).parent / "docs/kb_evaluation_cases.json")
    evaluate.add_argument("--baseline", action="store_true")
    activate = sub.add_parser("activate")
    activate.add_argument("--release")
    sub.add_parser("rollback")
    sub.add_parser("report")
    lifecycle = sub.add_parser("source-status",help="Record ownership/review deadline or explicitly retire a source for the next release")
    lifecycle.add_argument("--source-id",required=True)
    lifecycle.add_argument("--owner",required=True)
    lifecycle.add_argument("--review-by",required=True)
    lifecycle.add_argument("--retire",action="store_true")
    lifecycle.add_argument("--superseded-by",default="")
    lifecycle.add_argument("--reason",required=True)
    args = parser.parse_args()
    state = args.state.resolve()
    if args.command == "bootstrap":
        from huggingface_hub import snapshot_download
        import requests
        model = state / "models/multilingual-e5-small"
        snapshot_download(settings.KB_EMBEDDING_MODEL, revision=settings.KB_EMBEDDING_REVISION,
                          local_dir=model, allow_patterns=["*.json", "*.safetensors", "*.model", "1_Pooling/*"],
                          ignore_patterns=["onnx/*", "openvino/*"])
        response = requests.get("https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/hin.traineddata", timeout=60)
        response.raise_for_status()
        tessdata = state / "models/tessdata"
        tessdata.mkdir(parents=True, exist_ok=True)
        (tessdata / "hin.traineddata").write_bytes(response.content)
        from assistant.kb.common import digest
        write_json(state / "models/model_manifest.json", {"embedding_model": settings.KB_EMBEDDING_MODEL,
                   "embedding_revision": settings.KB_EMBEDDING_REVISION, "hindi_ocr_sha256": digest(response.content)})
        result = {"model_path": str(model), "hindi_ocr_bytes": len(response.content)}
    elif args.command == "refresh":
        from assistant.kb.sources import register_local, refresh
        register_local(Path(settings.KB_DIR), args.registry, state)
        result = refresh(args.registry, state, discover=args.discover, only_new=args.only_new)
    elif args.command == "ranks":
        from assistant.kb.josaa import collect_ranks
        result = collect_ranks(state, args.years)
    elif args.command == "extract":
        from assistant.kb.extraction import extract_all
        report = extract_all(state)
        merge_records(state)
        result = {k: v for k, v in report.items() if k != "sources"}
    elif args.command == "build":
        from assistant.kb.releases import build_release
        merge_records(state)
        result = build_release(state)
    elif args.command == "evaluate":
        from assistant.kb.evaluation import evaluate_release
        release = args.release or read_json(state / "latest_build.json")["release"]
        result = evaluate_release(state / "releases" / release, args.cases, baseline=args.baseline)
    elif args.command == "activate":
        from assistant.kb.releases import activate
        release = args.release or read_json(state / "latest_build.json")["release"]
        result = activate(state, release)
    elif args.command == "rollback":
        from assistant.kb.releases import rollback
        result = rollback(state)
    elif args.command == "source-status":
        from datetime import date
        date.fromisoformat(args.review_by)
        manifest = read_json(state/"sources.json")
        source = next((s for s in manifest["sources"] if s["id"]==args.source_id),None)
        if source is None or not args.owner.strip() or not args.reason.strip():
            parser.error("A known source, owner and reason are required")
        source.update(source_owner=args.owner,review_by=args.review_by,superseded_by=args.superseded_by,
                      source_status="retired" if args.retire else "active",lifecycle_reason=args.reason)
        write_json(state/"sources.json",manifest)
        result = {"source_id":args.source_id,"status":source["source_status"],"active_release_changed":False}
    else:
        from assistant.kb.reporting import write_reports
        result = write_reports(state)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
