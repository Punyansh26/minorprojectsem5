# Institute helpdesk project guidance

This directory is the text reasoning layer for an eventual college speech helpdesk.
The current scope is English, Hindi, and Hinglish text conversations. Chhattisgarhi remains
experimental. Implement audio/telephony only when requested. Parent guidance requires the
existing `minor` Conda environment; on this machine use
`/home/rtx/miniconda3/envs/minor/bin/python`. Preserve shared speech/model dependencies.

## Behavior invariants

- Local Ollama is the default reasoning provider. Groq is an explicit alternative, never an
  automatic fallback. Resolve per-turn `configurable.llm_provider` through the shared model
  layer; browser sessions must not mutate process settings. Speech retries retain the original
  turn's provider. Report labels and speech rendering use the same provider boundary.
- Prepare local tokenizers with `setup_local.py`; inference never downloads them. Match the
  tokenizer to the model. Budget whole history pairs and evidence excerpts before cache lookup,
  reserving draft and review output. Keep full Pydantic validation even when Ollama's grammar
  omits string/numeric bounds. Retain grounding review and exact citation checks for local models.
  Local evidence grammars select verbatim spans tied to source IDs; that constrains provenance,
  not factual correctness. Never treat successful structured decoding as a substitute for review.
- Institute facts must come from indexed approved sources. Off-topic turns receive a helpdesk
  redirect. Missing evidence produces an explicit inability to verify plus a staff-review offer.
- Run the grounding review before returning an answered result. A valid quote/source
  reference proves provenance, not full factual correctness. When changing
  grounding or prompts, inspect real answers against their original documents as well as tests.
- Groq 429 failures may retry the failed model call once within
  `LLM_RATE_LIMIT_MAX_WAIT_SECONDS`. Never bypass grounding or replay action nodes to
  recover from a provider quota. Exhausted limits remain `unavailable`, not KB gaps.
- Public-document category predictions are retrieval preferences, not access controls. Student
  category and ID are unverified context. Use independent random conversation IDs per caller.
- Only explicit staff-review requests or acceptance of a pending offer create tickets. Tickets
  are local drafts awaiting review; the graph never sends email or promises a response time.
- Reminder writes require validated details and confirmation. Keep them disabled until SMTP
  and the checker schedule are configured. Never claim that saving proves delivery readiness.
- Each turn must replace answer/status/sources/action IDs. Keep pending actions separate from
  turn output so a greeting cannot re-display old citations or imply another ticket was created.

## Change and verify

Read README.md for setup, knowledge-base maintenance, limitations, and the speech adapter
contract before changing retrieval, indexing, or the graph interface. Keep settings and env
reads in `assistant/config.py`; document new options in `.env.example`. Never expose `.env`.

Run `python -m pytest -q` in `minor` for behavior changes. Tests must use temporary databases,
local fake embeddings, and mocked model/actions. Use `evaluate_helpdesk.py --live --provider ollama`
(or `--provider groq`) for real model checks; it blocks ticket/reminder writes and saves answer evidence. Respect
provider quotas. Report live failures separately from offline test results.

- Keep `answer_text` suitable for speech; citations belong in `sources`. All graph state must
  be serializable. Preserve the CLI and future adapter result contract together.
- Build and query with the same embedding model and telemetry settings. Existing untagged
  indexes use all-MiniLM-L6-v2. Rebuild into a new collection before changing the model.
- Rebuild verified evidence using `kb_pipeline.py` into immutable releases; never edit an
  active collection. `active.json` switches Chroma and the structured sidecar together only
  after evaluation passes. Preserve the previous release and original index on failure.
  The original legacy builder requires stopped query processes and refuses to run while a
  verified release is active. Never put synthetic fixtures into `knowledge_base`.
- Verified releases use reviewed source/row years, periods and historical flags; legacy
  retrieval retains filename filtering. Never substitute publication dates for statistic
  periods or relabel historical material as current. Failed fetches are not fresh evidence.
- Every cutoff preserves authority, year, round, branch, quota, category, seat pool and rank
  basis. Use exact sidecar lookup; never substitute another category or quota's vector match.
  Short recognized category/round follow-ups edit the latest resolved query literally;
  other follow-ups use normal routing. This carries scope only, never prior answer facts.
- OCR and visual interpretations require an approval tied to the source SHA, reviewer and
  date. Retain page/crop evidence. General scholarship/loan rules do not establish institute
  or student eligibility; retain exclusions with benefits. Offline questions are not facts.
- The shared release root defaults beside absolute KB_DIR. Demo 2 and the text CLI use that
  same pointer, but keep conversations/tickets separate. Preserve additive citation fields.
  Tests must override KB_STATE_DIR or mock retrieval, so an active local release is not read.
- The no-op Chroma telemetry component handles the pinned Chroma/PostHog API mismatch;
  simply disabling `anonymized_telemetry` does not stop that obsolete API call in Chroma 0.5.23.
- Keep student messages, emails, databases, and provider exception bodies out of logs/artifacts.
  History trimming bounds active state; it does not implement checkpoint retention.
- History is bounded in complete question/answer pairs (`HISTORY_TURNS`, default 10 without
  legacy overrides) and by `HISTORY_MAX_CHARS` in prompts. Routing, generation and review
  use the same window; resolved queries in message metadata carry scope, never factual evidence.
  Every reply branch must pass through finalization to trim pairs and attach turn metadata.
- Resolve one immutable KB release per turn before cache lookup. Draft keys include history,
  language, self-reported category, source contents, model, prompts/schema and date. Cache
  only nonempty verified retrieval and fully reviewed/citation-validated answers as drafts.
  Always run grounding review on draft hits; reject unverifiable cited quotes. Verified
  cutoff quotes may expand ordered, uniquely matching complete lines into the exact
  canonical source span, restoring omitted qualifiers. Store/cite that expanded span;
  altered values, reordered lines, legacy and unstructured sources stay strict. Never cache
  actions or failures. Cache errors fall back; mutable legacy indexes bypass caching.
- `rag_metrics` is additive adapter metadata: cache outcomes, history pairs, logical model
  calls (provider retries excluded), and stage milliseconds. Never log cache inputs. CLI
  and Demo 2 caches are separate SQLite files. No cache file is committed.

Update this file when these project-specific invariants or integration contracts change.

## Optional local Open Jev routing

Before modifying the classifier, training data, acceptance policy or activation,
read `docs/OPEN_JEV.md`. `JEV_ROUTING_MODE` defaults off. Enabled mode requires
matching checkpoint/tokenizer hashes and passing quality, latency and source-review
records; never route with random weights. Keep fallback on the turn's selected
provider and preserve LLM query rewriting, grounding review and action consent.
Train only on synthetic/public examples; keep topic families across all languages
in one split. Model artifacts remain outside Git and outside the knowledge base.

For English recovery training or backend changes, read `docs/ENGLISH_ROUTER_RECOVERY.md`.
All JEV shortcuts are English-only; other languages retain LLM routing. Treat
`english-v2` results as development evidence. Activation additionally requires a
fresh final holdout and independent human review. Preserve the old pilot artifacts
and the KB embedding model.

Before changing v3 routing, query preparation, training or speed measurement,
read `docs/ENGLISH_ROUTER_SPEED.md`. V3 supports bounded institute scoping and
exact English rank follow-ups; retain v2's original policy. Distinguish classifier
and deterministic coverage. Keep optional retrieval preference in both retrieval
calls and cache keys. V3 activation requires three controlled full trials and the
same independent final-holdout/source-review gates.

English `audit` freezes the existing policy before extra development predictions;
`freeze` exports passing calibration to a separate immutable artifact. Confirmation
data is calibration exposure, never final gold. `evaluate --holdout --review` requires
a human attestation bound to the exact data and artifact, and never tunes thresholds.
Preserve the shared `english_holdout_exposures.json` beside experiment directories;
reused or partially exposed holdouts cannot become fresh by starting another run.
See `docs/ENGLISH_ROUTER_HOLDOUT.md` for the review schema and evidence files.

`normalize` creates a new artifact with versioned institute-alias normalization for
classifier inputs only. Preserve the original RAG query and reject changed policy
code hashes. Old artifacts retain their original preprocessing. Export may reuse
calibration only if every prior training/calibration message is unchanged by the
normalizer; otherwise recalibration is required. Never inherit activation records.

## Demo2 audit upgrade contracts (30 September 2026)

- `assistant.operations` carries optional per-turn deadline/cancellation/progress through
  context variables; never put Events, locks or callbacks in saved graph state. Check
  the budget before providers/actions and after native waits. Provider timing data uses
  a numeric allowlist; raw response/error bodies and student text are never telemetry.
- Draft action idempotency keys `(conversation_id, turn_id, kind)` commit in the same
  SQLite transaction as the ticket/reminder. Different contents under one key fail.
  This is local draft ownership, not authentication or a delivery guarantee.
- Material-policy templates in a release must bind exact source SHA/page/quote spans in
  English, Hindi and Hinglish. Retain the grounding reviewer and exact citations. Missing
  material evidence or rejected templates abstain. Preserve audience and source conflicts;
  general scheme rules do not establish current institute eligibility.
- Release manifest version 2 binds source/policy/parent content, logical SQL, persisted
  vectors, embedding artifacts and validation. Flush Chroma 0.5's final native batch before
  hashing. Do not edit an active release or relax validation to hide hash mismatches.
  Retired sources and their policies/records leave only through a new evaluated release.
- Demo2 owns 24-hour session/draft/managed-backup retention and deletion across its stores;
  CLI stores remain separate. Cache ownership links are additive, shared entries may be
  invalidated on deletion, and cache payload bytes are bounded independently of row count.
- Keep all manifest-bound JEV policy files unchanged when working on surrounding features.
  Missing activation, corrupt/missing artifacts, timeout and busy are distinct fallback
  reasons. A successful diagnostic benchmark never supplies independent human approval.
