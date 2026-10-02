# Overview & Research Thesis

## Core Thesis

> **Can a predominantly open-source, locally runnable, cascaded Speech-to-Speech (S2S) system support accurate, useful, and safe voice interaction in Chhattisgarhi under realistic student-compute and connectivity constraints?**

The agricultural shopping demo is the **reference implementation and evaluation environment** — it supplies real state, structured tools, safety constraints, and end-to-end user tasks. It is **not** the main novelty.

The **novelty** is the careful integration and empirical evaluation of a reusable, streaming, interruption-aware voice-to-voice layer for a low-resource language, including:

1. Spontaneous Chhattisgarhi speech input (not Hindi/English-first)
2. Observable cascade with measurable per-stage error sources
3. Agricultural/shopping vocabulary adaptation + code-switch handling
4. Informal speech → schema-valid grounded actions
5. Spoken Chhattisgarhi response generation
6. Interruption/barge-in + useful feedback during multi-second inference
7. Hard boundary: transactional help only, no agronomic advice
8. Reusable architecture: shopping domain = adapter around S2S core

---

## What Is Novel vs. Not Novel

| Novel (Our Contribution) | Not Novel (Prior Work) |
|---------------------------|------------------------|
| Chhattisgarhi-first voice pipeline integration | ASR (MMS, Whisper), MT (NLLB), TTS (VITS), LLM tool-calling |
| Observable cascaded error measurement | Agricultural e-commerce concepts |
| Domain vocabulary adaptation for hne | WebSocket audio streaming |
| Spoken response in Chhattisgarhi | FastAPI, PostgreSQL, React |
| Barge-in + recovery in low-resource S2S | Silero VAD, Coqui TTS |
| Safety boundary enforcement via templates | JSON file locking, idempotency |

**Description:** Research prototype — not production marketplace, not medical/agri advisor, not statistically validated deployment.

---

## Priority Order (When Choices Compete)

1. **End-to-end Chhattisgarhi voice-to-voice quality & natural interaction**
2. **Measurability, reproducibility, honest stage-by-stage evaluation**
3. **Safety, deterministic execution, privacy, traceability**
4. **Clean separation: reusable voice core vs. domain-specific behavior**
5. **Correct shopping workflow & transactional state**
6. **Web UI polish / e-commerce feature expansion**

> Do NOT optimize catalogue UI, payments, marketplace, or vendor ops at the expense of ASR, MT, orchestration, TTS, latency, barge-in, recovery, or evaluation.

---

## Users & Operating Conditions

| User | Constraint |
|------|------------|
| Smallholder farmer, mainly Chhattisgarhi | Voice for entire task, limited digital literacy |
| Code-switcher (Chhattisgarhi ↔ Hindi) | Avoids typing/menu navigation |
| Rural, intermittent 3G/4G | Needs visible/audible progress, clear recovery |

**Assumptions:**
- Ordinary laptop/desktop browsers (Chromium primary, Firefox checked)
- Variable microphones, background noise
- Informal/incomplete utterances, hesitations, accents
- Unstable networks
- **NOT assumed:** studio speech, constant broadband, high digital literacy, English literacy, identical codec behavior

---

## Scope Levels (Formal)

### Level 1: Preliminary Work (Already Demonstrated)

- FastAPI + WebSockets streaming 16 kHz PCM
- Silero VAD for speech boundaries + barge-in events
- Meta MMS `facebook/mms-1b-all` + `hne` adapter for ASR
- Pluggable `ASREngine` + shared inference workers
- Devanagari CTC cleanup for detached matras
- Coqui-TTS VITS with custom Male/Female Chhattisgarhi checkpoints
- Model-level speech pacing via `length_scale`
- English-only `faster-whisper` fallback
- Telephony adapter for 8 kHz mu-law (extensibility evidence)

> **L1 does NOT establish:** calibrated WER, production latency, agri vocab performance, translation quality, safe tool calling, web integration, user usability.

### Level 2: Current Minor Project MVP (Deliverable)

| Capability | Status |
|------------|--------|
| Product search & browsing | ✅ |
| Product details & price queries | ✅ |
| Deterministic quantity calculation (verified metadata) | ✅ |
| Add/remove cart | ✅ |
| View cart + total | ✅ |
| Simulated checkout (no payment) | ✅ |
| Spoken Chhattisgarhi responses | ✅ |
| Safety refusal + KVK referral (diagnosis/dosage) | ✅ |
| Voice, intent, outcome, latency instrumentation | ✅ |
| Minimal responsive web UI (confirm text, products, cart) | 📋 Spec only (`WEB_APP_SPECIFICATION.md`) |

### Level 3: Future Work (NOT Current Deliverable)

- Real UPI / payment gateway
- Live multi-vendor inventory sync
- Seller dashboards
- Delivery routing, tracking, OTP
- Unsupervised crop diagnosis / pesticide recommendation
- Production-scale farmer profiling/analytics
- Broad multilingual beyond evaluated Chhattisgarhi path

> Keep architecture open to L3, but don't let speculative generality block strong Chhattisgarhi S2S MVP.

---

## Research Questions (Implementation Must Help Answer)

| # | Question |
|---|----------|
| RQ1 | How accurately can informal Chhattisgarhi speech become correct shopping intents/entities (product, crop, quantity, unit, area)? |
| RQ2 | How much error is contributed by ASR, forward MT, intent/entity extraction, domain execution, response MT, TTS respectively? |
| RQ3 | Can constrained tool calling produce valid grounded operations without inventing products, state, prices, quantities, advice? |
| RQ4 | What end-to-end and per-stage latency does a zero-budget local pipeline have vs. API-assisted option (if available)? |
| RQ5 | Does voice-first interaction improve task completion/usability for Chhattisgarhi speakers with limited digital literacy vs. text search? |
| RQ6 | How intelligible, natural, interruption-tolerant, recoverable is the **complete spoken interaction** (not just intermediate text)? |

> RQ6 makes S2S emphasis explicit: pipeline fails if ASR transcript looks correct but user cannot complete spoken task or understand spoken result.

---

## Proposed Technology Baseline (Default Unless Measurements Justify Change)

| Layer | Default | Notes |
|-------|---------|-------|
| Web client | React + TypeScript + Vite | Browser mic, voice state, WS transport, playback, confirmations |
| API/Orchestrator | Python + FastAPI | REST for resources; WS/SSE for streaming |
| VAD | Silero VAD (ONNX) | Configurable thresholds, evaluate on representative audio |
| Chhattisgarhi ASR | Meta MMS 1B + `hne` adapter | Existing baseline; no WER claim until measured |
| ASR Comparison | SraVaani-1.0 | Benchmark candidate, not MVP dependency |
| Translation | NLLB-200 distilled 600M, `hne_Deva` | Measure translation drift as own failure source |
| Intent/Entities | Local instruction-tuned, tool-capable | Strict schemas; no paid provider assumed |
| TTS | Coqui-TTS VITS, existing checkpoints | Preserve Male/Female + pacing controls |
| Database | PostgreSQL | Transactions + referential integrity required |
| Optional APIs | Bhashini/hosted LLM only if confirmed | Comparison path, never hidden dependency |

> Zero-allocated budget. Prefer open-source + locally runnable. Never add paid/access-controlled service as required path without explicit approval, documented fallback, updated scope/cost docs.

---

## Next: `02-request-to-response-master.md` → all 4 flows with mermaid