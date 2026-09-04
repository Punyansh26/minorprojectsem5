# Web Application Specification

## Status and scope

This document defines the web client for the **Chhattisgarhi voice-to-voice agricultural shopping assistant**. It is the product, UI/UX, and front-end implementation reference for the Minor Project MVP.

The project proposal refers to a Flutter client; the repository-wide decision is now **web development only**. The user experience and research scope remain the same: a voice-first, safety-bounded shopping prototype. This is not a marketplace, payment app, crop-diagnosis service, or pesticide advisor.

The primary supported environment is a current Chromium-based desktop browser. The experience must remain responsive on mobile browsers, and Firefox must be checked for core capture, cart, and accessibility behavior. A secure context is required for microphone access (`localhost` is valid in development; deployed builds require HTTPS/WSS).

## 1. Product definition

### 1.1 User promise

The user can speak naturally in Chhattisgarhi to find a product, hear verified product information, update a cart, and complete a simulated checkout. The page always makes clear:

- what the system heard;
- whether it is listening, working, speaking, interrupted, or needs help;
- what grounded action was actually completed; and
- how to correct, cancel, or continue without needing to type.

Voice is the primary completion path. Text search, product cards, cart buttons, and typed input are useful fallbacks and confirmation mechanisms; they must not become a requirement for a voice-first user.

### 1.2 Supported MVP tasks

| Capability | Voice examples | Required client result |
| --- | --- | --- |
| Search/browse products | “धान के बीज देखाव” | Speak and show a short, grounded result set. |
| Product details and price | “ए बीज के दाम का हे?” | Speak and show facts returned by the catalogue only. |
| Verified quantity calculation | “दू एकड़ बर कतका बीज चाही?” | Collect missing product/area/unit details; display result and source/provenance supplied by the backend. |
| Add or remove cart items | “दू पैकेट टोकरी मं डाल दे” | Show an explicit confirmed cart mutation, never an optimistic unconfirmed state. |
| View cart and total | “मोर टोकरी देखाव” | Speak a concise summary and open/update the cart. |
| Simulated checkout | “ऑर्डर पूरा कर दे” | Present final order summary and record a simulated order; never collect payment data. |
| Safety refusal | Crop diagnosis, pesticide selection, dosage, or application request | Stop the shopping flow, present and speak the fixed reviewed KVK-referral response; show no model-generated advice. |

Not in this release: payments/UPI, delivery, tracking, vendor tools, user farming profiles, unrestricted recommendations, crop diagnosis, treatment selection, pesticide dosage, or broad multilingual support.

### 1.3 Users and design consequences

| Primary user condition | UX implication |
| --- | --- |
| Mainly Chhattisgarhi-speaking, low digital literacy | One obvious speak control; plain, short labels; no hidden essential action; voice response carries the outcome. |
| Chhattisgarhi/Hindi code-switcher | Do not reject Hindi terms or mixed speech; show the actual recognized transcript and allow correction/retry. |
| Intermittent 3G/4G | Compact audio, clear progress, bounded waiting, idempotent retry, and never claim an unconfirmed change. |
| Variable microphone/noise | Mic check, visible input meter, push-to-talk fallback, transcript confirmation, and useful recovery prompts. |
| Screen-reader/keyboard user | Fully operable semantic controls, live status announcements, visible focus, and no audio-only status. |

## 2. Information architecture

The app has four persistent destinations. Navigation must be optional during voice use; a user should be able to remain on Home and complete the MVP tasks.

```text
App shell
├── Home / Speak
│   ├── Voice interaction panel
│   ├── Current result / clarification / safety card
│   ├── Suggested task chips
│   └── Recent or featured catalogue items
├── Products
│   ├── Search and category filters
│   ├── Product results
│   └── Product detail
├── Cart
│   ├── Cart lines and totals
│   └── Simulated checkout
└── Help & settings
    ├── Voice and playback preferences
    ├── Microphone/support information
    ├── Privacy and data-use notice
    └── Safety boundary / KVK referral explanation
```

Use a desktop top navigation and a mobile bottom navigation. Both must expose Home, Products, Cart (with item count), and Help. The primary voice action stays fixed and reachable from every screen.

## 3. Visual design system

### 3.1 Design character

The visual language should feel calm, practical, rural-friendly, and trustworthy—not like a generic chatbot or a dense e-commerce marketplace. It should use strong hierarchy, generous spacing, recognisable product imagery, and low reading burden. Avoid decorative AI imagery, stock-farmer hero banners, unnecessary animation, and information-heavy dashboards.

### 3.2 Tokens and layout

Implement tokens as CSS custom properties or an equivalent typed theme. Final values may be adjusted after contrast testing, but preserve the roles below.

| Token role | Direction |
| --- | --- |
| Brand / action | Deep leaf green, used for the main speak and confirmed-action controls. |
| Supporting accent | Warm grain/gold for attention and progress, not as the only error indicator. |
| Background | Warm off-white / pale soil neutral. |
| Surfaces | White with subtle borders or low-elevation shadows. |
| Text | Near-black green/charcoal; meet WCAG AA contrast. |
| Success | Distinct green plus icon and text. |
| Warning | Amber plus icon and text. |
| Error/safety | Dark red or burgundy plus icon and explicit text. |

- Use an 8 px spacing scale.
- Use a readable Devanagari-capable sans-serif font with system fallbacks; verify glyph rendering for Chhattisgarhi text.
- Body text: at least 16 px; key status and voice controls: at least 18 px.
- Interactive targets: at least 44 × 44 CSS px; the main microphone control should be 72–96 px.
- Desktop content width: approximately 1,200 px maximum. Keep the voice panel within the first viewport and avoid a full-width text wall.
- Product grids: 3–4 columns on wide desktop, 2 on tablet, 1–2 on narrow mobile. Product cards must remain readable at 320 px width.
- Respect `prefers-reduced-motion`; motion must communicate state, not decorate the page.

### 3.3 Standard component treatment

| Component | Visual/behavior rule |
| --- | --- |
| Primary button | Solid green, icon plus short label, clear pressed/focus/disabled state. |
| Secondary button | Outlined or neutral surface; never visually compete with “Speak”. |
| Voice orb/button | Central, labelled, state-coloured, with a text status beside it. Do not rely on pulsing alone. |
| Status pill | Icon + short state text; colour is supplemental only. |
| Product card | Image, category, name, price/unit, availability, one concise action. No invented ratings/reviews. |
| Confirmation card | Prominent action outcome with product, quantity, price/total where relevant, and “Undo” only if backend supports a safe compensating action. |
| Safety card | High-contrast boundary message, fixed reviewed copy, KVK referral, and an option to return to product search. |
| Skeleton/loading | Preserve layout while data is loading; never display a misleading completed cart state. |

## 4. App shell and primary screen

### 4.1 Global header

The header contains:

1. Product mark/name and a concise Chhattisgarhi-first tagline.
2. Navigation links.
3. Cart button with count and accessible label (for example, “Cart, 2 items”).
4. A compact connection/service indicator only when degraded; do not show technical model status to normal users.
5. Account menu or clearly marked guest/demo state. Authentication must not block exploration of publicly visible product data, but mutations and checkout require an authenticated session according to backend policy.

### 4.2 Home / Speak screen

This is the default screen and the main research interaction surface.

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Brand     Home  Products  Cart (2)  Help                  Account    │
├─────────────────────────────────────────────────────────────────────┤
│  बोल के खोजव / Speak your request                                   │
│  Search products, ask price, manage your cart.                      │
│                                                                     │
│          [status: Ready to listen]                                  │
│               ┌─────────────────┐                                   │
│               │   🎙  Speak     │   [Type instead] [Mute/volume]   │
│               └─────────────────┘                                   │
│                                                                     │
│  Try: [Find paddy seed] [Check price] [View my cart]                │
│                                                                     │
│  What I heard                                                        │
│  “...”  [Edit] [Send] [Try again]                                  │
│                                                                     │
│  Assistant result / clarification / safety response                 │
│  [spoken-response controls] [product cards]                         │
├─────────────────────────────────────────────────────────────────────┤
│ Recent products / categories              Cart summary (desktop)    │
└─────────────────────────────────────────────────────────────────────┘
```

Rules:

- Keep the main voice control above the fold on desktop and mobile.
- The heading, control labels, response text, and spoken content should be Chhattisgarhi-first; a short Hindi/English gloss may be offered in settings, never substituted by default.
- Suggested chips are examples, not commands that silently execute. Selecting one pre-fills or speaks an example and requires an intentional send/speak action.
- “What I heard” appears for every finalized turn, including text fallback. It distinguishes provisional partial text from final text.
- The result area changes by outcome: results, a short clarification question, an action confirmation, a failure/recovery panel, or a safety refusal.
- On wide screens, show a compact cart summary beside or below the conversation; on mobile, use the Cart destination and a small sticky cart badge.

## 5. Voice interaction state machine

The client must model voice interaction explicitly. Components receive a typed state model; presentation components must not parse WebSocket events or infer state from arbitrary strings.

```text
idle
  → permission_check → listening → speech_detected → processing → responding
         │                  │             │               │            │
         │                  │             └→ idle          │            └→ idle
         │                  └→ cancelled / failed          │
         └→ permission_denied                              ├→ clarification
                                                           ├→ safety_refusal
                                                           ├→ failed → recovering → idle
                                                           └→ interrupted → listening
```

| State | User-facing copy/visual | Allowed user actions |
| --- | --- | --- |
| Idle | “Tap to speak” / ready indicator | Start voice, type request, browse. |
| Permission check | Explains browser microphone request | Continue or cancel. |
| Listening | Live meter and “Listening…” text; obvious Stop control | Stop/send, cancel. |
| Speech detected | “I can hear you” with bounded live transcript if available | Keep speaking, stop. |
| Processing | Step-neutral “Understanding your request…” and elapsed-wait cue; do not expose unsupported fake stage completion | Cancel; browse cached data. |
| Responding | Response text, audio progress, Replay, Stop | Stop playback; speak to barge in; inspect result. |
| Clarification | One concise question and resolved context card | Answer by voice/type, cancel context, select offered option. |
| Interrupted | “Listening to your new request” after stopping old audio promptly | Continue new turn or cancel. |
| Failed/recovering | Specific plain-language cause and next action | Retry safe action, type instead, check connection, browse cache. |
| Safety refusal | Fixed refusal/referral text and KVK action | Return to product search, replay response. |

### 5.1 Capture and turn behavior

- Ask for microphone permission only after the user activates Speak. Before this, explain why voice permission is useful and show the typed fallback.
- Prefer `AudioWorklet` for low-latency PCM/metering or client VAD when supported. Provide a dependable push-to-talk or `MediaRecorder` fallback.
- Feature-detect `MediaRecorder` types with `MediaRecorder.isTypeSupported()`; report the actual recording MIME type. Never label all uploads “Opus” by assumption.
- Canonical backend inference format is mono 16 kHz PCM after server-side decode/resample. The client must not imply that browser capture is already that format unless it is.
- Keep audio chunks bounded. Monitor `WebSocket.bufferedAmount`; pause/cancel according to the protocol before memory grows unbounded. Tell the user when a connection is too slow to continue.
- Use final transcript/validated interpretation only for cart or checkout actions. Partial transcripts are display-only.
- Generate and retain a conversation/session ID, turn ID, and idempotency key for every mutation-capable turn. The UI applies result events only if their turn ID is current.
- On page hide, navigation/unload, device loss, explicit Cancel, or barge-in, stop microphone tracks and cancel the active turn. Late ASR, tool, or TTS events must be ignored visually and must never revive playback.

### 5.2 Barge-in

When the assistant is speaking and the user taps Speak or VAD detects a new utterance:

1. Stop audio playback immediately.
2. Mark the preceding response as interrupted in the UI and trace.
3. Send cancellation for the preceding turn.
4. Start the new listening turn only after the client owns the new turn ID.
5. Suppress all late content/mutations from the interrupted turn.

Do not silently discard a completed cart mutation that occurred before interruption. Instead, show the confirmed action in history/result state, clearly separated from the new turn.

## 6. Functional screens and flows

### 6.1 Product browsing and search

The Products screen provides a visible fallback for the catalogue and a confirmation space for voice results.

- Search field with a microphone affordance and typed input; search supports aliases and tolerant matching through the backend.
- Category chips: Seed, Fertiliser, Basic tools, plus only categories actually present in the catalogue.
- Sort/filter controls must stay minimal: relevance/name, category, availability. Do not add marketplace-style filters unsupported by data.
- Empty state: “No matching product found” plus retry wording and a small set of valid example categories. Never invent a close match.
- Voice search result: annotate that results came from the last request; retain the transcript and a “Search again” action.
- A product card click opens details; Add to cart requires a clear quantity/unit choice if it is not already resolved.

### 6.2 Product detail

Show only verified, catalogue-grounded facts:

- image (with meaningful alt text), name, category, price and unit;
- availability state returned by backend;
- concise description, pack/unit information, and verified crop compatibility where available;
- approved calculation metadata/provenance only if it is verified and relevant;
- quantity selector with a visible unit and bounds from backend;
- Add to cart and “Ask by voice” controls.

Do not display dosage, application instructions, disease claims, ratings, discount percentages, “recommended for you,” or stock promises that are not verified data.

### 6.3 Cart

The cart must be a plain-language confirmation of server state, not a client-only scratchpad.

Each line shows product, unit/pack, quantity stepper, unit price, line total, Remove, and an accessible live update message after a confirmed change. The summary shows item count, subtotal/total using decimal money formatting, and a statement that checkout is simulated.

- Disable or constrain steppers using backend-provided quantity rules; handle rejection without losing the previous confirmed value.
- Show an empty-cart state with a route back to Speak/Search.
- While a cart mutation is pending, show a local pending indicator and prevent duplicate action; after timeout, show “We could not confirm this change” rather than assuming failure or success.
- If the backend returns a conflict or stale state, refresh the cart, explain that it changed, and preserve a retriable intent where safe.

### 6.4 Simulated checkout

Checkout is an intentional, reversible-looking confirmation flow but it creates a recorded simulated order. It must have:

1. Cart review with all totals and quantities.
2. Clear copy: “This is a simulated checkout. No payment, delivery, or order fulfilment is created.”
3. Single primary “Place simulated order” action.
4. Idempotent submission UI: disabled duplicate button, pending state, client idempotency key.
5. Completion receipt: simulated order ID, timestamp, line items, total, and “Continue shopping.”

Do not show address fields, cards, UPI, payment logos, delivery estimates, tracking, or success language suggesting a real purchase.

### 6.5 Clarification flow

Clarification is a successful safe outcome when product, quantity, unit, area, or cart referent is ambiguous.

- Ask one short question at a time in Chhattisgarhi.
- Show the understood context in compact editable chips, for example product and area, but do not present guessed values as confirmed.
- Offer up to three grounded selectable options only when the backend supplied them.
- Include “Start over” and “Cancel” without penalising the user.
- Never use a clarification card to lead a user into unsafe diagnosis or dosage advice.

### 6.6 Safety refusal and referral

The safety state has priority over product/assistant generation. Its UI and audio use a fixed reviewed Chhattisgarhi response obtained from the backend/template system.

- Header: “This assistant can help with shopping, not crop diagnosis or dosage.”
- Present a KVK/qualified-expert referral only with release-verified local details. Before details are verified, use the approved generic referral wording; do not fabricate a phone number, location, or contact link.
- Provide “Find products” and “Replay response,” not “Ask another farming question.”
- Do not echo unsafe requested dosage or generate an explanatory answer that could be construed as advice.
- Log the classified outcome through the backend with minimum necessary data; never expose internal safety confidence to the user.

### 6.7 Help, settings, and privacy

The Help screen should make the prototype understandable without technical jargon:

- how to speak, stop, replay, and correct a request;
- accepted task examples;
- a clear boundary: product discovery/cart help only, not advice on disease, sprays, or dosage;
- microphone troubleshooting and unsupported-browser message;
- playback/voice selection and speech-speed setting only if the TTS service actually supports these controls;
- privacy summary: what is captured, why, retention choice, and a link to the full project privacy notice;
- a consent control before optional evaluation recording, separate from normal product use.

Never put API keys, JWTs, raw audio URLs, model configuration, or debug traces in browser-visible settings.

## 7. Response, feedback, and language rules

### 7.1 Spoken and written response

- Keep one response focused on one outcome; lead with the answer/action, then a short next step.
- Render the Chhattisgarhi response text alongside every synthesized response so it is not audio-only.
- Provide Replay and Stop; audio starts only as allowed by browser user-gesture/autoplay policy. If autoplay is rejected, make Replay visually prominent and explain briefly.
- Show “Generated from verified catalogue data” only for outcomes whose payload/provenance supports that claim.
- Never expose raw English MT text as the normal user answer. A diagnostic/evaluation mode may capture it server-side with consent and access controls.
- Use plain, respectful Chhattisgarhi. Final reviewed strings and their Devanagari spelling live in versioned translation/template resources, not React components.

### 7.2 Progress feedback and latency

Target speech-end to first response audio byte is under five seconds; client timeout is configurable, initially eight seconds. Never fake precision such as “ASR 80% complete.”

| Wait condition | Client behavior |
| --- | --- |
| Under a brief threshold | Show a compact processing state. |
| Multi-second processing | Display/speak a short holding cue once, retain Cancel, and keep the transcript visible. |
| Service timeout | Cancel obsolete work, preserve no unconfirmed mutation, show retry/type fallback, and play the bundled Chhattisgarhi failure prompt where playback is permitted. |
| Network loss | Mark connection lost, stop sending audio, explain whether the action was confirmed, and allow only safe retries. |
| Reconnected | Restore browsing/cache state; do not automatically replay a potentially state-changing turn. |

## 8. Accessibility and inclusive interaction

The app must meet WCAG 2.2 AA as a project target for the web UI.

- Use semantic landmarks, heading order, `<button>` controls, visible focus rings, and logical keyboard order.
- Add `aria-live="polite"` for non-urgent listening/processing/status changes; use assertive announcements sparingly for permission denial, safety refusal, or confirmed mutation.
- Announce status with text, not sound or colour alone. The transcript and results remain available long enough to inspect.
- Every product image needs informative alt text; decorative imagery has empty alt text.
- Controls require labels in the active display language and accessible names that communicate purpose, for example “Start voice request.”
- Provide keyboard equivalents for start/stop, replay, cancel, cart review, and clarification options. Do not bind a global keyboard shortcut that steals focus from typing fields.
- Respect zoom up to 200%, landscape/narrow widths, reduced motion, high contrast, and browser text-size settings.
- Audio playback controls must not depend on dragging alone; volume and replay are operable with keyboard and touch.
- Typed requests offer a clear fallback to the same interpretation and safety path as voice input.

## 9. Client architecture and boundaries

Use React, TypeScript, Vite, and strict TypeScript settings. Keep browser-specific and protocol-specific logic outside page/presentation components.

```text
apps/web/src/
├── app/                 # routes, providers, application shell
├── features/
│   ├── voice/           # turn state, capture, playback, protocol controller
│   ├── catalogue/       # search, products, product detail
│   ├── cart/            # confirmed cart state and checkout
│   ├── auth/            # session UI only; no secrets
│   └── help/            # support, privacy, safety explanation
├── components/          # presentational reusable components
├── services/            # REST client, WebSocket client, cache adapter
├── hooks/               # UI-facing abstractions
├── types/               # versioned API and voice-event contracts
├── styles/              # tokens, global/reset, component styles
└── test/                # fixtures, doubles, browser test utilities
```

Required separation:

- `audioCapture`: permission, device selection, worklet/recorder fallback, chunks, meter, track cleanup.
- `voiceTransport`: session/connect/reconnect policy, bounded queue, outgoing audio metadata, typed incoming events, cancellation.
- `turnController`: valid state transitions, current turn ownership, stale-event suppression, timing capture.
- `audioPlayback`: decode/queue/play/stop/replay, autoplay failures, interruption latency.
- `catalogueApi` and `cartApi`: ordinary REST resources; they do not know audio or model stages.
- Page components: render typed view models and dispatch user actions; they do not access raw WebSocket messages or catalogue mutation endpoints directly.

The generic voice feature must not contain product aliases, price rules, catalogue SQL, cart IDs, safety copy, or agricultural calculations. Those belong to backend shopping/domain adapters and the response payloads they return.

## 10. Client–server contract requirements

Exact endpoint names may evolve, but all public messages must be versioned and typed. A voice turn needs at least:

```ts
type VoiceTurnStart = {
  schemaVersion: string;
  sessionId: string;
  conversationId: string;
  turnId: string;
  codec: string;
  mimeType: string;
  sampleRateHz: number;
  channels: number;
};

type VoiceEvent =
  | { type: "progress"; turnId: string; state: "listening" | "processing" | "responding" }
  | { type: "transcript"; turnId: string; text: string; isFinal: boolean; language: string }
  | { type: "clarification"; turnId: string; question: string; context: object; options?: object[] }
  | { type: "action_result"; turnId: string; result: GroundedActionResult }
  | { type: "safety_refusal"; turnId: string; response: FixedSafetyResponse }
  | { type: "audio"; turnId: string; sequence: number; format: AudioFormat; isFinal: boolean; data: ArrayBuffer }
  | { type: "error"; turnId: string; code: string; safeMessage: string; retryable: boolean };
```

Requirements:

- The client validates events at its boundary and fails safely on unknown schema/type/version.
- Every event carries `turnId`; stale events are logged locally for diagnostics if appropriate but never rendered as current state.
- `GroundedActionResult` contains only user-safe fields (resolved product ID/name, pricing/unit, cart/order state, provenance flags, and machine-readable outcome/error) needed for the UI.
- Mutations use an idempotency key and return a stable operation/result ID. Retrying cannot double-add, double-remove, or double-checkout.
- The server, not the browser, determines authorization, cart ownership, catalogue truth, stock, valid quantities, total, and whether an action was allowed.
- Audio format/sample rate/sequence/final status are explicit in messages; never infer TTS format from a file extension.
- Do not persist authentication tokens in unsafe browser storage by default. Follow the chosen authenticated transport/security design; never expose server secrets through `VITE_*` variables.

## 11. Offline, caching, and failure behavior

Cache only the app shell and recently viewed non-sensitive catalogue text/images when justified. IndexedDB/service-worker cache must not be treated as authoritative inventory, price, cart, order, or authentication state.

- Label cached product content when it may be stale and refresh it when connected.
- The cart screen always prefers the confirmed server response. While offline, hide/disable cart mutations and checkout with an explanation rather than queueing ambiguous state changes.
- A retry is permitted only for explicitly idempotent, safe operations. The UI must display whether a prior action was confirmed before offering retry.
- Provide a bundled pre-recorded Chhattisgarhi network-failure cue for ordinary voice failure, but ensure the written fallback remains available if audio cannot play.
- Test reordered, duplicated, dropped, and delayed network messages. No failure mode may leave a fake cart success message visible.

## 12. Privacy, security, and evaluation visibility

- Present concise microphone and recording notices before capture. Optional study recording requires separate informed consent.
- Do not request names, precise addresses, financial information, or unnecessary PII for evaluation.
- Default voice logs to the minimum needed for debugging/evaluation. Raw audio references, if used, follow a configurable retention policy and are never committed to Git.
- The user-facing UI shows a safe summary of the last recognized request/action; it must not expose raw authorization data, model prompts, provider responses, internal confidence, or debug exceptions.
- Development-only trace panels must be behind an explicit local development flag and must redact tokens and personal data.
- Error messages use stable safe codes/messages from the backend. Do not render stack traces or model output verbatim.

## 13. Acceptance criteria and test matrix

| Area | Minimum acceptance criterion |
| --- | --- |
| Voice start | A user gesture starts permission/capture; denial explains recovery and typed use remains possible. |
| Transcript | Final transcript is visible; partial text is visibly provisional and cannot mutate state. |
| Voice state | All defined states have text, visual, keyboard-accessible feedback and valid transitions. |
| Barge-in | Starting a new turn stops playback promptly and old-turn messages cannot update the current UI. |
| Search/details | Results and facts come from grounded backend payloads; missing products prompt retry/clarification, never invention. |
| Cart mutation | UI changes only after confirmed server result; duplicated/reordered responses cannot duplicate a mutation. |
| Calculation | UI shows required resolved metadata/context and communicates missing/invalid units as clarification; it never calculates locally from guessed values. |
| Checkout | Clearly simulated, idempotent, and contains no payment/delivery flow. |
| Safety | Representative diagnosis/dosage/code-switched requests render and speak only the fixed reviewed refusal/referral. |
| Failure | Timeout/offline/autoplay/socket/device-change cases offer a clear recovery action and no false success. |
| Accessibility | Keyboard, screen-reader announcements, contrast, focus, zoom, reduced-motion, and responsive checks pass. |
| Browser/audio | Chromium primary path works; Firefox core fallback is checked; unsupported codec/browser produces actionable feedback. |
| Instrumentation | Client records non-sensitive timing markers for capture/VAD, upload, first progress, final transcript, action result, first audio, playback stop, timeout, cancellation, and outcome, correlated by session/turn IDs. |

### Required test scenarios

1. Microphone allowed, denied, revoked during capture, no device, and device switched.
2. Text, push-to-talk, and streaming/VAD capture paths.
3. Partial transcript followed by cancellation; late final transcript/action/audio must be ignored.
4. Barge-in while audio plays and while a cart-capable request processes.
5. Product not found, ambiguous product, ambiguous cart reference, missing area/unit, invalid quantity, and out-of-stock response.
6. Network slow, WebSocket buffered, disconnect, reconnect, timeout, duplicate/reordered events, and retry after unknown outcome.
7. Autoplay rejection, tab hidden, page navigation, and replay/stop behavior.
8. Safety paraphrases, indirect requests, Hindi/Chhattisgarhi code-switching, multi-turn context, and prompt-injection-like spoken text.
9. Cart ownership/session expiry, stale cart version, duplicate idempotency key, and simulated checkout retry.
10. Keyboard-only, screen reader, 200% zoom, reduced motion, narrow mobile viewport, Chromium, and Firefox checks.

## 14. Explicit non-goals for UI implementation

Do not spend MVP time on promotional landing pages, real commerce styling, seller experiences, live maps, payment interfaces, delivery journeys, social features, ratings/reviews, analytics dashboards, generic chat history, or elaborate account profiles. Any UI addition must improve voice task completion, safety, recovery, measurability, or confirmation of grounded shopping state.

## 15. Implementation order

1. Theme, responsive shell, accessibility foundation, typed shared contracts, and mockable state machine.
2. Voice controls, transcript/progress/result panels, capture/playback fallback, cancellation and barge-in behavior.
3. Catalogue search/detail and confirmed cart UI against deterministic REST fixtures.
4. Clarification, safety, timeout/offline, and simulated checkout flows.
5. Live streaming protocol integration, instrumentation, cross-browser verification, and evaluation test fixtures.

This order intentionally establishes observable, safe voice behavior before catalogue polish.
