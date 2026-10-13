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
    index          Stage 7: Build dense embeddings, BM25, and facts.sqlite
    ask            Stage 8: Query the knowledge base and print retrieved evidence passages
    export-legacy  Stage 9: Export verified blocks to `institute-assistant` format
    all            Run full incremental pipeline (cache-aware)
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from kbb.canonical import load_canonical_doc, save_canonical_doc
from kbb.chunk import build_parents_and_units
from kbb.config import get_config
from kbb.enrich import enrich_parents_and_units
from kbb.export_legacy import export_to_legacy_blocks
from kbb.extract.pipeline import extract_document
from kbb.index import build_index
from kbb.llm import LLMClient
from kbb.models import Parent, Unit
from kbb.registry import discover, load_registry
from kbb.retrieve import KnowledgeRetriever
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


def cmd_index(args, cfg, stores):
    print("=== Stage 7: Building Search Index ===")
    build_id = f"build_{int(time.time())}"
    p_path = cfg.work / "parents_all.json"
    u_path = cfg.work / "units_enriched.json"
    if not u_path.exists():
        u_path = cfg.work / "units_all.json"

    parents = [Parent.from_dict(p) for p in read_json(p_path, [])]
    units = [Unit.from_dict(u) for u in read_json(u_path, [])]

    out_dir = build_index(cfg, build_id, parents, units)
    write_json(cfg.work / "latest_build.json", {"build_id": build_id, "path": str(out_dir)})
    print(f"Search index built at: {out_dir}")


def cmd_ask(args, cfg, stores):
    latest = read_json(cfg.work / "latest_build.json")
    if not latest:
        print("No index found! Run 'index' first.")
        return

    index_dir = Path(latest["path"])
    retriever = KnowledgeRetriever(cfg, index_dir)
    print(f"\nQuery: {args.question}\n" + "=" * 60)
    results = retriever.search(args.question, top_k=args.k)
    for idx, r in enumerate(results, 1):
        print(f"\n{r.citation(idx)}")
        print(f"Score: {r.score:.4f} | Status: {r.status} | Source: {r.source_file}")


def cmd_export_legacy(args, cfg, stores):
    print("=== Stage 9: Exporting to Legacy Assistant Format ===")
    p_path = cfg.work / "parents_all.json"
    if not p_path.exists():
        print("Run 'chunk' first.")
        return
    parents = [Parent.from_dict(p) for p in read_json(p_path, [])]
    out_dir = Path(args.out) if args.out else cfg.work / "legacy_export"
    export_to_legacy_blocks(cfg, parents, out_dir)


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
        cmd_index(args, cfg, stores)
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
    sub.add_parser("index")

    p_ask = sub.add_parser("ask")
    p_ask.add_argument("question", help="Question to ask")
    p_ask.add_argument("-k", type=int, default=5, help="Number of evidence chunks")

    p_exp = sub.add_parser("export-legacy")
    p_exp.add_argument("--out", help="Output directory")

    sub.add_parser("all")

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
        "index": cmd_index,
        "ask": cmd_ask,
        "export-legacy": cmd_export_legacy,
        "all": cmd_all,
    }

    fn = cmds.get(args.command)
    if fn:
        fn(args, cfg, stores)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
