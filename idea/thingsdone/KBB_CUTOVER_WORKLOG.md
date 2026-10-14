# Work log: making `kbb` the knowledge database for Demo 2

Session date: 2026-10-14. This document records what was asked, what was found, what was built, how it was verified, and what is still open. Paths are relative to the repository root (`Minor/`) unless stated otherwise. `KBE` below means `code/knowledgebaseenhanced`, `IA` means `code/Institute-voice-agent/institute-assistant`.

---

## 1. The request and the decisions taken

The user asked me to look at the newly pushed knowledge database (`KBE`, package `kbb`), integrate it into the main application (`code/demo2`), verify that everything works, and build a better database if needed, with the goal of populating it with quality data. I was told to ask before executing the plan.

Questions asked and the answers given:

| Question | Answer |
| --- | --- |
| Feed the old release pipeline, or replace the retriever? | **Make the new one primary and replace the old one.** |
| How far should "build a better database" go? | **Fix the data and build proper typed facts** (fees, dates, faculty, seats, cutoffs, finance), each linked to its source block. |
| How to judge "good enough"? | **Other** (no detail given). I assumed: a fact goes live after an agent spot-check against the page image and the user can override any row. |
| Cutoffs, policies, finance records | **Migrate them into `kbb`** so nothing answerable today is lost. |
| Heavy re-extraction | **Only the documents found broken, one at a time** (no full-corpus run). |
| Who approves critical facts | The agent, with a review sheet the user can override. |
| Does demo2 keep its own answering stack? | **Yes**: LangGraph, grounding pass, qwen3.5:9b or Groq, speech. `kbb/bot.py` (llama3.1:8b) is not used inside demo2. |

The agreed plan had 12 tasks. The old store (`IA/kb_state`) is never modified; it stays on disk as the rollback target.

---

## 2. What the investigation found (before any change)

### 2.1 How demo2 gets its data
`demo2/agent_bridge.py` calls the institute-assistant LangGraph. Retrieval goes `assistant/retrieval.py::retrieve()` → `assistant/kb/search.py::SearchEngine` over the release pointed to by `IA/kb_state/active.json` (release `20260927T010544717749Z`: Chroma index, 611 JoSAA/CSAB cutoff rows, `policies.json`, 758 evidence blocks). `demo2/health.py` verifies that release's hashes. demo2 never read `kbb`.

### 2.2 Problems in the new `kbb` data
- **Hand-written facts.** `kbb/facts.py` contained literal Python lists of fees, seats, dates and placements. They were not extracted from the documents. Their `parent_id` values pointed at pages that do not contain the facts (fees live on brochure page 11, the facts said page 3).
- **Invented value.** The placements fact said `Highest CTC: "Top tier competitive offers across batches"`. The source slide says **120 LPA** (and **Average CTC 18.90 LPA**), which the OCR had dropped.
- **Unsafe retrieval shortcuts.** Any question containing words like "fee", "date", "when" or "exam" was answered from the hand-written table and short-circuited retrieval. The cutoff fallback was `SELECT ... LIMIT 5` with no filters, which returns unrelated ranks.
- **Empty documents.** 11 documents had no body text (heading only): campus facilities, funded initiatives, two faculty pages, AIU certificate, UGC letter, guest-house rules, combined academic regulations, and the three 2022–24 B.Tech curricula.
- **Flattened tables and garbled Hindi.** The brochure fee table had OCR noise (`1, 81, 000. 000`); the cover page had dropped Devanagari conjuncts.
- **Dishonest statuses.** Every element was marked `extracted`, bypassing the dual-read verification and the human-approval rule for critical categories. Page units were hard-coded `extracted`. Merged documents carried fake hashes such as `multi-slide-synthesis`.
- **Missing capabilities.** No cutoffs, policies, finance/scholarship records or source-lifecycle data.
- **What "synthesize" meant.** I checked `scripts/build_markdown_corpus.py`: it merges Tesseract OCR from several images into one file. It does not use an LLM, so the "no LLM-authored evidence" rule was not violated.

### 2.3 Environment limits I had to design around
- **Docling and PaddleOCR are not installed** in the `minor` conda env, and Tesseract has only `eng`/`osd` system-wide. I did **not** install Docling (heavy dependency change without approval). I used what exists: `pdfplumber`, `pypdfium2`, BeautifulSoup, and Tesseract with the pinned `hin.traineddata` found in the old `kb_state/models/tessdata` (read-only use).
- Ollama was running with no model loaded, and the GPU had about 4 GB free, so embedding builds used CUDA briefly and serving uses CPU.

### 2.4 A discovery that shaped the design
The old store had `kb_state/reviews.json`: 13 entries where a reviewer compared the rendered page with the extraction and corrected the text (brochure pages 7, 10, 11, calendar pages 1–2, scholarship notice, finance record). Those corrections are higher quality than the new OCR. I imported them as reviewed evidence rather than discarding them.

---

## 3. What was built (task by task)

### T1. Quality audit and frozen baseline — done
- `KBE/kbb/audit.py`: flags thin documents, garbled Devanagari, flattened tables, OCR number noise, missing page anchors, text claiming to be generated. `kbb_cli.py audit` writes `data/kbb/audit/quality_report.json` (19 high-severity documents of 92).
- `KBE/scripts/baseline_old.py` runs the old engine (CPU) on all 117 reviewed legacy cases and writes `eval/baseline_old.json`: the old store finds the required terms in **93 of 93** answerable cases.
- Tests: `tests/test_audit.py` (9).

### T2. Spot-check set and runner — done
- `scripts/make_spotcheck.py` generates `eval/spotcheck.json`: **156 cases** = the 117 legacy cases (three languages, with the expected source file and page recovered from the old evidence blocks) + 39 new cases for content the old store never covered (seats, eligibility, fees, calendar, faculty, library, placements, FAQ, curriculum, out-of-scope questions). Every expected value was copied from the named source.
- `scripts/spotcheck.py` scores any engine: `answerable` (all terms present and the right file/page), `no_result` (exact lookup misses must return nothing), `answer_review` (not scored; for a human). It writes a side-by-side Markdown report.
- Starting gap measured: old store 124/140, first `kbb` build **12/140** (2 of 105 legacy-origin cases).
- Tests: `tests/test_spotcheck.py` (9).

### T3. Re-extraction of broken documents — done (with the tools that exist)
- `kbb/reextract.py` + `scripts/reextract.py`, processed one document at a time:
  - HTML: `html_reader` now has `prune_nav` (removes menu-like link lists) and skips duplicate nested list items; footer contact lines are added for pages whose body is only a footer.
  - Scanned PDFs: render + Tesseract `eng+hin`, status `needs_review`.
  - Lines with damaged Devanagari are **removed and reported**, never rewritten.
- Recovered: funded initiatives (2,700 words), two faculty pages, campus helpline and address, and OCR text for AIU, UGC, guest house, combined regulations and the three 2022–24 curricula. The previous Markdown is kept as `*.md.prev`.

### T4. Honest verification status — done
- `kbb/corpus.py` loads the Markdown into elements and assigns status per page: born-digital HTML/PDF text → `extracted`; OCR, scans and images → `needs_review` (stored, never served); `approved` only through a recorded review. `machine_verified` is supported by the model but never invented here (no independent second read exists in this environment).
- Pages without anchors in PDFs are judged by text-layer coverage. Real source hashes replace placeholders (merged documents hash their member files).
- `kbb/chunk.py`: page units now take the weakest element status; **parents never straddle pages**, so each citation names exactly one page.
- `kbb/reviews.py`: page-level reviews (exact-once patches or a transcription), bound to the source hash so a changed source voids them. Stored in `review/page_reviews.json`.
- Tests: `tests/test_corpus.py` (10).

### T5. Typed facts — done
- `kbb/facts.py` was rewritten. One `records` table (kinds: fee, seat, date, faculty, placement, cutoff, scholarship, finance). A record is rejected unless its evidence parent exists and is servable, the source hash matches, the **verbatim quote is in the evidence**, and every asserted number or date appears inside that quote. No totals are computed.
- Fee, date and faculty records are derived from table rows (keyed cells). Seats and placements are curated in `config/curated_facts.json` and validated against the evidence by the same rules.
- Critical kinds (fee, date, cutoff, scholarship, finance) are `pending` until reviewed.

### T6. Cutoffs — done
- All **611** JoSAA/CSAB rows were migrated with their original evidence blocks and validated again against the new evidence. `lookup_cutoffs` is exact and parameterised; no match returns nothing. The `LIMIT 5` fallback was removed from `kbb/retrieve.py` and the old structured shortcut was disabled.

### T7. Policies, finance links, source lifecycle — done
- `kbb/legacy_import.py`: reviewed page text replaces new text only where a reviewer actually corrected it (brochure 7, 10, 11; calendar 1–2). Page 8 keeps the new, more complete extraction (the old page-8 block lacked the Chhattisgarh-quota paragraph) and inherits the old metadata (audience, related evidence).
- PM Vidyalaxmi guidelines, the scholarship notice and the JoSAA blocks are imported verbatim. Scholarship/finance records keep their conditions and related pages. The 3-language policy rules re-bind to the new parents, and the build **fails** if any policy quote is not found (none failed).

### T8. Review gate — done
- `kbb_cli.py review-sheet` writes `review/critical_facts.{md,csv}` (value, quote, page, evidence status). `review-records` records decisions in `review/record_reviews.json`.
- I read the sheet, checked each value against its quote and page, and approved 57 fee/date records. Rows from faculty pages (PhD "awarded" dates) were excluded by a builder rule.
- I viewed the guest-house pages and the four placement slides as images and recorded page reviews for them.

### T9. Immutable releases — done
- `kbb/integrity.py` and `kbb/release.py`: `build-release` → `evaluate` (writes `validation.json`) → `activate` (refuses without a passing validation; writes pointer with manifest and validation hashes) → `rollback`. Content hashes cover vectors, units, parents, facts, policies, sources and the extraction report.
- Release state lives in `KBE/data/kbb/serving/`. The `parents.json` uses the institute-assistant block schema, so its nodes, policy rules, cache keys and citations work unchanged.
- **Active release `20261014T005813186766Z`**: 2,055 evidence blocks, 5,153 retrieval units, 784 structured records (611 cutoffs).
- Retrieval fix found while testing: a parent now counts once per channel (its best unit) instead of summing every row-unit, which had let big tables drown prose answers. Domain words ("IIIT", "Naya", "Raipur") are dropped from the sparse query.

### T10. Adapter in institute-assistant — done (tests pass)
- `IA/assistant/kb/kbb_engine.py` (`KbbSearchEngine`) wraps `kbb.release.ReleaseSearch` and returns `RetrievedChunk`. `retrieval.get_release_engine()` dispatches on `engine: kbb` in the manifest. `config.py` gained `KB_BACKEND` (`legacy` default, so its own tests are unaffected) and `KBB_STATE_DIR`. Query embedding runs on CPU.
- `IA/tests/test_kbb_engine.py`: 7 contract tests against the active release (dispatch, provenance, exact cutoff and empty result for a missing rank, matched fee row on page 11, unreviewed OCR never served, eligibility filter, embeddings for gap analysis). All 7 pass.

---

## 4. Results so far

| Measure | Old store | First `kbb` build | New release |
| --- | --- | --- | --- |
| Spot-check pass rate | 124/140 (88.6%) | 12/140 (8.6%) | **137/139 (98.6%)** |
| Legacy-origin cases | 105/105 | 2/105 | **105/105 (100%)** |

Two new-content cases still fail and are known limitations:
- `new_established` ("When did the first academic session start?" → FAQ, 2015).
- `new_curriculum_credits` ("Total Credit : 160" sits in a text block diluted by the letterhead and ranks outside the top 30). Contextual question enrichment (needs an LLM run) would likely fix it.

---

## 5. Findings the user should know about

1. **The NTPC quota seat count contradicts itself in the brochure** (40 seats, but 16 + 17 + 17 = 50). The earlier reviewer marked it "not verified", and the old hand-written `kbb` facts asserted 40. I kept the reviewed text, did not record a number, and turned the matching spot-check case into a human-review case.
2. **FAQ and brochure disagree** on the Chhattisgarh-quota marks rule (FAQ: Physics and Mathematics; brochure: Chemistry, Physics and Mathematics).
3. The old `kbb` facts asserted a placement headline with no number; the slide says 120 LPA.
4. The brochure's own text says "JEE (Main) 2024 Rank card" in a 2026 document (preserved verbatim by the earlier reviewer).
5. About **53 evidence parents remain `needs_review` and are not served**: the 24-slide deck, administrative and academic chart images, remuneration orders, AIU/UGC letters, combined regulations, and the three 2022–24 curricula. They become answerable only after a page review (recorded in `review/page_reviews.json`).
6. Docling and PaddleOCR were not used because they are not installed; installing Docling (with TableFormer) is the recommended way to improve table extraction further.

---

### T11. Demo 2 wiring — done
- `code/demo2/settings.py`: `configure_agent()` sets `KB_BACKEND=kbb`, `KBB_ROOT` and `KB_STATE_DIR` (the kbb serving directory) before the agent is imported. `DEMO2_KB_BACKEND=legacy` follows the old `kb_state` instead; any other value is rejected.
- `code/demo2/health.py`: a kbb branch verifies the content hashes and reports release id, engine, chunks, evidence blocks, cutoff records, structured records, parents by status and the number of pending critical reviews. The legacy branch is unchanged.
- `code/demo2/tests/test_kbb_backend.py` (4 tests). Real run of the LangGraph `retrieve_node` through demo2's configuration returned the page-11 fee row and the "Highest CTC | 120 LPA" row from release `20261014T005813186766Z`.

### T12. Cutover and cleanup — done except the live-model run
- Release `20261014T005813186766Z` is active. Gate: spot-check 137/139 (98.6%), legacy-origin 105/105.
- Documentation: `code/knowledgebaseenhanced/README.md` rewritten, `AGENTS.md` command list updated, `code/demo2/KNOWLEDGE_BASE.md` has an update note and the rollback switch.
- **Not verified: a full answer from the local model.** `agent_bridge.ask` stops with "Local tokenizer is missing" (`~/.cache/institute-assistant/qwen3-tokenizer.json`). That file is a download done by `institute-assistant/setup_local.py`; I did not run it because it fetches from the network. This is independent of the knowledge base. Retrieval, grounding inputs and all unit tests were verified instead (see section 4a).

### Cleanup (requested during the session)
Deleted (112 paths, about 369 MB), after checking each was superseded or regenerable and that the active release and rollback targets were untouched:
- The first `kbb` index (`data/kbb/index/build_1791935621`, `latest_build.json`, `units_all.json`, `parents_all.json`): it held the hand-written facts and the unfiltered cutoff fallback.
- 12 intermediate kbb development releases in `data/kbb/serving/releases` (only the active one is kept).
- Regenerable caches: `data/kbb/cache/pages` (rendered page images), `data/kbb/scratch`, all `__pycache__` and `.pytest_cache` directories in the three projects.
- Eleven `*.md.prev` backups of the re-extracted Markdown files (the previous versions are in git).
- Superseded code: `scripts/index_markdown_corpus.py` (wrote the old index and regex facts), `kbb/export_legacy.py`, the `index` and `export-legacy` CLI commands, the old `KnowledgeRetriever` and the `kbb-build:` option of `scripts/spotcheck.py`. `kbb/retrieve.py` now adapts the active release; `kbb/bot.py` and `ask/chat/serve` read it.
- Seven unused legacy releases in `institute-assistant/kb_state/releases` (never activated or older than the rollback target).
- `tests/test_rag_bot.py` was rewritten for the release (it asserted the removed hand-written facts).

Deliberately kept (needed for rollback or still referenced): the legacy active release `20260927T010544717749Z` and its rollback target `20260922T095421217856Z`, the legacy `kb_state` sources/blocks/records/reviews/raw/models, the whole `institute-assistant` package and its pipeline, and demo2's runtime data and evaluation reports. These are candidates for a later removal once the user confirms the legacy rollback is no longer wanted.

### 4a. Test results after the cleanup
`knowledgebaseenhanced`: 41 passed. `demo2`: 42 passed. `institute-assistant`: 286 passed (279 existing + 7 new kbb engine contract tests).

---

## 6. Still open
- A full spoken/typed answer through the local model could not be verified here (missing tokenizer file, see T12). Run `python setup_local.py` in `institute-assistant`, then `bash run.sh` in `code/demo2` and ask the fee, dean and placement questions.
- About 53 evidence parents are `needs_review` and not served (slides, charts, remuneration orders, AIU/UGC letters, combined regulations, 2022–24 curricula). Each becomes answerable after a page review.
- 122 sources have no named owner or review-by date (`source_owner: unassigned`); the legacy store had them only for a few sources. Health reports the count.
- Two spot-check misses (FAQ establishment year; curriculum total credits).
- Decision for the user: delete the legacy `kb_state` and the legacy pipeline once the rollback is no longer needed.

---

## 7. How to use and roll back

```bash
cd code/knowledgebaseenhanced
python kbb_cli.py audit                      # corpus quality report
python kbb_cli.py build-release --device cuda
python kbb_cli.py review-sheet               # facts awaiting a decision
python kbb_cli.py review-records --decision approved --reviewer "<name>" [--kind fee]
python kbb_cli.py evaluate                   # spot checks -> validation.json
python kbb_cli.py activate                   # point serving at it
python kbb_cli.py rollback                   # previous kbb release
python scripts/spotcheck.py --engine legacy --engine release:data/kbb/serving/releases/<id>
```

Roll back to the old store: set `KB_BACKEND=legacy` and `KB_STATE_DIR=code/Institute-voice-agent/institute-assistant/kb_state`. The old release was never changed.
