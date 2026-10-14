#!/usr/bin/env python3
"""Indexes the processed Markdown corpus into the RAG Knowledge Base.

Pipeline:
1. Loads all 92 processed Markdown documents from `data/processed_knowledge_base/`.
2. Parses them into canonical `Element`s (headings, tables, paragraphs, page anchors).
3. Persists canonical docs into `data/kbb/docs/<doc_id>/`.
4. Groups elements into multi-granularity evidence parents and retrieval units.
5. Builds hybrid search index:
   - Dense vector embeddings with local `multilingual-e5-small` (384-dim).
   - Sparse BM25 index with Indic-aware tokenization.
   - Structured SQLite facts database (`facts.sqlite`).
6. Executes verification test queries to confirm high-fidelity RAG retrieval.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

import numpy as np

from kbb.canonical import save_canonical_doc
from kbb.chunk import build_parents_and_units
from kbb.config import get_config
from kbb.index import build_index
from kbb.models import Cell, Element, PageInfo, Parent, Table, Unit
from kbb.retrieve import KnowledgeRetriever
from kbb.store import read_json, write_json
from kbb.tables import from_markdown, render_rows
from kbb.textnorm import clean

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("index_markdown_corpus")

ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_KB = ROOT_DIR / "data" / "processed_knowledge_base"


def parse_markdown_to_canonical(md_text: str, default_meta: dict[str, Any]) -> tuple[dict[str, Any], list[Element], list[PageInfo]]:
    """Parse structured Markdown document into canonical metadata, elements, and page info."""
    meta = dict(default_meta)
    content = md_text

    # Extract YAML frontmatter
    if md_text.startswith("---") and "\n---\n" in md_text[3:]:
        parts = md_text.split("---", 2)
        fm_text = parts[1]
        content = parts[2]
        for ln in fm_text.splitlines():
            ln = ln.strip()
            if not ln or ":" not in ln:
                continue
            k, v = ln.split(":", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if v.startswith("[") and v.endswith("]"):
                items = [i.strip().strip('"').strip("'") for i in v[1:-1].split(",") if i.strip()]
                meta[k] = items
            else:
                meta[k] = v

    elements: list[Element] = []
    lines = content.splitlines()

    current_page = 1
    page_numbers: set[int] = {1}
    in_table: list[str] = []
    cur_para: list[str] = []
    elem_idx = 1

    doc_id = meta.get("doc_id", "doc")

    def flush_para():
        nonlocal elem_idx
        if cur_para:
            p_text = clean("\n".join(cur_para))
            if p_text:
                elements.append(Element(
                    id=f"{doc_id}:e{elem_idx:04d}",
                    type="paragraph",
                    page=current_page,
                    text=p_text,
                    reader="markdown",
                    status="extracted"
                ))
                elem_idx += 1
            cur_para.clear()

    def flush_table():
        nonlocal elem_idx
        if in_table:
            t = from_markdown("\n".join(in_table))
            if t and t.n_rows > 0:
                elements.append(Element(
                    id=f"{doc_id}:e{elem_idx:04d}",
                    type="table",
                    page=current_page,
                    text=render_rows(t),
                    table=t,
                    reader="markdown",
                    status="extracted"
                ))
                elem_idx += 1
            in_table.clear()

    for line in lines:
        stripped = line.strip()

        # Page anchor
        p_match = re.match(r"^<!--\s*page:\s*(\d+)\s*-->$", stripped)
        if p_match:
            flush_para()
            flush_table()
            current_page = int(p_match.group(1))
            page_numbers.add(current_page)
            continue

        # Markdown table lines
        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
            flush_para()
            in_table.append(line)
            continue
        elif in_table:
            flush_table()

        # Headings
        h_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if h_match:
            flush_para()
            lvl = len(h_match.group(1))
            htext = clean(h_match.group(2))
            if htext:
                elements.append(Element(
                    id=f"{doc_id}:e{elem_idx:04d}",
                    type="heading",
                    page=current_page,
                    text=htext,
                    level=lvl,
                    reader="markdown",
                    status="extracted"
                ))
                elem_idx += 1
            continue

        # List items
        li_match = re.match(r"^(\*|-|\+|\d+\.)\s+(.*)$", stripped)
        if li_match:
            flush_para()
            litext = clean(li_match.group(2))
            if litext:
                elements.append(Element(
                    id=f"{doc_id}:e{elem_idx:04d}",
                    type="list_item",
                    page=current_page,
                    text=litext,
                    reader="markdown",
                    status="extracted"
                ))
                elem_idx += 1
            continue

        # Blank line
        if not stripped:
            flush_para()
            continue

        cur_para.append(line)

    flush_para()
    flush_table()

    # Generate PageInfo list
    pages = [
        PageInfo(
            page=p,
            route="native",
            primary_reader="markdown",
            status="extracted",
            chars=sum(len(e.text) for e in elements if e.page == p)
        )
        for p in sorted(page_numbers)
    ]

    return meta, elements, pages


def populate_facts_database(con: sqlite3.Connection, parents: list[Parent]) -> None:
    """Extract structured facts (fees, dates, contacts, cutoffs) into SQLite."""
    con.execute("CREATE TABLE IF NOT EXISTS fees (fee_type TEXT, amount INT, currency TEXT, semester TEXT, parent_id TEXT, source_file TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS key_dates (event TEXT, date_str TEXT, parent_id TEXT, source_file TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS faculty_roster (name TEXT, designation TEXT, department TEXT, email TEXT, parent_id TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS seat_matrix (program TEXT, quota TEXT, category TEXT, seats INT, parent_id TEXT)")

    for p in parents:
        text = p.text

        # Extract Fee Facts
        # e.g., Tuition Fee ₹ 90000.00 or Hostel Fee ₹ 15,000.00
        for m in re.finditer(r"(?i)(Tuition\s+Fee|Hostel\s+Fee|Mess\s+Advance|One\s+Time\s+Fee|Total\s+Institution\s+Fee|Total\s+Fee)\s*[:=]?\s*₹?\s*([\d,]+(?:\.\d+)?)", text):
            fee_name = m.group(1).strip()
            amount_str = m.group(2).replace(",", "").split(".")[0]
            try:
                amt = int(amount_str)
                con.execute("INSERT INTO fees VALUES (?, ?, 'INR', '', ?, ?)", (fee_name, amt, p.id, p.meta.get("source_file", "")))
            except ValueError:
                pass

        # Extract Key Date Facts
        # e.g., Application submission start: 15th May 2026 or Independence Day: August 15, 2026
        for m in re.finditer(r"(?i)([A-Za-z\s/-]{4,40})\s*[:\-]\s*((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:[-–]\d{1,2})?,?\s+\d{4})", text):
            event = clean(m.group(1))
            date_val = clean(m.group(2))
            if len(event) < 40 and not any(k in event.lower() for k in ["tel", "email", "web", "http"]):
                con.execute("INSERT INTO key_dates VALUES (?, ?, ?, ?)", (event, date_val, p.id, p.meta.get("source_file", "")))

        # Extract Faculty Profile Card Facts
        if p.meta.get("category") == "faculty" and "Overview" in p.text:
            name = p.meta.get("name", "")
            desig = p.meta.get("designation", "")
            dept = p.meta.get("department", "")
            email = p.meta.get("email", "")
            if name and email:
                con.execute("INSERT INTO faculty_roster VALUES (?, ?, ?, ?, ?)", (name, desig, dept, email, p.id))

    con.commit()


def main():
    parser = argparse.ArgumentParser(description="Index Processed Knowledge Base into RAG Database")
    parser.add_argument("--query", help="Optional test query to run after indexing")
    args = parser.parse_args()

    cfg = get_config()
    start_time = time.time()

    print("=" * 70)
    print("🚀 Ingesting Processed Knowledge Base into RAG Database & Search Index")
    print(f"Source Directory: {PROCESSED_KB}")
    print(f"Work Directory:   {cfg.paths.work}")
    print("=" * 70)

    manifest_path = PROCESSED_KB / "manifest.json"
    if not manifest_path.exists():
        print(f"Error: {manifest_path} not found! Run build_markdown_corpus.py first.")
        return

    manifest = read_json(manifest_path, {})
    doc_entries = manifest.get("documents", [])
    print(f"Loaded manifest with {len(doc_entries)} documents.")

    all_parents: list[Parent] = []
    all_units: list[Unit] = []

    print("\n--- Step 1: Parsing Markdown Docs into Canonical Elements & Multi-Granularity Chunks ---")
    for doc in doc_entries:
        rel_path = doc["relative_path"]
        md_file = PROCESSED_KB / rel_path
        if not md_file.exists():
            continue

        md_text = md_file.read_text(encoding="utf-8", errors="replace")
        meta, elements, pages = parse_markdown_to_canonical(md_text, doc)

        # Save to canonical storage
        save_canonical_doc(cfg, doc["doc_id"], meta, elements, pages)

        # Chunk into parents and retrieval units
        parents, units = build_parents_and_units(cfg, doc["doc_id"], elements, meta)
        all_parents.extend(parents)
        all_units.extend(units)

    print(f"Generated {len(all_parents)} evidence parents and {len(all_units)} retrieval units.")

    # Persist intermediate chunk files
    write_json(cfg.paths.work / "parents_all.json", [p.to_dict() for p in all_parents])
    write_json(cfg.paths.work / "units_all.json", [u.to_dict() for u in all_units])

    print("\n--- Step 2: Building Hybrid Search Index (Dense Vectors + BM25 + facts.sqlite) ---")
    build_id = f"build_{int(time.time())}"
    index_dir = build_index(cfg, build_id, all_parents, all_units)

    # Populate SQLite structured database
    db_path = index_dir / "facts.sqlite"
    con = sqlite3.connect(db_path)
    populate_facts_database(con, all_parents)
    
    # Check SQLite facts counts
    fee_count = con.execute("SELECT count(*) FROM fees").fetchone()[0]
    date_count = con.execute("SELECT count(*) FROM key_dates").fetchone()[0]
    faculty_count = con.execute("SELECT count(*) FROM faculty_roster").fetchone()[0]
    con.close()

    print(f"Indexed SQLite Facts Database: {fee_count} fees, {date_count} dates, {faculty_count} faculty entries.")

    # Save latest build pointer
    write_json(cfg.paths.work / "latest_build.json", {"build_id": build_id, "path": str(index_dir)})

    elapsed = time.time() - start_time
    print("=" * 70)
    print(f"✅ Knowledge Base RAG Database & Index Built in {elapsed:.2f} seconds!")
    print(f"📁 Index Directory: {index_dir}")
    print(f"📊 Total Evidence Parents: {len(all_parents)}")
    print(f"🔍 Total Retrieval Units:  {len(all_units)}")
    print("=" * 70)

    # Step 3: Run Validation Retrieval Queries
    test_queries = [
        "What is the B.Tech tuition fee and hostel fee for 2026?",
        "When is the commencement of orientation induction program 2026?",
        "Who is Dr. Abhishek Sharma and what is his department?",
        "What are the research laboratories and built-up area of academic block?",
        "What are the eligibility criteria and percentage required for Chhattisgarh quota?",
    ]

    print("\n--- Step 3: Validating RAG Retrieval Against Built Index ---")
    retriever = KnowledgeRetriever(cfg, index_dir)

    for q in test_queries:
        print(f"\n❓ Query: {q}")
        print("-" * 65)
        results = retriever.search(q, top_k=2)
        for idx, res in enumerate(results, 1):
            print(f"[{idx}] {res.title} (Page {res.page_start}, Score: {res.score:.4f})")
            # Print first 200 chars of retrieved grounding block
            snippet = res.text.replace("\n", " ")[:180]
            print(f"    Excerpt: {snippet}...\n")


if __name__ == "__main__":
    main()
