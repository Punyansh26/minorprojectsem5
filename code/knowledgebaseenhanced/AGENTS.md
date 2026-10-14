# AGENTS.md — Knowledge Base Pipeline v2 (`kbb`)

> **Authoritative operating guide for AI agents and human contributors.**  
> Read this before modifying or executing any part of this package.

---

## 1. System Overview & Core Invariants

`kbb` is a **parser-first, verified-by-structure, multi-granularity** knowledge base pipeline designed for high-accuracy RAG on institutional documents (PDFs, scans, office documents, web notices, tabular reports) in **English, Hindi (Devanagari), and Hinglish**.

### Invariant Rules
1. **The source text is the evidence; nothing generated is:** User answers and `source_quote` citations quote *only* text from official parsers/OCR or approved by human reviewers. Summaries, contextual prefixes, and synthetic questions are strictly retrieval aids.
2. **Never rewrite source facts with an LLM:** Generative models silently hallucinate or alter numbers, dates, and names. Structural corrections (e.g. heading levels, FAQ pairing) are made strictly via JSON patches over element IDs (`{"op": "set_heading", "id": "e12", "level": 2}`). The LLM is never permitted to emit or modify text content.
3. **Verify structure, not bags of tokens:** Table fidelity is verified by checking keyed triples:
   $$\{(\text{row\_key}, \text{col\_key}, \text{value})\}_{\text{Read A}} = \{(\text{row\_key}, \text{col\_key}, \text{value})\}_{\text{Read B}}$$
   Multiset token checks pass when columns swap; keyed-cell checks catch swapped columns.
4. **Any-Format Ingestion:** Ingests PDF, scans, photos, HTML, MHTML, DOCX, PPTX, XLSX, legacy Office (.doc, .xls, .ppt), ODF, RTF, EPUB, CSV, TSV, JSON, XML, YAML, EML, and plain text.
5. **Machine Verified Status:** Scanned pages where two independent reads agree on all keyed cells and numbers are promoted to `machine_verified` (safely unlocking previously unindexed content). Critical categories (fees, deadlines, cutoffs) always require human approval.
6. **Multi-Granularity Retrieval:** Index units at section, table, row-fact, and page levels, all referencing verified evidence `parent_id`s.

---

## 2. Directory Structure

```text
code/knowledgebaseenhanced/
├── AGENTS.md                       # This file
├── README.md                       # Quickstart guide
├── kbb_cli.py                      # Single CLI entry point
├── kbb/                            # Python package
│   ├── __init__.py                 # Version and package invariants
│   ├── config.py                   # Pydantic settings with env/YAML overrides
│   ├── models.py                   # Canonical dataclasses (Cell, Table, Element, Parent, Unit)
│   ├── textnorm.py                 # Devanagari digit folding, number tokens, text cleaning
│   ├── store.py                    # SQLite KVCache (WAL mode), atomic IO, run_lock
│   ├── registry.py                 # Stage 0: Magic byte sniffing, SHA-256 dedupe
│   ├── convert.py                  # Headless LibreOffice converter with isolated profiles
│   ├── render.py                   # Content-addressed page image renderer (pypdfium2)
│   ├── triage.py                   # Stage 1: Page routing (native, scanned, legacy, blank)
│   ├── tables.py                   # HTML/Markdown table parsing & keyed cell generator
│   ├── canonical.py                # Storage manager (meta.json, elements.jsonl, document.md)
│   ├── structure.py                # Stage 4: Deterministic structural assembly & safe patches
│   ├── verify.py                   # Stage 5: Keyed cell and number fidelity verification
│   ├── chunk.py                    # Stage 6: Multi-granularity chunking engine
│   ├── llm.py                      # Unified caching LLM client (Ollama & Groq/OpenAI)
│   ├── enrich.py                   # Stage 6: Contextual prefixes & bilingual questions
│   ├── index.py                    # Stage 7: Dense vector embeddings, BM25, facts.sqlite
│   ├── retrieve.py                 # Stage 8: Hybrid retriever with RRF & parent expansion
│   ├── release.py                  # Stage 7-9: immutable releases + ReleaseSearch (used by Demo 2)
│   ├── extract/                    # Stage 2 reader modules
│   │   ├── __init__.py
│   │   ├── pipeline.py             # Extraction orchestrator
│   │   ├── docling_reader.py       # Docling layout + TableFormer (native & OCR mode)
│   │   ├── paddle_reader.py        # PaddleOCR-VL reader & batch client
│   │   ├── tesseract_reader.py     # Tesseract TSV OCR reader with thread limiting
│   │   ├── legacy_font.py          # Lipi KrutiDev/Chanakya font decoder
│   │   ├── html_reader.py          # HTML/Drupal/MHTML/view-source reader
│   │   └── text_reader.py          # CSV, JSON, YAML, Markdown, Email reader
│   └── workers/
│       └── paddle_worker.py        # Standalone PaddleOCR-VL worker for isolated env
├── tests/                          # Unit tests
│   └── test_kbb.py
└── data/                           # Ingested data & generated artifacts (git-ignored)
    ├── knowledge_base/             # Raw source files
    └── kbb/                        # Generated cache, docs, indices, reviews
```

---

## 3. Environment & Execution Guidelines

- **Active Conda Environment:** `minor`
  ```bash
  conda activate minor
  cd "/run/media/rtx/Files/Study/Semester 5/Minor/code/knowledgebaseenhanced"
  ```
- **Execution Policy:** Do NOT run automatic full-corpus batch runs without explicit user approval.
- **Hardware Budget:** Laptop RTX 4060 (8 GB VRAM). Never run heavy GPU vision inference simultaneously with serving LLMs.

---

## 4. CLI Commands Reference

```bash
# Stage 0: Register all sources and deduplicate
python kbb_cli.py register

# Stage 1: Triage pages by format and layout
python kbb_cli.py triage [--doc DOC_ID]

# Stage 2: Extract content with primary and second readers
python kbb_cli.py extract [--doc DOC_ID]

# Stage 4: Assemble document structure and markdown view
python kbb_cli.py structure [--doc DOC_ID]

# Stage 5: Verify keyed table cells and number fidelity
python kbb_cli.py verify [--doc DOC_ID]

# Stage 6: Chunk into multi-granularity units
python kbb_cli.py chunk

# Stage 6: Enrich units with contextual prefixes and bilingual questions
python kbb_cli.py enrich

# Stage 7: Build an immutable release (dense + BM25 + typed facts), then gate and activate it
python kbb_cli.py build-release --device cuda
python kbb_cli.py evaluate && python kbb_cli.py activate

# Stage 8: Test search query with RRF and parent expansion
python kbb_cli.py ask "What is the B.Tech tuition fee for 2026?"

# Run complete pipeline incrementally
python kbb_cli.py all
```
