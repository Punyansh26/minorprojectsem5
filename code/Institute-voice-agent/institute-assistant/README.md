# IIIT Naya Raipur Institute Helpdesk

A text helpdesk built with LangGraph, local Ollama inference (default), optional Groq, and a local Chroma knowledge base. Replies are
short enough for a future phone interface. English, Hindi, and Hinglish are supported;
Chhattisgarhi is experimental and falls back to Hindi or clarification. The
[Demo 2 browser adapter](../../demo2/README.md) provides speech input/output; telephony
and continuous audio streaming remain future work.

## Project status

The text helpdesk is implemented for English, Hindi, and Hinglish. It has a CLI, a local
indexed knowledge base, source-backed answers with a grounding review, off-topic redirects,
and an explicit fallback when evidence is missing. Staff-review requests create local draft
tickets. Reminders collect and confirm details, but remain disabled until delivery and the
checker schedule are configured. Browser speech is implemented in Demo 2; this package
provides its shared reasoning layer and the standalone text CLI.

Recent fixes include isolated conversation IDs, per-turn output resets, confirmation before
action writes, safer index rebuilds, and a no-op Chroma telemetry component for the pinned
Chroma/PostHog mismatch. Groq 429 handling retries only the failed model call once within a
configured wait budget; exhausted limits return `unavailable`. The current default is
local `qwen3.5:9b` with `TOP_K=6`; existing Groq model configuration remains available
through explicit selection.

The rebuilt database uses local multilingual E5 embeddings, structured PDF/OCR extraction,
and an exact SQLite sidecar for category-specific ranks. The current audit covers 611 official
JoSAA cutoff rows (2022–2026), the supplied institute documents, a 2026–27 Chhattisgarh
scholarship notice, and government-hosted PM-Vidyalaxmi guidelines. See
[rebuild validation](docs/KB_REBUILD_VALIDATION.md), [source inventory](docs/KB_SOURCE_INVENTORY.md),
and [offline questions](../../demo2/OFFLINE_INFORMATION_NEEDED.md).
The October 2026 technical audit implementation passes **279 agent tests and 37 Demo 2 tests (316 total passing, 0 failures)**.
Key additions include:
- Multi-evidence block citation page attribution (`[Page X]`) in `record_text()` for exact condition provenance (F18).
- Multilingual query expansion in `search.py` covering Hindi loan repayment terminology variants (`विद्यालक्ष्मी`, `अवधि`, `मोरेटोरियम`, `चुक`) (F12).
- Real-time cache telemetry counters (`hit`, `miss`, `bypass`, `put`, `evict`, `error`, `hit_rate`) and storage reporting in `RagCache.telemetry()` and `maintain()` (F10).
- Deep runtime health inspection and environment summary in `health.py` and `ops.py status` (F01, F13).

See the comprehensive [technical audit implementation report](../../../idea/DEMO2_IMPROVEMENT_REPORT.md)
and [Demo 2 validation record](../../demo2/VALIDATION.md) for live measurements and benchmarks.

## Optional local Open Jev classifier

The [Open Jev pilot](docs/OPEN_JEV.md) adds local intent classification with trained
artifacts, conservative fallback and evaluation-gated activation. It defaults off;
answer generation and grounding review retain the selected Ollama/Groq provider.
See [pilot validation](docs/OPEN_JEV_VALIDATION.md) before enabling it.

The [English-only recovery](docs/ENGLISH_ROUTER_RECOVERY.md) provides pretrained
MiniLM training and corrected rewrite targets. Train locally and return its
development report before final evaluation. Hindi/Hinglish retain LLM routing;
training never enables a model.

The [English v3 speed workflow](docs/ENGLISH_ROUTER_SPEED.md) adds bounded query
preparation, exact English rank follow-ups and neutral retrieval when department
confidence is insufficient. Its benchmark measures total reply latency across
three balanced trials. Training and calibration remain separate from activation.

## Run locally

Use the existing shared `minor` Conda environment. Preserve its speech/model dependencies.
See [local inference setup and provider switching](docs/LOCAL_INFERENCE.md) for model preparation,
context limits, CPU/GPU allocation, and recovery instructions. Local mode needs no Groq key.

```bash
conda activate minor
python -m pip install -r requirements.txt  # only if dependencies are missing
# For a fresh checkout, copy .env.example to .env and prepare its Ollama model.
python setup_local.py
python run_cli.py
```

The CLI accepts `gen`/`general` and `cg`/`CG`. Email is optional and validated when entered.
A student reference is self-reported, not authentication. Each launch creates a fresh random
conversation ID, so entering another person's student ID does not resume their conversation.
Use `/new` to start another conversation and `/quit` to exit.
Set `LLM_PROVIDER=groq` and retain your existing `GROQ_API_KEY` to explicitly use the cloud provider.

## Behavior

- Greetings and thanks use local replies. Other turns use one model call to route the request,
  choose the response language, and rewrite follow-ups into standalone English search queries.
- Questions outside the college helpdesk's scope receive a short redirect. They do not reach
  retrieval, answer generation, or ticket creation. There is no general-knowledge fallback.
- Retrieval combines semantic distance with BM25 keyword ranking and reciprocal rank fusion.
  A predicted category is a preference; documents in other categories remain searchable.
  Admission category is context, not an access-control rule for these public documents.
- Verified releases filter by reviewed source/row years before retrieval. Historical material
  is excluded from undated current questions. Publication years do not replace the period
  a statistic describes. Undated sources remain qualified; a download date does not prove
  a policy is current. Cutoffs use exact year, round, branch, quota, category, seat pool and
  rank-basis fields. Every returned row retains these qualifiers; unspecified dimensions
  are never treated as a student's confirmed category.
- Answers use a validated JSON schema internally. A second model pass reviews claim scope
  and is instructed to remove unsupported additions before the answer is shown. An answered
  result requires at least one valid source ID and a quotation found in a supplied chunk
  after whitespace normalization and case folding. Invalid citations are discarded. This
  check establishes provenance for retained quotes, not support for every claim in the
  answer. Display references come from retrieval metadata, separate from speech text.
- Missing information produces an honest fallback and offers staff review. A ticket is saved
  after an affirmative response, or when the student explicitly requests staff review. The
  reply describes a local pending draft; no office contact or turnaround time is promised.
- Model/index/review failures produce a temporary-unavailable reply. Per-turn sources, action IDs,
  and escalation flags are reset. Model context and active message state are bounded.
- A Groq 429 can retry the failed model call once when a numeric `Retry-After` or
  `x-ratelimit-reset-tokens` delay fits within `LLM_RATE_LIMIT_MAX_WAIT_SECONDS` (default
  45 seconds; 0 disables; maximum 60). If neither header supplies a usable delay, the code
  tries a 5-second pause within that budget. Longer or repeated limits produce a specific
  rate-limit reply. The grounding review is still required before displaying an answer.

## Maintain the knowledge base

The CLI and Demo 2 share `kb_state/active.json`, resolved beside the absolute `KB_DIR`.
A release contains its own Chroma collection, `facts.sqlite`, source snapshot, parent blocks,
model profile and evaluation. A build never edits the active release or original index.
Activation atomically switches both stores; running retrieval follows the pointer on its next
call. Keep the old index for rollback. Use these commands from this directory in `minor`:

```bash
python kb_pipeline.py bootstrap        # first setup: pinned E5 weights and Hindi OCR data
python kb_pipeline.py refresh --discover
python kb_pipeline.py ranks --years 2026 2025 2024 2023 2022
python kb_pipeline.py extract
# Review sources, extracted blocks and charts before building; see below.
python kb_pipeline.py build
python kb_pipeline.py evaluate --baseline
python kb_pipeline.py activate         # requires a complete release and passing evaluation
python kb_pipeline.py report
python ask_kb.py                       # inspect retrieval without calling the LLM
# To restore the previous release (or the original index):
python kb_pipeline.py rollback
```

`--state /absolute/path` precedes the subcommand when using a separate workspace. `evaluate`
and `activate` accept `--release ID`; `refresh --only-new` avoids refetching existing sources.
Refresh is bounded to approved public hosts, file size and source count. Failed downloads
retain cached bytes and their original fetch dates. The JoSAA adapter uses the public form's
ASP.NET state and stores result pages; it never equates JoSAA, CSAB, CG/NTPC or spot rounds.
Local supplied PDFs are identified as local copies, not fresh website downloads.

Maintain titles, URLs, source status, topic, programme, actual years and effective periods in
`kb_sources.json`. Place local PDFs/text under `knowledge_base/` and register their relative
paths in `local_sources`. Source additions default to review, unless explicitly approved.
A refresh does not resolve conflicting circulars automatically: identify superseded notices
and correct source/block metadata before releasing. Never relabel historical facts as current.

Extraction uses pdfplumber for text and tables, local Tesseract English/Hindi OCR for scans
and legacy Indic fonts, and OpenCV grid detection for scanned tables. Crops and page/box
locations remain under `kb_state/assets`; extraction errors are recorded per page. OCR,
figures, chart interpretations and uncertain tables require review before indexing. Charts
are preserved for inspection; precise unlabeled values are not inferred automatically.
Inspect [the review queue](docs/KB_EXTRACTION_REVIEW.md) and `kb_state/extraction_report.json`.

Record approvals/corrections in `kb_state/reviews.json`, keyed by block ID, with exact
`source_sha256`, `reviewer`, `reviewed_at`, and `status: "approved"`. Optional corrected
`text`, `rows`, `years`, `period`, `kind` and `historical` fields retain verified scope. A changed
source hash invalidates an old approval. Re-run `extract` after review. Inspect numerical
amounts, units, dates, category conditions and row headers against the rendered source.
The current fee table, two calendar pages, NIRF summary tables and CG scholarship notice
were visually reviewed; the remaining queue is explicitly excluded from factual answers.

Curated scholarships/finance records in `kb_state/manual_records.json` require approved
source excerpts, conditions and explicit institution applicability. Benefits and exclusions
from different pages remain linked. General scheme guidelines alone do not establish that
IIIT-NR or an individual student qualifies. The offline question checklist is never indexed.

The pinned `intfloat/multilingual-e5-small` model runs locally on CPU with normalized
`query:`/`passage:` embeddings, cached vectors, batches of 32, 350-token chunks and
50-token overlap. Complete table rows and source headings remain attached. Overlong rows
are rejected for review rather than silently truncated. BM25 and semantic candidates are
combined with reciprocal rank fusion; short parent evidence is restored for context.
The legacy `RETRIEVAL_MAX_DISTANCE` threshold applies only to the original MiniLM path.
See `.env.example` for the `KB_*` settings. Tesseract must be installed with English data;
`bootstrap` downloads Hindi data. No embedding/OCR inference calls an external model API.

Evaluation uses 117 English/Hindi/Hinglish cases, verified evidence targets, and exact numeric
checks. Activation requires at least 90 cases, evidence recall >= 90%, and every exact-rank
case passing. This is a retrieval gate, not proof of generated-answer correctness. Review
live answers separately with `evaluate_helpdesk.py --live --release ID`. Source additions or
changes may require updating the source-backed evaluation set.

`build_index.py` is the legacy maintenance command and refuses to modify the old collection
while a verified release is active. Heavy runtime files are ignored by Git; back them up or
rebuild them when moving machines. Keep model weights, source bytes and reviews together
for auditability. Original collections, conversations and tickets are preserved.

## Staff review and reminders

```bash
python review_tickets.py  # shows pending drafts; asks staff before sending each email
python kb_gap_report.py
```

Replace example office recipients and configure SMTP before approving delivery. The graph
never sends emails. Gap reports use saved review tickets; declined handoffs are not recorded
as tickets, so those reports are not a complete unanswered-question log.

Reminders are disabled by default. To enable them, configure SMTP, set
`REMINDERS_ENABLED=true`, and arrange for `python check_reminders.py` to run regularly.
The reminder conversation collects a valid date and email, presents the details, then saves
only after confirmation. Relative dates use `TIMEZONE` (default `Asia/Kolkata`). These are
calendar-date email reminders, not timed phone notifications. Scheduling the checker is a
separate operational step; saving a reminder does not prove that the scheduler is running.

## Verification

### Conversation history and frequent-query caching

Each private conversation ID retains complete question/answer pairs. `HISTORY_TURNS=10`
sets how many previous pairs can inform the next turn, separately from retrieval's `TOP_K`.
Routing, answer generation and grounding review receive the same recent history. Resolved
questions are saved with replies so “and for ST?” followed by “and round 4?” can retain
the original programme, year and quota. History is conversational context, never evidence
of institute facts. Ambiguous references require clarification.

`HISTORY_MAX_CHARS=12000` limits serialized prompt history, dropping the oldest complete
pairs first; unusually long conversations can therefore use fewer than k pairs. Explicit
`HISTORY_TURNS` takes precedence over deprecated `HISTORY_MESSAGES`. Without the new option,
an explicit legacy count uses `HISTORY_MESSAGES // 2` pairs; without either, the default
is 10. Finalization keeps the latest k complete pairs in active state. Older SQLite
checkpoints are not deleted. `/new` starts a separate session.

`RAG_CACHE_ENABLED=true` enables a disposable persistent SQLite cache at `RAG_CACHE_DB_PATH`
(default `rag_cache.sqlite`). It holds at most 2,000 entries across retrieval and drafts,
expires entries after one hour, and evicts the least frequently used entries first (oldest
access breaks ties). Individual entries are capped at 128 KiB. These limits and the short
database timeout are configurable in `.env.example`. Cache errors fall back to normal RAG.

Only exact effective inputs match. Retrieval keys include the resolved question, retrieval
parameters, local date and immutable release. Draft keys additionally include the original
question, bounded history, language, profile category, full sources, prompts/schema and model
configuration. Changing context can produce a draft miss even when the wording repeats.
Raw histories/profile inputs are not stored as cache keys; only their hashes are saved.
Cached values contain evidence or answer drafts, so treat the local database as application
data. It is ignored by Git and never included in logs.

An answered result is admitted as a draft only after grounding review and all quoted
citations pass validation. Draft hits still run grounding review and citation validation:
they save one generation call, not all model calls. Failed, insufficient, clarification and
action results are never cached. Each turn pins one release before lookup; subsequent turns
follow a newly activated release. Mutable legacy indexes bypass caching. Restarting preserves
eligible entries; changing configuration requires restarting the app. Set `RAG_CACHE_ENABLED=false`
to bypass it without changing the KB.

For verified structured cutoff records, a model quotation that skips an intervening line
(such as rank basis) is expanded into the exact source span when all quoted lines match
uniquely and in order. The citation includes the restored qualifier. Changed values,
partial/reordered lines and unverified or unstructured sources remain subject to strict
validation. This avoids rejecting supported answers solely because the model omitted a
line while copying a table; it adds no model calls and does not bypass grounding review.

The additive `rag_metrics` result reports `retrieval_cache`/`draft_cache` (`hit`, `miss`,
`bypass`), `history_pairs`, `model_calls`, and `stage_ms`. Model calls count logical calls;
provider retries are excluded. Stage timings include nested model timings and must not be
summed together. These metrics contain no questions or profiles.

Run public multi-turn checks and cold/warm comparisons with:

```bash
python evaluate_helpdesk.py --live --case followup_english --cache-benchmark --interval 30
python evaluate_helpdesk.py --live --case cache_exact --cache-benchmark --interval 35
python evaluate_helpdesk.py --live --case followup_hindi --case followup_hinglish --interval 30
```

Evaluation uses temporary caches and memory-only conversations, blocks action writes, saves
resolved queries/source quotations/timings, and checks retained cutoff dimensions. Warm runs
start fresh conversations; exact draft hits also require identical rewritten queries and
history. Report provider-blocked checks separately and inspect real answers against source
evidence. Timings exclude deliberate inter-turn pauses.
See [the dated memory/cache validation report](docs/RAG_MEMORY_CACHE_VALIDATION.md) for
offline results, live timings and source inspection.

```bash
python -m pip install pytest  # if unavailable in minor
python -m pytest -q
python evaluate_helpdesk.py --live --output /tmp/helpdesk-evaluation.json
# Run selected live cases, with spacing to respect provider quotas:
python evaluate_helpdesk.py --live --case hindi_admissions --case followup --interval 30
```

Offline tests use fake model decisions, deterministic local embeddings, temporary Chroma
collections, and memory-only graph sessions. They cover routing boundaries, grounded output
validation, cross-category search, old-source exclusion, action consent, state isolation,
reminder validation, telemetry, index rebuild preservation, local context budgets and provider
isolation. The current run passed 142 tests; remaining warnings are Chroma/LangChain Pydantic deprecations.

The live evaluation calls your selected local or Groq model with the existing KB, blocks ticket and
reminder writes, and saves all answers and quotes for inspection. Status and language checks alone do not
prove factual accuracy. Review the outputs against the original documents. Groq quotas can
cause `unavailable` results. SDK retries (`LLM_MAX_RETRIES`) default to zero; keep them disabled
to avoid adding unbounded provider waits to the application's single bounded retry. Lower
`LLM_RATE_LIMIT_MAX_WAIT_SECONDS` for a speech adapter with a tighter latency budget.
JSON mode is validated locally because it guarantees JSON syntax, not
schema adherence ([Groq documentation](https://console.groq.com/docs/structured-outputs)).

For the reported fee/rank questions, run `--case fee_structure --case sc_ntpc_rank
--case cg_obc_rank --interval 30`. The supplied B.Tech 2026 brochure contains its fee table on
page 11. The current indexed corpus has no SC–NTPC or CG–OBC opening-rank table; those
questions should clarify missing details or offer staff review until an approved cutoff
document is added and indexed. Historical opening-rank statistics in the 2022–23 annual
report do not establish current category-specific cutoffs. Rate-limit retries cannot supply
missing evidence or remove an account quota; see [Groq's rate-limit documentation](https://console.groq.com/docs/rate-limits).

Chroma 0.5.23 calls an obsolete PostHog API even with its telemetry flag disabled. Both indexing
and retrieval use a configured no-op telemetry component, avoiding those calls without
changing the shared PostHog installation. Chroma/Pydantic deprecation warnings may still
appear in tests; those are separate from the fixed telemetry errors.

## Speech adapter contract

Call `build_graph()` once per service process. Pass one final recognized utterance as a
`HumanMessage` per turn and use a random, private ID per call as `configurable.thread_id`.
Serialize turns within a session. For an async speech service, run the synchronous graph in
a worker thread; do not block the audio event loop.
Pass `configurable.llm_provider` as `ollama` or `groq` to select the provider for a turn;
when omitted, the configured default applies. Demo 2 carries this choice through audio
rendering and retries without changing process-wide settings.

| Result field | Consumer |
| --- | --- |
| `answer_text` | Text to speak; contains the full reply for this turn |
| `response_status` | `answered`, `smalltalk`, `out_of_scope`, `clarification`, `insufficient`, `unavailable`, `confirmation`, `handoff`, `reminder`, or `cancelled` |
| `sources` | UI/audit metadata: source file, page, category, exact quote; verified releases add official URL, title, period, block ID, kind, extraction method and asset reference |
| `ticket_id`, `reminder_id` | IDs only when that action was successfully saved this turn |
| `language` | `english`, `hindi`, or `hinglish` after language routing |
| `rag_metrics` | Provider/model names, cache hit/miss/bypass, history pairs used, logical model calls, and stage timings in milliseconds |
| `llm_error` | Optional safe recovery message for provider failures; never raw provider response text |

The public result fields are additive to LangGraph's state. `build_graph(checkpointer=...)`
accepts an injected checkpoint store for testing or service integration. When using the default
SQLite store, close `graph.checkpointer.conn` when the service shuts down.

This remains a local demo foundation. Source quotations validate provenance; the model-based grounding review reduces scope errors
but cannot guarantee semantic correctness. A model can still misinterpret a real quote. Undated sources and uncertain effective periods
need human review. Before public deployment, evaluate a representative question set with
college staff, authenticate access to any private student data, define checkpoint retention,
and configure the actual delivery/scheduling service. Active history trimming does not delete
older SQLite checkpoints. Concurrent workers, action retry deduplication, call interruption,
and audio streaming need dedicated integration work in the speech phase.
