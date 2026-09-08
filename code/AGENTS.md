# AGENTS.md — STS Pipeline (Speech-to-Speech for Chhattisgarhi / Hindi)

> This file is the authoritative guide for any AI coding agent (or human contributor) working in
> this repository. Read it before touching any code. It explains what the project does, how the
> pieces fit together, what the invariants are, and what "done" looks like.

> **Environment (decided 2026-09-05)**: All Python work in this repository uses the existing Conda
> environment **`minor`** — run `conda activate minor` before any install, script, server,
> notebook, or test. On this machine its interpreter is
> `/home/rtx/miniconda3/envs/minor/bin/python` (Python 3.11.15). Do not create a
> `venv`/`virtualenv` and do not install into the system Python.
> See [§7 Development Conventions](#7-development-conventions).

> **Demo subdirectory**: The user-authorized Streamlit/Groq/MCP demo lives in `demo/`; read
> `demo/AGENTS.md` before changing it. It uses the same `minor` env, but its API-assisted
> routing remains API-assisted. As of the 2026-09-06 user request it reuses the
> local STT/VITS components described below and stores shopping state in JSON.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Repository Layout](#2-repository-layout)
3. [Module Deep-Dives](#3-module-deep-dives)
   - [3.1 STT Service](#31-stt-service-sttstt-service)
   - [3.2 TTS Models](#32-tts-models-ttschattisgarhi-tts-models)
4. [Architecture & Data Flow](#4-architecture--data-flow)
5. [Integration Contract](#5-integration-contract-read-this-before-touching-schemaspy)
6. [Configuration Reference](#6-configuration-reference)
7. [Development Conventions](#7-development-conventions)
8. [Testing](#8-testing)
9. [Extending the Codebase](#9-extending-the-codebase)
10. [Known Constraints & Gotchas](#10-known-constraints--gotchas)
11. [Out-of-Scope / Do Not Touch](#11-out-of-scope--do-not-touch)

---

## 1. Project Overview

This is a **fully local Speech-to-Speech (STS) pipeline** for the **Chhattisgarhi language** (`hne`
ISO 639-3), targeting voice-assistant use cases (e.g., automated appointment booking for clinics).

**Two independently deployable components:**

| Component | Location | Purpose |
|---|---|---|
| **STT Service** | `STT/stt-service/` | Real-time streaming speech-to-text microservice |
| **TTS Models** | `TTS/chattisgarhi-tts-models/` | Pre-trained VITS text-to-speech models (Male & Female) |

Neither component calls an external cloud API at inference time. Everything runs on local hardware.
The STT service exposes a WebSocket API that a downstream LangChain/LLM service consumes. The TTS
models are consumed via the Coqui TTS Python library.

**Target language stack:**
- STT: Meta MMS (`facebook/mms-1b-all`) with the `hne` Chhattisgarhi adapter for Chhattisgarhi,
  or `faster-whisper` for English/other Whisper-supported languages.
- TTS: Coqui VITS models trained on Chhattisgarhi speech (Male & Female voices), output at 22050 Hz.

---

## 2. Repository Layout

```
code/
├── AGENTS.md                           ← you are here
│
├── STT/
│   └── stt-service/                    ← standalone FastAPI WebSocket microservice
│       ├── src/
│       │   ├── __init__.py
│       │   ├── config.py               ← ALL tunables, env-var driven (single source of truth)
│       │   ├── schemas.py              ← WebSocket event contract (STTEvent) — the API surface
│       │   ├── vad.py                  ← Silero VAD wrapper (speech boundary detection)
│       │   ├── asr.py                  ← ASREngine interface + FasterWhisper + ChhattisgarhiMMS impl
│       │   ├── session.py              ← Per-caller state machine (the core logic)
│       │   ├── server.py               ← FastAPI app: auth, capacity, WebSocket handler
│       │   └── telephony_adapter.py    ← Twilio mu-law ↔ PCM16 converter
│       ├── tests/
│       │   ├── test_client_mic.py      ← Live microphone test client
│       │   └── test_client_wav.py      ← WAV file streaming test client
│       ├── run.py                      ← Entry point (uvicorn launcher)
│       ├── requirements.txt
│       ├── Dockerfile
│       ├── .env.example                ← Template — copy to .env and edit
│       └── README.md
│
└── TTS/
    └── chattisgarhi-tts-models/        ← Pre-trained VITS model weights + configs
        ├── Female/
        │   ├── best_model.pth          ← ~950 MB checkpoint (tracked via Git LFS)
        │   └── config.json             ← Coqui VITS training config
        ├── Male/
        │   ├── best_model.pth          ← ~950 MB checkpoint (tracked via Git LFS)
        │   └── config.json
        ├── indictts.ipynb              ← Usage notebook / scratchpad
        ├── test_speed.py
        ├── test_speed2.py
        ├── test_speed_override.py
        ├── output.wav                  ← Sample output
        └── README.md
```

> **Git LFS**: The `.pth` model weight files (~950 MB each) are stored in Git LFS via
> `.gitattributes`. Never commit large binary files without Git LFS tracking.

---

## 3. Module Deep-Dives

### 3.1 STT Service (`STT/stt-service/`)

#### `src/config.py` — Central configuration

**Read this first.** Every tunable in the system lives here as a frozen `Settings` dataclass.
All fields are overridable via environment variables (loaded from `.env` via `python-dotenv`).

Key groups:
- **Audio format**: `SAMPLE_RATE` (16000 Hz, mono, 16-bit PCM — fixed contract with clients)
- **ASR model**: `ASR_MODEL_SIZE`, `ASR_DEVICE`, `ASR_COMPUTE_TYPE`, `ASR_LANGUAGE`
- **VAD**: `VAD_THRESHOLD`, `VAD_MIN_SILENCE_MS`
- **Endpointing**: `END_OF_SPEECH_SILENCE_MS`, `MAX_UTTERANCE_MS`, `PARTIAL_INTERVAL_MS`, `PARTIAL_WINDOW_MS`
- **Server**: `HOST`, `PORT`, `LOG_LEVEL`, `API_KEY`
- **Concurrency**: `ASR_WORKER_THREADS`, `MAX_CONCURRENT_SESSIONS`, `IDLE_TIMEOUT_S`

**Rule**: Never hardcode a numeric constant or model path anywhere else in the codebase. Add it to
`Settings` and reference `settings.<FIELD>`.

---

#### `src/schemas.py` — The WebSocket contract (THE API surface)

This file defines `STTEvent` — **the only type the server ever sends to a client**. Treat it as a
public API: downstream LLM services are coded against these shapes.

```python
class EventType(str, Enum):
    SESSION_STARTED   # one-time on connect
    SPEECH_STARTED    # VAD detected speech; carries interrupt_previous_response=True (barge-in signal)
    PARTIAL           # live, unstable transcript — for UI captions only, never trigger LLM on this
    FINAL             # end-of-utterance — THIS is what the LLM/orchestrator should consume
    ERROR
    SESSION_ENDED
    SESSION_REJECTED  # at capacity or bad auth; connection closes immediately after
```

**Agent rule**: If you add a new event type, update `EventType` here AND update the README's
integration contract section AND notify the LLM/orchestration consumer.

`ClientControlMessage` defines the only JSON text frame a client can send:
- `{"action": "stop"}` — flush and end the session cleanly.

---

#### `src/vad.py` — Silero VAD wrapper

`SpeechDetector` wraps Silero VAD (ONNX, ships in pip package — no runtime downloads).

**Key design decisions:**
- One shared ONNX model instance per process (`_shared_model()` singleton). Never instantiate
  `load_silero_vad()` more than once.
- One `VADIterator` per session (stateful per-caller).
- Silero requires exactly **512 samples per frame at 16 kHz** (or 256 at 8 kHz). The wrapper
  handles arbitrary-size input chunks by maintaining a `_residual` buffer.
- Returns `[{"start": <sample_idx>}]` or `[{"end": <sample_idx>}]` events.

`reset()` must be called after each finalized utterance to clear Silero's internal state.

---

#### `src/asr.py` — ASR engine abstraction

**Interface**: `ASREngine.transcribe(audio: np.ndarray, *, fast: bool) -> Transcript`
- `audio`: float32 mono PCM, values in [-1, 1], at `settings.SAMPLE_RATE`
- `fast=True`: greedy decoding (beam_size=1) — for partial transcripts, prioritizes speed
- `fast=False`: beam search (beam_size=5) — for final transcripts, prioritizes accuracy

**Current implementations:**

| Class | Backend | Language | Notes |
|---|---|---|---|
| `FasterWhisperEngine` | `faster-whisper` (CTranslate2) | English + others | Default for non-`hne` |
| `ChhattisgarhiMMSEngine` | `facebook/mms-1b-all` + `hne` adapter | Chhattisgarhi only | ~1B params, heavier |

**Factory**: `get_engine()` — singleton, chosen by `settings.ASR_LANGUAGE`:
- `"hne"` → `ChhattisgarhiMMSEngine`
- anything else → `FasterWhisperEngine`

**Helpers:**
- `clean_mms_devanagari(text)`: fixes stray spaces before Devanagari matras in MMS CTC output.
  Must be applied to all MMS transcripts. See the docstring for why.
- `logprob_to_confidence(avg_logprob)`: converts Whisper's `avg_logprob` to a 0–1 float for
  downstream UX decisions. Not a calibrated probability — do not treat it as one.

**Adding a new ASR backend:** Implement `ASREngine`, add an `elif` branch in `get_engine()`. No
other file needs to change. This is the intended extension point.

---

#### `src/session.py` — Per-caller state machine

One `SttSession` instance per live WebSocket connection. This is the core business logic.

**State machine:**
```
SILENCE
  ↓ VAD detects speech
SPEAKING
  ├── periodic PARTIAL events (every PARTIAL_INTERVAL_MS, using last PARTIAL_WINDOW_MS of buffer)
  └── → SILENCE when silence ≥ END_OF_SPEECH_SILENCE_MS OR buffer ≥ MAX_UTTERANCE_MS
        (emits one FINAL event)
```

**Critical implementation detail — partial windowing:**
Partials only transcribe the **last `PARTIAL_WINDOW_MS`** of the buffer, not the entire growing
utterance. This prevents partial-transcript latency from growing linearly with utterance length.
Finals always use the full buffer.

**ASR is blocking (CPU/GPU bound):** All `get_engine().transcribe()` calls are dispatched to
`_EXECUTOR` (a `ThreadPoolExecutor` shared across all sessions) via `loop.run_in_executor()`.
Never call `transcribe()` directly in the async event loop — it will block all concurrent callers.

**Hallucination filter:** `_finalize()` drops transcripts where `no_speech_prob >= settings.NO_SPEECH_PROB_THRESHOLD`.
This prevents Whisper echoing its `ASR_INITIAL_PROMPT` on near-silent audio.

**Public API:**
- `session.start()` → `STTEvent(SESSION_STARTED)`
- `session.process_chunk(pcm16_bytes)` → `list[STTEvent]` (0 or more events)
- `session.flush()` → `STTEvent | None` (force-finalize on disconnect/stop)

---

#### `src/server.py` — FastAPI WebSocket entrypoint

**Model loading**: happens once in the `lifespan` context manager at startup via `get_engine()`.
Never load models inside the WebSocket handler.

**Auth**: If `settings.API_KEY` is set, clients must pass `?api_key=<value>` in the WebSocket URL.
Auth is checked before `accept()` for the pre-capacity rejection case.

**Capacity**: `asyncio.Semaphore(MAX_CONCURRENT_SESSIONS)` bounds live sessions. When full, the
server sends a `SESSION_REJECTED` event and closes with code 4503.

**Idle timeout**: `asyncio.wait_for(..., timeout=IDLE_TIMEOUT_S)` on every `receive()` call.
Closes sessions where the client connected but never sent audio.

**Auto-flush on disconnect**: The `finally` block always calls `session.flush()` so the last
utterance of a call is never silently dropped, even if the caller hangs up mid-sentence.

**Health endpoint**: `GET /health` returns JSON with `at_capacity: bool`. Wire this to a load
balancer to stop routing new calls to an overloaded instance.

---

#### `src/telephony_adapter.py` — Twilio Media Streams bridge

Converts 8kHz mu-law (G.711) audio as sent by Twilio to 16kHz PCM16 as expected by `session.py`.

**One public function**: `mulaw_8k_to_pcm16_16k(mulaw_bytes: bytes) -> bytes`

The conversion is two steps:
1. `audioop.ulaw2lin`: mu-law → 16-bit linear PCM at 8 kHz
2. `audioop.ratecv`: 8 kHz → 16 kHz upsampling

> **Python 3.13+ note**: `audioop` was removed from the stdlib in 3.13. The file imports
> `audioop_lts` as a fallback (listed in `requirements.txt` as conditional).

This file does NOT connect to Twilio. See the docstring for a minimal Twilio endpoint sketch.

---

### 3.2 TTS Models (`TTS/chattisgarhi-tts-models/`)

Pre-trained **VITS** (Variational Inference with adversarial learning for end-to-end Text-to-Speech)
models for Chhattisgarhi, trained with the **Coqui TTS** library.

**Two voices:**

| Voice | Path | Sample rate | Checkpoint |
|---|---|---|---|
| Female | `Female/best_model.pth` | 22050 Hz | ~920k training steps |
| Male | `Male/best_model.pth` | 22050 Hz | ~920k training steps |

**Input**: Chhattisgarhi text in **Devanagari script** (Unicode).
**Output**: WAV audio at 22050 Hz.

**Inference API (Coqui TTS):**
```python
import torch
from TTS.utils.synthesizer import Synthesizer

tts = Synthesizer(
    tts_checkpoint="Female/best_model.pth",
    tts_config_path="Female/config.json",
    use_cuda=torch.cuda.is_available(),
)
wav = tts.tts(text="मुला तोर संग रहना हे")
tts.save_wav(wav=wav, path="output.wav")
```

**Speed control**: Adjust `tts.tts_model.length_scale` **before** calling `.tts()`.
- `length_scale = 1.0`: normal speed
- `length_scale = 1.25`: ~20% slower
- Do NOT pass `speed=` as a parameter to `.tts()` — it is non-functional in the Coqui version used here.

**Model architecture highlights (from `config.json`):**
- `text_cleaner: multilingual_cleaners` — handles Devanagari Unicode
- `use_phonemes: false` — grapheme-to-phoneme not used; model takes raw characters
- `add_blank: true` — blank token inserted between characters (standard VITS)
- `sample_rate: 22050` in audio config
- `use_sdp: true` — stochastic duration predictor

**Hardware**: Can run on CPU; GPU (CUDA) recommended for production throughput. Each forward pass
on CPU takes ~100-120ms for a typical sentence (real-time factor ~0.014 — well under real-time).

---

## 4. Architecture & Data Flow

```
 ┌─────────────────────────────────────────────────────────────────┐
 │                       Caller / Client                           │
 │  (browser mic | telephony / Twilio | WAV test client)           │
 └────────────────────────────┬────────────────────────────────────┘
                              │  Binary WebSocket frames
                              │  (16kHz PCM16 mono, no WAV header)
                              ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │  src/server.py  (FastAPI WebSocket  ws://host:8000/ws/stt/{id}) │
 │                                                                 │
 │  ① Auth check (api_key query param)                             │
 │  ② Capacity check (Semaphore → SESSION_REJECTED if full)        │
 │  ③ Idle timeout (IDLE_TIMEOUT_S per receive() call)             │
 │  ④ Delegates chunks to SttSession.process_chunk()               │
 │  ⑤ Auto-flush on disconnect / "stop" control frame              │
 └────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │  src/session.py  (SttSession — one per WebSocket connection)    │
 │                                                                 │
 │  pcm16_bytes → VAD → state: SILENCE | SPEAKING                  │
 │                    → SPEAKING: buffer audio                     │
 │                    → periodic PARTIAL (last PARTIAL_WINDOW_MS)  │
 │                    → silence ≥ EOS_SILENCE_MS → FINAL           │
 │                    → utterance ≥ MAX_UTTERANCE_MS → FINAL       │
 └───────────┬────────────────────────────────────┬───────────────┘
             │                                    │
             ▼                                    ▼
 ┌──────────────────────┐              ┌──────────────────────────┐
 │  src/vad.py          │              │  src/asr.py              │
 │  SpeechDetector      │              │  get_engine()            │
 │  (Silero VAD, ONNX)  │              │                          │
 │                      │              │  ┌──────────────────┐    │
 │  per-chunk: 512-sample│             │  │FasterWhisperEngine│   │
 │  frames, stateful    │              │  │(English/general) │    │
 │  per session         │              │  └──────────────────┘    │
 └──────────────────────┘              │  ┌──────────────────┐    │
                                       │  │ChhattisgarhiMMS  │    │
                                       │  │Engine (hne)      │    │
                                       │  └──────────────────┘    │
                                       │  ThreadPoolExecutor       │
                                       │  (ASR_WORKER_THREADS)     │
                                       └──────────────────────────┘
             │
             ▼  JSON text WebSocket frames (STTEvent)
 ┌─────────────────────────────────────────────────────────────────┐
 │  Downstream LangChain / LLM orchestrator                        │
 │  • Listens for type=="final"  → feeds text to LLM chain         │
 │  • Listens for type=="speech_started" → barge-in: stop TTS      │
 └─────────────────────────────────────────────────────────────────┘
             │
             ▼  LLM response text
 ┌─────────────────────────────────────────────────────────────────┐
 │  TTS/chattisgarhi-tts-models  (Coqui VITS)                      │
 │  • Female/best_model.pth  OR  Male/best_model.pth               │
 │  • Input: Chhattisgarhi Devanagari text                         │
 │  • Output: WAV audio @ 22050 Hz → stream back to caller         │
 └─────────────────────────────────────────────────────────────────┘
```

**Telephony path (Twilio):**
```
PSTN call → Twilio → 8kHz mu-law WebSocket
  → telephony_adapter.mulaw_8k_to_pcm16_16k()
  → SttSession.process_chunk()  (same path as above)
```

---

## 5. Integration Contract (read this before touching `schemas.py`)

The WebSocket endpoint is: `ws://<host>:8000/ws/stt/{session_id}`

### Client sends (binary frames):
Raw 16-bit PCM, mono, 16000 Hz. No WAV header. Any chunk size (20–100ms/frame recommended).

### Client receives (JSON text frames):

| Event type | When | Key fields |
|---|---|---|
| `session_started` | Immediately on connect | `session_id` |
| `speech_started` | VAD detects caller is speaking | `interrupt_previous_response: true` |
| `partial` | Every `PARTIAL_INTERVAL_MS` while speaking | `text`, `confidence`, `start_ms`, `end_ms` |
| `final` | End of utterance (silence or max length) | `text`, `confidence`, `utterance_id`, `start_ms`, `end_ms` |
| `session_rejected` | Server at capacity or auth fail | `error_message`; connection closes after |

### Rules for downstream consumers:
1. **Only act on `final` events.** Feed `text` from those into the LLM chain.
2. **Never trigger LLM generation on `partial`** — text is unstable and will change.
3. **`speech_started` with `interrupt_previous_response: true` = barge-in signal.** Stop any
   in-progress TTS playback immediately.
4. **`utterance_id`** is monotonically increasing per session — use it to deduplicate.
5. **`confidence`** is a 0–1 float derived from Whisper's `avg_logprob`. Use it to decide whether
   to ask the user to repeat, not as a calibrated probability.

### To end a session cleanly:
Send JSON text frame `{"action": "stop"}` — the server will flush any buffered speech as a final
transcript before closing. Alternatively, just close the socket; auto-flush runs either way.

---

## 6. Configuration Reference

All settings are in `STT/stt-service/src/config.py` and overridable via `.env`.
Copy `.env.example` to `.env` before first run.

| Env Var | Default | What it controls |
|---|---|---|
| `STT_LANGUAGE` | `en` | ASR language; set to `hne` for Chhattisgarhi (triggers MMS engine) |
| `STT_MODEL_SIZE` | `small.en` | Whisper model size (ignored when `STT_LANGUAGE=hne`) |
| `STT_DEVICE` | `cpu` | `cpu` or `cuda` |
| `STT_COMPUTE_TYPE` | `int8` | Whisper: `int8` (CPU) / `float16` (GPU) |
| `STT_MMS_DTYPE` | `float32` | MMS CUDA weight/input dtype: float32, float16, bfloat16; CPU stays float32 |
| `STT_EOS_SILENCE_MS` | `600` | Pause duration that ends an utterance |
| `STT_MAX_UTTERANCE_MS` | `20000` | Hard cap on utterance length |
| `STT_PARTIAL_INTERVAL_MS` | `700` | How often partials are emitted |
| `STT_PARTIAL_WINDOW_MS` | `6000` | How much audio is re-transcribed for each partial |
| `STT_API_KEY` | `""` | Auth key; leave blank for localhost dev only |
| `STT_MAX_CONCURRENT_SESSIONS` | `8` | Hard concurrency cap per process |
| `STT_IDLE_TIMEOUT_S` | `30` | Seconds before an idle session is closed |
| `STT_ASR_WORKER_THREADS` | `4` | Thread pool size for blocking ASR inference |
| `STT_INITIAL_PROMPT` | (clinic vocabulary) | Domain vocabulary hint for Whisper |
| `STT_NO_SPEECH_PROB_THRESHOLD` | `0.6` | Above this, finals are dropped as hallucinations |
| `STT_PORT` | `8000` | Server port |

---

## 7. Development Conventions

### Development environment

Every Python command — installs, the STT server, the TTS notebook, benchmarks, and tests — runs
inside the existing Conda environment **`minor`**:

```bash
conda activate minor
```

- Interpreter on this machine: `/home/rtx/miniconda3/envs/minor/bin/python` (Python 3.11.15).
- Never create a `venv`/`virtualenv` alongside it, and never install into the system Python.
- Install missing dependencies into `minor` (`pip install -r requirements.txt` with the env
  active). Preserve its existing speech/model stack — check the installed version before
  upgrading a shared dependency such as `torch`, `transformers`, or `TTS`.
- The `Dockerfile` (`python:3.11-slim`) is the container path only; it does not replace `minor`
  for local work.

### Code style
- Python 3.11 — matches the `minor` env (3.11.15) and the Dockerfile's `python:3.11-slim`.
- Follow existing docstring style (imperative mood, one-paragraph summaries with "why" context).
- All public functions and classes must have docstrings explaining *why* they exist, not just *what*
  they do — this codebase's existing docs are a good model.

### Singletons
The following **must remain singletons** — instantiating them more than once per process is a bug:
- `_ENGINE_SINGLETON` in `asr.py` (`get_engine()`)
- `_MODEL_SINGLETON` in `vad.py` (`_shared_model()`)
- `_EXECUTOR` in `session.py`

### Async safety
- `SttSession` is **not thread-safe**. Each session belongs to exactly one asyncio task (one
  WebSocket connection). Never share a `SttSession` across connections.
- All blocking operations (ASR inference) **must** use `loop.run_in_executor(_EXECUTOR, ...)`.
  Calling `transcribe()` directly in an `async` function is a critical bug that will block all
  concurrent callers.

### Adding configuration
1. Add the field to the `Settings` dataclass in `config.py` with `os.getenv(...)` and a sensible
   default.
2. Add it to `.env.example` with a comment.
3. Reference it as `settings.<FIELD_NAME>` everywhere — never read `os.getenv` outside `config.py`.

### Changing the WebSocket protocol
`src/schemas.py` is the API surface. Before modifying `STTEvent` or `EventType`:
1. Check whether any downstream consumer (LLM service, test clients) depends on the field.
2. Add new fields as `Optional` with defaults — never remove or rename existing fields without
   a versioning discussion.
3. Update the integration contract table in this file and in `README.md`.

---

## 8. Testing

> Activate the Conda env once per shell before running anything below: `conda activate minor`.

### STT Service

**Run the server first:**
```bash
conda activate minor
cd STT/stt-service
pip install -r requirements.txt   # installs into the minor env
cp .env.example .env  # edit STT_LANGUAGE=hne for Chhattisgarhi
python run.py
```

**Test with live mic** (most realistic):
```bash
python tests/test_client_mic.py
```
Speak; watch `PARTIAL` lines update live, `FINAL` lines print on pause.

**Test with a WAV file** (repeatable, CI-friendly):
```bash
# Audio must be mono 16kHz 16-bit PCM
# Convert if needed:
ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 audio.wav

python tests/test_client_wav.py audio.wav
```

**Health check:**
```bash
curl http://localhost:8000/health
# → {"status":"ok","model":"small.en","device":"cpu","active_sessions":0,"max_sessions":8,"at_capacity":false}
```

**MMS speed benchmark:**
```bash
python test_mms_speed.py  # in STT/stt-service/
```

### TTS Models

**Jupyter Notebook (interactive):**
```bash
conda activate minor
cd TTS/chattisgarhi-tts-models
jupyter notebook indictts.ipynb   # select the "minor" kernel
```

**Speed benchmarks:**
```bash
python test_speed.py
python test_speed2.py
python test_speed_override.py  # tests length_scale override
```

Expected inference: real-time factor ~0.014 (14ms compute per second of audio) on CPU for typical
sentence lengths.

---

## 9. Extending the Codebase

### Adding a new ASR backend (e.g., NVIDIA Parakeet-TDT)

1. In `src/asr.py`, create a new class inheriting `ASREngine`:
   ```python
   class ParakeetEngine(ASREngine):
       def transcribe(self, audio: np.ndarray, *, fast: bool) -> Transcript:
           ...
   ```
2. Add an `elif` branch in `get_engine()`:
   ```python
   elif settings.ASR_LANGUAGE == "en-parakeet":
       _ENGINE_SINGLETON = ParakeetEngine()
   ```
3. Add any new config fields to `Settings` in `config.py`.
4. Nothing in `session.py`, `server.py`, or `vad.py` needs to change.

### Adding a new STT language

1. If the language is Whisper-supported: set `STT_LANGUAGE=<code>` in `.env` and
   `STT_MODEL_SIZE=large-v3` (Whisper multilingual models, not `.en` variants).
2. If it requires MMS: extend `ChhattisgarhiMMSEngine` to accept a `lang` parameter, or create a
   new `MMSEngine(lang="<code>")` and add it to `get_engine()`.
3. Add `clean_mms_<script>()` post-processing if the target script has similar joining issues.

### Adding a new TTS voice

1. Train a VITS model with Coqui TTS following the existing `config.json` structure.
2. Place `best_model.pth` and `config.json` in a new `TTS/chattisgarhi-tts-models/<Voice>/` dir.
3. Track the `.pth` file with Git LFS: `git lfs track "TTS/**/*.pth"`.

### Adding telephony support (Twilio)

1. Add a new WebSocket route to `src/server.py` (sketch is in `telephony_adapter.py`'s docstring).
2. Use `telephony_adapter.mulaw_8k_to_pcm16_16k()` to convert incoming audio before passing to
   `SttSession.process_chunk()`.
3. The STT output flows to the LLM layer as normal; TTS audio is sent back via Twilio's
   `<Play>` or Media Streams response websocket.
4. This endpoint needs a public HTTPS/WSS URL (ngrok in dev, real domain + TLS cert in prod).

---

## 10. Known Constraints & Gotchas

| Issue | Details |
|---|---|
| **MMS is a 1B-param model** | `ChhattisgarhiMMSEngine` is much heavier than Whisper `small.en`. Measure actual CPU latency before relying on it for live partial transcripts. Consider using it only for finals. |
| **Coqui `speed=` param is broken** | Do NOT pass `speed=` to `tts.tts()`. Set `tts.tts_model.length_scale` before the call instead. |
| **audioop removed in Python 3.13+** | `telephony_adapter.py` falls back to the `audioop_lts` pip package, already conditional in `requirements.txt`. The `minor` env is Python 3.11.15, so the stdlib `audioop` is what actually gets used — the fallback only matters if that env is ever moved past 3.12. |
| **Silero frame size** | Silero VAD requires exactly 512 samples/frame at 16 kHz. The `SpeechDetector` wrapper enforces this — don't bypass it. |
| **MMS Devanagari matras** | MMS CTC can insert stray spaces before Devanagari vowel signs. Always run `clean_mms_devanagari()` on MMS output. |
| **Whisper hallucinations** | On near-silent audio, Whisper sometimes echoes `ASR_INITIAL_PROMPT`. The `no_speech_prob` filter in `_finalize()` catches most of these. |
| **PCM16 only** | The server expects raw 16-bit PCM, mono, 16 kHz — **no WAV header**. Browser microphones and Twilio (after adapter) both comply. Test WAVs must be resampled first (`ffmpeg -ar 16000 -ac 1 -sample_fmt s16`). |
| **Session affinity** | If you run multiple server replicas, a WebSocket connection must be pinned to one instance for its full duration (session state is in-memory). Use a load balancer with session affinity (IP hash or sticky cookies). |
| **Git LFS for model weights** | Model `.pth` files are in Git LFS. Running `git clone` without `git lfs pull` gives pointer files, not actual weights. Always run `git lfs pull` after cloning. |
| **TTS output sample rate** | VITS models output at 22050 Hz, not 16000 Hz. If you pipe TTS output back into the STT pipeline for some reason, resample first. |

---

## 11. Out-of-Scope / Do Not Touch

- **`TTS/chattisgarhi-tts-models/.git/`** — the TTS model repo is a nested git repo.
  Do not commit to its `.git` from the outer repo.
- **`TTS/chattisgarhi-tts-models/*.pth`** — pre-trained model weights. Do not modify these files.
  If you need a new model version, train a new checkpoint and add it as a new file.
- **`STT/stt-service/src/__pycache__/`** — generated by Python, already in `.gitignore`.
- **The `minor` Conda env's existing model stack** — the MMS and Coqui-VITS paths depend on the
  `torch`/`transformers`/`TTS` versions already installed there. Add what a task needs; do not
  upgrade or downgrade a shared dependency to satisfy one script without checking what else breaks.
  Never replace the env with a fresh `venv`.
- **`.env`** — contains secrets (`STT_API_KEY`). Never commit it. Only `.env.example` goes to git.
- **The audio contract (16kHz, mono, PCM16, no header)** — this is a hard protocol contract shared
  with all clients. Changing it requires changing every client and the telephony adapter simultaneously.
- **`STTEvent` field removal / rename** — downstream LLM services depend on this shape. Additive
  changes (new optional fields) are safe; removals/renames are breaking changes.

---

*Last updated: auto-generated from codebase analysis. Keep this file in sync when adding new
modules, changing the WebSocket contract, or adding new configuration fields.*
