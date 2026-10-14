# Knowledge Base Pipeline v2 (`kbb`)

Structure-aware knowledge base for IIIT-NR documents (PDF, scans, images, HTML). Since 2026-10-14 it is the **only knowledge base used by Demo 2**: Demo 2 serves the active immutable release in `data/kbb/serving/`.

## Principles
- Evidence text is verbatim reader output. A model never writes or edits evidence.
- Scans, OCR and images are `needs_review` (stored, never served) until a recorded page review compares them with the page image (`review/page_reviews.json`).
- Typed facts (fee, seat, date, faculty, placement, cutoff, scholarship, finance) must quote their evidence and only assert numbers printed inside the quote. Critical kinds are served only after a decision in `review/record_reviews.json`.
- Cutoffs are looked up exactly; a missing combination returns nothing.
- Releases are immutable, hash-bound, validated by the spot-check set (`eval/spotcheck.json`) before activation, and can be rolled back.

## Commands
```bash
conda activate minor
cd "code/knowledgebaseenhanced"
python kbb_cli.py audit                       # corpus defects -> data/kbb/audit/quality_report.json
python scripts/reextract.py --doc <doc_id>    # re-read one flagged document (stop Ollama first for OCR)
python kbb_cli.py build-release --device cuda # corpus + reviewed evidence + records -> new release
python kbb_cli.py review-sheet                # review/critical_facts.{md,csv}
python kbb_cli.py review-records --decision approved --reviewer "<name>" [--kind fee]
python kbb_cli.py evaluate                    # spot checks -> validation.json (gate)
python kbb_cli.py activate                    # serve this release
python kbb_cli.py rollback                    # previous release
python kbb_cli.py ask "What is the mess advance?" --raw
python scripts/spotcheck.py --engine legacy --engine release:data/kbb/serving/releases/<id>
python -m pytest tests -q
```

## Layout
```
kbb/audit.py reextract.py corpus.py reviews.py legacy_import.py facts.py release.py integrity.py retrieve.py bot.py
review/        page_reviews.json (page reviews)  record_reviews.json (fact decisions)  critical_facts.{md,csv}
config/        curated_facts.json (seats, placements: quotes validated against evidence)
eval/          spotcheck.json  baseline_old.json  reports/
data/knowledge_base/ (raw)  data/processed_knowledge_base/ (Markdown corpus)  data/kbb/serving/ (releases)
```
Old-store rollback and the history of this change: `idea/thingsdone/KBB_CUTOVER_WORKLOG.md`. See [AGENTS.md](AGENTS.md) for invariants.
