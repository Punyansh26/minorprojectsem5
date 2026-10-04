# 14 — Review of the Proposed Knowledge-Base Methodology

This chapter reviews `code/knowledgebaseenhanced/Knowledge Base Building.md` (the "KBB
proposal": PDF → per-page tagged TXT → LLM-restructured Markdown → structure-aware chunks →
enriched hybrid index). It checks the proposal against the current corpus and against
2024–2026 research, then says what to keep, what to change and what is missing. The
replacement design is in [15](15_KNOWLEDGE_BASE_PIPELINE_V2.md).

## Verdict in one paragraph

The direction is right. Structure-aware parsing and chunking, page-anchored provenance,
fidelity checks, content-addressed caching and an A/B release gate all match current good
practice. Three parts should change:

- **The LLM rewrite of every section** (Stage 4.2) is the riskiest and least necessary step.
  Current document parsers already emit Markdown with headings, tables and reading order.
- **The number-fidelity check** only proves that the *set* of numbers is unchanged. It cannot
  catch a fee or rank that moved to the wrong row or column.
- **The proposed VLM** (a general Qwen2.5-VL-7B in Ollama) is now outperformed by small
  specialised document models that support Hindi and fit easily in 8 GB, such as
  PaddleOCR-VL 0.9B [R1404].

Most importantly, the measured problem is less "semantic search is poor" than
**"41% of extracted content is invisible to search"**: 266 of 644 blocks are pending review.
Fixing coverage safely is worth more than re-chunking what is already found.

## 1. What the corpus and benchmark actually show

Measured on the active release `20260927T010544717749Z` on 2026-10-05 **[Measured-here]**:

| Quantity | Value | Source |
|---|---:|---|
| Extracted blocks / answerable / pending review | 644 / 145 / **266** | `kb_state/releases/…/extraction_report.json` |
| Evidence parents in the release | 758 (611 JoSAA cutoff rows + 147 others) | `parents.json` |
| Non-cutoff evidence text | 174,927 characters | `parents.json` |
| Extraction methods of the 147 non-cutoff parents | 142 native, 5 Tesseract | `parents.json` |
| Supporting-evidence recall@6 (117-case benchmark) | 92/93 = 98.9% | `code/demo2/VALIDATION.md` |
| Source inventory | 75 entries, 26 failed fetches | `code/demo2/VALIDATION.md` |
| Scanned calendar `ACF2026.pdf` | 0 extractable characters | KBB proposal §4 |

Interpretation:

1. **Retrieval over what is indexed already works.** Recall@6 is 98.9% on the existing
   benchmark, so a better chunker cannot raise it much there. The benchmark is saturated, not
   the system. It contains no questions about the 266 pending blocks.
2. **Coverage is the bottleneck.** Scanned pages, figures and many tables start as
   `needs_review` and are excluded by `kb/search.py::eligible`. That is the right safety
   policy, but it hides much of the annual report, the NIRF tables and the scanned calendar.
3. **The corpus is small.** 175k characters of non-cutoff evidence is roughly 45–60k tokens
   (estimated at 3–4 characters per token for mixed English/Hindi). Index size and ANN speed
   do not matter at this scale; parse quality, table fidelity and coverage do.

So the user-reported symptom ("PDFs and images give poor chunks; semantic search often gives
poor results") is real for **scanned, tabular and visually laid-out pages**, and for
questions whose answer sits in pending blocks. It is not a general failure of dense search.

## 2. Stage-by-stage review

| KBB stage | Verdict | Why (evidence) | Change |
|---|---|---|---|
| 0 Intake, SHA-256 registry | ✅ Keep | Matches the existing release discipline | Extend to DOCX/PPTX/XLSX/HTML/images, not only PDF |
| 1 Page triage (native / scanned / legacy font / table-heavy / figure) | ✅ Keep | Routing cheap pages to fast extractors is standard practice | Add a **legacy-font decode** route before OCR (§3.4) |
| 2a Native extraction with Docling, PyMuPDF4LLM baseline | ✅ Keep Docling | Docling is MIT, CPU-friendly, keeps page and bbox per element | Drop PyMuPDF4LLM from the production path (AGPL ⚠) |
| 2b Dual read: Tesseract + general VLM | ⚠️ Change models | Specialised small doc-VLMs beat 72B general VLMs on parsing: PaddleOCR-VL 0.9B scores 92.86 on OmniDocBench v1.5 vs Marker 71.30 and MinerU2-pipeline 75.51, Devanagari edit distance 0.097 vs 0.164 for Qwen2.5-VL-72B [R1404, Reported] | PaddleOCR-VL (or MinerU2.5) as read B; PP-OCRv5/Tesseract as read A |
| 2c VLM figure descriptions | ✅ Keep, low priority | Figures cannot support a numeric answer alone — correct | Use the doc-VLM's chart-to-table output, verified like tables |
| 3 Custom tagged page TXT + parser | ⚠️ Simplify | Re-implements what DoclingDocument JSON / DocTags already store losslessly (elements, page, bbox, tables) [R1408][R1409] | Keep the **page-anchored text view** for humans, generated from the document JSON; don't maintain a second format and parser |
| 4.1 Deterministic Markdown assembly | ✅ Keep | Cross-page paragraph and table merging is needed | Prefer the parser's own merging (MinerU 3.x merges cross-page tables [R1424]); keep anchors |
| 4.2 LLM restructuring of every section with `qwen3.5:9b` | ❌ Replace | Highest risk of silent fact changes. Modern parsers already emit structured Markdown. Costs about an hour of 9B decoding per corpus build on T0 (§3.2) | Let the LLM propose **edit operations** (heading level, FAQ pairing, label→table) as JSON patches over element IDs; never regenerate text |
| 4.4 Fidelity checks (number multiset, coverage, table cell multiset) | ⚠️ Strengthen | A multiset check passes when values swap rows or columns (§3.1) | Add **keyed-cell verification**: (row label, column label) → value, compared across two independent reads |
| 5 Structure-aware chunking, atomic tables, row facts, heading path, parent link | ✅ Keep (core win) | Element-based chunking beat fixed 512-token chunks on FinanceBench Q&A: manual accuracy 48.23% → 53.19% [R1401, Reported] | Use Docling's HybridChunker instead of a custom chunker; add multi-granularity units (§3.5) |
| 6 Enrichment: contextual prefix, bilingual synthetic questions, aliases | ✅ Keep | Contextual retrieval −35% to −49% top-20 failures [R39]; question-based indexing over atomic units raises recall [R1416] | Generate once, cache, A/B. Check the Hindi questions with a native speaker (sample) |
| 7 Index: e5-small → bge-m3 A/B, BM25, facts.sqlite | ✅ Keep | See [04](04_RETRIEVAL_AND_KNOWLEDGE_BASE.md) | Also A/B Qwen3-Embedding-0.6B [R34]; extend `facts.sqlite` to fees, dates, contacts |
| 8 Hybrid + RRF + reranker + parent expansion | ✅ Keep | Matches [04](04_RETRIEVAL_AND_KNOWLEDGE_BASE.md) | — |
| 9 Answering via the existing grounded graph | ✅ Keep | Preserves `evidence.py::source_quote` | Quotes must come from the **original-text layer**, never from LLM-restructured text |
| Evaluation gate (recall@5/@20, coverage, number fidelity) | ✅ Keep, extend | Recall is saturated on the current set | Add parse-quality metrics on our own pages (cell accuracy, text edit distance) and new cases on pending content |
| `machine_verified` status decision (§9 of KBB) | ✅ Recommend adopting | It is the lever that unlocks the 266 pending blocks | Allow only when two independent reads agree on every keyed cell; fees/dates/eligibility still need human approval |

## 3. The five issues that matter most

### 3.1 The number-fidelity check cannot see moved numbers

KBB §5.4.4 checks that every number in the Markdown occurs in the page TXT and that ≥98% of
TXT numbers appear in the Markdown, plus a table **cell multiset**. Consider a fee table:

| Fee | General/OBC | SC/ST |
|---|---|---|
| Tuition | 1,25,000 | 0 |

If restructuring swaps the two value columns, the set of numbers, the set of cells and the
row and column counts are all unchanged. Every check passes, and the bot then tells an SC
student they owe ₹1,25,000. The same failure applies to cutoff rows (category ↔ rank) and
to dates in calendars.

**Fix.** Verify **keyed tuples**, not bags:
$\{(\text{row\_key}, \text{col\_key}, \text{value})\}_{\text{Markdown}} = \{(\cdot)\}_{\text{source}}$.
The source tuples come from the parser's table structure (OTSL/TableFormer cells), and they
are cross-checked against a second independent read for OCR pages. The cleanest way to
guarantee this is not to let an LLM touch cell text at all (§3.2).

### 3.2 LLM restructuring is the wrong tool for this job

Arguments against regenerating each section with the 9B chat model:

- **Risk.** Rewriting is generation, so a silent change is always possible. Grounding then
  depends on a verifier with blind spots (§3.1).
- **Little added value.** Document parsers now output headings, lists, tables and reading
  order directly. PaddleOCR-VL has a separate layout and reading-order model, PP-DocLayoutV2,
  with reading-order edit distance 0.043 on OmniDocBench v1.5 [R1404, Reported]. Docling
  exports Markdown with heading levels from its layout model [R1408].
- **Cost on T0.** Rewriting the whole corpus means generating as many tokens as it contains:
  ≈50k output tokens ÷ ≈17.7 tok/s ≈ 47 minutes of decoding, plus prefill and retries
  (estimate, using the decode rate measured in [01](01_BASELINE_AND_CURRENT_ARCHITECTURE.md) §4.3).
  It also cannot run while Demo 2 is serving.

What the LLM *is* good at here is small structural decisions. Examples: "this ALL-CAPS line
is a level-2 heading", "these two blocks are a Q/A pair", "this label-dot-value list is a
two-column table". These can be emitted as **patches over element IDs**, such as
`{"op": "set_heading", "id": "e42", "level": 2}`. A patch can move or relabel elements but
cannot change their characters. That keeps the benefit and removes the fact-change risk by
construction. See [15](15_KNOWLEDGE_BASE_PIPELINE_V2.md) §4.

### 3.3 The VLM choice is out of date

The KBB proposal suggests "a Qwen2.5-VL-7B-class model … in Ollama". On document parsing,
2025–2026 specialised models are both better and much smaller:

| Model | Size | OmniDocBench v1.5 overall | Hindi / Devanagari | Licence | Fits T0 beside nothing else? |
|---|---:|---:|---|---|---|
| PaddleOCR-VL [R1404] | 0.9B | **92.86** | Yes, 109 languages incl. Hindi; Devanagari edit distance 0.097 | Apache-2.0 | Yes |
| PaddleOCR-VL-1.5 [R1405] | 0.9B | 94.5 (reported) | Same family | Apache-2.0 | Yes |
| MinerU2.5 (1.2B) [R1404 table][R1424] | 1.2B | 90.67 | MinerU 3.x adds "native multilingual OCR" (not verified for Hindi) | MinerU Open Source License (Apache-2.0-based, extra terms) | Yes |
| Docling standard pipeline [R1408] | layout + TableFormer | not on v1.5 table; v1.0 English edit 0.589 | Via OCR engine | MIT | Yes (CPU) |
| Marker 1.8.2 | pipeline | 71.30 | Via Surya | GPL ⚠ / weights RAIL ⚠ | — |
| olmOCR 2 [R1407] | 7B | n/a (82.4 on olmOCR-Bench) | **English-focused** | Apache-2.0 | No (≥12 GB per KBB) |
| Granite-Docling [R1409] | 258M | not reported here | English-centric; other scripts experimental | Apache-2.0 | Yes |
| Qwen2.5-VL-72B (general VLM) | 72B | below PaddleOCR-VL [R1404] | Devanagari edit 0.164 | Qwen licence | No |

Scores are as reported by the PaddleOCR-VL paper on its benchmark tables, not reproduced on
our documents. Benchmarks are Chinese/English-heavy, so they are a guide, not a decision.
The decision comes from the A/B on our own pages ([15](15_KNOWLEDGE_BASE_PIPELINE_V2.md) §9).

### 3.4 Legacy Hindi fonts should be decoded, not OCR'd first

KBB routes Kruti Dev / Chanakya / DevLys pages to OCR. These pages often carry a complete
text layer whose characters are Latin code points drawn with Devanagari glyphs. Open-source
decoders map that layer back to Unicode deterministically: `aparsoft/lipi` handles KrutiDev,
Chanakya and DevLys PDFs, and `krutiextract` reads the logical character stream [R1420].
Decoding is exact when the mapping is correct, and it costs milliseconds. OCR stays the
fallback and the second read for verification.

### 3.5 One chunk size is not enough; neither is semantic chunking

Evidence on chunking units:

- **Semantic chunking** (embedding breakpoints or clustering) is not worth its cost on real
  documents. Fixed-size chunking was as good or better on non-synthetic data, and the
  embedding model mattered more than the chunker [R1400, Reported]. Sentence chunking was the
  most cost-effective in another 2026 study [R1423].
- **Structure-aware / element-based chunks** beat fixed tokens on structured reports
  [R1401]. Prefixing chunks with their heading path improved MRR@5 from 0.374 to 0.463 on a
  1,600-query evaluation [R1422, Reported].
- **Page-level chunks** had the best average and lowest variance across five datasets in
  NVIDIA's study (0.648 accuracy), with factoid queries favouring 256–512-token chunks
  [R1402, Reported].
- **Finer units** such as propositions, atomic facts and synthetic questions improve dense
  recall, especially for rare entities and unsupervised retrievers: Recall@5 +12.0 / +9.3
  points for SimCSE / Contriever, smaller gains for supervised retrievers [R1403, Reported].
- **Combining granularities** gave the best page-level retrieval on FinanceBench (84.4% for
  aggregated element chunks vs 68.1% for 512-token chunks) [R1401, Reported].

The KBB proposal already has sections plus row facts. Add page units and atomic-fact or
question units, all pointing to the same parent evidence block (§6 of
[15](15_KNOWLEDGE_BASE_PIPELINE_V2.md)). Retrieval can then match small units and answer from
the verified parent ("small-to-big").

## 4. What the proposal is missing

| Missing | Why it matters | Where addressed |
|---|---|---|
| Non-PDF formats (DOCX, PPTX, XLSX, HTML notices, photos of notices) | The corpus already includes HTML notices and government web pages; future uploads will be mixed | [15](15_KNOWLEDGE_BASE_PIPELINE_V2.md) §2 (Docling and MinerU 3.x parse these natively [R1408][R1424]) |
| Structured fact tables beyond cutoffs (fees, dates, intake, contacts, scholarship conditions) | Most voice questions are factoid; exact SQL answers are fast and verifiable | 15 §7 |
| Visual page retrieval as a recall safety net | Figures, charts and scanned forms that text extraction misses | 15 §8 (optional, T1+) |
| Whole-corpus-in-context option | Only ≈45–60k tokens of non-cutoff evidence; on a 64k+ context model with prefix caching, retrieval errors can be avoided for broad questions | 15 §10 (T1/T2 only) [R1418] |
| Parse-quality evaluation on our own pages | Public benchmarks are not institute brochures; we need cell accuracy and text edit distance on our hard pages | 15 §9 |
| Update policy (re-fetching, superseded notices, release diffs) | Notices change yearly; stale facts are a grounding risk | 15 §11 |
| Compute budget and runtime plan | VRAM is shared with the chat model on T0 | 15 §12 |

## 5. Does it need improvement at all?

Yes, but the gain will come from different places than the proposal expects:

| Lever | Expected effect | Label |
|---|---|---|
| Re-chunking content that is already eligible | Small on the current benchmark (recall 98.9% has ≤1 case of headroom) | [Estimated from measured saturation] |
| Making pending blocks safely answerable (doc-VLM + second read + keyed-cell checks + `machine_verified`) | Up to 266 more blocks (41% of extracted blocks) reachable; new questions answerable instead of "insufficient" | [Measured-here count; effect on answers to be measured] |
| Correct tables (keyed cells) and structured fact tables | Fewer wrong-row answers; exact lookups for fees/dates | [Estimated] |
| Multi-granularity units + contextual prefixes + reranker | Better ranking on harder, paraphrased and Hindi/Hinglish questions | [Reported elsewhere R39][R1403]; measure on new hard cases |
| Removing the LLM rewrite | Removes the main fact-change risk; saves ≈1 h of GPU per build on T0 | [Estimated, §3.2] |

**Which method to follow:** the hybrid "parser-first, verify-by-structure,
multi-granularity index" pipeline in [15](15_KNOWLEDGE_BASE_PIPELINE_V2.md). It uses
Docling for born-digital files, PaddleOCR-VL for scanned, legacy-font and complex-table
pages, LLM patches only for structure, keyed-cell verification, Docling HybridChunker plus
row facts, atomic facts and page units, and extended `facts.sqlite`. Visual retrieval and
whole-corpus context remain optional add-ons for bigger hardware.

## What we could not verify

- No parser was run on the project PDFs for this report. All parser scores are as reported by
  their papers, mostly on Chinese/English benchmarks.
- MinerU 3.x Hindi accuracy and the exact terms of its new licence were seen only in release
  notes and search snippets.
- `lipi` / `krutiextract` decoding accuracy on our files is untested.
- The token count of the corpus (≈45–60k) is an estimate from character counts.
