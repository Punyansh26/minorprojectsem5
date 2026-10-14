# Knowledge Base Pipeline v2 (`kbb`)

High-fidelity, structure-aware Knowledge Base pipeline for multilingual institutional documents (PDF, scans, office, HTML, text).

## Key Features
- **Parser-First Architecture:** Uses Docling (native layout + TableFormer), PaddleOCR-VL (PP-DocLayout + 0.9B VLM for Hindi/English scans), Lipi (legacy Hindi fonts), and BeautifulSoup (web notices).
- **Dual Read Verification:** Independent second read (Tesseract / Docling-OCR) on all non-native pages.
- **Keyed Table Cell Verification:** Compares `(row_key, col_key, value)` triples across reads to catch swapped rows or columns.
- **Machine Verified Status:** Promotes consenting non-critical scanned pages to `machine_verified`, unlocking previously unsearchable content without sacrificing safety.
- **Multi-Granularity RAG:** Retrieves across section, table, row-fact, and page units; fuses scores with Reciprocal Rank Fusion (RRF); quotes verified parent blocks.
- **Universal Ingestion:** Ingests PDF, images, HTML, DOCX, PPTX, XLSX, legacy Office, ODF, RTF, EPUB, CSV, JSON, YAML, EML, and plain text.

## Quick Usage & RAG Bot Commands

```bash
conda activate minor
cd "/run/media/rtx/Files/Study/Semester 5/Minor/code/knowledgebaseenhanced"

# 1. Ask a question to the RAG Bot (grounded with source citations [S1], [S2])
python kbb_cli.py ask "What is the tuition fee and hostel fee for B.Tech students?"
python kbb_cli.py ask "What was the average package and top recruiters in campus placements?"
python kbb_cli.py ask "When does the orientation program commence and when is semester break?"

# 2. Interactive Terminal Chat
python kbb_cli.py chat

# 3. Launch HTTP REST API Server
python kbb_cli.py serve --port 8000
# Test health: curl http://localhost:8000/health
# Query API:   curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d '{"question": "How many seats are available in CSE?"}'

# 4. Run Test Suites
PYTHONPATH=. python -m unittest tests/test_kbb.py
PYTHONPATH=. python -m unittest tests/test_rag_bot.py
```

## Knowledge Base Architecture

```
Raw Documents (133 files: PDFs, HTML, JPG/PNG)
       │
       ▼ (scripts/build_markdown_corpus.py)
Processed Structured Markdown (92 files in data/processed_knowledge_base/)
  ├── academics/  (16 docs: Syllabus books, curricula, Ph.D. roster, calendar)
  ├── admissions/ (6 docs: B.Tech 2026 brochure, JoSAA reporting, spot rounds)
  ├── faculty/    (38 docs: Individual faculty cards + master directory)
  └── general/    (32 docs: 24-slide presentation, placements, circulars, FAQs)
       │
       ▼ (scripts/index_markdown_corpus.py)
Multi-Granularity Hybrid Index (data/kbb/index/build_1791935621/)
  ├── Dense Vector Store (384-dim multilingual-e5-small on CUDA)
  ├── Sparse BM25 Index (Indic-tokenized retrieval)
  ├── Structured Facts SQL (facts.sqlite: fees, seats, dates, faculty, placements)
  └── Parent Blocks (1,262 parent passages with page provenance)
       │
       ▼ (kbb/bot.py)
Grounded Zero-Hallucination RAG Bot
  ├── Local LLM generation via Ollama (llama3.1:8b)
  ├── Strict citation grounding ([S1], [S2])
  └── Extractive synthesis fallback
```

See [AGENTS.md](AGENTS.md) and [15_KNOWLEDGE_BASE_PIPELINE_V2.md](15_KNOWLEDGE_BASE_PIPELINE_V2.md) for full architecture details and design invariants.
