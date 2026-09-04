# AGENTS.md

## Purpose and authority

This file describes the project and gives repository-wide guidance to human contributors and coding agents. It applies to the entire repository unless a more specific `AGENTS.md` is later added inside a subdirectory.

The background source is `Chhattisgarhi_Voice_Shopping_Assistant_Proposal2.pdf`. Read the relevant parts of that proposal before making a change that affects scope, research claims, safety, evaluation, or architecture. The proposal originally describes a Flutter client, but the current team decision is **web development only**. The web-client decision in this file overrides the proposal's Flutter/mobile implementation details. If the implementation and the remaining proposal content disagree, do not silently rewrite the project's intent: document the discrepancy and preserve the academically defensible interpretation described here.

## Project identity

### Short description

This is a **Chhattisgarhi voice-to-voice (Speech-to-Speech, or S2S) conversational system** for low-resource-language interaction. It accepts a user's spoken Chhattisgarhi request, understands it through a measurable cascaded speech/language pipeline, executes a constrained domain action, and returns a spoken Chhattisgarhi response.

The current agricultural shopping website is the project's **reference implementation and evaluation environment**. It matters because it supplies real state, structured tools, safety constraints, and end-to-end user tasks. It is not the main novelty by itself. The central engineering and research focus is the reusable, streaming, interruption-aware voice-to-voice layer and its behavior in a low-resource language.

### Core thesis

The project asks whether a predominantly open-source, locally runnable, cascaded S2S system can support accurate, useful, and safe voice interaction in Chhattisgarhi under realistic student-compute and connectivity constraints.

The shopping workflow demonstrates that the voice system can do more than transcribe and repeat speech. It must reliably turn speech into structured actions, maintain transactional state, obtain grounded results, and speak those results back to the user. The same voice core should ultimately be adaptable to other bounded systems such as public-service access, appointment workflows, field operations, education, or enterprise support by replacing the domain tools and policies rather than rebuilding the speech stack.

### Priority order

When time, design, or implementation choices compete, use this order:

1. End-to-end Chhattisgarhi voice-to-voice quality and natural interaction.
2. Measurability, reproducibility, and honest stage-by-stage evaluation.
3. Safety, deterministic execution, privacy, and traceability.
4. Clean separation between the reusable voice core and domain-specific behavior.
5. Correct shopping workflow and transactional state.
6. General web UI polish or expansion of e-commerce features.

Do not optimize the catalogue UI, payments, marketplace features, or vendor operations at the expense of ASR, translation, orchestration, TTS, latency, barge-in, recovery behavior, or evaluation.

## What is novel—and what is not

The project must not claim that ASR, machine translation, TTS, LLM tool calling, or agricultural e-commerce was invented here. The contribution is their careful integration and empirical evaluation as a low-resource-language, voice-to-voice transactional system, including:

- spontaneous Chhattisgarhi speech input rather than a Hindi- or English-first interface;
- an observable cascade whose individual error sources can be measured;
- agricultural/shopping vocabulary adaptation and code-switch handling;
- conversion of informal speech into schema-valid, grounded actions;
- spoken response generation in Chhattisgarhi;
- interruption/barge-in and useful feedback during multi-second inference;
- a hard boundary between permitted transactional help and unsafe agronomic advice;
- a reusable architecture in which the shopping domain is an adapter around the S2S core.

The project should be described as a research prototype, not a production marketplace, production medical/agricultural advisor, or statistically validated deployment.

## Scope and maturity levels

Always distinguish these three levels in code, documentation, demonstrations, and claims.

### Level 1: preliminary work already demonstrated

The team has previously run a local Chhattisgarhi speech pipeline with:

- FastAPI and WebSockets for streaming 16 kHz PCM audio;
- Silero VAD for speech-boundary detection and barge-in events;
- Meta MMS (`facebook/mms-1b-all`) with the `hne` Chhattisgarhi adapter for ASR;
- a pluggable `ASREngine` concept and shared inference workers;
- a Devanagari CTC cleanup step for detached matras;
- Coqui-TTS VITS with custom male and female Chhattisgarhi checkpoints;
- model-level speech pacing through `length_scale`;
- an English-only `faster-whisper` fallback when the selected language is English;
- a telephony adapter for 8 kHz mu-law input as evidence of extensibility.

This preliminary work demonstrates feasibility only. It does **not** establish calibrated WER, production latency, agricultural vocabulary performance, translation quality, safe tool calling, web integration, or user usability.

### Level 2: current Minor Project MVP

The current deliverable is an evaluated Chhattisgarhi S2S prototype connected to a small, curated agricultural catalogue. Its bounded tasks are:

- product search and browsing;
- product details and price queries;
- deterministic quantity calculation from verified metadata;
- add-to-cart and remove-from-cart;
- view cart and total;
- simulated checkout with no payment processing;
- spoken Chhattisgarhi responses;
- safety refusal and KVK referral for diagnostic or dosage advice;
- voice, intent, outcome, and latency instrumentation;
- a minimal responsive web UI that confirms recognized text, products, and cart state.

### Level 3: future work, not a current deliverable

Do not implement or present these as committed MVP features unless the project scope is formally changed:

- real UPI or payment-gateway integration;
- live multi-vendor inventory synchronization;
- seller dashboards;
- delivery routing, tracking, or OTP confirmation;
- unsupervised crop diagnosis or pesticide/chemical recommendations;
- production-scale farmer profiling or analytics;
- broad multilingual support beyond the evaluated Chhattisgarhi path.

Additional languages, domains, telephony deployment, end-to-end multimodal models, and a larger commerce platform are valuable future directions. Keep the architecture open to them, but do not let speculative generality block a strong Chhattisgarhi S2S MVP.

## Research questions

Implementation and evaluation should help answer the following questions:

1. How accurately can informal Chhattisgarhi speech become correct shopping intents and entities such as product, crop, quantity, unit, and area?
2. How much error is contributed by ASR, forward translation, intent/entity extraction, domain execution, response translation, and TTS respectively?
3. Can constrained tool calling produce valid, grounded operations without inventing products, state, prices, quantities, or advice?
4. What end-to-end and per-stage latency does a zero-budget local pipeline have, and how does it compare with an API-assisted option if access is actually available?
5. Does the voice-first interaction improve task completion and usability for Chhattisgarhi-speaking users with limited digital literacy compared with text search?
6. How intelligible, natural, interruption-tolerant, and recoverable is the complete spoken interaction—not just its intermediate text?

The sixth question makes explicit the repository's S2S emphasis. A pipeline is not successful merely because its ASR transcript looks correct; the user must be able to complete the spoken task and understand the spoken result.

## Users and operating conditions

Design primarily for:

- a smallholder farmer who speaks mainly Chhattisgarhi and depends on voice for the whole task;
- a user who code-switches between Chhattisgarhi and Hindi and uses voice to avoid typing and menu navigation;
- a rural user on intermittent 3G/4G connectivity who needs visible/audible progress and clear recovery behavior.

Assume ordinary laptop/desktop browsers and, where useful, mobile browsers; variable microphones and background noise; informal or incomplete utterances; hesitations; accents; code-switching; and unstable networks. The primary release target is a current Chromium-based desktop browser, with Firefox checked for core compatibility where feasible. Do not assume studio speech, constant broadband, high digital literacy, English literacy, or identical codec behavior across browsers.

## Architectural principles

### 1. Treat S2S as a platform layer

Keep the reusable voice pipeline independent from agricultural catalogue and cart logic. The voice core should know how to:

- ingest, validate, decode, and segment audio;
- detect speech boundaries and interruptions;
- transcribe speech with timestamps/confidence where available;
- normalize/translate text;
- invoke a constrained interpretation interface;
- turn grounded response text into streaming speech;
- cancel obsolete work when a user barges in;
- emit detailed timing and error events.

The shopping adapter should know:

- the allowed intents and JSON schemas;
- product vocabulary and aliases;
- catalogue, cart, and order operations;
- the domain safety policy;
- response templates and grounding data;
- which verified metadata may be used for calculations.

Do not bury catalogue SQL, product names, cart state, or agricultural policy inside ASR/TTS engines. Do not couple React components directly to model implementations or raw WebSocket messages.

### 2. Prefer explicit, typed stage contracts

Stages should exchange structured records rather than untracked strings. Exact class names may evolve, but preserve equivalents of:

- `AudioChunk`: bytes, codec, sample rate, channels, sequence, turn ID;
- `Transcript`: original text, language, final/partial status, confidence/timestamps;
- `TranslationResult`: source/target language, translated text, model/version;
- `Interpretation`: permitted intent or safety class, entities, confidence, clarification need;
- `ToolCall`: schema version, tool name, validated arguments, turn/session ID;
- `ToolResult`: success/failure, grounded data, safe user-facing fields;
- `ResponseText`: source text, Chhattisgarhi text, provenance/template information;
- `AudioResponseChunk`: audio format, sequence, final status;
- `VoiceTrace`: stage timings, versions, outcome, error category, cancellation state.

Every state-changing request needs a session/conversation ID, turn ID, and idempotency strategy. Stale results from an interrupted turn must never update the cart or begin playback after a newer turn has taken control.

### 3. Keep the cascade observable and replaceable

The recommended MVP is:

```text
User speech
  -> capture + VAD + compression
  -> gateway decode/resample
  -> Chhattisgarhi ASR
  -> Devanagari cleanup/normalization
  -> Chhattisgarhi-to-English MT
  -> safety classification + constrained intent/entity interpretation
  -> validated domain tool
  -> deterministic database/business result
  -> grounded response construction
  -> English-to-Chhattisgarhi MT or approved Chhattisgarhi template
  -> Chhattisgarhi TTS
  -> streamed audio playback
```

No single stage may become an opaque shortcut that prevents per-stage evaluation. Use interfaces/adapters so MMS can be compared with SraVaani or an approved API, and local MT/TTS/LLM components can be benchmarked against alternatives without rewriting orchestration.

### 4. Preserve streaming and interruption semantics

Voice UX is a core deliverable. Implement it as a state machine, not as an ordinary long-running request with audio attached.

At minimum, model states equivalent to idle, listening, speech detected, processing, responding, interrupted, failed, and recovering. Define valid transitions. On barge-in:

- stop client playback promptly;
- emit/propagate cancellation for the previous turn;
- prevent late partials or tool results from being applied;
- retain only the context explicitly safe and useful for the next turn;
- log the interruption and cancellation latency.

Stream progress or a short holding cue so multi-stage processing never looks like a frozen page. Keep responses concise because long text increases TTS delay and working-memory burden.

### 5. Ground actions before generating responses

The LLM is an interpreter and router, not the source of catalogue facts or transactional truth. It may select a permitted tool and extract arguments. The backend validates the tool call, performs the operation, and returns facts. Only then may response text be constructed.

Never allow free-form model text to directly mutate data. Reject unknown tools, extra fields, invalid enum values, impossible quantities, nonexistent product IDs, malformed units, and unauthorized user/cart IDs. Database constraints remain mandatory even when application validation exists.

### 6. Ask rather than guess

When a product, quantity, unit, area, cart referent, or intent is ambiguous, produce a short clarification turn. Do not guess values merely to keep the conversation moving. Clarification is a normal S2S state and must be included in tests and latency/usability evaluation.

## Proposed technology baseline

Use the following as the default baseline unless measurements justify a change:

| Layer | Default/current direction | Notes |
| --- | --- | --- |
| Web client | React + TypeScript + Vite | Browser microphone capture, voice state, WebSocket transport, playback, confirmations, and responsive UI |
| API/orchestrator | Python + FastAPI | REST for ordinary resources; WebSocket or SSE where streaming/progress requires it |
| VAD | Silero VAD | Keep thresholds configurable and evaluate on representative audio |
| Chhattisgarhi ASR | Meta MMS 1B with `hne` adapter | Existing baseline; do not claim WER until measured |
| ASR comparison | SraVaani-1.0 | Benchmark candidate, not an MVP dependency |
| Translation | NLLB-200 distilled 600M, `hne_Deva` | Measure translation drift as its own failure source |
| Intent/entities | Local instruction-tuned, tool-capable model | Strict schemas; no specific paid provider is assumed |
| TTS | Coqui-TTS VITS, existing Chhattisgarhi checkpoints | Preserve male/female configuration and pacing controls |
| Database | PostgreSQL | Transactions and referential integrity are required |
| Optional APIs | Bhashini or hosted LLM only if confirmed | Comparison path, never a hidden dependency |

The project has a zero-allocated-budget baseline. Prefer open-source and locally runnable components. Never add a paid or access-controlled service as a required path without explicit approval, a documented fallback, and updated scope/cost documentation.

Do not replace a component because a newer model sounds stronger. First define a comparable dataset, warm-up behavior, hardware, model configuration, accuracy metrics, latency metrics, and resource measurements.

## Audio and model-serving requirements

- Browser microphone capture uses `navigator.mediaDevices.getUserMedia()` and therefore requires a secure context. `localhost` is acceptable for local development; any non-local deployment must use HTTPS/WSS.
- Detect browser capabilities at runtime. Use `MediaRecorder.isTypeSupported()` before selecting an Opus/container combination, and send the actual MIME type with each turn.
- Prefer `AudioWorklet` when raw low-latency PCM frames, metering, or client-side VAD requires processing away from the main UI thread. Retain a simpler push-to-talk/`MediaRecorder` path as the dependable fallback.
- Respect browser autoplay and permission policies. Start capture/playback from an explicit user gesture, explain microphone denial clearly, and stop every `MediaStreamTrack` when a turn/session ends.
- The browser `WebSocket` API does not provide automatic backpressure. Keep chunks bounded, monitor `bufferedAmount`, pause/drop only according to the documented protocol, and close stalled sessions before queued audio exhausts memory.
- Normalize inference audio to an explicitly documented canonical format, expected initially to be mono 16 kHz PCM after transport decoding.
- Treat Opus as a transport/storage choice, not as the ASR tensor format. Validate headers, sample rate, channels, duration, and maximum payload size.
- Do not reload large models for each request. Load once per process/worker and use bounded inference concurrency.
- Do not block the FastAPI event loop with CPU/GPU inference. Use an inference worker, executor, queue, or service boundary appropriate to the measured load.
- Warm up models before benchmark runs and report cold and warm latency separately where relevant.
- Record model ID, adapter/checkpoint version, decoding parameters, device, precision, and relevant hardware with every formal benchmark.
- Keep Devanagari normalization deterministic and independently tested. Preserve original ASR output alongside normalized output for error analysis.
- Maintain domain vocabulary/alias lists as injectable data. Do not bake shopping words permanently into the generic ASR interface.
- Treat partial ASR results as provisional. Only finalized, validated interpretations may trigger state-changing tools.
- Make TTS output sample rate/format explicit. The client must not infer it from a filename or model default.
- Support cancellation between stages and, where practical, during streaming synthesis.

## Domain tools and shopping behavior

The minimum intent/tool family is:

- `SEARCH_PRODUCT`
- `PRODUCT_DETAILS`
- `CHECK_PRICE`
- `CALCULATE_REQUIRED_QUANTITY`
- `ADD_TO_CART`
- `REMOVE_FROM_CART`
- `VIEW_CART`
- simulated `CHECKOUT`

Tool names in code may use lower snake case, but one canonical taxonomy and schema version must be documented. Tool schemas should distinguish product names from resolved product IDs, amount from unit, field area from purchase quantity, and conversational mention from verified backend entity.

The catalogue is intentionally small—approximately 50–100 relevant seed, fertilizer, and basic-tool records—because it is an instrumented test domain, not an attempt to clone a large marketplace.

Use PostgreSQL transactions for cart, inventory, and simulated-order changes. Capture `price_at_addition` and `price_locked` semantics deliberately. Enforce foreign keys and validate ownership server-side. Authentication is JWT-based in the proposal; secrets and signing material must remain server-side environment configuration.

Do not introduce RAG for the structured product catalogue without evidence that relational/full-text/fuzzy search is insufficient. Direct database search is easier to validate, faster at this scale, and less likely to invent products.

### Deterministic quantity calculation

An LLM must never calculate agricultural quantities from memory. A permitted calculation must:

1. resolve a real catalogue item;
2. use a verified, versioned metadata field from an authoritative source;
3. normalize area and product units deterministically;
4. execute ordinary Python/SQL arithmetic;
5. apply explicit plausibility bounds;
6. return the value and provenance to response construction;
7. refuse or ask for clarification if metadata or units are missing.

Seed/application-rate metadata must include source, source date/version, units, applicable crop/context, and verification status. Proposal-stage example figures are not verified facts. Do not add them to the production catalogue until sourced from IGKV or another authoritative regional reference.

## Safety boundary

This system is a transactional/product-discovery assistant. It is **not an agronomist, crop doctor, or pesticide advisor**.

Permitted behavior includes finding a catalogue item, stating verified product details, changing the cart, checking price/availability, and performing an explicitly allowed deterministic calculation from verified static metadata.

Disallowed behavior includes:

- diagnosing crop disease or deficiency;
- choosing a pesticide, chemical, treatment, or cure for observed symptoms;
- generating pesticide dosage or application instructions;
- turning uncertainty into a confident recommendation;
- bypassing the boundary because the request is phrased indirectly or as a hypothetical.

For disallowed queries, the backend must select a fixed, reviewed Chhattisgarhi refusal/referral response directing the user to an appropriate Krishi Vigyan Kendra (KVK) or qualified expert. Do not let the LLM freely improvise the advice, disclaimer, contact details, or dosage. Any actual referral details must be verified before release.

Safety classification belongs before tool execution and should be defense in depth:

- a labelled permitted/disallowed/ambiguous taxonomy;
- constrained model output;
- deterministic validation of requested tool and entities;
- tool-level policy checks;
- fixed refusal templates;
- an audit event without unnecessary personal data.

Measure false negatives and false positives separately. A false negative can produce unsafe advice; a false positive blocks a legitimate shopping task. Test paraphrases, code-switching, euphemisms, multi-turn context, prompt injection, and ambiguous quantity-versus-dosage wording.

## Data, privacy, and ethics

Relevant public resources identified in the proposal include RESPIN-S1.0 for dialect-rich ASR data, SYSPIN_S1.0 for Chhattisgarhi TTS, and FLORES-200/NLLB evaluation material for `hne_Deva`. Confirm licenses and record exact dataset/model versions before redistribution or training.

Build a project-specific evaluation set containing realistic Chhattisgarhi shopping commands from native speakers, including noise, code-switching, hesitations, ambiguous requests, corrections, and safety-boundary cases. Separate training/development/test speakers where the sample size permits; never evaluate only on phrases used as prompts or adaptation data.

For human recordings:

- obtain informed consent before recording;
- do not request names, precise addresses, financial information, or other unnecessary PII;
- define purpose, access, retention, deletion, and publication rules;
- store raw recordings outside the Git repository unless an explicitly consented, appropriately licensed subset is prepared;
- do not publish or send recordings to third-party APIs without consent covering that use;
- report small studies as indicative pilot results, not population-wide evidence.

Voice logs should default to the minimum needed for debugging and evaluation. Prefer pseudonymous participant/session IDs. If `audio_ref` exists, make retention configurable. Never log JWTs, API keys, full authorization headers, or raw third-party responses that may contain sensitive data.

## Evaluation requirements

Evaluation is a deliverable, not cleanup after the demo. Preserve stage outputs and timestamps from the beginning.

### Speech and language metrics

- ASR: WER and CER on held-out Chhattisgarhi speech, with normalization rules published.
- ASR slices: speaker, noise condition, code-switching, domain term, utterance length, and model/configuration where sample size allows.
- Translation: a declared automatic metric if appropriate plus native-speaker/human error review for meaning-changing drift; do not hide translation errors inside intent scores.
- Intent: accuracy and confusion matrix.
- Entities: precision, recall, and F1 by entity type.
- Tool calling: schema-validity rate, correct-tool rate, correct-arguments rate, clarification rate, and hallucinated-entity rate.
- TTS: real-time factor, time to first audio, intelligibility/task comprehension, and a small listening-quality assessment where feasible.

### End-to-end voice metrics

- complete spoken-task success rate;
- product search, cart mutation, and calculation success rate;
- safety false-negative and false-positive rates;
- end-to-end latency from end of user speech to first response audio byte;
- capture/VAD, upload, ASR, MT, interpretation, tool, response MT, TTS-first-byte, and total timing;
- timeout, retry, cancellation, and recovery rates;
- barge-in detection and playback-stop latency;
- percentage of turns requiring clarification or manual UI repair.

The proposal's provisional target is under 5 seconds for speech-in to speech-response, with an 8-second client timeout and a local Chhattisgarhi network-error prompt. Keep thresholds configurable. If measurements show that these targets conflict, report the actual results and rationale; do not discard slow runs or silently redefine the metric.

### Benchmark discipline

- Version evaluation manifests and expected labels.
- Never train/tune on the held-out test set.
- Pin or record model, adapter, tokenizer, prompt, schema, dependency, and hardware versions.
- Save aggregate results in machine-readable form and generate report tables from them where practical.
- Distinguish cold start, warm inference, streaming time to first result, and total completion time.
- Report failures and excluded samples with reasons.
- Do not put invented, estimated, cherry-picked, or uncalibrated numbers in reports.

## Reliability and low-connectivity behavior

True fully offline in-browser conversational inference is outside the current scope. The connected web design must degrade clearly:

- prefer Opus for uploaded audio when the current browser reports a compatible container/codec; otherwise use the documented supported fallback and send the actual media type;
- cache the web application shell and recently viewed product text/images with a service worker and IndexedDB where justified;
- provide visible and audible listening/processing/responding state;
- apply bounded retries only to safe, idempotent operations;
- cancel at the configured timeout;
- play a bundled, pre-recorded Chhattisgarhi failure prompt when the service is unavailable;
- never duplicate a cart mutation because the client retried after losing the response.

Simulate slow, reordered, duplicated, dropped, and disconnected requests in tests. A network failure must not leave the UI claiming an unconfirmed cart state.

## Security and integrity

- Keep API keys, database URLs, model-service credentials, and JWT secrets out of source and browser bundles. Any Vite environment variable exposed to client code is public by design and must not contain a secret.
- Provide redacted example environment files only.
- Validate authentication and resource ownership on every cart/order endpoint.
- Constrain model outputs with machine-validated schemas; prompt instructions alone are not a security boundary.
- Validate file/audio type, duration, size, codec, and decode outcome before inference.
- Rate-limit or otherwise bound expensive inference entry points when exposed beyond local development.
- Use parameterized queries/ORM bindings and database constraints.
- Make state-changing operations idempotent where retries can occur.
- Treat transcripts, recordings, and conversation context as untrusted input.
- Include prompt-injection and malformed-tool-call tests.

## Suggested repository organization

The repository currently begins from a proposal document. As implementation is added, prefer boundaries similar to the following; adapt names to the framework rather than creating empty scaffolding prematurely.

```text
apps/
  web/                    # React/TypeScript capture, voice state, playback, responsive UI
services/
  backend/
    app/
      api/                # REST/WebSocket/SSE transport
      voice/              # audio, VAD, ASR, MT, TTS adapters
      orchestration/      # turn state machine, cancellation, traces
      interpretation/     # safety class, intents, entities, tool schemas
      domains/
        shopping/         # catalogue/cart/order tools and response policy
      db/                 # models, repositories, migrations, transactions
evaluation/               # manifests, metric code, benchmark runners, reports
data/
  fixtures/               # synthetic/licensed non-sensitive test fixtures
  lexicons/               # versioned domain vocabulary and aliases
configs/                  # non-secret model and runtime configuration
docs/                     # architecture, decisions, data cards, evaluation protocol
tests/                    # cross-component/integration tests if not colocated
```

Keep model checkpoints, generated audio, participant recordings, database dumps, and large benchmark outputs out of Git. Store only small licensed fixtures, configs, checksums/manifests, and documented retrieval instructions.

## Engineering conventions

### General

- Make the smallest coherent change that advances a measured project objective.
- Preserve the voice/domain boundary even when building a quick demo.
- Prefer configuration and dependency injection for model/provider choices.
- Use clear, domain-neutral names in the S2S core and agricultural names only in the shopping adapter.
- Add comments for safety invariants, concurrency behavior, cancellation, audio formats, and non-obvious model quirks—not for obvious syntax.
- Update architecture, schema, API, and evaluation documentation with behavior changes.
- Record meaningful architectural decisions, especially model replacements or changes to safety/scope.
- Do not claim that a stub, mocked model, or simulated checkout is production functionality.

### Python/FastAPI

- Use type hints and validated request/response models at external and model/tool boundaries.
- Keep route handlers thin; orchestration, safety, domain logic, and persistence belong in separate modules.
- Keep blocking model inference off the async event loop.
- Translate internal exceptions into stable error codes that the voice client can render or speak safely.
- Use database migrations rather than startup-time ad hoc schema creation once persistence is established.
- Make unit conversion and quantity calculations pure and heavily tested.

### React/web

- Use TypeScript in strict mode and model listening/processing/playback as explicit state, including permission denial, timeout, cancellation, retry, and barge-in.
- Keep microphone capture, audio processing/playback, REST, WebSocket protocol handling, and persistence outside presentation components.
- Show what the system heard and what action it took without requiring the visual UI to complete the primary path.
- Build a responsive, keyboard-accessible interface with visible focus, semantic controls, large voice controls, and readable status text; keep voice task completion the primary UX criterion.
- Never store backend secrets in frontend code, static assets, local storage, or browser-readable environment values.
- Test permission denial, tab visibility changes, page navigation/unload, device changes, disconnected sockets, autoplay rejection, and playback cancellation.
- Feature-detect audio/container support and display an actionable unsupported-browser message instead of failing silently.

### Database and APIs

- Use consistent units and explicit decimal/money semantics; do not use binary floating point for prices.
- Preserve transactional integrity for cart/order operations.
- Version public/tool schemas before making incompatible changes.
- Return grounded identifiers and machine-readable errors, not only prose.
- Keep voice orchestration endpoints separate from reusable catalogue/cart APIs.

## Testing expectations

Every feature should be tested at the lowest sensible layer and across the relevant pipeline boundary.

Minimum categories include:

- audio decode/resample/validation and VAD boundary fixtures;
- Devanagari cleanup and normalization golden tests;
- model-adapter contract tests using lightweight doubles where full checkpoints are unavailable;
- intent/entity and JSON-schema validation tests;
- safety-boundary adversarial and regression cases;
- deterministic unit/area/quantity calculations;
- product resolution and nonexistent-product rejection;
- authenticated cart ownership, transactions, retries, and idempotency;
- turn cancellation, late result suppression, and barge-in;
- timeout and low-connectivity behavior;
- a small consent-safe recorded-audio end-to-end regression suite;
- reproducible benchmark/evaluation commands.

Do not make every ordinary test load billion-parameter models. Separate fast CI tests from hardware/model integration tests and document how to run both. A model change is not complete until the relevant evaluation subset is rerun and compared with the recorded baseline.

## Work planning and review checklist

Before implementing a change, identify whether it belongs to:

- the reusable S2S core;
- domain interpretation/policy;
- shopping tools/data;
- web presentation;
- evaluation/research infrastructure.

If it spans layers, define or update the contract first. During review, ask:

1. Does this improve or preserve the complete spoken interaction?
2. Is domain-specific behavior kept outside the reusable voice core?
3. Can every model-generated action be validated and grounded?
4. Does it remain safe under ambiguity, prompt injection, interruption, timeout, and retry?
5. Are latency and failure states observable per stage?
6. Are claims supported by versioned, reproducible measurements?
7. Does it preserve the zero-budget local path?
8. Does it avoid collecting or exposing unnecessary voice/identity data?
9. Is it inside Level 2 scope, or clearly marked future work?

## Definition of done

A voice-pipeline change is done when it has a stable interface, format/config documentation, cancellation/error behavior, tests, instrumentation, and a recorded evaluation comparison where performance may change.

A shopping-domain change is done when its tool schema is validated, facts come from the database, mutations are transactional/idempotent as needed, spoken confirmation is grounded, and end-to-end voice execution is tested.

A safety change is done only when the fixed response path, tool-level enforcement, audit behavior, and labelled false-positive/false-negative regression set all pass. Prompt wording alone is not completion.

An evaluation change is done when its dataset split, normalization, configuration, hardware, command, metric definition, and outputs are reproducible and documented.

A documentation or demonstration claim is done when it clearly labels preliminary work, implemented MVP behavior, measured results, limitations, and future work without conflating them.

## Project plan and ownership context

The proposal targets an approximately sixteen-week Autumn 2026 project ending around mid-December 2026. The current web-only plan completes by the end of November and covers scoping/data/schema, backend/database, voice and conversational pipeline, React web client, integration, evaluation, and final documentation/demo. Treat evaluation infrastructure as something built throughout, not only in the final phase.

The proposal's primary allocations are:

- Punyansh Thakur: speech/AI pipeline, translation, tool schema/prompting, safety, and evaluation design;
- Harsh Dadsena: FastAPI, PostgreSQL, deterministic calculation, authentication, and deployment;
- Aakash Sen: React/TypeScript web client, browser audio/VAD/transport, voice/cart UX, browser caching, and integration.

These are ownership guides, not silos. All contributors share responsibility for integration, test data, evaluation, documentation, and the final S2S demonstration.

## Final guiding rule

If a proposed change makes the repository look more like a generic shopping website but does not strengthen the voice-to-voice research system, treat it as secondary. If a change improves Chhattisgarhi speech accuracy, spoken-response quality, streaming interaction, interruption handling, grounded action execution, safety, observability, reproducibility, or domain portability, it is aligned with the heart of the project.
