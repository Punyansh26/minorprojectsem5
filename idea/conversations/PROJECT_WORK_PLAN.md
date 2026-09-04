# Project Work Plan: Chhattisgarhi Voice-to-Voice Assistant

## Plan summary

**Team:** Harsh Dadsena, Punyansh Thakur, and Aakash Sen

**Execution window:** 7 September–29 November 2026

**Emergency buffer:** 30 November 2026 only

**Cadence:** Three four-week checkpoints

**Expected effort:** 10–12 focused hours per person per week, approximately 360–432 total person-hours

The goal is to finish a measured, demonstrable Chhattisgarhi Speech-to-Speech system before December. The agricultural shopping website is the reference implementation used to prove that the voice system can understand speech, execute grounded stateful actions, and answer in speech. Voice-to-voice quality, safety, latency, interruption handling, and evaluation take priority over marketplace features or UI polish.

This is a **web-development-only project**. There is no Flutter, Android-native, iOS-native, APK, or app-store deliverable. The client is a responsive browser application that may run on desktop or mobile browsers, with a current Chromium-based desktop browser as the dependable demonstration target.

## Final outcome by 29 November

In a supported web browser, a user must be able to speak in Chhattisgarhi and complete this path:

```text
Speak -> detect speech -> stream audio -> Chhattisgarhi ASR
      -> translate/normalize -> detect safety class and shopping intent
      -> execute a validated product/cart tool -> build grounded reply
      -> translate to Chhattisgarhi -> synthesize speech -> play response
```

The final build must demonstrate:

1. product search and product-detail/price lookup;
2. add to cart, remove from cart, and view cart;
3. deterministic quantity calculation using verified metadata;
4. simulated checkout without payment;
5. a clarification question for an ambiguous command;
6. a fixed refusal/KVK referral for unsafe diagnosis or pesticide advice;
7. visible and audible recovery from timeout/network failure;
8. interruption of response playback when the user starts a new turn;
9. per-stage logs and a reproducible evaluation report.

## The three checkpoints

| Checkpoint | Dates | Outcome | Release gate |
| --- | --- | --- | --- |
| **1. Walking Voice Vertical Slice** | 7 Sep–4 Oct | One real spoken Chhattisgarhi request travels from the browser through ASR and the backend to a real spoken response | Search and price-query demo works end to end; stage contracts and baseline measurements are frozen |
| **2. Feature-Complete Voice MVP** | 5 Oct–1 Nov | All required shopping tools, safety behavior, cart state, clarification, browser voice states, and interruption/recovery paths are integrated | Every required scenario works in the supported browser; no major feature is added after this gate |
| **3. Evaluated Release Candidate** | 2–29 Nov | The system is hardened, measured, documented, packaged, and rehearsed | Production web bundle/backend package, final metrics, report material, backup demo, and presentation are ready |

The rule is simple: **Checkpoint 1 proves the architecture, Checkpoint 2 completes behavior, and Checkpoint 3 proves and presents the result.**

## Ownership model

Each member has a primary area and a secondary integration duty. Ownership means the person drives design, implementation, tests, and documentation; it does not mean that only that person may touch the code.

| Member | Primary ownership | Secondary/integration ownership | Final measurable responsibility |
| --- | --- | --- | --- |
| **Punyansh** | Audio/AI pipeline: VAD, MMS ASR, Devanagari cleanup, NLLB translation, intent/entity model, safety classification, VITS TTS | Evaluation design and model benchmarking | A reproducible S2S pipeline with stage-level accuracy and latency results |
| **Harsh** | FastAPI orchestration, PostgreSQL, authentication, product/cart/order tools, deterministic calculations, deployment | Protocol validation, observability, security, and idempotency | Correct grounded actions, reliable orchestration, and a runnable backend |
| **Aakash** | React/TypeScript website, browser microphone capture, audio transport/playback, state management, visual confirmations, and caching | End-to-end integration, browser testing, accessibility, and usability workflow | A production web build that completes the voice tasks and handles browser failure states |

### Shared responsibilities

All three members must participate in:

- defining the WebSocket and tool contracts;
- reviewing safety behavior;
- recording or validating Chhattisgarhi test phrases;
- weekly integration and browser/microphone testing;
- evaluation data collection;
- report writing and demonstration rehearsal.

No one should maintain a private branch for longer than three working days. Integration problems are team problems, not only the responsibility of the person whose layer exposed them.

## Technology decisions

### Overall architecture: modular monolith first

Build one **FastAPI modular backend** with clear adapters for ASR, translation, interpretation, TTS, and shopping tools. Run heavy model inference in bounded worker threads/processes so it does not block the asynchronous API event loop.

Do not begin with multiple independently deployed microservices. Three students can test and deploy a modular monolith more reliably. The adapter boundaries allow a model to become a separate service later if GPU memory, dependency conflicts, or scaling measurements require it.

### Recommended stack

| Concern | Technology | Why this choice | Primary owner |
| --- | --- | --- | --- |
| Web UI | React + TypeScript + Vite | Component UI, strict browser/API types, fast local development, and a simple static production build | Aakash |
| Server data | TanStack Query | Caching, loading/error states, invalidation after cart operations, and less hand-written request state | Aakash |
| Voice UI state | Typed reducer/state machine | Keeps listening/processing/responding/interrupted/error transitions explicit without adding unnecessary framework complexity | Aakash |
| REST client | Native `fetch` wrapper + `AbortController` | Built-in browser support, typed response boundary, timeout/cancellation without a second HTTP abstraction | Aakash |
| Bidirectional voice transport | Native browser `WebSocket` using one versioned protocol | Audio, progress, interruption, and returned audio need two-way streaming | Aakash + Harsh |
| Recording | `getUserMedia`, `MediaRecorder`, and `MediaRecorder.isTypeSupported()` | Standard browser capture with runtime codec/container detection | Aakash |
| Low-latency audio | Web Audio API + `AudioWorklet` where needed | Off-main-thread PCM frames, metering, client VAD experiments, and controllable playback | Aakash |
| Browser cache | IndexedDB through a small typed wrapper such as `idb`; service worker only after core behavior works | Structured recent-product/cart cache and optional application-shell caching | Aakash |
| Backend API | Python + FastAPI | Matches existing speech work and supports typed async REST/WebSocket APIs | Harsh |
| Validation/contracts | Pydantic | Rejects malformed model tool calls and provides explicit API schemas | Harsh + Punyansh |
| Persistence | PostgreSQL + SQLAlchemy + Alembic | ACID transactions, relational integrity, and versioned migrations | Harsh |
| Local development database | PostgreSQL through Docker Compose | Reproducible setup; do not make the final demo depend on internet access | Harsh |
| ASR | PyTorch/Transformers MMS 1B with `hne` adapter | Existing demonstrated Chhattisgarhi baseline | Punyansh |
| VAD | Silero VAD | Existing baseline and configurable real-time speech detection | Punyansh + Aakash |
| Translation | NLLB-200 distilled 600M with `hne_Deva`; CTranslate2 if conversion is validated | Native Chhattisgarhi support; optimized runtime may reduce latency | Punyansh |
| Intent/entities | Small quantized instruction model through `llama.cpp`-compatible local server | Local, replaceable, and capable of constrained structured output | Punyansh |
| Output validation | JSON schema/Pydantic plus deterministic policy checks | A model response is never trusted directly | Harsh + Punyansh |
| TTS | Existing Coqui-TTS VITS Chhattisgarhi checkpoints | Existing male/female voices and fast local synthesis | Punyansh |
| Web testing | Vitest + React Testing Library + Playwright | Unit/component tests plus real browser microphone/WebSocket workflow tests | Aakash |
| Backend testing | `pytest` + FastAPI test client | Fast API/domain tests separate from full model tests | Harsh + Punyansh |
| Evaluation | `jiwer`, pandas, scikit-learn, and project scripts | WER/CER, intent/entity metrics, confusion matrices, timing summaries | Punyansh |
| Code quality | Ruff plus a Python type checker; ESLint, Prettier, and `tsc --noEmit` | Fast automated checks and consistent Python/TypeScript code | All |

Pin the actual compatible versions after the Week 1 environment spike. Coqui-TTS, PyTorch, CUDA, and Python compatibility must be tested together; do not blindly select the newest version of each package.

### Official web-platform references

Use these as the implementation source of truth for the browser layer:

- [React with TypeScript](https://react.dev/learn/typescript)
- [Vite setup and supported templates](https://vite.dev/guide/)
- [Microphone capture and secure-context requirements](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- [MediaRecorder and runtime media-type detection](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder)
- [Off-main-thread audio processing with AudioWorklet](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Using_AudioWorklet)
- [WebSocket behavior and lack of automatic backpressure](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [IndexedDB structured browser storage](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)
- [Service-worker caching](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers)

### Deployment topology for the final demonstration

Use this as the primary, dependable topology:

```text
Current Chromium browser on integration laptop
        |
        | same-origin HTTP + WebSocket on localhost
        v
FastAPI on the same laptop/lab machine
  - serves the built Vite frontend
  - REST and voice WebSocket endpoints
  - model workers
  - local PostgreSQL
  - model/checkpoint files
```

This avoids making the final demonstration depend on free cloud sleep limits, rural internet, API approval, or uploading large models. Browser microphone access requires a secure context: `localhost` is acceptable for the single-machine demo, while any non-local or public deployment must use HTTPS and WSS. In development, Vite may proxy `/api` and `/ws` to FastAPI; for release, FastAPI should serve the Vite `dist/` directory so frontend, REST, and WebSocket traffic share one origin. A hosted frontend/backend or Bhashini comparison may be shown as a stretch result, but the main MVP must remain runnable locally.

### Hardware decision in Week 1

The team must record the available CPU, RAM, GPU, VRAM, CUDA/driver version, browsers, microphones/headsets, and display sizes used for testing. Punyansh then measures each model separately. Harsh uses that data to select one of these runtime modes:

1. **Preferred:** all models remain warm, with GPU/CPU placement chosen to fit memory.
2. **Limited VRAM:** MMS/VITS use GPU; NLLB and the quantized intent model use CPU or partial GPU offload.
3. **Dependency conflict:** one or more models run in a separate local worker process/environment behind a small internal adapter.
4. **Severe hardware limit:** use smaller/quantized models and concise template responses; preserve the local path and report the trade-off.

Do not wait until November to discover that all models cannot run together.

## Component boundaries and implementation contracts

### Web-client responsibilities

The browser client owns:

- checking for a secure context and browser audio capabilities;
- requesting microphone permission with `getUserMedia()` after an explicit user action;
- stopping every `MediaStreamTrack` when recording/session use ends;
- push-to-talk as the dependable baseline;
- browser-side VAD/automatic endpoint detection once proven stable;
- selecting a supported recording MIME type with `MediaRecorder.isTypeSupported()`;
- audio chunk numbering and upload;
- stopping `HTMLAudioElement`/Web Audio playback immediately on barge-in;
- rendering recognized text, current action, products, and confirmed cart state;
- a bundled timeout/failure audio prompt;
- caching recent products and the last server-confirmed cart snapshot in IndexedDB.

Push-to-talk must remain available even after VAD is added. It is the recovery path on noisy microphones and protects the final demo if automatic endpoint detection or a browser audio API behaves poorly.

### Voice WebSocket protocol

Freeze protocol version 1 during Checkpoint 1. Use JSON control messages and binary audio frames. Every message must carry or be associated with a `session_id`, `turn_id`, and monotonically increasing sequence where ordering matters.

Client events:

- `start_turn` with codec/sample-rate/channel metadata;
- binary audio chunks;
- `end_turn`;
- `interrupt_turn`;
- `ack_audio` if response flow control needs it.

The browser WebSocket API has no automatic backpressure. The client must monitor `socket.bufferedAmount`, keep chunks bounded, and follow a documented high-water/low-water policy. The server must bound each session's queued audio and reject or close a stalled producer cleanly rather than allowing unbounded memory growth.

Server events:

- `listening`;
- `speech_started` / `speech_ended`;
- `partial_transcript`;
- `final_transcript`;
- `translating` / `interpreting` / `executing` / `synthesizing`;
- `clarification_required`;
- `tool_result` containing safe display data;
- `response_text`;
- `audio_start`, binary response chunks, and `audio_end`;
- structured `error` with a stable code and retryability flag;
- `turn_cancelled`.

Only a finalized transcript and validated interpretation may execute a state-changing tool. A late result from an interrupted turn must be discarded before database mutation and before playback.

### Backend REST surface

Use REST for normal application data and WebSocket for the voice turn. The initial API should expose equivalents of:

- `POST /v1/auth/login` for seeded/demo users and JWT issuance;
- `GET /v1/products` with text/category query parameters;
- `GET /v1/products/{product_id}`;
- `GET /v1/cart`;
- `POST /v1/cart/items` with an idempotency key;
- `PATCH /v1/cart/items/{item_id}`;
- `DELETE /v1/cart/items/{item_id}`;
- `POST /v1/orders/simulate`;
- `GET /v1/health` and a model-readiness endpoint;
- `WS /v1/voice/sessions/{session_id}`.

For the academic MVP, use seeded username/password demo accounts. Do not spend time integrating real SMS OTP. Hash stored passwords, validate cart ownership, and keep JWT keys on the backend. Prefer an in-memory token for the demo session over long-lived browser storage; never expose secrets in Vite client environment variables.

### Model adapter interfaces

Define small replaceable interfaces in Checkpoint 1:

- `VAD.detect(audio) -> speech segments/events`
- `ASR.transcribe(audio, language, hints) -> Transcript`
- `Translator.translate(text, source, target) -> TranslationResult`
- `Interpreter.interpret(text, context, tool_schema) -> Interpretation`
- `SafetyPolicy.classify(text, context) -> permitted/disallowed/ambiguous`
- `TTS.synthesize(text, voice, pace) -> audio stream/result`

Every result should include model/configuration identity and timing. Preserve raw ASR text, cleaned text, translated text, interpreted tool call, grounded tool result, response text, and timing in a trace without storing unnecessary PII.

### Shopping tool contracts

Implement one Pydantic/JSON schema for each tool:

- `search_product(query, category?, crop?)`
- `product_details(product_id)`
- `check_price(product_id, quantity?, unit?)`
- `calculate_required_quantity(product_id, area, area_unit)`
- `add_to_cart(product_id, quantity, unit, idempotency_key)`
- `remove_from_cart(product_id or cart_item_id, quantity?)`
- `view_cart()`
- `simulate_checkout(idempotency_key)`

The interpreter may propose a tool, but Harsh's domain layer resolves names to real product IDs, validates units and ownership, and performs the transaction. Unknown products must lead to search suggestions or clarification—not fabricated product records.

### Safe response construction

Prefer short response templates filled from the `ToolResult`. Translate those controlled sentences to Chhattisgarhi and synthesize them. Frequently used responses—network failure, unsafe-query referral, empty cart, and clarification prompts—should have reviewed Chhattisgarhi text and may also be pre-synthesized for speed and consistency.

Never ask the LLM to freely compose prices, stock, dosage, or cart totals. These values must be inserted from backend results after validation.

## Checkpoint 1: Walking Voice Vertical Slice

**Dates:** 7 September–4 October 2026

**Purpose:** Remove the largest technical risks early and produce one real end-to-end spoken interaction.

### Week 1: 7–13 September — environments, contracts, and browser-audio spikes

#### Punyansh

- Bring the existing MMS ASR, Devanagari cleanup, Silero VAD, and both VITS checkpoints into reproducible project environments.
- Add one command per model for a smoke test; record exact model/checkpoint identifiers and hardware.
- Benchmark cold start, warm inference, peak memory, input/output formats, and latency on at least five existing non-sensitive utterances.
- Verify NLLB `hne_Deva -> eng_Latn` and reverse translation on a small set reviewed by a Chhattisgarhi speaker.
- Propose the canonical `Transcript`, `TranslationResult`, and `AudioResult` structures.

#### Harsh

- Initialize the FastAPI backend, configuration system, health endpoints, test setup, and local PostgreSQL Compose service.
- Create the first SQLAlchemy models and Alembic migration for users, products, categories, carts, cart items, orders, order items, and voice traces.
- Draft WebSocket protocol v1 and REST OpenAPI contracts with Aakash and Punyansh.
- Add CI/local quality commands for formatting, linting, unit tests, and migration checks.

#### Aakash

- Initialize the React + TypeScript + Vite web client with strict TypeScript, linting, unit tests, and the listening/processing/responding/error reducer.
- Test `getUserMedia()` permission, `MediaRecorder`, Web Audio playback, and stream cleanup in the primary Chromium browser and Firefox where available.
- Use `MediaRecorder.isTypeSupported()` to test likely Ogg/WebM Opus options and a dependable fallback. Record actual browser/OS support rather than assuming a fixed container.
- Test `AudioContext`/`AudioWorklet` capture to learn the browser's actual sample rate and whether raw PCM streaming is needed.
- Build a browser diagnostic route showing secure-context status, permission state, selected MIME type, audio sample rate, chunk duration, upload status, and playback result.

#### Shared output

- Repository structure, setup instructions, issue board, architecture sketch, and Definition of Done.
- Hardware/browser/runtime decision and known dependency risks.
- Protocol draft reviewed by all three members.

### Week 2: 14–20 September — database, audio transport, and stage adapters

#### Punyansh

- Wrap ASR, translation, and TTS in the agreed adapters.
- Add deterministic Devanagari normalization tests that preserve both raw and cleaned output.
- Build an initial agriculture/shopping vocabulary and alias file separate from model code.
- Create an initial 30–50 text-command intent/entity set covering search, details, price, cart, ambiguity, and unsafe requests.

#### Harsh

- Complete migrations, repositories, and seed import for at least 20 placeholder/verified-status-labelled catalogue items.
- Implement product search/details and basic cart REST APIs with tests.
- Implement audio validation, decoding/resampling to canonical mono 16 kHz PCM, and maximum-duration/size enforcement.
- Implement `VoiceTrace` stage timestamps and structured error codes.

#### Aakash

- Implement push-to-talk capture, WebSocket connection, binary audio upload, progress-state rendering, and returned-audio playback.
- Add bounded chunk sizes and a tested `WebSocket.bufferedAmount` high-water/low-water policy.
- Add responsive REST product list/detail pages and typed network error mapping.
- Use `AbortController`, WebSocket close/cancel messages, and effect cleanup so navigation, page unload, or a new turn stops current capture/upload/playback.
- Add keyboard operation, visible focus, and semantic labels to the primary voice control.

#### Shared output

- Protocol v1 frozen for the checkpoint.
- Audio from the browser reaches the backend and returns through a temporary echo/playback test.
- Product API and web catalogue integration work independently of AI.

### Week 3: 21–27 September — constrained interpretation and first vertical slice

#### Punyansh

- Select a small quantized local instruction model after measuring two realistic candidates on the same command set.
- Implement grammar/schema-constrained intent/entity output with at most one repair attempt.
- Implement the first safety taxonomy and fixed refusal text with native-speaker review.
- Connect grounded response text to reverse translation and VITS synthesis.

#### Harsh

- Implement Pydantic schemas and domain services for `search_product`, `product_details`, and `check_price`.
- Connect the voice orchestrator: final ASR -> translation -> safety/intent -> tool -> template -> reverse translation -> TTS.
- Add JWT demo authentication and attach authenticated user/session/turn IDs to voice actions.
- Ensure model inference runs outside the FastAPI event loop.

#### Aakash

- Integrate final transcript, tool result, response text, and audio events.
- Show what the system heard, the matching product, its price, and the spoken answer.
- Implement bundled processing and network-error sounds/prompts, triggered in a browser-compatible playback path.

#### Shared output

- First real vertical slice in the browser: speak a Chhattisgarhi product query, retrieve a real catalogue result, and hear a Chhattisgarhi response.

### Week 4: 28 September–4 October — stabilize and pass Checkpoint 1

#### Team integration work

- Fix environment, protocol, audio format, and model-loading failures before adding features.
- Run at least 20 recorded turns across search and price/detail requests in the supported integration browser.
- Establish initial WER/CER, intent correctness, time-to-first-response-audio, total latency, and failure counts.
- Profile combined model memory and select final Checkpoint 2 serving topology.
- Write the consent/data-handling protocol and begin participant recruitment only after supervisor/ethics requirements are satisfied.
- Record architecture and protocol decisions in `docs/`.

### Checkpoint 1 acceptance gate

Checkpoint 1 passes only if:

- a new developer can start database/backend/models/web from written instructions;
- the supported browser completes real search and price/detail voice turns;
- no catalogue fact is invented by the model;
- raw and normalized transcript, translation, intent/tool result, and per-stage timing are observable;
- all fast tests pass without loading every large model;
- baseline measurements and known limitations are saved;
- all three members can explain the complete data flow.

If this gate fails, Week 5 becomes a recovery week. Do not proceed to optional UI features or model comparisons.

## Checkpoint 2: Feature-Complete Voice MVP

**Dates:** 5 October–1 November 2026

**Purpose:** Complete every required user behavior and freeze scope.

### Week 5: 5–11 October — complete domain tools and catalogue

#### Punyansh

- Extend the labelled command set for all required intents and entity types.
- Improve product/crop/unit recognition using the injectable lexicon and error analysis from Checkpoint 1.
- Expand the safety set with code-switching, indirect requests, and quantity-versus-dosage ambiguity.

#### Harsh

- Implement add/remove/view-cart and simulated checkout as tested transactions.
- Implement deterministic area/unit normalization and required-quantity calculation.
- Require source, unit, verification status, and applicability metadata for any calculable rate.
- Add idempotency keys to cart mutation and simulated checkout paths.

#### Aakash

- Complete the responsive cart UI, product confirmation cards, totals, and server-confirmed state updates.
- Add cached recent products and the last confirmed cart snapshot using IndexedDB through a typed wrapper.
- Never show an optimistic cart mutation as confirmed before the server result.

#### Shared output

- All shopping operations work through REST and direct tool tests before they are exposed through voice.
- Catalogue reaches the targeted 50–100 records only as verified metadata becomes available; unverified records are clearly marked and excluded from calculations.

### Week 6: 12–18 October — voice-enable every task and clarification

#### Punyansh

- Add intent/entity examples for every tool and multi-turn clarification cases.
- Build controlled response templates for success, empty results, invalid units, ambiguity, insufficient stock, empty cart, and checkout.
- Evaluate forward and reverse translation failures that change products, numbers, units, or negation.

#### Harsh

- Route every validated interpretation to the correct domain tool.
- Add short-lived conversation context containing only resolved references and pending clarification fields.
- Revalidate entities after clarification; never execute an incomplete original tool call.
- Enforce safety both before interpretation and inside sensitive calculation/tool paths.

#### Aakash

- Implement clarification turns without resetting the whole voice session.
- Add explicit listening, processing, executing, speaking, failed, and interrupted states.
- Provide visible keyboard-accessible correction/retry controls while preserving voice as the primary path.

#### Shared output

- Search -> details -> add -> view -> remove -> calculate -> simulated checkout works by voice.
- Ambiguous “add it” or missing-quantity cases cause a spoken clarification, not a guess.

### Week 7: 19–25 October — streaming, VAD, barge-in, and network reliability

#### Punyansh

- Tune Silero VAD on representative quiet/noisy browser recordings and document thresholds.
- Make model stages cancellation-aware at safe boundaries.
- Pre-synthesize fixed safety and network prompts where appropriate.

#### Harsh

- Implement cancellation propagation and stale-turn suppression.
- Prevent interrupted/late turns from mutating the cart.
- Add request timeouts, readiness status, bounded inference concurrency, and overload errors.
- Add tests for duplicate, delayed, reordered, and cancelled control events.

#### Aakash

- Integrate browser endpoint detection through `AudioWorklet`/metering if the Week 1 spike proved reliable; retain push-to-talk fallback and server-side Silero.
- Stop `HTMLAudioElement` or Web Audio playback when new speech/recording begins and send `interrupt_turn`.
- Add the configured eight-second timeout, bundled failure prompt, retry UI, and cached catalogue view.
- Test permission denial/revocation, tab visibility changes, route navigation, page refresh/unload, disconnected WebSockets, autoplay rejection, and microphone/output-device changes where supported.

#### Shared output

- Demonstrable barge-in and clean recovery without duplicate cart mutations.
- Demonstrable network-disconnect behavior with no frozen screen.

### Week 8: 26 October–1 November — feature freeze and pass Checkpoint 2

#### Team integration work

- Run the complete final demo script repeatedly in the primary Chromium browser and at least one secondary browser where feasible.
- Fix all severity-1 issues: crash, unsafe response, wrong transaction, stale playback/action, inability to start, or unrecoverable voice state.
- Fix severity-2 issues affecting a required scenario.
- Create at least one integration test/fixture for every tool and safety outcome.
- Freeze tool schema, WebSocket protocol, database schema except bug-fix migrations, and web routes/navigation.
- Produce a production Vite bundle served by FastAPI and a reproducible backend startup bundle.

### Checkpoint 2 acceptance gate

Checkpoint 2 passes only if:

- every required shopping intent works through real speech in the supported browser;
- all mutations are schema-validated, authenticated, transactional, and retry-safe;
- all catalogue facts and calculations are grounded in the database;
- critical unsafe requests always reach the fixed refusal in the regression suite;
- clarification, interruption, timeout, and network recovery work;
- the team can run a 10-minute end-to-end demo without manual database repair;
- no Level 3 feature remains on the active board.

After this checkpoint, feature work stops. November is for measurement, reliability, documentation, and presentation.

## Checkpoint 3: Evaluated Release Candidate

**Dates:** 2–29 November 2026

**Purpose:** Turn the feature-complete prototype into an academically defensible final submission.

### Week 9: 2–8 November — controlled evaluation dataset and full baseline

#### Punyansh

- Finalize the evaluation manifest and normalization rules before running the held-out set.
- Target 12–15 consenting speakers and 180–250 total utterances if approvals, time, and access permit; define a minimum viable set of 8 speakers/120 utterances.
- Keep speakers used for vocabulary/prompt development separate from held-out speakers where feasible.
- Compute ASR WER/CER, intent accuracy, entity precision/recall/F1, tool/schema validity, safety false positives/negatives, and TTS real-time factor.

#### Harsh

- Export anonymized per-stage timings and outcomes into machine-readable evaluation records.
- Verify that evaluation logging excludes JWTs, secrets, names, phone numbers, and raw audio unless explicitly consented.
- Run backend transaction, idempotency, ownership, and failure-injection tests.

#### Aakash

- Build an instrumented web release that records task outcome, retries, clarification, timeout, and user cancellation without collecting unnecessary PII.
- Validate the full task script and audio behavior in the supported browser matrix, using built-in and external microphones where available.

#### Shared output

- Frozen held-out dataset/manifest.
- One complete, unrevised baseline result set, including failures.

If human-subject approval or consent cannot be completed in time, do not collect covert or informal recordings. Use only appropriately consented team/volunteer data and state the limitation clearly.

### Week 10: 9–15 November — improve only measured bottlenecks

Use the Week 9 results to choose at most two high-impact improvements. Examples:

- agriculture keyword recall is poor -> improve lexicon/normalization or domain adaptation;
- translation changes quantities/negation -> add protected tokens, controlled templates, or terminology handling;
- tool validity is poor -> improve grammar constraints/examples or use a smaller deterministic pre-router;
- latency is dominated by model loading -> keep models warm and revise placement;
- TTS first audio is late -> synthesize shorter clauses or stream/pre-render common prompts;
- VAD cuts speech -> retune thresholds and retain push-to-talk fallback.

#### Ownership

- Punyansh implements and measures model/pipeline improvements.
- Harsh implements orchestration/performance improvements and guards against regressions.
- Aakash measures perceived behavior in the browser and ensures improvements do not break playback/state.

Rerun the same frozen evaluation set and publish before/after results. Do not tune on the held-out labels repeatedly; use a development subset for iteration and run the final held-out evaluation once the choice is frozen.

API-assisted or SraVaani comparisons happen only if the local MVP, report pipeline, and final demo are already safe. They are optional research comparisons, not release blockers.

### Week 11: 16–22 November — release candidate, usability walkthrough, and report

#### Punyansh

- Finalize model/data cards, evaluation tables, error analysis, safety analysis, and limitations.
- Select honest qualitative examples: success, ASR error, translation drift, clarification, and safety refusal.

#### Harsh

- Produce one-command or clearly documented startup steps, seed/migration process, health checks, and backup/restore instructions.
- Freeze configuration defaults and generate the release evaluation report artifacts.
- Review security, secrets, log redaction, and demo-user setup.

#### Aakash

- Produce the release-candidate web bundle, onboarding/demo instructions, and browser compatibility notes.
- Conduct a small structured usability walkthrough if approved, recording task completion and short feedback rather than leading participants.
- Fix only release-blocking responsive UI, browser lifecycle, audio, and accessibility issues.

#### Shared output

- Release Candidate 1 by 22 November.
- Draft final report sections and architecture diagrams.
- A screen-recorded backup demonstration with audible input/output and visible stage/result confirmation.

### Week 12: 23–29 November — freeze, rehearse, and deliver

#### 23–24 November

- Fix only critical regressions.
- Tag/freeze code, model configuration, database seed, production web bundle, and evaluation outputs.
- Verify build and startup from a clean checkout and clean browser profile where possible.

#### 25–26 November

- Complete report, references, diagrams, setup guide, limitations, future-scope section, and individual contribution record.
- Cross-check every numerical claim against generated output.
- Cross-check every claimed feature against the release build.

#### 27–28 November

- Run at least three full timed rehearsals.
- Rehearse failure recovery: backend restart, microphone denial, unsupported/insecure context, disconnected WebSocket, slow response, and model not ready.
- Prepare power, charger, a supported browser profile, backup microphone/headset if available, pre-seeded database, cached dependencies/assets, and a screen-recorded fallback demo.

#### 29 November

- Final acceptance run and archive.
- Deliver the production web bundle, frontend/backend source and setup, configuration manifest, database seed, metrics, report, slides, and backup demo.
- No new features or model swaps.

#### 30 November

Emergency buffer only. Use it for packaging or a release-blocking correction, not improvements.

### Checkpoint 3 acceptance gate

The project is complete when:

- a clean setup can run the documented local demo topology;
- the final script works from spoken input through spoken output;
- safety and critical transaction regression suites pass;
- measurements are reproducible and include failures/limitations;
- the production web bundle, backend, seed data, model manifest, and documentation agree;
- a live demo and recorded fallback are ready;
- the report clearly presents S2S as the central contribution and shopping as the reference implementation.

## Weekly operating rhythm

### Monday: 25-minute planning

- Review the checkpoint gate.
- Select at most two active tasks per member.
- State every cross-member dependency and its needed date.
- Move optional work below the line.

### Wednesday: 45-minute integration session

- Merge and run the current vertical slice in the integration browser.
- Inspect one trace from audio input to response playback.
- Resolve contract mismatch immediately; do not defer all integration to Sunday.

### Friday or Saturday: test and measure

- Run fast tests, one model smoke test, and the current demo script.
- Record new failures and performance changes.
- Update setup instructions when they are discovered to be wrong.

### Sunday: checkpoint review

- Demonstrate completed work, not slides about work.
- Merge small reviewed changes to the main branch.
- Record a short decision note for any scope, model, protocol, or safety change.
- Replan the next week from actual progress.

### Branch and review rules

- Keep the main branch runnable.
- Use small feature/fix branches and descriptive commits.
- Require one teammate to review changes affecting contracts, safety, transactions, or evaluation.
- Require both affected owners to review a cross-layer protocol change.
- Never commit credentials, raw participant recordings, large checkpoints, or database dumps.

## Evaluation targets and release gates

These are engineering targets for planning, not results to claim before measurement.

| Area | Provisional target | Hard release behavior |
| --- | --- | --- |
| Tool schema validity | 100% for executed calls | Invalid calls are rejected; never execute malformed output |
| Catalogue grounding | 100% of stated products/prices/totals come from backend results | Unknown product triggers suggestions/clarification |
| Cart transaction tests | 100% critical-path pass | No duplicate mutation on retry/interruption |
| Safety critical suite | Zero generated diagnosis/dosage advice | Fail closed to fixed referral when classification is uncertain |
| Intent accuracy | Aim for at least 85% on held-out commands | Report actual value and confusion matrix |
| Entity F1 | Aim for at least 80% overall, with per-entity breakdown | Missing critical entities trigger clarification |
| Clean scripted task completion | Aim for at least 90% | Every required demo scenario has a reliable tested phrase |
| Median response latency | Aim below 5 seconds to first response audio on integration hardware | Show progress; configured timeout and recovery must work |
| Warm p95 latency | Aim below 8 seconds | Do not hide slow/failing turns; report hardware and distribution |
| Barge-in | Playback stops promptly; exact target set after Checkpoint 1 measurement | Old turn must not speak or mutate state afterward |
| ASR WER/CER | Baseline in Checkpoint 1; improvement target chosen from error analysis | Report honestly even if the numeric target is missed |

If an accuracy target is missed but the system safely asks for clarification and completes tasks, report both the raw metric and recovery success. Do not tune the report by dropping hard utterances.

## Final demonstration script

Freeze exact native-speaker-reviewed Chhattisgarhi phrases by 15 November. The demo should cover:

1. **Search:** Ask for a product/category and hear available matches.
2. **Details/price:** Ask the price or details and show that the answer matches PostgreSQL.
3. **Cart:** Add a specified quantity and hear/see confirmation.
4. **Clarification:** Give an incomplete or ambiguous request and answer the follow-up.
5. **Quantity:** Ask how much of an allowed product is needed for a field area; show the verified metadata and deterministic arithmetic.
6. **Cart state:** View/remove an item and confirm the total.
7. **Safety:** Ask a crop-diagnosis or pesticide-dosage question and receive only the fixed KVK referral.
8. **Barge-in:** Interrupt a spoken response with a new request; the old response/action must stop.
9. **Recovery:** Demonstrate the local timeout/network prompt without corrupting the cart.
10. **Simulated checkout:** Create a non-payment order and clearly state that it is simulated.

Keep the live demonstration under ten minutes. Show one evaluation dashboard/table after the interaction rather than narrating every internal technology before users see the system work.

## Work that must not enter the critical path

Do not schedule these before the three checkpoint gates are secure:

- real payments or UPI;
- OTP/SMS integration;
- vendor or admin dashboards;
- multi-vendor inventory;
- delivery tracking;
- native mobile packaging or app-store work;
- a public production deployment;
- multiple additional languages;
- RAG over the small catalogue;
- model training from scratch;
- open-ended agricultural advice;
- elaborate animations or marketplace-style UI.

## Risk register and fallback decisions

| Risk | Detect by | Primary response | Safe fallback | Owner |
| --- | --- | --- | --- | --- |
| Existing ASR/TTS code or checkpoints are not reproducible | 10 Sep | Consolidate environments and smoke commands | Isolate legacy model in a worker process; document exact environment | Punyansh |
| All models do not fit/run together | 13 Sep | Measure memory and stage latency | CPU/offload/quantize or split processes; keep model adapters unchanged | Punyansh + Harsh |
| Browser audio container/VAD support differs | 13 Sep | `MediaRecorder.isTypeSupported()` and AudioWorklet spike | Runtime capability detection, push-to-talk, and server-side Silero; document the supported browser | Aakash |
| NLLB changes product names, numbers, units, or negation | 27 Sep | Translation error set | Protect/restore entities, use controlled templates, ask clarification | Punyansh |
| Local LLM emits invalid tools | 27 Sep | Schema-validity tests | Grammar-constrained output, one repair, then clarification/refusal | Punyansh + Harsh |
| LLM invents product or price | Continuous | Grounding tests | Backend rejects unresolved IDs and constructs response from `ToolResult` | Harsh |
| Unsafe query bypasses classifier | Continuous; formal gate 1 Nov | Expand safety set and defense in depth | Fail closed to reviewed referral on uncertainty | Punyansh + Harsh |
| Cart duplicates after timeout/retry | 25 Oct | Failure-injection tests | Idempotency keys and database transaction constraints | Harsh |
| Web client becomes stuck after permission/tab/socket error | 25 Oct | Reducer/state-transition and Playwright/manual browser tests | Stop media tracks, close obsolete sockets, reset to a recoverable state, and preserve confirmed cart only | Aakash |
| Participant/data approval is delayed | 18 Oct | Supervisor review | Use only consented team/volunteer data; reduce claims and report limitation | All |
| External API access is absent | Immediate | None required | Local pipeline remains the official MVP | All |
| Schedule slips | Weekly | Cut optional work immediately | Preserve search/cart/safety/S2S/evaluation; cut polish and comparisons | All |

## Required project artifacts

By final delivery, the repository or release archive should contain:

- `README.md`: quick start and project overview;
- `docs/architecture.md`: S2S core, shopping adapter, deployment, and turn state machine;
- `docs/voice_protocol.md`: WebSocket messages, audio formats, errors, cancellation;
- `docs/tool_schemas.md`: intent/entity taxonomy and validated tool arguments;
- `docs/safety_policy.md`: allowed/disallowed/ambiguous cases and fixed response behavior;
- `docs/data_and_consent.md`: sources, licenses, collection, privacy, retention, and splits;
- `docs/evaluation_protocol.md`: metrics, hardware, normalization, manifests, commands;
- `docs/demo_runbook.md`: setup, exact scenarios, recovery, and backup procedure;
- backend source, migrations, tests, seed importer, and redacted environment example;
- React/TypeScript source, browser tests, and production Vite bundle;
- non-sensitive evaluation manifests and generated aggregate results;
- model/configuration manifest with retrieval locations and checksums where possible;
- final report, slides, and recorded fallback demonstration.

Model weights, raw participant audio, secrets, and private database dumps must not be committed to Git.

## Scope-cut order if the team falls behind

Cut work in this order, from first to remove to last to protect:

1. API-assisted/Bhashini comparison.
2. SraVaani model comparison.
3. automatic VAD polish beyond a dependable push-to-talk fallback.
4. elaborate offline catalogue browsing and images.
5. multi-turn memory beyond one pending clarification/resolved referent.
6. nonessential catalogue categories and UI polish.

Never cut the core spoken input/output loop, grounded search/cart actions, fixed safety refusal, transaction correctness, basic timeout recovery, or honest evaluation. Those are the project.

## Immediate first actions

On the first working day:

1. Create the issue board with the three checkpoints and weekly milestones.
2. Inventory and import the team's existing ASR/TTS code and checkpoint metadata.
3. Inventory hardware, browsers, microphones, and headsets.
4. Agree on the final demo's must-have scenarios.
5. Initialize backend, React web client, PostgreSQL, tests, and documentation structure.
6. Schedule the Week 1 joint protocol review and Week 3 first vertical-slice demo.

The team should judge progress by the quality of the integrated spoken interaction produced every week—not by the number of isolated files, screens, endpoints, or models created.
