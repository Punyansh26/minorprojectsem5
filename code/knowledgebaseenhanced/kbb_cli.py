#!/usr/bin/env python3
"""Unified CLI entry point for the Knowledge Base Pipeline v2 (`kbb`).

Subcommands:
    register       Stage 0: Discover sources, compute SHA-256, merge metadata -> registry.json
    triage         Stage 1: Render pages and classify (native, scanned, legacy, blank) -> triage.json
    extract        Stage 2: Run primary & secondary readers -> canonical elements & second reads
    structure      Stage 4: Assemble clean document structure and apply structure patches
    verify         Stage 5: Keyed table cell equality, number token and coverage fidelity checks
    chunk          Stage 6: Multi-granularity chunking (section, table, row-fact, page)
    enrich         Stage 6: Generate contextual prefixes and bilingual synthetic questions
    build-release  Stage 7: Build an immutable release (vectors, BM25 units, typed facts) from the corpus
    ask            Stage 8: Query the active release and print retrieved evidence passages
    evaluate / activate / rollback   Release gate and pointer (see build-release)
    all            Run full incremental pipeline (cache-aware)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from kbb.canonical import load_canonical_doc, save_canonical_doc
from kbb.chunk import build_parents_and_units
from kbb.config import get_config
from kbb.enrich import enrich_parents_and_units
from kbb.extract.pipeline import extract_document
from kbb.llm import LLMClient
from kbb.models import Parent, Unit
from kbb.registry import discover, load_registry
from kbb.retrieve import ReleaseRetriever, active_release_root
from kbb.store import Stores, read_json, run_lock, write_json
from kbb.structure import assemble_structure
from kbb.triage import triage_doc
from kbb.verify import verify_document

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("kbb_cli")


def cmd_register(args, cfg, stores):
    print("=== Stage 0: Registering Sources ===")
    reg = discover(cfg)
    print(f"Total documents: {len(reg.get('docs', []))} | Skipped: {len(reg.get('skipped', []))} | Duplicates: {len(reg.get('duplicates', []))}")


def cmd_triage(args, cfg, stores):
    print("=== Stage 1: Triaging Pages ===")
    docs = load_registry(cfg)
    target_docs = [d for d in docs if not args.doc or d.doc_id == args.doc]
    for d in target_docs:
        pages = triage_doc(cfg, d)
        doc_dir = cfg.doc_dir(d.doc_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        write_json(doc_dir / "triage.json", pages)
        print(f"[{d.doc_id}] Triaged {len(pages)} pages")


def cmd_extract(args, cfg, stores):
    print("=== Stage 2: Extracting Documents ===")
    docs = load_registry(cfg)
    target_docs = [d for d in docs if not args.doc or d.doc_id == args.doc]
    for d in target_docs:
        print(f"Extracting {d.doc_id} ({d.format})...")
        elements, second_reads, pages = extract_document(cfg, d, stores.cache)
        save_canonical_doc(cfg, d.doc_id, d.meta(), elements, pages, second_reads)
        print(f"Saved {len(elements)} elements, {len(second_reads)} second reads")


def cmd_structure(args, cfg, stores):
    print("=== Stage 4: Assembling Document Structure ===")
    docs = load_registry(cfg)
    target_docs = [d for d in docs if not args.doc or d.doc_id == args.doc]
    for d in target_docs:
        cdoc = load_canonical_doc(cfg, d.doc_id)
        structured_elements = assemble_structure(cfg, cdoc.elements, len(cdoc.pages))
        save_canonical_doc(cfg, d.doc_id, cdoc.meta, structured_elements, cdoc.pages, cdoc.second_reads)
        print(f"[{d.doc_id}] Structured {len(structured_elements)} elements")


def cmd_verify(args, cfg, stores):
    print("=== Stage 5: Verifying Document Fidelity ===")
    docs = load_registry(cfg)
    target_docs = [d for d in docs if not args.doc or d.doc_id == args.doc]
    for d in target_docs:
        cdoc = load_canonical_doc(cfg, d.doc_id)
        verified_elements, report = verify_document(cfg, cdoc.elements, cdoc.second_reads, cdoc.meta)
        save_canonical_doc(cfg, d.doc_id, cdoc.meta, verified_elements, cdoc.pages, cdoc.second_reads)
        write_json(cfg.doc_dir(d.doc_id) / "verify.json", report)
        print(f"[{d.doc_id}] Status: {report['status']} | Checked: {report['numbers_checked']} numbers, {report['tables_checked']} tables | Mismatches: {report['mismatches']}")


def cmd_chunk(args, cfg, stores):
    print("=== Stage 6: Chunking Multi-Granularity Units ===")
    docs = load_registry(cfg)
    all_parents, all_units = [], []
    for d in docs:
        try:
            cdoc = load_canonical_doc(cfg, d.doc_id)
            parents, units = build_parents_and_units(cfg, d.doc_id, cdoc.elements, cdoc.meta)
            all_parents.extend(parents)
            all_units.extend(units)
        except Exception as exc:
            log.warning("Chunking failed on %s: %s", d.doc_id, exc)

    write_json(cfg.work / "parents_all.json", [p.to_dict() for p in all_parents])
    write_json(cfg.work / "units_all.json", [u.to_dict() for u in all_units])
    print(f"Generated {len(all_parents)} evidence parents and {len(all_units)} retrieval units")


def cmd_enrich(args, cfg, stores):
    print("=== Stage 6: Enriching Units (Context & Questions) ===")
    p_path = cfg.work / "parents_all.json"
    u_path = cfg.work / "units_all.json"
    if not p_path.exists() or not u_path.exists():
        print("Run 'chunk' first before 'enrich'!")
        return

    parents = [Parent.from_dict(p) for p in read_json(p_path, [])]
    units = [Unit.from_dict(u) for u in read_json(u_path, [])]

    llm = LLMClient(cfg, stores.cache)
    enriched_units = enrich_parents_and_units(cfg, llm, parents, units)
    write_json(cfg.work / "units_enriched.json", [u.to_dict() for u in enriched_units])
    print(f"Enriched units total: {len(enriched_units)}")


def cmd_ask(args, cfg, stores):
    from kbb.bot import RAGBot
    release_root = active_release_root(cfg)

    if getattr(args, "raw", False):
        retriever = ReleaseRetriever(cfg, release_root)
        print(f"\nQuery: {args.question}\n" + "=" * 60)
        results = retriever.search(args.question, top_k=args.k)
        for idx, r in enumerate(results, 1):
            print(f"\n{r.citation(idx)}")
            print(f"Score: {r.score:.4f} | Status: {r.status} | Source: {r.source_file}")
        return

    bot = RAGBot(cfg, release_root)
    print(f"\n❓ Question: {args.question}")
    print("=" * 70)
    resp = bot.ask(args.question, top_k=args.k)
    print(f"\n💡 Answer ({resp.mode}, {resp.latency_ms}ms):\n")
    print(resp.answer)
    print("\n" + "-" * 70)
    print("📚 Verified Sources & Citations:")
    for c in resp.citations:
        sec = " › ".join(c.heading_path) if c.heading_path else c.title
        loc = f"p. {c.page}" if c.page > 0 else "Official Document"
        print(f"  • {c.id} {c.title} ({loc}) — {sec}")
        if c.source_file:
            print(f"    Source: {c.source_file}")
    print("=" * 70)


def cmd_chat(args, cfg, stores):
    from kbb.bot import RAGBot
    bot = RAGBot(cfg, active_release_root(cfg))

    print("=" * 70)
    print("🎓 IIIT Naya Raipur Verified Knowledge Assistant")
    print("Type your questions below. Enter 'exit', 'quit', or 'q' to stop.")
    print("=" * 70)

    while True:
        try:
            q = input("\nUser > ").strip()
            if not q:
                continue
            if q.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break

            resp = bot.ask(q, top_k=args.k)
            print(f"\nAssistant ({resp.mode}, {resp.latency_ms}ms):\n")
            print(resp.answer)
            if resp.citations:
                print("\nSources:")
                for c in resp.citations:
                    sec = " › ".join(c.heading_path) if c.heading_path else c.title
                    loc = f"p. {c.page}" if c.page > 0 else "Official Doc"
                    print(f"  • {c.id} {c.title} ({loc})")
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


def cmd_serve(args, cfg, stores):
    import http.server
    import json
    from kbb.bot import RAGBot

    root = active_release_root(cfg)
    latest = {"build_id": root.name}
    bot = RAGBot(cfg, root)
    port = args.port

    class RAGRequestHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ["/health", "/"]:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "healthy", "build": latest.get("build_id", "unknown")}).encode("utf-8"))
            else:
                self.send_error(404, "Not Found")

        def do_POST(self):
            if self.path == "/query":
                content_length = int(self.headers.get("Content-Length", 0))
                post_data = self.rfile.read(content_length)
                try:
                    req_json = json.loads(post_data.decode("utf-8"))
                    q = req_json.get("question", "").strip()
                    top_k = req_json.get("top_k", 5)
                    resp = bot.ask(q, top_k=top_k)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(resp.to_dict()).encode("utf-8"))
                except Exception as exc:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
            else:
                self.send_error(404, "Not Found")

    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), RAGRequestHandler)
    print(f"🚀 IIIT-NR RAG API Server listening at http://0.0.0.0:{port}")
    print(f"Endpoints: GET /health | POST /query")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()


def _serving(cfg):
    return cfg.work / "serving"


def cmd_build_release(args, cfg, stores):
    from kbb.release import build_release
    root = cfg.paths.work.parent
    manifest = build_release(
        cfg, _serving(cfg), processed_dir=root / "processed_knowledge_base", source_root=root / "knowledge_base",
        legacy_state=cfg.paths.legacy_state, curated_path=cfg.paths.config_dir / "curated_facts.json",
        record_reviews_path=cfg.paths.config_dir.parent / "review" / "record_reviews.json",
        device=args.device, embed=not args.no_embed)
    print(json.dumps({k: v for k, v in manifest.items() if k != "content_sha256"}, indent=2, ensure_ascii=False))


def cmd_evaluate(args, cfg, stores):
    from kbb.release import evaluate, latest_release
    release = args.release or latest_release(_serving(cfg))
    report = evaluate(_serving(cfg), release, cfg.paths.eval_dir / "spotcheck.json", min_legacy_pass=args.min_legacy_pass)
    print(json.dumps({k: v for k, v in report.items() if k != "failures"}, indent=2))
    for f in report["failures"][:25]:
        print("  FAIL", f["id"], f.get("terms_ok"), f.get("source_ok"), f.get("got"))


def cmd_activate(args, cfg, stores):
    from kbb.release import activate, latest_release
    print(json.dumps(activate(_serving(cfg), args.release or latest_release(_serving(cfg))), indent=2))


def cmd_rollback(args, cfg, stores):
    from kbb.release import rollback
    print(json.dumps(rollback(_serving(cfg)), indent=2))


def cmd_review_sheet(args, cfg, stores):
    import csv
    from kbb.release import latest_release
    root = _serving(cfg) / "releases" / latest_release(_serving(cfg))
    import sqlite3
    parents = read_json(root / "parents.json")
    rows = []
    with sqlite3.connect(f"file:{root / 'facts.sqlite'}?mode=ro", uri=True) as con:
        for rid, kind, status, payload in con.execute("SELECT id, kind, review_status, payload FROM records WHERE kind != 'cutoff' ORDER BY kind, label"):
            rec = json.loads(payload)
            ev = parents[rec["evidence_block_id"]]
            value = rec.get("amount") or rec.get("date_text") or rec.get("seats") or rec.get("value") or rec.get("email") or rec.get("benefit", "")
            rows.append({"id": rid, "kind": kind, "status": status, "label": rec.get("label") or rec.get("name", ""), "value": value,
                         "quote": rec.get("quote", rec.get("conditions", ""))[:300], "source": ev["source_file"], "page": ev["page_number"],
                         "evidence_status": ev["verification_status"]})
    out = cfg.paths.config_dir.parent / "review"
    out.mkdir(exist_ok=True)
    with (out / "critical_facts.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    md = ["# Facts awaiting / holding a review decision", "", "Edit `review/record_reviews.json` (or run `review-records`) to override any row.", "",
          "| status | kind | label | value | source (page) | quote |", "| --- | --- | --- | --- | --- | --- |"]
    md += [f"| {r['status']} | {r['kind']} | {r['label'][:60]} | {r['value']} | {Path(r['source']).name[:40]} (p{r['page']}) | {r['quote'][:90]} |" for r in rows if r["kind"] in {"fee", "date", "seat", "placement", "scholarship", "finance"}]
    (out / "critical_facts.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    pending = sum(r["status"] == "pending" for r in rows)
    print(f"{len(rows)} records, {pending} pending -> {out / 'critical_facts.csv'}")


def cmd_review_records(args, cfg, stores):
    from datetime import datetime, timezone
    path = cfg.paths.config_dir.parent / "review" / "record_reviews.json"
    data = read_json(path, {"version": 1, "decisions": {}})
    from kbb.release import latest_release
    root = _serving(cfg) / "releases" / latest_release(_serving(cfg))
    import sqlite3
    with sqlite3.connect(f"file:{root / 'facts.sqlite'}?mode=ro", uri=True) as con:
        q = "SELECT id FROM records WHERE kind != 'cutoff' AND review_status = 'pending'"
        ids = [r[0] for r in con.execute(q + (" AND kind = ?" if args.kind else ""), [args.kind] if args.kind else [])]
    if args.id:
        ids = [i for i in ids if i in set(args.id)]
    for rid in ids:
        data["decisions"][rid] = {"decision": args.decision, "reviewer": args.reviewer, "notes": args.notes,
                                  "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    write_json(path, data)
    print(f"{args.decision}: {len(ids)} records")


def cmd_audit(args, cfg, stores):
    from kbb.audit import audit_corpus
    processed = Path(args.dir) if args.dir else cfg.paths.work.parent / "processed_knowledge_base"
    out = cfg.work / "audit" / "quality_report.json"
    report = audit_corpus(processed, out)
    print(f"Audited {report['documents']} documents: {report['flagged_high']} with high-severity defects, "
          f"{report['flagged_any']} with any defect. Issue counts: {report['issue_counts']}")
    for d in report["details"]:
        high = [i for i in d["issues"] if i["severity"] == "high"]
        if high:
            print(f"  ✗ {d['doc_id']:<55} {d['words']:>6}w  " + "; ".join(f"{i['code']}({i['detail']})" for i in high))
    print(f"Report: {out}")


def cmd_all(args, cfg, stores):
    print("=== Running Complete Incremental Knowledge Pipeline ===")
    with run_lock(cfg.work):
        cmd_register(args, cfg, stores)
        cmd_triage(args, cfg, stores)
        cmd_extract(args, cfg, stores)
        cmd_structure(args, cfg, stores)
        cmd_verify(args, cfg, stores)
        cmd_chunk(args, cfg, stores)
        if cfg.enrich.enabled:
            cmd_enrich(args, cfg, stores)
        print("Next: python kbb_cli.py build-release, evaluate, activate")
        print("=== Complete Pipeline Run Finished Successfully ===")


def main():
    parser = argparse.ArgumentParser(description="Knowledge Base Pipeline v2 (`kbb`)")
    parser.add_argument("--config", help="Path to custom kbb.yaml config")
    sub = parser.add_subparsers(dest="command", required=True)

    # Subcommands
    sub.add_parser("register")
    p_triage = sub.add_parser("triage")
    p_triage.add_argument("--doc", help="Optional doc_id filter")
    p_extract = sub.add_parser("extract")
    p_extract.add_argument("--doc", help="Optional doc_id filter")
    p_struct = sub.add_parser("structure")
    p_struct.add_argument("--doc", help="Optional doc_id filter")
    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--doc", help="Optional doc_id filter")
    sub.add_parser("chunk")
    sub.add_parser("enrich")

    p_ask = sub.add_parser("ask")
    p_ask.add_argument("question", help="Question to ask")
    p_ask.add_argument("-k", type=int, default=4, help="Number of evidence chunks")
    p_ask.add_argument("--raw", action="store_true", help="Print raw retrieved evidence chunks instead of LLM answer")

    p_chat = sub.add_parser("chat")
    p_chat.add_argument("-k", type=int, default=4, help="Number of evidence chunks")

    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--port", type=int, default=8000, help="Port to listen on")

    sub.add_parser("all")

    p_build = sub.add_parser("build-release", help="Build an immutable release from the corpus + migrated evidence")
    p_build.add_argument("--device", default="cpu")
    p_build.add_argument("--no-embed", action="store_true", help="structure only (no vectors) for inspection")
    p_eval = sub.add_parser("evaluate", help="Run the spot-check set against a release and write validation.json")
    p_eval.add_argument("--release")
    p_eval.add_argument("--min-legacy-pass", type=float, default=1.0)
    p_act = sub.add_parser("activate", help="Point serving at a validated release")
    p_act.add_argument("--release")
    sub.add_parser("rollback", help="Restore the previously active release")

    sub.add_parser("review-sheet", help="Write review/critical_facts.{csv,md} for the latest release")
    p_rr = sub.add_parser("review-records", help="Record a decision for pending facts")
    p_rr.add_argument("--decision", choices=["approved", "rejected"], required=True)
    p_rr.add_argument("--reviewer", required=True)
    p_rr.add_argument("--kind")
    p_rr.add_argument("--id", action="append")
    p_rr.add_argument("--notes", default="")

    p_audit = sub.add_parser("audit", help="Report documents with extraction defects")
    p_audit.add_argument("--dir", help="Markdown corpus directory (default data/processed_knowledge_base)")

    args = parser.parse_args()
    cfg = get_config()
    stores = Stores(cfg.work)

    cmds = {
        "register": cmd_register,
        "triage": cmd_triage,
        "extract": cmd_extract,
        "structure": cmd_structure,
        "verify": cmd_verify,
        "chunk": cmd_chunk,
        "enrich": cmd_enrich,
        "ask": cmd_ask,
        "chat": cmd_chat,
        "serve": cmd_serve,
        "all": cmd_all,
        "audit": cmd_audit,
        "review-sheet": cmd_review_sheet,
        "review-records": cmd_review_records,
        "build-release": cmd_build_release,
        "evaluate": cmd_evaluate,
        "activate": cmd_activate,
        "rollback": cmd_rollback,
    }

    fn = cmds.get(args.command)
    if fn:
        fn(args, cfg, stores)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

