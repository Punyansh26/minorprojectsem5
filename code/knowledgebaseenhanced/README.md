# Knowledge Base Pipeline v2 (`kbb`)

High-fidelity, structure-aware Knowledge Base pipeline for multilingual institutional documents (PDF, scans, office, HTML, text).

## Key Features
- **Parser-First Architecture:** Uses Docling (native layout + TableFormer), PaddleOCR-VL (PP-DocLayout + 0.9B VLM for Hindi/English scans), Lipi (legacy Hindi fonts), and BeautifulSoup (web notices).
- **Dual Read Verification:** Independent second read (Tesseract / Docling-OCR) on all non-native pages.
- **Keyed Table Cell Verification:** Compares `(row_key, col_key, value)` triples across reads to catch swapped rows or columns.
- **Machine Verified Status:** Promotes consenting non-critical scanned pages to `machine_verified`, unlocking previously unsearchable content without sacrificing safety.
- **Multi-Granularity RAG:** Retrieves across section, table, row-fact, and page units; fuses scores with Reciprocal Rank Fusion (RRF); quotes verified parent blocks.
- **Universal Ingestion:** Ingests PDF, images, HTML, DOCX, PPTX, XLSX, legacy Office, ODF, RTF, EPUB, CSV, JSON, YAML, EML, and plain text.

## Getting Started

```bash
conda activate minor
cd "/run/media/rtx/Files/Study/Semester 5/Minor/code/knowledgebaseenhanced"

# Run tests
PYTHONPATH=. python -m unittest tests/test_kbb.py

# Inspect CLI commands
python kbb_cli.py --help
```

See [AGENTS.md](AGENTS.md) for full architecture details and design invariants.
