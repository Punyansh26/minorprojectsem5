# Chhattisgarhi Voice Shopping Assistant — End-to-End Documentation

**Project:** Minor Project, Semester 5, IIIT  
**Students:** Punyansh Thakur, Harsh Dadsena, Aakash Sen  
**Supervisor:** Prof. Santosh Kumar  
**Environment:** Conda `minor` (Python 3.11.15), React+TypeScript+Vite, FastAPI, PostgreSQL

---

## 30-Second Pitch

We built a **fully local, streaming Speech-to-Speech (S2S) pipeline** for Chhattisgarhi (ISO `hne`) that:
- Accepts spoken Chhattisgarhi → transcribes with **Meta MMS-1B + hne adapter** (Silero VAD for boundaries)
- Translates to English via **NLLB-200 distilled** → interprets intent/entities with constrained LLM → executes grounded tool calls on PostgreSQL
- Constructs response → translates back to Chhattisgarhi → synthesizes with **Coqui VITS (Male/Female)** → streams audio back
- All with **barge-in/interruption**, **idempotent transactions**, **safety boundary** (fixed KVK refusal for diagnosis/dosage), and **per-stage observability**

The agricultural shopping demo (50–100 seed/fertilizer items) is the **evaluation environment**, not the novelty. The reusable S2S core is.

---

## Repository Map

```
Minor/
├── app/                          # Web client (React+TS) — spec only, not implemented yet
│   └── README.md
├── code/                         # All runnable code
│   ├── STT/stt-service/          # FastAPI WebSocket microservice (MMS/Whisper + Silero VAD)
│   ├── TTS/chattisgarhi-tts-models/  # Pre-trained VITS Male/Female checkpoints (Coqui)
│   ├── Speech2Speech.ipynb       # End-to-end notebook bench (mic/WAV → STT WS → TTS)
│   ├── demo/                     # Kisan Saathi: Streamlit + Groq + MCP + local STT/TTS, JSON store
│   ├── demo2/                    # IIIT-NR helpdesk: Streamlit + Ollama/Groq + Whisper/MMS + VITS/Edge
│   └── Institute-voice-agent/    # LangGraph RAG text helpdesk + thin voice orchestrator
├── idea/                         # Governance, specs, audits, work plan
│   ├── AGENTS.md                 # Authority: thesis, priorities, scope L1/L2/L3, conventions
│   ├── proposal.txt/.pdf         # Formal B.Tech proposal (superseded by AGENTS.md on Flutter→web)
│   ├── docs/
│   │   ├── WEB_APP_SPECIFICATION.md    # Web client spec (replaces Flutter)
│   │   └── OPEN_JEV_FAILURE_ANALYSIS_AND_RECOVERY.md
│   ├── DEMO2_TECHNICAL_AUDIT.md
│   ├── DEMO2_IMPROVEMENT_REPORT.md
│   ├── presentation/
│   │   ├── DEMO2_KNOWLEDGE_BASE_RESULTS.md
│   │   └── working/                    # ← YOU ARE HERE
│   └── conversations/                # Build logs: work plan, MCP contract, mic UX, local STS demo
```

---

## How to Read This Documentation

| File | Audience | Start Here If... |
|------|----------|------------------|
| `01-overview-and-thesis.md` | Both | You need the research framing, scope levels, why decisions |
| `02-request-to-response-master.md` | Both | You want **all 4 request→response flows** with mermaid diagrams |
| `03-stt-service-deepdive.md` | Dev | You need function-level detail on STT microservice |
| `04-tts-models-deepdive.md` | Dev | You need VITS model structure, `length_scale`, inference code |
| `05-notebook-bench.md` | Dev | You want to run/understand the end-to-end notebook |
| `06-demo-shopping.md` | Dev | You work on the shopping demo (Groq + MCP + JSON) |
| `07-demo2-helpdesk.md` | Dev | You work on the helpdesk (Ollama + bounded workers + 24h retention) |
| `08-institute-agent.md` | Dev | You need LangGraph RAG + voice orchestrator |
| `09-web-client-spec.md` | Both | You implement the React web client |
| `10-architecture-decisions.md` | Viva | You need a table of every choice with alternatives + rationale |
| `diagrams/*.mmd` | Both | You want standalone mermaid files for slides |

---

## Quick Start Commands

```bash
# Activate env (REQUIRED for all Python work)
conda activate minor

# 1. STT microservice (port 8000)
cd code/STT/stt-service
cp .env.example .env          # edit STT_LANGUAGE=hne for Chhattisgarhi
pip install -r requirements.txt
python run.py                 # serves ws://localhost:8000/ws/stt/{id} + GET /health

# 2. Shopping demo (port 8501)
cd code/demo
pip install -r requirements.txt
cp .env.example .env          # needs GROQ_API_KEY
streamlit run app.py

# 3. Helpdesk demo (port 8501)
cd code/demo2
bash run.sh                   # conda run -n minor streamlit run app.py

# 4. Voice orchestrator (needs STT running)
cd code/Institute-voice-agent/voice-orchestrator
cp .env.example .env          # set STT_WS_BASE_URL
python orchestrator.py        # mic → STT WS → graph.invoke → prints reply

# 5. Notebook bench
cd code
jupyter notebook Speech2Speech.ipynb  # select 'minor' kernel
```

---

## Scope Levels (from AGENTS.md)

| Level | Status | What It Is |
|-------|--------|------------|
| **L1** | Demonstrated | Streaming 16k PCM WS, Silero VAD, MMS-hne ASR, pluggable ASREngine, Devanagari cleanup, VITS Male/Female, `length_scale`, Whisper fallback, telephony adapter |
| **L2** | **Current MVP** | Evaluated Chhattisgarhi S2S + small agri catalogue: search, details, price, `CALCULATE_REQUIRED_QUANTITY`, add/remove/view cart, simulated checkout, spoken reply, KVK refusal, instrumentation, minimal responsive UI |
| **L3** | Future | UPI/payments, multi-vendor sync, seller dashboards, logistics/OTP, unsupervised crop diagnosis, pesticide dosage, farmer profiling, broad multilingual |

---

## Audio Contracts (Hard Protocol)

| Direction | Format | Where Enforced |
|-----------|--------|----------------|
| **Client → STT** | 16 kHz, mono, 16-bit PCM, **no WAV header** | `schemas.py`, `session.py`, `telephony_adapter.py`, `voice.py`, `demo/local_speech.py` |
| **STT → LLM** | JSON `STTEvent` (text frames) | `schemas.py::EventType` = `SESSION_STARTED`, `SPEECH_STARTED`, `PARTIAL`, `FINAL`, `ERROR`, `SESSION_ENDED`, `SESSION_REJECTED` |
| **TTS → Client** | 22.05 kHz WAV (float32) | `Synthesizer.save_wav`, `speech.py::synthesize`, `local_speech.speak` |
| **Twilio → STT** | 8 kHz mu-law (G.711) base64 JSON | `telephony_adapter.py::mulaw_8k_to_pcm16_16k` |

> **Never** change sample rate/encoding without updating all clients + adapter simultaneously.

---

## Key Invariants (Do Not Break)

1. **Singletons**: `_ENGINE_SINGLETON` (asr), `_MODEL_SINGLETON` (vad), `_EXECUTOR` (session) — one per process
2. **Async safety**: All blocking ASR/TTS in `loop.run_in_executor(_EXECUTOR, ...)` — never on event loop
3. **Config only in `config.py`** — no `os.getenv` elsewhere
4. **STTEvent additive only** — downstream LLM services depend on exact shape
5. **Money = paise (int)** — no binary floating point for prices
6. **Idempotency keys**: `(session, turn, fn, args)` SHA-256 on every mutating tool
6. **Safety**: Fixed KVK refusal template — LLM never improvises dosage/advice
7. **Environment**: All Python in `conda minor` — no venv, no system Python

---

## Next: `01-overview-and-thesis.md` → research framing