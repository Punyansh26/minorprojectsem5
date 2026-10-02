# New session - 2026-10-02T16:57:30.301Z

**Session ID:** ses_f02735242ffe1eFvAcyKoMwRF9
**Created:** 10/2/2026, 10:27:30 PM
**Updated:** 10/2/2026, 10:52:18 PM

---

## User

ok in this project go through everything everycode and see how everything is working and then in the '/run/media/rtx/Files/Study/Semester 5/Minor/idea/presentation' make a folder name working and in that from end to end explain each and everypart of this project how is it working how everything is connecting what function each thing does what is the use what architeture choise is made and why like in depth explain everything. from requeest to response how everything is flowing 

---

## Assistant (Plan · Muse Spark 1.3 Free · 15.4s)

_Thinking:_



_Thinking:_



**Tool: read**

**Input:**
```json
{
  "filePath": "/run/media/rtx/Files/Study/Semester 5/Minor"
}
```

**Output:**
```
<path>/run/media/rtx/Files/Study/Semester 5/Minor</path>
<type>directory</type>
<entries>
.git/
.gitignore
.gitmodules
.playwright-cli/
app/
code/
idea/
README.md

(8 entries)
</entries>
```

---

## Assistant (Plan · Muse Spark 1.3 Free · 4.7s)

_Thinking:_



**Tool: read**

**Input:**
```json
{
  "filePath": "/run/media/rtx/Files/Study/Semester 5/Minor/README.md"
}
```

**Output:**
```
<path>/run/media/rtx/Files/Study/Semester 5/Minor/README.md</path>
<type>file</type>
<content>
1: # Minor Project - Semester 5
2: 
3: **Chhattisgarhi Voice Shopping Assistant**
4: 
5: A voice-enabled agricultural shopping assistant that understands Chhattisgarhi language using Speech-to-Text (STT) and Text-to-Speech (TTS) pipelines.
6: 
7: ## Current institute helpdesk demo
8: 
9: [Demo 2](code/demo2/README.md) is the institute helpdesk built on the shared speech
10: components. It defaults to **Qwen3.5 9B through local Ollama**, with Groq available by
11: explicit sidebar selection. English, Hindi and Hinglish questions are supported;
12: Chhattisgarhi remains experimental. Hindi speech is local after setup, while
13: English/Hinglish speech uses online Edge TTS.
14: 
15: On the configured machine, start it from the repository root:
16: 
17: ```bash
18: cd code/demo2
19: bash run.sh
20: ```
21: 
22: Open `http://localhost:8501`. For a fresh installation, follow the
23: [local model setup](code/Institute-voice-agent/institute-assistant/docs/LOCAL_INFERENCE.md).
24: The [validation record](code/demo2/VALIDATION.md) covers 159 passing automated tests,
25: live multilingual checks and the Hindi voice pipeline. Local answers commonly took
26: 20–50 seconds on the tested 8 GB RTX 4060; this is not a guarantee of cloud-model speed.
27: 
28: ---
29: 
30: ## 📂 Repository Structure
31: 
32: ```
33: Minor/
34: ├── app/       # Web client application layer
35: ├── code/      # STS-Pipeline (ASR, FasterWhisper, MMS, TTS, WebSockets)
36: └── idea/      # Project proposal, agent definitions, work plan, and features
37: ```
38: 
39: ---
40: 
41: ## 🔀 Branch Guide
42: 
43: This repository maintains dedicated branches for each component:
44: 
45: | Branch | Description | Direct Link |
46: |--------|-------------|-------------|
47: | `main` | Structured overview containing `app/`, `idea/`, and `code/` submodule | [View branch](https://github.com/Punyansh26/minorprojectsem5/tree/main) |
48: | `code` | Complete STT/TTS pipeline codebase (`STS-Pipeline`) | [View branch](https://github.com/Punyansh26/minorprojectsem5/tree/code) |
49: | `chattisgarhi-tts-models` | Chhattisgarhi TTS models (checkpoint and tests) | [View branch](https://github.com/Punyansh26/minorprojectsem5/tree/chattisgarhi-tts-models) |
50: | `idea` | Project proposals, architecture specifications, and work plans | [View branch](https://github.com/Punyansh26/minorprojectsem5/tree/idea) |
51: | `app` | Web application client specifications and frontend components | [View branch](https://github.com/Punyansh26/minorprojectsem5/tree/app) |
52: 
53: ---
54: 
55: ## 🚀 Getting Started
56: 
57: ### Clone with all submodules:
58: ```bash
59: git clone --recurse-submodules https://github.com/Punyansh26/minorprojectsem5.git
60: ```
61: 
62: ### Or clone a specific branch directly:
63: ```bash
64: # Clone the STS Pipeline code
65: git clone -b code https://github.com/Punyansh26/minorprojectsem5.git
66: 
67: # Clone the documentation and proposal
68: git clone -b idea https://github.com/Punyansh26/minorprojectsem5.git
69: ```
70: 
71: ---
72: 
73: ## 👥 Author
74: 
75: - **Punyansh26** — [GitHub Profile](https://github.com/Punyansh26) (punyansh2005@gmail.com)

(End of file - total 75 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "/run/media/rtx/Files/Study/Semester 5/Minor/app"
}
```

**Output:**
```
<path>/run/media/rtx/Files/Study/Semester 5/Minor/app</path>
<type>directory</type>
<entries>
README.md

(1 entries)
</entries>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "/run/media/rtx/Files/Study/Semester 5/Minor/code"
}
```

**Output:**
```
<path>/run/media/rtx/Files/Study/Semester 5/Minor/code</path>
<type>directory</type>
<entries>
AGENTS.md
demo/
demo2/
Institute-voice-agent/
speech2speech_outputs/
Speech2Speech.ipynb
STT/
TTS/

(8 entries)
</entries>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "/run/media/rtx/Files/Study/Semester 5/Minor/idea"
}
```

**Output:**
```
<path>/run/media/rtx/Files/Study/Semester 5/Minor/idea</path>
<type>directory</type>
<entries>
AGENTS.md
Chhattisgarhi_Voice_Shopping_Assistant_Proposal2.pdf
conversations/
DEMO2_IMPROVEMENT_REPORT.md
DEMO2_TECHNICAL_AUDIT.md
docs/
presentation/
proposal.txt

(8 entries)
</entries>
```

---

## Assistant (Plan · Muse Spark 1.3 Free · 6.1s)

_Thinking:_



**Tool: read**

**Input:**
```json
{
  "filePath": "/run/media/rtx/Files/Study/Semester 5/Minor/idea/presentation"
}
```

**Output:**
```
<path>/run/media/rtx/Files/Study/Semester 5/Minor/idea/presentation</path>
<type>directory</type>
<entries>
DEMO2_KNOWLEDGE_BASE_RESULTS.md

(1 entries)
</entries>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "/run/media/rtx/Files/Study/Semester 5/Minor/app/README.md"
}
```

**Output:**
```
<path>/run/media/rtx/Files/Study/Semester 5/Minor/app/README.md</path>
<type>file</type>
<content>
1: # Web Application Client
2: 
3: **Chhattisgarhi Voice-to-Voice Agricultural Shopping Assistant**
4: 
5: This directory hosts the web client front-end for the Minor Project MVP.
6: 
7: ---
8: 
9: ## 🎯 Scope & Product Definition
10: 
11: - **Format:** Web development (Chromium-based desktop browser priority, responsive for mobile browsers)
12: - **Voice-first UX:** The user speaks naturally in Chhattisgarhi to browse agricultural products, verify prices/quantities, update their shopping cart, and complete a simulated checkout.
13: - **Safety Boundaries:** Grounded actions only. Fixed KVK-referral response on pesticide/dosage or crop-diagnosis requests.
14: - **Backend Communication:** Real-time WebSocket connection to the STS (Speech-to-Speech) pipeline for live audio streaming, transcription, and TTS playback.
15: 
16: For the complete specification and UI/UX flows, refer to [`idea/docs/WEB_APP_SPECIFICATION.md`](../idea/docs/WEB_APP_SPECIFICATION.md).

(End of file - total 16 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "/run/media/rtx/Files/Study/Semester 5/Minor/code/AGENTS.md"
}
```

**Output:**
```
<path>/run/media/rtx/Files/Study/Semester 5/Minor/code/AGENTS.md</path>
<type>file</type>
<content>
1: # AGENTS.md — STS Pipeline (Speech-to-Speech for Chhattisgarhi / Hindi)
2: 
3: > This file is the authoritative guide for any AI coding agent (or human contributor) working in
4: > this repository. Read it before touching any code. It explains what the project does, how the
5: > pieces fit together, what the invariants are, and what "done" looks like.
6: 
7: > **Environment (decided 2026-09-05)**: All Python work in this repository uses the existing Conda
8: > environment **`minor`** — run `conda activate minor` before any install, script, server,
9: > notebook, or test. On this machine its interpreter is
10: > `/home/rtx/miniconda3/envs/minor/bin/python` (Python 3.11.15). Do not create a
11: > `venv`/`virtualenv` and do not install into the system Python.
12: > See [§7 Development Conventions](#7-development-conventions).
13: 
14: > **Demo subdirectory**: The user-authorized Streamlit/Groq/MCP demo lives in `demo/`; read
15: > `demo/AGENTS.md` before changing it. It uses the same `minor` env, but its API-assisted
16: > routing remains API-assisted. As of the 2026-09-06 user request it reuses the
17: > local STT/VITS components described below and stores shopping state in JSON.
18: 
19: ---
20: 
21: ## Table of Contents
22: 
23: 1. [Project Overview](#1-project-overview)
24: 2. [Repository Layout](#2-repository-layout)
25: 3. [Module Deep-Dives](#3-module-deep-dives)
26:    - [3.1 STT Service](#31-stt-service-sttstt-service)
27:    - [3.2 TTS Models](#32-tts-models-ttschattisgarhi-tts-models)
28: 4. [Architecture & Data Flow](#4-architecture--data-flow)
29: 5. [Integration Contract](#5-integration-contract-read-this-before-touching-schemaspy)
30: 6. [Configuration Reference](#6-configuration-reference)
31: 7. [Development Conventions](#7-development-conventions)
32: 8. [Testing](#8-testing)
33: 9. [Extending the Codebase](#9-extending-the-codebase)
34: 10. [Known Constraints & Gotchas](#10-known-constraints--gotchas)
35: 11. [Out-of-Scope / Do Not Touch](#11-out-of-scope--do-not-touch)
36: 
37: ---
38: 
39: ## 1. Project Overview
40: 
41: This is a **fully local Speech-to-Speech (STS) pipeline** for the **Chhattisgarhi language** (`hne`
42: ISO 639-3), targeting voice-assistant use cases (e.g., automated appointment booking for clinics).
43: 
44: **Two independently deployable components:**
45: 
46: | Component | Location | Purpose |
47: |---|---|---|
48: | **STT Service** | `STT/stt-service/` | Real-time streaming speech-to-text microservice |
49: | **TTS Models** | `TTS/chattisgarhi-tts-models/` | Pre-trained VITS text-to-speech models (Male & Female) |
50: 
51: Neither component calls an external cloud API at inference time. Everything runs on local hardware.
52: The STT service exposes a WebSocket API that a downstream LangChain/LLM service consumes. The TTS
53: models are consumed via the Coqui TTS Python library.
54: 
55: **Target language stack:**
56: - STT: Meta MMS (`facebook/mms-1b-all`) with the `hne` Chhattisgarhi adapter for Chhattisgarhi,
57:   or `faster-whisper` for English/other Whisper-supported languages.
58: - TTS: Coqui VITS models trained on Chhattisgarhi speech (Male & Female voices), output at 22050 Hz.
59: 
60: ---
61: 
62: ## 2. Repository Layout
63: 
64: ```
65: code/
66: ├── AGENTS.md                           ← you are here
67: │
68: ├── STT/
69: │   └── stt-service/                    ← standalone FastAPI WebSocket microservice
70: │       ├── src/
71: │       │   ├── __init__.py
72: │       │   ├── config.py               ← ALL tunables, env-var driven (single source of truth)
73: │       │   ├── schemas.py              ← WebSocket event contract (STTEvent) — the API surface
74: │       │   ├── vad.py                  ← Silero VAD wrapper (speech boundary detection)
75: │       │   ├── asr.py                  ← ASREngine interface + FasterWhisper + ChhattisgarhiMMS impl
76: │       │   ├── session.py              ← Per-caller state machine (the core logic)
77: │       │   ├── server.py               ← FastAPI app: auth, capacity, WebSocket handler
78: │       │   └── telephony_adapter.py    ← Twilio mu-law ↔ PCM16 converter
79: │       ├── tests/
80: │       │   ├── test_client_mic.py      ← Live microphone test client
81: │       │   └── test_client_wav.py      ← WAV file streaming test client
82: │       ├── run.py                      ← Entry point (uvicorn launcher)
83: │       ├── requirements.txt
84: │       ├── Dockerfile
85: │       ├── .env.example                ← Template — copy to .env and edit
86: │       └── README.md
87: │
88: └── TTS/
89:     └── chattisgarhi-tts-models/        ← Pre-trained VITS model weights + configs
90:         ├── Female/
91:         │   ├── best_model.pth          ← ~950 MB checkpoint (tracked via Git LFS)
92:         │   └── config.json             ← Coqui VITS training config
93:         ├── Male/
94:         │   ├── best_model.pth          ← ~950 MB checkpoint (tracked via Git LFS)
95:         │   └── config.json
96:         ├── indictts.ipynb              ← Usage notebook / scratchpad
97:         ├── test_speed.py
98:         ├── test_speed2.py
99:         ├── test_speed_override.py
100:         ├── output.wav                  ← Sample output
101:         └── README.md
102: ```
103: 
104: > **Git LFS**: The `.pth` model weight files (~950 MB each) are stored in Git LFS via
105: > `.gitattributes`. Never commit large binary files without Git LFS tracking.
106: 
107: ---
108: 
109: ## 3. Module Deep-Dives
110: 
111: ### 3.1 STT Service (`STT/stt-service/`)
112: 
113: #### `src/config.py` — Central configuration
114: 
115: **Read this first.** Every tunable in the system lives here as a frozen `Settings` dataclass.
116: All fields are overridable via environment variables (loaded from `.env` via `python-dotenv`).
117: 
118: Key groups:
119: - **Audio format**: `SAMPLE_RATE` (16000 Hz, mono, 16-bit PCM — fixed contract with clients)
120: - **ASR model**: `ASR_MODEL_SIZE`, `ASR_DEVICE`, `ASR_COMPUTE_TYPE`, `ASR_LANGUAGE`
121: - **VAD**: `VAD_THRESHOLD`, `VAD_MIN_SILENCE_MS`
122: - **Endpointing**: `END_OF_SPEECH_SILENCE_MS`, `MAX_UTTERANCE_MS`, `PARTIAL_INTERVAL_MS`, `PARTIAL_WINDOW_MS`
123: - **Server**: `HOST`, `PORT`, `LOG_LEVEL`, `API_KEY`
124: - **Concurrency**: `ASR_WORKER_THREADS`, `MAX_CONCURRENT_SESSIONS`, `IDLE_TIMEOUT_S`
125: 
126: **Rule**: Never hardcode a numeric constant or model path anywhere else in the codebase. Add it to
127: `Settings` and reference `settings.<FIELD>`.
128: 
129: ---
130: 
131: #### `src/schemas.py` — The WebSocket contract (THE API surface)
132: 
133: This file defines `STTEvent` — **the only type the server ever sends to a client**. Treat it as a
134: public API: downstream LLM services are coded against these shapes.
135: 
136: ```python
137: class EventType(str, Enum):
138:     SESSION_STARTED   # one-time on connect
139:     SPEECH_STARTED    # VAD detected speech; carries interrupt_previous_response=True (barge-in signal)
140:     PARTIAL           # live, unstable transcript — for UI captions only, never trigger LLM on this
141:     FINAL             # end-of-utterance — THIS is what the LLM/orchestrator should consume
142:     ERROR
143:     SESSION_ENDED
144:     SESSION_REJECTED  # at capacity or bad auth; connection closes immediately after
145: ```
146: 
147: **Agent rule**: If you add a new event type, update `EventType` here AND update the README's
148: integration contract section AND notify the LLM/orchestration consumer.
149: 
150: `ClientControlMessage` defines the only JSON text frame a client can send:
151: - `{"action": "stop"}` — flush and end the session cleanly.
152: 
153: ---
154: 
155: #### `src/vad.py` — Silero VAD wrapper
156: 
157: `SpeechDetector` wraps Silero VAD (ONNX, ships in pip package — no runtime downloads).
158: 
159: **Key design decisions:**
160: - One shared ONNX model instance per process (`_shared_model()` singleton). Never instantiate
161:   `load_silero_vad()` more than once.
162: - One `VADIterator` per session (stateful per-caller).
163: - Silero requires exactly **512 samples per frame at 16 kHz** (or 256 at 8 kHz). The wrapper
164:   handles arbitrary-size input chunks by maintaining a `_residual` buffer.
165: - Returns `[{"start": <sample_idx>}]` or `[{"end": <sample_idx>}]` events.
166: 
167: `reset()` must be called after each finalized utterance to clear Silero's internal state.
168: 
169: ---
170: 
171: #### `src/asr.py` — ASR engine abstraction
172: 
173: **Interface**: `ASREngine.transcribe(audio: np.ndarray, *, fast: bool) -> Transcript`
174: - `audio`: float32 mono PCM, values in [-1, 1], at `settings.SAMPLE_RATE`
175: - `fast=True`: greedy decoding (beam_size=1) — for partial transcripts, prioritizes speed
176: - `fast=False`: beam search (beam_size=5) — for final transcripts, prioritizes accuracy
177: 
178: **Current implementations:**
179: 
180: | Class | Backend | Language | Notes |
181: |---|---|---|---|
182: | `FasterWhisperEngine` | `faster-whisper` (CTranslate2) | English + others | Default for non-`hne` |
183: | `ChhattisgarhiMMSEngine` | `facebook/mms-1b-all` + `hne` adapter | Chhattisgarhi only | ~1B params, heavier |
184: 
185: **Factory**: `get_engine()` — singleton, chosen by `settings.ASR_LANGUAGE`:
186: - `"hne"` → `ChhattisgarhiMMSEngine`
187: - anything else → `FasterWhisperEngine`
188: 
189: **Helpers:**
190: - `clean_mms_devanagari(text)`: fixes stray spaces before Devanagari matras in MMS CTC output.
191:   Must be applied to all MMS transcripts. See the docstring for why.
192: - `logprob_to_confidence(avg_logprob)`: converts Whisper's `avg_logprob` to a 0–1 float for
193:   downstream UX decisions. Not a calibrated probability — do not treat it as one.
194: 
195: **Adding a new ASR backend:** Implement `ASREngine`, add an `elif` branch in `get_engine()`. No
196: other file needs to change. This is the intended extension point.
197: 
198: ---
199: 
200: #### `src/session.py` — Per-caller state machine
201: 
202: One `SttSession` instance per live WebSocket connection. This is the core business logic.
203: 
204: **State machine:**
205: ```
206: SILENCE
207:   ↓ VAD detects speech
208: SPEAKING
209:   ├── periodic PARTIAL events (every PARTIAL_INTERVAL_MS, using last PARTIAL_WINDOW_MS of buffer)
210:   └── → SILENCE when silence ≥ END_OF_SPEECH_SILENCE_MS OR buffer ≥ MAX_UTTERANCE_MS
211:         (emits one FINAL event)
212: ```
213: 
214: **Critical implementation detail — partial windowing:**
215: Partials only transcribe the **last `PARTIAL_WINDOW_MS`** of the buffer, not the entire growing
216: utterance. This prevents partial-transcript latency from growing linearly with utterance length.
217: Finals always use the full buffer.
218: 
219: **ASR is blocking (CPU/GPU bound):** All `get_engine().transcribe()` calls are dispatched to
220: `_EXECUTOR` (a `ThreadPoolExecutor` shared across all sessions) via `loop.run_in_executor()`.
221: Never call `transcribe()` directly in the async event loop — it will block all concurrent callers.
222: 
223: **Hallucination filter:** `_finalize()` drops transcripts where `no_speech_prob >= settings.NO_SPEECH_PROB_THRESHOLD`.
224: This prevents Whisper echoing its `ASR_INITIAL_PROMPT` on near-silent audio.
225: 
226: **Public API:**
227: - `session.start()` → `STTEvent(SESSION_STARTED)`
228: - `session.process_chunk(pcm16_bytes)` → `list[STTEvent]` (0 or more events)
229: - `session.flush()` → `STTEvent | None` (force-finalize on disconnect/stop)
230: 
231: ---
232: 
233: #### `src/server.py` — FastAPI WebSocket entrypoint
234: 
235: **Model loading**: happens once in the `lifespan` context manager at startup via `get_engine()`.
236: Never load models inside the WebSocket handler.
237: 
238: **Auth**: If `settings.API_KEY` is set, clients must pass `?api_key=<value>` in the WebSocket URL.
239: Auth is checked before `accept()` for the pre-capacity rejection case.
240: 
241: **Capacity**: `asyncio.Semaphore(MAX_CONCURRENT_SESSIONS)` bounds live sessions. When full, the
242: server sends a `SESSION_REJECTED` event and closes with code 4503.
243: 
244: **Idle timeout**: `asyncio.wait_for(..., timeout=IDLE_TIMEOUT_S)` on every `receive()` call.
245: Closes sessions where the client connected but never sent audio.
246: 
247: **Auto-flush on disconnect**: The `finally` block always calls `session.flush()` so the last
248: utterance of a call is never silently dropped, even if the caller hangs up mid-sentence.
249: 
250: **Health endpoint**: `GET /health` returns JSON with `at_capacity: bool`. Wire this to a load
251: balancer to stop routing new calls to an overloaded instance.
252: 
253: ---
254: 
255: #### `src/telephony_adapter.py` — Twilio Media Streams bridge
256: 
257: Converts 8kHz mu-law (G.711) audio as sent by Twilio to 16kHz PCM16 as expected by `session.py`.
258: 
259: **One public function**: `mulaw_8k_to_pcm16_16k(mulaw_bytes: bytes) -> bytes`
260: 
261: The conversion is two steps:
262: 1. `audioop.ulaw2lin`: mu-law → 16-bit linear PCM at 8 kHz
263: 2. `audioop.ratecv`: 8 kHz → 16 kHz upsampling
264: 
265: > **Python 3.13+ note**: `audioop` was removed from the stdlib in 3.13. The file imports
266: > `audioop_lts` as a fallback (listed in `requirements.txt` as conditional).
267: 
268: This file does NOT connect to Twilio. See the docstring for a minimal Twilio endpoint sketch.
269: 
270: ---
271: 
272: ### 3.2 TTS Models (`TTS/chattisgarhi-tts-models/`)
273: 
274: Pre-trained **VITS** (Variational Inference with adversarial learning for end-to-end Text-to-Speech)
275: models for Chhattisgarhi, trained with the **Coqui TTS** library.
276: 
277: **Two voices:**
278: 
279: | Voice | Path | Sample rate | Checkpoint |
280: |---|---|---|---|
281: | Female | `Female/best_model.pth` | 22050 Hz | ~920k training steps |
282: | Male | `Male/best_model.pth` | 22050 Hz | ~920k training steps |
283: 
284: **Input**: Chhattisgarhi text in **Devanagari script** (Unicode).
285: **Output**: WAV audio at 22050 Hz.
286: 
287: **Inference API (Coqui TTS):**
288: ```python
289: import torch
290: from TTS.utils.synthesizer import Synthesizer
291: 
292: tts = Synthesizer(
293:     tts_checkpoint="Female/best_model.pth",
294:     tts_config_path="Female/config.json",
295:     use_cuda=torch.cuda.is_available(),
296: )
297: wav = tts.tts(text="मुला तोर संग रहना हे")
298: tts.save_wav(wav=wav, path="output.wav")
299: ```
300: 
301: **Speed control**: Adjust `tts.tts_model.length_scale` **before** calling `.tts()`.
302: - `length_scale = 1.0`: normal speed
303: - `length_scale = 1.25`: ~20% slower
304: - Do NOT pass `speed=` as a parameter to `.tts()` — it is non-functional in the Coqui version used here.
305: 
306: **Model architecture highlights (from `config.json`):**
307: - `text_cleaner: multilingual_cleaners` — handles Devanagari Unicode
308: - `use_phonemes: false` — grapheme-to-phoneme not used; model takes raw characters
309: - `add_blank: true` — blank token inserted between characters (standard VITS)
310: - `sample_rate: 22050` in audio config
311: - `use_sdp: true` — stochastic duration predictor
312: 
313: **Hardware**: Can run on CPU; GPU (CUDA) recommended for production throughput. Each forward pass
314: on CPU takes ~100-120ms for a typical sentence (real-time factor ~0.014 — well under real-time).
315: 
316: ---
317: 
318: ## 4. Architecture & Data Flow
319: 
320: ```
321:  ┌─────────────────────────────────────────────────────────────────┐
322:  │                       Caller / Client                           │
323:  │  (browser mic | telephony / Twilio | WAV test client)           │
324:  └────────────────────────────┬────────────────────────────────────┘
325:                               │  Binary WebSocket frames
326:                               │  (16kHz PCM16 mono, no WAV header)
327:                               ▼
328:  ┌─────────────────────────────────────────────────────────────────┐
329:  │  src/server.py  (FastAPI WebSocket  ws://host:8000/ws/stt/{id}) │
330:  │                                                                 │
331:  │  ① Auth check (api_key query param)                             │
332:  │  ② Capacity check (Semaphore → SESSION_REJECTED if full)        │
333:  │  ③ Idle timeout (IDLE_TIMEOUT_S per receive() call)             │
334:  │  ④ Delegates chunks to SttSession.process_chunk()               │
335:  │  ⑤ Auto-flush on disconnect / "stop" control frame              │
336:  └────────────────────────────┬────────────────────────────────────┘
337:                               │
338:                               ▼
339:  ┌─────────────────────────────────────────────────────────────────┐
340:  │  src/session.py  (SttSession — one per WebSocket connection)    │
341:  │                                                                 │
342:  │  pcm16_bytes → VAD → state: SILENCE | SPEAKING                  │
343:  │                    → SPEAKING: buffer audio                     │
344:  │                    → periodic PARTIAL (last PARTIAL_WINDOW_MS)  │
345:  │                    → silence ≥ EOS_SILENCE_MS → FINAL           │
346:  │                    → utterance ≥ MAX_UTTERANCE_MS → FINAL       │
347:  └───────────┬────────────────────────────────────┬───────────────┘
348:              │                                    │
349:              ▼                                    ▼
350:  ┌──────────────────────┐              ┌──────────────────────────┐
351:  │  src/vad.py          │              │  src/asr.py              │
352:  │  SpeechDetector      │              │  get_engine()            │
353:  │  (Silero VAD, ONNX)  │              │                          │
354:  │                      │              │  ┌──────────────────┐    │
355:  │  per-chunk: 512-sample│             │  │FasterWhisperEngine│   │
356:  │  frames, stateful    │              │  │(English/general) │    │
357:  │  per session         │              │  └──────────────────┘    │
358:  └──────────────────────┘              │  ┌──────────────────┐    │
359:                                        │  │ChhattisgarhiMMS  │    │
360:                                        │  │Engine (hne)      │    │
361:                                        │  └──────────────────┘    │
362:                                        │  ThreadPoolExecutor       │
363:                                        │  (ASR_WORKER_THREADS)     │
364:                                        └──────────────────────────┘
365:              │
366:              ▼  JSON text WebSocket frames (STTEvent)
367:  ┌─────────────────────────────────────────────────────────────────┐
368:  │  Downstream LangChain / LLM orchestrator                        │
369:  │  • Listens for type=="final"  → feeds text to LLM chain         │
370:  │  • Listens for type=="speech_started" → barge-in: stop TTS      │
371:  └─────────────────────────────────────────────────────────────────┘
372:              │
373:              ▼  LLM response text
374:  ┌─────────────────────────────────────────────────────────────────┐
375:  │  TTS/chattisgarhi-tts-models  (Coqui VITS)                      │
376:  │  • Female/best_model.pth  OR  Male/best_model.pth               │
377:  │  • Input: Chhattisgarhi Devanagari text                         │
378:  │  • Output: WAV audio @ 22050 Hz → stream back to caller         │
379:  └─────────────────────────────────────────────────────────────────┘
380: ```
381: 
382: **Telephony path (Twilio):**
383: ```
384: PSTN call → Twilio → 8kHz mu-law WebSocket
385:   → telephony_adapter.mulaw_8k_to_pcm16_16k()
386:   → SttSession.process_chunk()  (same path as above)
387: ```
388: 
389: ---
390: 
391: ## 5. Integration Contract (read this before touching `schemas.py`)
392: 
393: The WebSocket endpoint is: `ws://<host>:8000/ws/stt/{session_id}`
394: 
395: ### Client sends (binary frames):
396: Raw 16-bit PCM, mono, 16000 Hz. No WAV header. Any chunk size (20–100ms/frame recommended).
397: 
398: ### Client receives (JSON text frames):
399: 
400: | Event type | When | Key fields |
401: |---|---|---|
402: | `session_started` | Immediately on connect | `session_id` |
403: | `speech_started` | VAD detects caller is speaking | `interrupt_previous_response: true` |
404: | `partial` | Every `PARTIAL_INTERVAL_MS` while speaking | `text`, `confidence`, `start_ms`, `end_ms` |
405: | `final` | End of utterance (silence or max length) | `text`, `confidence`, `utterance_id`, `start_ms`, `end_ms` |
406: | `session_rejected` | Server at capacity or auth fail | `error_message`; connection closes after |
407: 
408: ### Rules for downstream consumers:
409: 1. **Only act on `final` events.** Feed `text` from those into the LLM chain.
410: 2. **Never trigger LLM generation on `partial`** — text is unstable and will change.
411: 3. **`speech_started` with `interrupt_previous_response: true` = barge-in signal.** Stop any
412:    in-progress TTS playback immediately.
413: 4. **`utterance_id`** is monotonically increasing per session — use it to deduplicate.
414: 5. **`confidence`** is a 0–1 float derived from Whisper's `avg_logprob`. Use it to decide whether
415:    to ask the user to repeat, not as a calibrated probability.
416: 
417: ### To end a session cleanly:
418: Send JSON text frame `{"action": "stop"}` — the server will flush any buffered speech as a final
419: transcript before closing. Alternatively, just close the socket; auto-flush runs either way.
420: 
421: ---
422: 
423: ## 6. Configuration Reference
424: 
425: All settings are in `STT/stt-service/src/config.py` and overridable via `.env`.
426: Copy `.env.example` to `.env` before first run.
427: 
428: | Env Var | Default | What it controls |
429: |---|---|---|
430: | `STT_LANGUAGE` | `en` | ASR language; set to `hne` for Chhattisgarhi (triggers MMS engine) |
431: | `STT_MODEL_SIZE` | `small.en` | Whisper model size (ignored when `STT_LANGUAGE=hne`) |
432: | `STT_DEVICE` | `cpu` | `cpu` or `cuda` |
433: | `STT_COMPUTE_TYPE` | `int8` | Whisper: `int8` (CPU) / `float16` (GPU) |
434: | `STT_MMS_DTYPE` | `float32` | MMS CUDA weight/input dtype: float32, float16, bfloat16; CPU stays float32 |
435: | `STT_EOS_SILENCE_MS` | `600` | Pause duration that ends an utterance |
436: | `STT_MAX_UTTERANCE_MS` | `20000` | Hard cap on utterance length |
437: | `STT_PARTIAL_INTERVAL_MS` | `700` | How often partials are emitted |
438: | `STT_PARTIAL_WINDOW_MS` | `6000` | How much audio is re-transcribed for each partial |
439: | `STT_API_KEY` | `""` | Auth key; leave blank for localhost dev only |
440: | `STT_MAX_CONCURRENT_SESSIONS` | `8` | Hard concurrency cap per process |
441: | `STT_IDLE_TIMEOUT_S` | `30` | Seconds before an idle session is closed |
442: | `STT_ASR_WORKER_THREADS` | `4` | Thread pool size for blocking ASR inference |
443: | `STT_INITIAL_PROMPT` | (clinic vocabulary) | Domain vocabulary hint for Whisper |
444: | `STT_NO_SPEECH_PROB_THRESHOLD` | `0.6` | Above this, finals are dropped as hallucinations |
445: | `STT_PORT` | `8000` | Server port |
446: 
447: ---
448: 
449: ## 7. Development Conventions
450: 
451: ### Development environment
452: 
453: Every Python command — installs, the STT server, the TTS notebook, benchmarks, and tests — runs
454: inside the existing Conda environment **`minor`**:
455: 
456: ```bash
457: conda activate minor
458: ```
459: 
460: - Interpreter on this machine: `/home/rtx/miniconda3/envs/minor/bin/python` (Python 3.11.15).
461: - Never create a `venv`/`virtualenv` alongside it, and never install into the system Python.
462: - Install missing dependencies into `minor` (`pip install -r requirements.txt` with the env
463:   active). Preserve its existing speech/model stack — check the installed version before
464:   upgrading a shared dependency such as `torch`, `transformers`, or `TTS`.
465: - The `Dockerfile` (`python:3.11-slim`) is the container path only; it does not replace `minor`
466:   for local work.
467: 
468: ### Code style
469: - Python 3.11 — matches the `minor` env (3.11.15) and the Dockerfile's `python:3.11-slim`.
470: - Follow existing docstring style (imperative mood, one-paragraph summaries with "why" context).
471: - All public functions and classes must have docstrings explaining *why* they exist, not just *what*
472:   they do — this codebase's existing docs are a good model.
473: 
474: ### Singletons
475: The following **must remain singletons** — instantiating them more than once per process is a bug:
476: - `_ENGINE_SINGLETON` in `asr.py` (`get_engine()`)
477: - `_MODEL_SINGLETON` in `vad.py` (`_shared_model()`)
478: - `_EXECUTOR` in `session.py`
479: 
480: ### Async safety
481: - `SttSession` is **not thread-safe**. Each session belongs to exactly one asyncio task (one
482:   WebSocket connection). Never share a `SttSession` across connections.
483: - All blocking operations (ASR inference) **must** use `loop.run_in_executor(_EXECUTOR, ...)`.
484:   Calling `transcribe()` directly in an `async` function is a critical bug that will block all
485:   concurrent callers.
486: 
487: ### Adding configuration
488: 1. Add the field to the `Settings` dataclass in `config.py` with `os.getenv(...)` and a sensible
489:    default.
490: 2. Add it to `.env.example` with a comment.
491: 3. Reference it as `settings.<FIELD_NAME>` everywhere — never read `os.getenv` outside `config.py`.
492: 
493: ### Changing the WebSocket protocol
494: `src/schemas.py` is the API surface. Before modifying `STTEvent` or `EventType`:
495: 1. Check whether any downstream consumer (LLM service, test clients) depends on the field.
496: 2. Add new fields as `Optional` with defaults — never remove or rename existing fields without
497:    a versioning discussion.
498: 3. Update the integration contract table in this file and in `README.md`.
499: 
500: ---
501: 
502: ## 8. Testing
503: 
504: > Activate the Conda env once per shell before running anything below: `conda activate minor`.
505: 
506: ### STT Service
507: 
508: **Run the server first:**
509: ```bash
510: conda activate minor
511: cd STT/stt-service
512: pip install -r requirements.txt   # installs into the minor env
513: cp .env.example .env  # edit STT_LANGUAGE=hne for Chhattisgarhi
514: python run.py
515: ```
516: 
517: **Test with live mic** (most realistic):
518: ```bash
519: python tests/test_client_mic.py
520: ```
521: Speak; watch `PARTIAL` lines update live, `FINAL` lines print on pause.
522: 
523: **Test with a WAV file** (repeatable, CI-friendly):
524: ```bash
525: # Audio must be mono 16kHz 16-bit PCM
526: # Convert if needed:
527: ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 audio.wav
528: 
529: python tests/test_client_wav.py audio.wav
530: ```
531: 
532: **Health check:**
533: ```bash
534: curl http://localhost:8000/health
535: # → {"status":"ok","model":"small.en","device":"cpu","active_sessions":0,"max_sessions":8,"at_capacity":false}
536: ```
537: 
538: **MMS speed benchmark:**
539: ```bash
540: python test_mms_speed.py  # in STT/stt-service/
541: ```
542: 
543: ### TTS Models
544: 
545: **Jupyter Notebook (interactive):**
546: ```bash
547: conda activate minor
548: cd TTS/chattisgarhi-tts-models
549: jupyter notebook indictts.ipynb   # select the "minor" kernel
550: ```
551: 
552: **Speed benchmarks:**
553: ```bash
554: python test_speed.py
555: python test_speed2.py
556: python test_speed_override.py  # tests length_scale override
557: ```
558: 
559: Expected inference: real-time factor ~0.014 (14ms compute per second of audio) on CPU for typical
560: sentence lengths.
561: 
562: ---
563: 
564: ## 9. Extending the Codebase
565: 
566: ### Adding a new ASR backend (e.g., NVIDIA Parakeet-TDT)
567: 
568: 1. In `src/asr.py`, create a new class inheriting `ASREngine`:
569:    ```python
570:    class ParakeetEngine(ASREngine):
571:        def transcribe(self, audio: np.ndarray, *, fast: bool) -> Transcript:
572:            ...
573:    ```
574: 2. Add an `elif` branch in `get_engine()`:
575:    ```python
576:    elif settings.ASR_LANGUAGE == "en-parakeet":
577:        _ENGINE_SINGLETON = ParakeetEngine()
578:    ```
579: 3. Add any new config fields to `Settings` in `config.py`.
580: 4. Nothing in `session.py`, `server.py`, or `vad.py` needs to change.
581: 
582: ### Adding a new STT language
583: 
584: 1. If the language is Whisper-supported: set `STT_LANGUAGE=<code>` in `.env` and
585:    `STT_MODEL_SIZE=large-v3` (Whisper multilingual models, not `.en` variants).
586: 2. If it requires MMS: extend `ChhattisgarhiMMSEngine` to accept a `lang` parameter, or create a
587:    new `MMSEngine(lang="<code>")` and add it to `get_engine()`.
588: 3. Add `clean_mms_<script>()` post-processing if the target script has similar joining issues.
589: 
590: ### Adding a new TTS voice
591: 
592: 1. Train a VITS model with Coqui TTS following the existing `config.json` structure.
593: 2. Place `best_model.pth` and `config.json` in a new `TTS/chattisgarhi-tts-models/<Voice>/` dir.
594: 3. Track the `.pth` file with Git LFS: `git lfs track "TTS/**/*.pth"`.
595: 
596: ### Adding telephony support (Twilio)
597: 
598: 1. Add a new WebSocket route to `src/server.py` (sketch is in `telephony_adapter.py`'s docstring).
599: 2. Use `telephony_adapter.mulaw_8k_to_pcm16_16k()` to convert incoming audio before passing to
600:    `SttSession.process_chunk()`.
601: 3. The STT output flows to the LLM layer as normal; TTS audio is sent back via Twilio's
602:    `<Play>` or Media Streams response websocket.
603: 4. This endpoint needs a public HTTPS/WSS URL (ngrok in dev, real domain + TLS cert in prod).
604: 
605: ---
606: 
607: ## 10. Known Constraints & Gotchas
608: 
609: | Issue | Details |
610: |---|---|
611: | **MMS is a 1B-param model** | `ChhattisgarhiMMSEngine` is much heavier than Whisper `small.en`. Measure actual CPU latency before relying on it for live partial transcripts. Consider using it only for finals. |
612: | **Coqui `speed=` param is broken** | Do NOT pass `speed=` to `tts.tts()`. Set `tts.tts_model.length_scale` before the call instead. |
613: | **audioop removed in Python 3.13+** | `telephony_adapter.py` falls back to the `audioop_lts` pip package, already conditional in `requirements.txt`. The `minor` env is Python 3.11.15, so the stdlib `audioop` is what actually gets used — the fallback only matters if that env is ever moved past 3.12. |
614: | **Silero frame size** | Silero VAD requires exactly 512 samples/frame at 16 kHz. The `SpeechDetector` wrapper enforces this — don't bypass it. |
615: | **MMS Devanagari matras** | MMS CTC can insert stray spaces before Devanagari vowel signs. Always run `clean_mms_devanagari()` on MMS output. |
616: | **Whisper hallucinations** | On near-silent audio, Whisper sometimes echoes `ASR_INITIAL_PROMPT`. The `no_speech_prob` filter in `_finalize()` catches most of these. |
617: | **PCM16 only** | The server expects raw 16-bit PCM, mono, 16 kHz — **no WAV header**. Browser microphones and Twilio (after adapter) both comply. Test WAVs must be resampled first (`ffmpeg -ar 16000 -ac 1 -sample_fmt s16`). |
618: | **Session affinity** | If you run multiple server replicas, a WebSocket connection must be pinned to one instance for its full duration (session state is in-memory). Use a load balancer with session affinity (IP hash or sticky cookies). |
619: | **Git LFS for model weights** | Model `.pth` files are in Git LFS. Running `git clone` without `git lfs pull` gives pointer files, not actual weights. Always run `git lfs pull` after cloning. |
620: | **TTS output sample rate** | VITS models output at 22050 Hz, not 16000 Hz. If you pipe TTS output back into the STT pipeline for some reason, resample first. |
621: 
622: ---
623: 
624: ## 11. Out-of-Scope / Do Not Touch
625: 
626: - **`TTS/chattisgarhi-tts-models/.git/`** — the TTS model repo is a nested git repo.
627:   Do not commit to its `.git` from the outer repo.
628: - **`TTS/chattisgarhi-tts-models/*.pth`** — pre-trained model weights. Do not modify these files.
629:   If you need a new model version, train a new checkpoint and add it as a new file.
630: - **`STT/stt-service/src/__pycache__/`** — generated by Python, already in `.gitignore`.
631: - **The `minor` Conda env's existing model stack** — the MMS and Coqui-VITS paths depend on the
632:   `torch`/`transformers`/`TTS` versions already installed there. Add what a task needs; do not
633:   upgrade or downgrade a shared dependency to satisfy one script without checking what else breaks.
634:   Never replace the env with a fresh `venv`.
635: - **`.env`** — contains secrets (`STT_API_KEY`). Never commit it. Only `.env.example` goes to git.
636: - **The audio contract (16kHz, mono, PCM16, no header)** — this is a hard protocol contract shared
637:   with all clients. Changing it requires changing every client and the telephony adapter simultaneously.
638: - **`STTEvent` field removal / rename** — downstream LLM services depend on this shape. Additive
639:   changes (new optional fields) are safe; removals/renames are breaking changes.
640: 
641: ---
642: 
643: *Last updated: auto-generated from codebase analysis. Keep this file in sync when adding new
644: modules, changing the WebSocket contract, or adding new configuration fields.*
645: 
646: 
647: ## Demo2 local upgrade (30 September 2026)
648: 
649: `demo2/jobs.py` owns one bounded reasoning worker and one speech worker. Workers never
650: call Streamlit or mutate browser session state. The fragment UI displays reviewed text
651: before audio. Retain stable conversation/turn IDs, same-session ordering, durable result
652: reuse, atomic draft idempotency and explicit speech-only retries. Cancellation suppresses
653: late results while non-preemptible native work retains its capacity slot.
654: 
655: `demo2/storage.py` owns 24-hour conversation/draft/managed-backup retention, deletion and
656: consistent SQLite backup/restore. The app and operator writes share an interprocess lock.
657: Test changes against temporary stores. New conversation is distinct from deletion.
658: Online English/Hinglish speech is opt-in per browser session. Deterministic domain/number
659: verbalization replaces generative pronunciation rewriting; preserve negation and refuse
660: unknown Latin text for Hindi. Native speech remains unvalidated.
661: 
662: The user authorized a temporary Conda clone for this compatibility repair; normal work
663: continues in `minor`. Proven pins are in `demo2/compatibility-constraints.txt`. Preserve
664: Torch, Transformers, Coqui TTS, model weights and CPU defaults. See the saved implementation
665: report and Demo2 operations guide before repeating dependency or release changes.

(End of file - total 665 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "/run/media/rtx/Files/Study/Semester 5/Minor/idea/AGENTS.md"
}
```

**Output:**
```
<path>/run/media/rtx/Files/Study/Semester 5/Minor/idea/AGENTS.md</path>
<type>file</type>
<content>
1: # AGENTS.md
2: 
3: ## Purpose and authority
4: 
5: This file describes the project and gives repository-wide guidance to human contributors and coding agents. It applies to the entire repository unless a more specific `AGENTS.md` is later added inside a subdirectory.
6: 
7: The background source is `Chhattisgarhi_Voice_Shopping_Assistant_Proposal2.pdf`. Read the relevant parts of that proposal before making a change that affects scope, research claims, safety, evaluation, or architecture. The proposal originally describes a Flutter client, but the current team decision is **web development only**. The web-client decision in this file overrides the proposal's Flutter/mobile implementation details. If the implementation and the remaining proposal content disagree, do not silently rewrite the project's intent: document the discrepancy and preserve the academically defensible interpretation described here.
8: 
9: ## Project identity
10: 
11: ### Short description
12: 
13: This is a **Chhattisgarhi voice-to-voice (Speech-to-Speech, or S2S) conversational system** for low-resource-language interaction. It accepts a user's spoken Chhattisgarhi request, understands it through a measurable cascaded speech/language pipeline, executes a constrained domain action, and returns a spoken Chhattisgarhi response.
14: 
15: The current agricultural shopping website is the project's **reference implementation and evaluation environment**. It matters because it supplies real state, structured tools, safety constraints, and end-to-end user tasks. It is not the main novelty by itself. The central engineering and research focus is the reusable, streaming, interruption-aware voice-to-voice layer and its behavior in a low-resource language.
16: 
17: ### Core thesis
18: 
19: The project asks whether a predominantly open-source, locally runnable, cascaded S2S system can support accurate, useful, and safe voice interaction in Chhattisgarhi under realistic student-compute and connectivity constraints.
20: 
21: The shopping workflow demonstrates that the voice system can do more than transcribe and repeat speech. It must reliably turn speech into structured actions, maintain transactional state, obtain grounded results, and speak those results back to the user. The same voice core should ultimately be adaptable to other bounded systems such as public-service access, appointment workflows, field operations, education, or enterprise support by replacing the domain tools and policies rather than rebuilding the speech stack.
22: 
23: ### Priority order
24: 
25: When time, design, or implementation choices compete, use this order:
26: 
27: 1. End-to-end Chhattisgarhi voice-to-voice quality and natural interaction.
28: 2. Measurability, reproducibility, and honest stage-by-stage evaluation.
29: 3. Safety, deterministic execution, privacy, and traceability.
30: 4. Clean separation between the reusable voice core and domain-specific behavior.
31: 5. Correct shopping workflow and transactional state.
32: 6. General web UI polish or expansion of e-commerce features.
33: 
34: Do not optimize the catalogue UI, payments, marketplace features, or vendor operations at the expense of ASR, translation, orchestration, TTS, latency, barge-in, recovery behavior, or evaluation.
35: 
36: ## What is novel—and what is not
37: 
38: The project must not claim that ASR, machine translation, TTS, LLM tool calling, or agricultural e-commerce was invented here. The contribution is their careful integration and empirical evaluation as a low-resource-language, voice-to-voice transactional system, including:
39: 
40: - spontaneous Chhattisgarhi speech input rather than a Hindi- or English-first interface;
41: - an observable cascade whose individual error sources can be measured;
42: - agricultural/shopping vocabulary adaptation and code-switch handling;
43: - conversion of informal speech into schema-valid, grounded actions;
44: - spoken response generation in Chhattisgarhi;
45: - interruption/barge-in and useful feedback during multi-second inference;
46: - a hard boundary between permitted transactional help and unsafe agronomic advice;
47: - a reusable architecture in which the shopping domain is an adapter around the S2S core.
48: 
49: The project should be described as a research prototype, not a production marketplace, production medical/agricultural advisor, or statistically validated deployment.
50: 
51: ## Scope and maturity levels
52: 
53: Always distinguish these three levels in code, documentation, demonstrations, and claims.
54: 
55: ### Level 1: preliminary work already demonstrated
56: 
57: The team has previously run a local Chhattisgarhi speech pipeline with:
58: 
59: - FastAPI and WebSockets for streaming 16 kHz PCM audio;
60: - Silero VAD for speech-boundary detection and barge-in events;
61: - Meta MMS (`facebook/mms-1b-all`) with the `hne` Chhattisgarhi adapter for ASR;
62: - a pluggable `ASREngine` concept and shared inference workers;
63: - a Devanagari CTC cleanup step for detached matras;
64: - Coqui-TTS VITS with custom male and female Chhattisgarhi checkpoints;
65: - model-level speech pacing through `length_scale`;
66: - an English-only `faster-whisper` fallback when the selected language is English;
67: - a telephony adapter for 8 kHz mu-law input as evidence of extensibility.
68: 
69: This preliminary work demonstrates feasibility only. It does **not** establish calibrated WER, production latency, agricultural vocabulary performance, translation quality, safe tool calling, web integration, or user usability.
70: 
71: ### Level 2: current Minor Project MVP
72: 
73: The current deliverable is an evaluated Chhattisgarhi S2S prototype connected to a small, curated agricultural catalogue. Its bounded tasks are:
74: 
75: - product search and browsing;
76: - product details and price queries;
77: - deterministic quantity calculation from verified metadata;
78: - add-to-cart and remove-from-cart;
79: - view cart and total;
80: - simulated checkout with no payment processing;
81: - spoken Chhattisgarhi responses;
82: - safety refusal and KVK referral for diagnostic or dosage advice;
83: - voice, intent, outcome, and latency instrumentation;
84: - a minimal responsive web UI that confirms recognized text, products, and cart state.
85: 
86: ### Level 3: future work, not a current deliverable
87: 
88: Do not implement or present these as committed MVP features unless the project scope is formally changed:
89: 
90: - real UPI or payment-gateway integration;
91: - live multi-vendor inventory synchronization;
92: - seller dashboards;
93: - delivery routing, tracking, or OTP confirmation;
94: - unsupervised crop diagnosis or pesticide/chemical recommendations;
95: - production-scale farmer profiling or analytics;
96: - broad multilingual support beyond the evaluated Chhattisgarhi path.
97: 
98: Additional languages, domains, telephony deployment, end-to-end multimodal models, and a larger commerce platform are valuable future directions. Keep the architecture open to them, but do not let speculative generality block a strong Chhattisgarhi S2S MVP.
99: 
100: ## Research questions
101: 
102: Implementation and evaluation should help answer the following questions:
103: 
104: 1. How accurately can informal Chhattisgarhi speech become correct shopping intents and entities such as product, crop, quantity, unit, and area?
105: 2. How much error is contributed by ASR, forward translation, intent/entity extraction, domain execution, response translation, and TTS respectively?
106: 3. Can constrained tool calling produce valid, grounded operations without inventing products, state, prices, quantities, or advice?
107: 4. What end-to-end and per-stage latency does a zero-budget local pipeline have, and how does it compare with an API-assisted option if access is actually available?
108: 5. Does the voice-first interaction improve task completion and usability for Chhattisgarhi-speaking users with limited digital literacy compared with text search?
109: 6. How intelligible, natural, interruption-tolerant, and recoverable is the complete spoken interaction—not just its intermediate text?
110: 
111: The sixth question makes explicit the repository's S2S emphasis. A pipeline is not successful merely because its ASR transcript looks correct; the user must be able to complete the spoken task and understand the spoken result.
112: 
113: ## Users and operating conditions
114: 
115: Design primarily for:
116: 
117: - a smallholder farmer who speaks mainly Chhattisgarhi and depends on voice for the whole task;
118: - a user who code-switches between Chhattisgarhi and Hindi and uses voice to avoid typing and menu navigation;
119: - a rural user on intermittent 3G/4G connectivity who needs visible/audible progress and clear recovery behavior.
120: 
121: Assume ordinary laptop/desktop browsers and, where useful, mobile browsers; variable microphones and background noise; informal or incomplete utterances; hesitations; accents; code-switching; and unstable networks. The primary release target is a current Chromium-based desktop browser, with Firefox checked for core compatibility where feasible. Do not assume studio speech, constant broadband, high digital literacy, English literacy, or identical codec behavior across browsers.
122: 
123: ## Architectural principles
124: 
125: ### 1. Treat S2S as a platform layer
126: 
127: Keep the reusable voice pipeline independent from agricultural catalogue and cart logic. The voice core should know how to:
128: 
129: - ingest, validate, decode, and segment audio;
130: - detect speech boundaries and interruptions;
131: - transcribe speech with timestamps/confidence where available;
132: - normalize/translate text;
133: - invoke a constrained interpretation interface;
134: - turn grounded response text into streaming speech;
135: - cancel obsolete work when a user barges in;
136: - emit detailed timing and error events.
137: 
138: The shopping adapter should know:
139: 
140: - the allowed intents and JSON schemas;
141: - product vocabulary and aliases;
142: - catalogue, cart, and order operations;
143: - the domain safety policy;
144: - response templates and grounding data;
145: - which verified metadata may be used for calculations.
146: 
147: Do not bury catalogue SQL, product names, cart state, or agricultural policy inside ASR/TTS engines. Do not couple React components directly to model implementations or raw WebSocket messages.
148: 
149: ### 2. Prefer explicit, typed stage contracts
150: 
151: Stages should exchange structured records rather than untracked strings. Exact class names may evolve, but preserve equivalents of:
152: 
153: - `AudioChunk`: bytes, codec, sample rate, channels, sequence, turn ID;
154: - `Transcript`: original text, language, final/partial status, confidence/timestamps;
155: - `TranslationResult`: source/target language, translated text, model/version;
156: - `Interpretation`: permitted intent or safety class, entities, confidence, clarification need;
157: - `ToolCall`: schema version, tool name, validated arguments, turn/session ID;
158: - `ToolResult`: success/failure, grounded data, safe user-facing fields;
159: - `ResponseText`: source text, Chhattisgarhi text, provenance/template information;
160: - `AudioResponseChunk`: audio format, sequence, final status;
161: - `VoiceTrace`: stage timings, versions, outcome, error category, cancellation state.
162: 
163: Every state-changing request needs a session/conversation ID, turn ID, and idempotency strategy. Stale results from an interrupted turn must never update the cart or begin playback after a newer turn has taken control.
164: 
165: ### 3. Keep the cascade observable and replaceable
166: 
167: The recommended MVP is:
168: 
169: ```text
170: User speech
171:   -> capture + VAD + compression
172:   -> gateway decode/resample
173:   -> Chhattisgarhi ASR
174:   -> Devanagari cleanup/normalization
175:   -> Chhattisgarhi-to-English MT
176:   -> safety classification + constrained intent/entity interpretation
177:   -> validated domain tool
178:   -> deterministic database/business result
179:   -> grounded response construction
180:   -> English-to-Chhattisgarhi MT or approved Chhattisgarhi template
181:   -> Chhattisgarhi TTS
182:   -> streamed audio playback
183: ```
184: 
185: No single stage may become an opaque shortcut that prevents per-stage evaluation. Use interfaces/adapters so MMS can be compared with SraVaani or an approved API, and local MT/TTS/LLM components can be benchmarked against alternatives without rewriting orchestration.
186: 
187: ### 4. Preserve streaming and interruption semantics
188: 
189: Voice UX is a core deliverable. Implement it as a state machine, not as an ordinary long-running request with audio attached.
190: 
191: At minimum, model states equivalent to idle, listening, speech detected, processing, responding, interrupted, failed, and recovering. Define valid transitions. On barge-in:
192: 
193: - stop client playback promptly;
194: - emit/propagate cancellation for the previous turn;
195: - prevent late partials or tool results from being applied;
196: - retain only the context explicitly safe and useful for the next turn;
197: - log the interruption and cancellation latency.
198: 
199: Stream progress or a short holding cue so multi-stage processing never looks like a frozen page. Keep responses concise because long text increases TTS delay and working-memory burden.
200: 
201: ### 5. Ground actions before generating responses
202: 
203: The LLM is an interpreter and router, not the source of catalogue facts or transactional truth. It may select a permitted tool and extract arguments. The backend validates the tool call, performs the operation, and returns facts. Only then may response text be constructed.
204: 
205: Never allow free-form model text to directly mutate data. Reject unknown tools, extra fields, invalid enum values, impossible quantities, nonexistent product IDs, malformed units, and unauthorized user/cart IDs. Database constraints remain mandatory even when application validation exists.
206: 
207: ### 6. Ask rather than guess
208: 
209: When a product, quantity, unit, area, cart referent, or intent is ambiguous, produce a short clarification turn. Do not guess values merely to keep the conversation moving. Clarification is a normal S2S state and must be included in tests and latency/usability evaluation.
210: 
211: ## Proposed technology baseline
212: 
213: Use the following as the default baseline unless measurements justify a change:
214: 
215: | Layer | Default/current direction | Notes |
216: | --- | --- | --- |
217: | Web client | React + TypeScript + Vite | Browser microphone capture, voice state, WebSocket transport, playback, confirmations, and responsive UI |
218: | API/orchestrator | Python + FastAPI | REST for ordinary resources; WebSocket or SSE where streaming/progress requires it |
219: | VAD | Silero VAD | Keep thresholds configurable and evaluate on representative audio |
220: | Chhattisgarhi ASR | Meta MMS 1B with `hne` adapter | Existing baseline; do not claim WER until measured |
221: | ASR comparison | SraVaani-1.0 | Benchmark candidate, not an MVP dependency |
222: | Translation | NLLB-200 distilled 600M, `hne_Deva` | Measure translation drift as its own failure source |
223: | Intent/entities | Local instruction-tuned, tool-capable model | Strict schemas; no specific paid provider is assumed |
224: | TTS | Coqui-TTS VITS, existing Chhattisgarhi checkpoints | Preserve male/female configuration and pacing controls |
225: | Database | PostgreSQL | Transactions and referential integrity are required |
226: | Optional APIs | Bhashini or hosted LLM only if confirmed | Comparison path, never a hidden dependency |
227: 
228: The project has a zero-allocated-budget baseline. Prefer open-source and locally runnable components. Never add a paid or access-controlled service as a required path without explicit approval, a documented fallback, and updated scope/cost documentation.
229: 
230: Do not replace a component because a newer model sounds stronger. First define a comparable dataset, warm-up behavior, hardware, model configuration, accuracy metrics, latency metrics, and resource measurements.
231: 
232: ## Audio and model-serving requirements
233: 
234: - Browser microphone capture uses `navigator.mediaDevices.getUserMedia()` and therefore requires a secure context. `localhost` is acceptable for local development; any non-local deployment must use HTTPS/WSS.
235: - Detect browser capabilities at runtime. Use `MediaRecorder.isTypeSupported()` before selecting an Opus/container combination, and send the actual MIME type with each turn.
236: - Prefer `AudioWorklet` when raw low-latency PCM frames, metering, or client-side VAD requires processing away from the main UI thread. Retain a simpler push-to-talk/`MediaRecorder` path as the dependable fallback.
237: - Respect browser autoplay and permission policies. Start capture/playback from an explicit user gesture, explain microphone denial clearly, and stop every `MediaStreamTrack` when a turn/session ends.
238: - The browser `WebSocket` API does not provide automatic backpressure. Keep chunks bounded, monitor `bufferedAmount`, pause/drop only according to the documented protocol, and close stalled sessions before queued audio exhausts memory.
239: - Normalize inference audio to an explicitly documented canonical format, expected initially to be mono 16 kHz PCM after transport decoding.
240: - Treat Opus as a transport/storage choice, not as the ASR tensor format. Validate headers, sample rate, channels, duration, and maximum payload size.
241: - Do not reload large models for each request. Load once per process/worker and use bounded inference concurrency.
242: - Do not block the FastAPI event loop with CPU/GPU inference. Use an inference worker, executor, queue, or service boundary appropriate to the measured load.
243: - Warm up models before benchmark runs and report cold and warm latency separately where relevant.
244: - Record model ID, adapter/checkpoint version, decoding parameters, device, precision, and relevant hardware with every formal benchmark.
245: - Keep Devanagari normalization deterministic and independently tested. Preserve original ASR output alongside normalized output for error analysis.
246: - Maintain domain vocabulary/alias lists as injectable data. Do not bake shopping words permanently into the generic ASR interface.
247: - Treat partial ASR results as provisional. Only finalized, validated interpretations may trigger state-changing tools.
248: - Make TTS output sample rate/format explicit. The client must not infer it from a filename or model default.
249: - Support cancellation between stages and, where practical, during streaming synthesis.
250: 
251: ## Domain tools and shopping behavior
252: 
253: The minimum intent/tool family is:
254: 
255: - `SEARCH_PRODUCT`
256: - `PRODUCT_DETAILS`
257: - `CHECK_PRICE`
258: - `CALCULATE_REQUIRED_QUANTITY`
259: - `ADD_TO_CART`
260: - `REMOVE_FROM_CART`
261: - `VIEW_CART`
262: - simulated `CHECKOUT`
263: 
264: Tool names in code may use lower snake case, but one canonical taxonomy and schema version must be documented. Tool schemas should distinguish product names from resolved product IDs, amount from unit, field area from purchase quantity, and conversational mention from verified backend entity.
265: 
266: The catalogue is intentionally small—approximately 50–100 relevant seed, fertilizer, and basic-tool records—because it is an instrumented test domain, not an attempt to clone a large marketplace.
267: 
268: Use PostgreSQL transactions for cart, inventory, and simulated-order changes. Capture `price_at_addition` and `price_locked` semantics deliberately. Enforce foreign keys and validate ownership server-side. Authentication is JWT-based in the proposal; secrets and signing material must remain server-side environment configuration.
269: 
270: Do not introduce RAG for the structured product catalogue without evidence that relational/full-text/fuzzy search is insufficient. Direct database search is easier to validate, faster at this scale, and less likely to invent products.
271: 
272: ### Deterministic quantity calculation
273: 
274: An LLM must never calculate agricultural quantities from memory. A permitted calculation must:
275: 
276: 1. resolve a real catalogue item;
277: 2. use a verified, versioned metadata field from an authoritative source;
278: 3. normalize area and product units deterministically;
279: 4. execute ordinary Python/SQL arithmetic;
280: 5. apply explicit plausibility bounds;
281: 6. return the value and provenance to response construction;
282: 7. refuse or ask for clarification if metadata or units are missing.
283: 
284: Seed/application-rate metadata must include source, source date/version, units, applicable crop/context, and verification status. Proposal-stage example figures are not verified facts. Do not add them to the production catalogue until sourced from IGKV or another authoritative regional reference.
285: 
286: ## Safety boundary
287: 
288: This system is a transactional/product-discovery assistant. It is **not an agronomist, crop doctor, or pesticide advisor**.
289: 
290: Permitted behavior includes finding a catalogue item, stating verified product details, changing the cart, checking price/availability, and performing an explicitly allowed deterministic calculation from verified static metadata.
291: 
292: Disallowed behavior includes:
293: 
294: - diagnosing crop disease or deficiency;
295: - choosing a pesticide, chemical, treatment, or cure for observed symptoms;
296: - generating pesticide dosage or application instructions;
297: - turning uncertainty into a confident recommendation;
298: - bypassing the boundary because the request is phrased indirectly or as a hypothetical.
299: 
300: For disallowed queries, the backend must select a fixed, reviewed Chhattisgarhi refusal/referral response directing the user to an appropriate Krishi Vigyan Kendra (KVK) or qualified expert. Do not let the LLM freely improvise the advice, disclaimer, contact details, or dosage. Any actual referral details must be verified before release.
301: 
302: Safety classification belongs before tool execution and should be defense in depth:
303: 
304: - a labelled permitted/disallowed/ambiguous taxonomy;
305: - constrained model output;
306: - deterministic validation of requested tool and entities;
307: - tool-level policy checks;
308: - fixed refusal templates;
309: - an audit event without unnecessary personal data.
310: 
311: Measure false negatives and false positives separately. A false negative can produce unsafe advice; a false positive blocks a legitimate shopping task. Test paraphrases, code-switching, euphemisms, multi-turn context, prompt injection, and ambiguous quantity-versus-dosage wording.
312: 
313: ## Data, privacy, and ethics
314: 
315: Relevant public resources identified in the proposal include RESPIN-S1.0 for dialect-rich ASR data, SYSPIN_S1.0 for Chhattisgarhi TTS, and FLORES-200/NLLB evaluation material for `hne_Deva`. Confirm licenses and record exact dataset/model versions before redistribution or training.
316: 
317: Build a project-specific evaluation set containing realistic Chhattisgarhi shopping commands from native speakers, including noise, code-switching, hesitations, ambiguous requests, corrections, and safety-boundary cases. Separate training/development/test speakers where the sample size permits; never evaluate only on phrases used as prompts or adaptation data.
318: 
319: For human recordings:
320: 
321: - obtain informed consent before recording;
322: - do not request names, precise addresses, financial information, or other unnecessary PII;
323: - define purpose, access, retention, deletion, and publication rules;
324: - store raw recordings outside the Git repository unless an explicitly consented, appropriately licensed subset is prepared;
325: - do not publish or send recordings to third-party APIs without consent covering that use;
326: - report small studies as indicative pilot results, not population-wide evidence.
327: 
328: Voice logs should default to the minimum needed for debugging and evaluation. Prefer pseudonymous participant/session IDs. If `audio_ref` exists, make retention configurable. Never log JWTs, API keys, full authorization headers, or raw third-party responses that may contain sensitive data.
329: 
330: ## Evaluation requirements
331: 
332: Evaluation is a deliverable, not cleanup after the demo. Preserve stage outputs and timestamps from the beginning.
333: 
334: ### Speech and language metrics
335: 
336: - ASR: WER and CER on held-out Chhattisgarhi speech, with normalization rules published.
337: - ASR slices: speaker, noise condition, code-switching, domain term, utterance length, and model/configuration where sample size allows.
338: - Translation: a declared automatic metric if appropriate plus native-speaker/human error review for meaning-changing drift; do not hide translation errors inside intent scores.
339: - Intent: accuracy and confusion matrix.
340: - Entities: precision, recall, and F1 by entity type.
341: - Tool calling: schema-validity rate, correct-tool rate, correct-arguments rate, clarification rate, and hallucinated-entity rate.
342: - TTS: real-time factor, time to first audio, intelligibility/task comprehension, and a small listening-quality assessment where feasible.
343: 
344: ### End-to-end voice metrics
345: 
346: - complete spoken-task success rate;
347: - product search, cart mutation, and calculation success rate;
348: - safety false-negative and false-positive rates;
349: - end-to-end latency from end of user speech to first response audio byte;
350: - capture/VAD, upload, ASR, MT, interpretation, tool, response MT, TTS-first-byte, and total timing;
351: - timeout, retry, cancellation, and recovery rates;
352: - barge-in detection and playback-stop latency;
353: - percentage of turns requiring clarification or manual UI repair.
354: 
355: The proposal's provisional target is under 5 seconds for speech-in to speech-response, with an 8-second client timeout and a local Chhattisgarhi network-error prompt. Keep thresholds configurable. If measurements show that these targets conflict, report the actual results and rationale; do not discard slow runs or silently redefine the metric.
356: 
357: ### Benchmark discipline
358: 
359: - Version evaluation manifests and expected labels.
360: - Never train/tune on the held-out test set.
361: - Pin or record model, adapter, tokenizer, prompt, schema, dependency, and hardware versions, along with the environment the run used (`minor`) and its resolved package versions.
362: - Save aggregate results in machine-readable form and generate report tables from them where practical.
363: - Distinguish cold start, warm inference, streaming time to first result, and total completion time.
364: - Report failures and excluded samples with reasons.
365: - Do not put invented, estimated, cherry-picked, or uncalibrated numbers in reports.
366: 
367: ## Reliability and low-connectivity behavior
368: 
369: True fully offline in-browser conversational inference is outside the current scope. The connected web design must degrade clearly:
370: 
371: - prefer Opus for uploaded audio when the current browser reports a compatible container/codec; otherwise use the documented supported fallback and send the actual media type;
372: - cache the web application shell and recently viewed product text/images with a service worker and IndexedDB where justified;
373: - provide visible and audible listening/processing/responding state;
374: - apply bounded retries only to safe, idempotent operations;
375: - cancel at the configured timeout;
376: - play a bundled, pre-recorded Chhattisgarhi failure prompt when the service is unavailable;
377: - never duplicate a cart mutation because the client retried after losing the response.
378: 
379: Simulate slow, reordered, duplicated, dropped, and disconnected requests in tests. A network failure must not leave the UI claiming an unconfirmed cart state.
380: 
381: ## Security and integrity
382: 
383: - Keep API keys, database URLs, model-service credentials, and JWT secrets out of source and browser bundles. Any Vite environment variable exposed to client code is public by design and must not contain a secret.
384: - Provide redacted example environment files only.
385: - Validate authentication and resource ownership on every cart/order endpoint.
386: - Constrain model outputs with machine-validated schemas; prompt instructions alone are not a security boundary.
387: - Validate file/audio type, duration, size, codec, and decode outcome before inference.
388: - Rate-limit or otherwise bound expensive inference entry points when exposed beyond local development.
389: - Use parameterized queries/ORM bindings and database constraints.
390: - Make state-changing operations idempotent where retries can occur.
391: - Treat transcripts, recordings, and conversation context as untrusted input.
392: - Include prompt-injection and malformed-tool-call tests.
393: 
394: ## Suggested repository organization
395: 
396: The repository currently begins from a proposal document. As implementation is added, prefer boundaries similar to the following; adapt names to the framework rather than creating empty scaffolding prematurely.
397: 
398: ```text
399: apps/
400:   web/                    # React/TypeScript capture, voice state, playback, responsive UI
401: services/
402:   backend/
403:     app/
404:       api/                # REST/WebSocket/SSE transport
405:       voice/              # audio, VAD, ASR, MT, TTS adapters
406:       orchestration/      # turn state machine, cancellation, traces
407:       interpretation/     # safety class, intents, entities, tool schemas
408:       domains/
409:         shopping/         # catalogue/cart/order tools and response policy
410:       db/                 # models, repositories, migrations, transactions
411: evaluation/               # manifests, metric code, benchmark runners, reports
412: data/
413:   fixtures/               # synthetic/licensed non-sensitive test fixtures
414:   lexicons/               # versioned domain vocabulary and aliases
415: configs/                  # non-secret model and runtime configuration
416: docs/                     # architecture, decisions, data cards, evaluation protocol
417: tests/                    # cross-component/integration tests if not colocated
418: ```
419: 
420: Keep model checkpoints, generated audio, participant recordings, database dumps, and large benchmark outputs out of Git. Store only small licensed fixtures, configs, checksums/manifests, and documented retrieval instructions.
421: 
422: ## Engineering conventions
423: 
424: ### Development environment
425: 
426: All Python work in this project—backend, voice pipeline, evaluation, benchmarks, and tests—runs in the existing Conda environment **`minor`**. Activate it before running anything:
427: 
428: ```bash
429: conda activate minor
430: ```
431: 
432: On the current development machine its interpreter is `/home/rtx/miniconda3/envs/minor/bin/python` (Python 3.11.15).
433: 
434: - Do not create a `venv`/`virtualenv`, and do not install into the system Python.
435: - Install missing dependencies into `minor` and preserve its existing speech/model stack (MMS, Coqui-TTS VITS, Silero VAD, `faster-whisper`). Check the installed version before upgrading a shared dependency such as `torch` or `transformers`; a convenience upgrade that breaks the ASR or TTS checkpoints costs more than it saves.
436: - Every documented command, script, `Makefile` target, and README snippet should assume this environment rather than a per-directory virtualenv.
437: - Node/npm tooling for the React web client is separate and unaffected; `minor` covers Python only.
438: - Container images may pin their own Python 3.11 base, but that is a deployment path and does not replace `minor` for local development.
439: - Record the environment and its resolved package versions with any formal benchmark, as required by the benchmark-discipline rules above.
440: 
441: ### General
442: 
443: - Make the smallest coherent change that advances a measured project objective.
444: - Preserve the voice/domain boundary even when building a quick demo.
445: - Prefer configuration and dependency injection for model/provider choices.
446: - Use clear, domain-neutral names in the S2S core and agricultural names only in the shopping adapter.
447: - Add comments for safety invariants, concurrency behavior, cancellation, audio formats, and non-obvious model quirks—not for obvious syntax.
448: - Update architecture, schema, API, and evaluation documentation with behavior changes.
449: - Record meaningful architectural decisions, especially model replacements or changes to safety/scope.
450: - Do not claim that a stub, mocked model, or simulated checkout is production functionality.
451: 
452: ### Python/FastAPI
453: 
454: - Use type hints and validated request/response models at external and model/tool boundaries.
455: - Keep route handlers thin; orchestration, safety, domain logic, and persistence belong in separate modules.
456: - Keep blocking model inference off the async event loop.
457: - Translate internal exceptions into stable error codes that the voice client can render or speak safely.
458: - Use database migrations rather than startup-time ad hoc schema creation once persistence is established.
459: - Make unit conversion and quantity calculations pure and heavily tested.
460: 
461: ### React/web
462: 
463: - Use TypeScript in strict mode and model listening/processing/playback as explicit state, including permission denial, timeout, cancellation, retry, and barge-in.
464: - Keep microphone capture, audio processing/playback, REST, WebSocket protocol handling, and persistence outside presentation components.
465: - Show what the system heard and what action it took without requiring the visual UI to complete the primary path.
466: - Build a responsive, keyboard-accessible interface with visible focus, semantic controls, large voice controls, and readable status text; keep voice task completion the primary UX criterion.
467: - Never store backend secrets in frontend code, static assets, local storage, or browser-readable environment values.
468: - Test permission denial, tab visibility changes, page navigation/unload, device changes, disconnected sockets, autoplay rejection, and playback cancellation.
469: - Feature-detect audio/container support and display an actionable unsupported-browser message instead of failing silently.
470: 
471: ### Database and APIs
472: 
473: - Use consistent units and explicit decimal/money semantics; do not use binary floating point for prices.
474: - Preserve transactional integrity for cart/order operations.
475: - Version public/tool schemas before making incompatible changes.
476: - Return grounded identifiers and machine-readable errors, not only prose.
477: - Keep voice orchestration endpoints separate from reusable catalogue/cart APIs.
478: 
479: ## Testing expectations
480: 
481: Every feature should be tested at the lowest sensible layer and across the relevant pipeline boundary.
482: 
483: Minimum categories include:
484: 
485: - audio decode/resample/validation and VAD boundary fixtures;
486: - Devanagari cleanup and normalization golden tests;
487: - model-adapter contract tests using lightweight doubles where full checkpoints are unavailable;
488: - intent/entity and JSON-schema validation tests;
489: - safety-boundary adversarial and regression cases;
490: - deterministic unit/area/quantity calculations;
491: - product resolution and nonexistent-product rejection;
492: - authenticated cart ownership, transactions, retries, and idempotency;
493: - turn cancellation, late result suppression, and barge-in;
494: - timeout and low-connectivity behavior;
495: - a small consent-safe recorded-audio end-to-end regression suite;
496: - reproducible benchmark/evaluation commands run in the `minor` Conda env.
497: 
498: Do not make every ordinary test load billion-parameter models. Separate fast CI tests from hardware/model integration tests and document how to run both; locally both categories run in the `minor` Conda env (`conda activate minor && python -m pytest -q`). A model change is not complete until the relevant evaluation subset is rerun and compared with the recorded baseline.
499: 
500: ## Work planning and review checklist
501: 
502: Before implementing a change, identify whether it belongs to:
503: 
504: - the reusable S2S core;
505: - domain interpretation/policy;
506: - shopping tools/data;
507: - web presentation;
508: - evaluation/research infrastructure.
509: 
510: If it spans layers, define or update the contract first. During review, ask:
511: 
512: 1. Does this improve or preserve the complete spoken interaction?
513: 2. Is domain-specific behavior kept outside the reusable voice core?
514: 3. Can every model-generated action be validated and grounded?
515: 4. Does it remain safe under ambiguity, prompt injection, interruption, timeout, and retry?
516: 5. Are latency and failure states observable per stage?
517: 6. Are claims supported by versioned, reproducible measurements?
518: 7. Does it preserve the zero-budget local path?
519: 8. Does it avoid collecting or exposing unnecessary voice/identity data?
520: 9. Is it inside Level 2 scope, or clearly marked future work?
521: 
522: ## Definition of done
523: 
524: A voice-pipeline change is done when it has a stable interface, format/config documentation, cancellation/error behavior, tests, instrumentation, and a recorded evaluation comparison where performance may change.
525: 
526: A shopping-domain change is done when its tool schema is validated, facts come from the database, mutations are transactional/idempotent as needed, spoken confirmation is grounded, and end-to-end voice execution is tested.
527: 
528: A safety change is done only when the fixed response path, tool-level enforcement, audit behavior, and labelled false-positive/false-negative regression set all pass. Prompt wording alone is not completion.
529: 
530: An evaluation change is done when its dataset split, normalization, configuration, hardware, command, metric definition, and outputs are reproducible and documented.
531: 
532: A documentation or demonstration claim is done when it clearly labels preliminary work, implemented MVP behavior, measured results, limitations, and future work without conflating them.
533: 
534: ## Project plan and ownership context
535: 
536: The proposal targets an approximately sixteen-week Autumn 2026 project ending around mid-December 2026. The current web-only plan completes by the end of November and covers scoping/data/schema, backend/database, voice and conversational pipeline, React web client, integration, evaluation, and final documentation/demo. Treat evaluation infrastructure as something built throughout, not only in the final phase.
537: 
538: The proposal's primary allocations are:
539: 
540: - Punyansh Thakur: speech/AI pipeline, translation, tool schema/prompting, safety, and evaluation design;
541: - Harsh Dadsena: FastAPI, PostgreSQL, deterministic calculation, authentication, and deployment;
542: - Aakash Sen: React/TypeScript web client, browser audio/VAD/transport, voice/cart UX, browser caching, and integration.
543: 
544: These are ownership guides, not silos. All contributors share responsibility for integration, test data, evaluation, documentation, and the final S2S demonstration.
545: 
546: ## Final guiding rule
547: 
548: If a proposed change makes the repository look more like a generic shopping website but does not strengthen the voice-to-voice research system, treat it as secondary. If a change improves Chhattisgarhi speech accuracy, spoken-response quality, streaming interaction, interruption handling, grounded action execution, safety, observability, reproducibility, or domain portability, it is aligned with the heart of the project.

(End of file - total 548 lines)
</content>
```

---

## Assistant (Plan · Muse Spark 1.3 Free · 206.8s)

_Thinking:_



_Thinking:_



**Tool: task**

**Input:**
```json
{
  "description": "Explore STT service code",
  "prompt": "In /run/media/rtx/Files/Study/Semester 5/Minor/code, explore every file recursively. Focus on STT/stt-service/src/*.py, run.py, requirements, README, TTS models, Speech2Speech.ipynb, demo/ and demo2/ and Institute-voice-agent/. For each file, report: full path, purpose, key functions/classes, how it connects to others, request-to-response flow. Be thorough and return a structured summary. READ-ONLY, do not edit anything.",
  "subagent_type": "explore"
}
```

**Output:**
```
<task id="ses_f0272ce02ffeVrOq6NznlS7Soa" state="completed">
<task_result>
# `code/` — Full Recursive Exploration (READ-ONLY)

Root: `/run/media/rtx/Files/Study/Semester 5/Minor/code`

```
code/
├── AGENTS.md
├── STT/stt-service/
├── TTS/chattisgarhi-tts-models/ + indic_tts_out.wav
├── Speech2Speech.ipynb + speech2speech_outputs/
├── demo/          # Kisan Saathi: Streamlit+Groq+MCP+local speech, JSON store
├── demo2/         # IIIT-NR voice helpdesk: Streamlit+Ollama/Groq+Whisper/MMS+VITS/Edge
└── Institute-voice-agent/
    ├── institute-assistant/ # LangGraph RAG text helpdesk (shared reasoning)
    └── voice-orchestrator/  # mic->STT WS->graph thin glue
```

Global invariant from `AGENTS.md`+`demo/AGENTS.md`: all Python in Conda `minor` (`/home/rtx/miniconda3/envs/minor/bin/python`, 3.11.15). STT audio contract everywhere: `16kHz mono 16-bit PCM, no WAV header`. TTS output: `22050Hz WAV` via Coqui VITS. `speed=` to `tts.tts()` is broken; use `tts_model.length_scale`.

---

## 0. Top-level

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/AGENTS.md`
**Purpose:** Authoritative STS pipeline guide. Defines STT+TTS architecture, integration contract, config reference, singletons, async-safety, testing.
**Key:** Documents `Settings`, `STTEvent/EventType`, `SpeechDetector`, `ASREngine/FasterWhisper/ChhattisgarhiMMS`, `SttSession`, server auth/capacity/idle, VITS `length_scale`, Twilio path, MMS/Whisper/VAD gotchas. Appendix covers `demo2/jobs.py+storage.py` bounded workers, 24h retention, deterministic verbalization.
**Connects:** Indexes all `STT/stt-service/src/*.py`, `TTS/*`, `demo/AGENTS.md`.
**Flow:** Caller->`server.py` WS binary PCM->`session.py+VAD+ASR`->JSON `STTEvent`->LLM->TTS VITS->caller.

---

## 1. STT — `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/`

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/run.py`
**Purpose:** Uvicorn launcher entrypoint.
**Key:** `uvicorn.run("src.server:app", host=settings.HOST, port=settings.PORT, ws_ping_interval=None...)`; Win32 `SelectorEventLoop` guard.
**Connects:** Imports `src.config.settings`, runs `src.server:app`.
**Flow:** `python run.py` -> loads `get_engine()` in `lifespan` -> serves `ws://host:8000/ws/stt/{id}` + `GET /health`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/requirements.txt`
**Purpose:** Pinned server deps. **Key:** `faster-whisper==1.2.1`, `silero-vad==6.2.1`, `fastapi==0.115.6`, `uvicorn[standard]==0.34.0`, `websockets==14.1`, `pydantic==2.10.4`, `numpy==2.2.1`, `soundfile==0.13.0`, `sounddevice==0.5.1` (mic client only), `audioop-lts; python>=3.13`.
**Connects:** Used by `Dockerfile`, `Speech2Speech.ipynb` cell 2, `demo/demo2` (preserve stack).
**Flow:** Install into `minor`, not venv.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/README.md`
**Purpose:** User+LangChain teammate manual. Architecture diagram, setup/run, `ws://<host>:8000/ws/stt/{id}` contract with JSON examples, barge-in, tuning, clinic deployment (Twilio, auth, capacity, idle, vocab, privacy, scaling), MMS `float32/float16/bfloat16` note.
**Connects:** Mirrors `AGENTS.md §3-5` and `schemas.py::STTEvent`.
**Flow:** Documents request->response.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/src/__init__.py`
Empty package marker.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/src/config.py`
**Purpose:** Single source of truth, frozen `Settings` dataclass, `load_dotenv()`.
**Key:** `class Settings`: `SAMPLE_RATE=16000, FRAME_MS=32`, `ASR_MODEL_SIZE/DEVICE/COMPUTE_TYPE/MMS_DTYPE/BEAM_SIZE/FINAL_BEAM_SIZE/LANGUAGE`, `VAD_THRESHOLD/MIN_SILENCE_MS`, `END_OF_SPEECH_SILENCE_MS=600, MAX_UTTERANCE_MS=20000, PARTIAL_INTERVAL_MS=700, MIN_SPEECH_MS_FOR_PARTIAL=300, PARTIAL_WINDOW_MS=6000`, `ASR_INITIAL_PROMPT, NO_SPEECH_PROB_THRESHOLD=0.6, MIN_FINAL_AUDIO_MS=300`, `HOST/PORT/LOG_LEVEL/API_KEY`, `ASR_WORKER_THREADS=4, MAX_CONCURRENT_SESSIONS=8, IDLE_TIMEOUT_S=30, WS_PING_INTERVAL/TIMEOUT`; `settings=Settings()`; `_get_bool()` helper. Rule: no `os.getenv` outside here.
**Connects:** Read by `asr.py, vad.py, session.py, server.py, telephony_adapter.py`, `demo/config.py::configure_stt()`, `demo2/settings.py::configure_stt()`.
**Flow:** `.env`->`Settings`->all timing/model/behavior.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/src/schemas.py`
**Purpose:** WS API surface.
**Key:** `class EventType: SESSION_STARTED, SPEECH_STARTED, PARTIAL, FINAL, ERROR, SESSION_ENDED, SESSION_REJECTED`; `class STTEvent: type, session_id, text, start_ms/end_ms, confidence, utterance_id, error_message, interrupt_previous_response`; `class ClientControlMessage: action(start|stop|flush), language`.
**Connects:** Emitted by `session.py/server.py`, consumed by orchestrator/notebook/test clients/LLM. Additive-only changes.
**Flow:** Server sends `STTEvent.model_dump_json()` text frames; client sends `{"action":"stop"}` or binary PCM.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/src/vad.py`
**Purpose:** Silero VAD wrapper enforcing frame contract.
**Key:** `SILERO_FRAME_SAMPLES=512@16k`; `class SpeechDetector: __init__(_shared_model()+VADIterator), process(pcm16_bytes)->[{start}|{end}], reset()` with `_residual` buffering; `_shared_model()->_MODEL_SINGLETON=load_silero_vad(onnx=True)`.
**Connects:** Per-`SttSession` instance, shares ONNX singleton.
**Flow:** Arbitrary PCM chunks -> sliced 512-sample frames -> start/end events -> `session.py` state machine.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/src/asr.py`
**Purpose:** `ASREngine` abstraction + 2 backends.
**Key:** `@dataclass Transcript(text, avg_logprob, no_speech_prob, inference_ms)`; `ABC ASREngine.transcribe(audio:float32[-1,1], *, fast:bool)`; `FasterWhisperEngine(WhisperModel(...).transcribe(language, beam_size, vad_filter=False, condition_on_previous_text=False, initial_prompt))`; `clean_mms_devanagari()` (rejoins `\s+([093E-094C...])`); `ChhattisgarhiMMSEngine(Wav2Vec2ForCTC facebook/mms-1b-all + hne adapter, cuda/cpu+float32/16/bf16, AutoProcessor, argmax+decode)`; `get_engine()->_ENGINE_SINGLETON` (`hne`->MMS else Whisper); `logprob_to_confidence=clamp(1+avg_logprob)`.
**Connects:** Called via `run_in_executor` from `session.py`, warmed in `server.py:lifespan`, reused directly by `demo/local_speech.py::recognize()` and `demo2/speech.py::transcribe()`(MMS path).
**Flow:** `float32 PCM` -> `fast=True greedy(beam1)` for partials vs `fast=False beam5` for finals -> `Transcript`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/src/session.py`
**Purpose:** Core per-connection state machine. Not thread-safe.
**Key:** `_EXECUTOR=ThreadPoolExecutor(ASR_WORKER_THREADS)`; `enum _State(SILENCE,SPEAKING)`; `class SttSession(session_id, _vad, _buffer:bytearray, _utterance_start_ms, _last_partial_emit_ts, _silence_started_ts, _utterance_counter)`: `async start()->SESSION_STARTED`, `async process_chunk(pcm16)->[SPEECH_STARTED,PARTIAL,FINAL]`, `async flush()`, `_buffer_ms/_elapsed_audio_ms/_bytes_to_float32`, `_emit_partial()` (last `PARTIAL_WINDOW_MS` only), `_finalize()` (full buffer, `MIN_FINAL_AUDIO_MS`, `no_speech_prob` hallucination filter, `utterance_id++`, `vad.reset()`).
**Connects:** Uses `vad.py+asr.py+schemas.py+config.py`; driven by `server.py`, `telephony_adapter` output.
**Flow:** `SILENCE --VAD start--> SPEAKING(buffer+periodic windowed PARTIAL every PARTIAL_INTERVAL_MS) --silence>=EOS or len>=MAX--> FINAL-->SILENCE`; `flush()` on `stop`/disconnect.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/src/server.py`
**Purpose:** FastAPI WS entrypoint, auth/capacity/timeout.
**Key:** `lifespan(get_engine() warm)`, `app=FastAPI`, `GET /health->{status,model,device,active_sessions,max_sessions,at_capacity}`, `@app.websocket("/ws/stt/{session_id}") stt_websocket`: api_key check `4401`, `Semaphore` full->`SESSION_REJECTED+4503`, `accept+SttSession`, `wait_for(receive, IDLE_TIMEOUT_S)`, binary->`process_chunk`, text->`ClientControlMessage(stop->flush+break)`, `finally: flush+release`.
**Connects:** Owns `SttSession` per socket, shares `get_engine()`.
**Flow:** Connect->`session_started`->loop audio->`speech_started/partial/final`->`stop`/disconnect->auto-flush->close.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/src/telephony_adapter.py`
**Purpose:** PSTN bridge, no Twilio I/O itself.
**Key:** `TWILIO_SAMPLE_RATE=8000`; `mulaw_8k_to_pcm16_16k(mulaw_bytes)` via `audioop.ulaw2lin+ratecv(8k->16k)` with `audioop/audioop_lts` fallback; docstring `/twilio/stream` sketch (`base64->converter->process_chunk`).
**Connects:** Preprocessor before `session.process_chunk()`.
**Flow:** `PSTN->Twilio 8k mu-law base64 JSON->converter->16k PCM16->normal STT path`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/Dockerfile`
`python:3.11-slim+ffmpeg`, `COPY requirements/src/run.py`, `ENV STT_HOST/PORT`, `EXPOSE 8000`, `CMD python run.py`. GPU comment: use `nvidia/cuda` + `STT_DEVICE=cuda`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/.env.example` (+`.env`)
Template for all `STT_*` vars (defaults: `MODEL small.en, DEVICE cpu, COMPUTE int8, LANGUAGE hne, VAD 0.5/100ms, EOS 600ms, MAX 20000ms, PARTIAL 700/6000ms`, clinic `INITIAL_PROMPT`, `API_KEY=`, `MAX_SESSIONS 8, IDLE 30s, WS ping 20/60s, MMS_DTYPE float32`). `.env` is secret, never committed.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/tests/test_client_wav.py`
Streams WAV (`soundfile`, 40ms chunks, `sleep CHUNK_MS`) to `ws://localhost:8000/ws/stt/test-session`, prints `PARTIAL/FINAL`, sends `{"action":"stop"}`. Requires mono 16k PCM (`ffmpeg -ar 16000 -ac1 -sample_fmt s16`).

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/tests/test_client_mic.py`
Live mic via `sounddevice RawInputStream(16k,40ms,int16,mono)+queue+websockets(ping_interval=None)`, receiver prints events, `Ctrl-C->stop`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/STT/stt-service/test_mms_speed.py`
Benchmark: loads `ChhattisgarhiMMSEngine`, transcribes 5s zeros, prints `inference_ms`.

---

## 2. TTS — `/run/media/rtx/Files/Study/Semester 5/Minor/code/TTS/`

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/TTS/chattisgarhi-tts-models/README.md`
Usage for Chhattisgarhi Coqui VITS: `pip torch TTS`, `Synthesizer(tts_checkpoint, tts_config_path, use_cuda)`, `tts.tts(text Devanagari)->save_wav(output.wav)`. CPU ok, GPU faster. MIT.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/TTS/chattisgarhi-tts-models/Female/config.json` + `Female/best_model.pth` (~950MB LFS)
VITS Female: `model:vits, audio sample_rate 22050, fft1024/win1024/hop256/mel80`, `text_cleaner multilingual_cleaners, use_phonemes false, add_blank true`, `model_args num_chars 114, hidden192/ffn768/heads2/layers6, posterior16, flow4, upsample[8,8,2,2], use_sdp true, length_scale 1.0`, `characters` Devanagari set + `!¡'(),-.:;¿? `. `best_model.pth` weights (do not edit, `git lfs pull` needed).

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/TTS/chattisgarhi-tts-models/Male/config.json` + `Male/best_model.pth`
Same VITS but Male voice: `num_chars 106` (different vocab order), `restore_path .../Chhattisgarhi_Male/...checkpoint_920000.pth`, otherwise identical audio/arch. Used via `DEMO_TTS_VOICE=Male`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/TTS/chattisgarhi-tts-models/indictts.ipynb` (4 cells)
Cell0 legacy `from models import Synthesizer...speak()`; Cell1 `TTS.utils.synthesizer.Synthesizer(Female...)+tts.tts(speed=12)` (demonstrates broken `speed`)+`length_scale=.2+save outputslow.wav`; Cells2-3 truncated/experimental. Purpose: scratchpad proving `length_scale` is correct control (documented in AGENTS.md).

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/TTS/chattisgarhi-tts-models/test_speed.py`
Tries `tts(text,speed=1.5)` vs `tts(text,length_scale=1.5)` on `जम्मू कश्मीर`, prints which kwarg works (establishes `speed` broken).

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/TTS/chattisgarhi-tts-models/test_speed2.py`
Compares wav lengths default vs `speed` vs `length_scale`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/TTS/chattisgarhi-tts-models/test_speed_override.py`
Correct pattern: `tts.tts_model.length_scale=1.5/.5` before `tts()` on long sentence, prints lengths.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/TTS/chattisgarhi-tts-models/output.wav`, `outputslow.wav`, `/run/media/rtx/Files/Study/Semester 5/Minor/code/TTS/indic_tts_out.wav`
Sample synthesis artifacts. Not code.

**TTS request->response:** `Devanagari text -> Synthesizer(checkpoint+config) -> set length_scale (1.0 normal,1.25 slower) -> tts.tts()->22050Hz float WAV -> save/play`. Consumed by notebook, `demo/local_speech.speak()`, `demo2/speech.synthesize()`.

---

## 3. Notebook + outputs

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/Speech2Speech.ipynb` (16 cells, 488K)
**Purpose:** End-to-end local test bench: mic/WAV->STT WS->response text->VITS->playback. No LLM required.
**Key funcs:** `record_from_microphone(seconds=6)->PCM16` (`sounddevice`), `load_wav_as_pcm16(path)` (`soundfile+scipy resample_poly`), `stt_health()/subprocess.Popen(run.py)+300s MMS wait`, `Synthesizer(Female/Male)`, `async transcribe_pcm16(pcm16,realtime)->events` (40ms chunks+`{"action":"stop"}`, collects `final`), `make_response(transcript)` (empty->apology, hello->greeting, else echo `आपने कहा:`), `synthesize_response(text,length_scale)->speech2speech_outputs/response_*.wav`, `stop_stt_service()`, TTS-only sanity `नमस्ते!...`.
**Connects:** Requires `STT/stt-service` running (`STT_LANGUAGE=hne` for MMS) + `TTS` checkpoints. Pattern reused by `demo/local_speech.py` and `demo2/speech.py` (but they call engine directly, not WS).
**Flow:** Setup paths->ensure STT `GET /health` else launch->load VITS->mic/WAV PCM16->stream WS 40ms binary->print `PARTIAL/FINAL`->last `final`->`make_response()` (replace with LLM)->`length_scale` synthesis->`Audio(display)`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/speech2speech_outputs/response_20260904_073029.wav`
Saved notebook response example.

---

## 4. `demo/` — Kisan Saathi (`/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/`)

Farmer shopping Streamlit+Groq(free-tier)+real MCP stdio+local speech, JSON store (no SQLite). Push-to-talk: mic Stop->auto transcribe+submit.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/AGENTS.md`
Invariants: separate dir, `minor` env, real MCP stdio, session/idempotency outside model args, paise integers+file-lock atomic JSON, simulated checkout+explicit confirm, synthetic catalogue, reuse STT/VITS via `local_speech.py`, claim recording before processing, keys in `.env`, grounded templates, `pytest+` MCP transport check, skills `farmer-mcp-demo/SKILL.md`, `demo-verification/SKILL.md`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/README.md`
Run `streamlit run app.py`, `GROQ_CHAT_MODEL=openai/gpt-oss-120b` (llama 404 replaced), exact cart/checkout shortcuts skip LLM, `local_speech` uses `get_engine(fast=False)` + `STT/.env` with `DEMO_STT_DEVICE=cuda/DTYPE=float16` (no silent fallback), TTS `DEMO_TTS_VOICE/DEVICE/LENGTH_SCALE`, lazy cached+locked models, in-mem PCM16 16k in / 22050 out, Hindi words for `₹`/digits, Groq gets transcript only, keyless local still works, JSON locking/atomic, verification `pytest/pip check/smoke_demo.py[--live]`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/requirements.txt`
`streamlit1.49.1, mcp1.12.4, groq0.37.1, filelock, soundfile, sse-starlette2.2.1/starlette0.41.3/protobuf4.25.9/click8.4.2, dotenv, jsonschema, rapidfuzz, pytest, numpy<2, scipy`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/config.py`
**Key:** `ROOT, STATE_PATH(data/shop.json|DEMO_STATE_PATH), API_KEY/CHAT_MODEL, STT_ROOT/TTS_ROOT, STT_ENV(STT/.env+environ), STT_LANGUAGE(hne)/DEVICE(cuda)/DTYPE(float16)/MODEL, TTS_VOICE(Female)/DEVICE(cpu)/LENGTH_SCALE, SPEECH_THREADS, TTS_MAX_CHARS1800, SESSION/TURN/CONFIRM ids, API_TIMEOUT25/MCP20/MAX_ROUNDS4/MAX_QUANTITY100/MAX_AUDIO4MB/45s/MAX_TEXT1500`; `configure_stt()` validates device/dtype, `setdefault`s `STT_*`, forces `STT_DEVICE/MMS_DTYPE`.
**Connects:** Read by all demo modules; bridges STT research config without mutating it.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/app.py`
Streamlit UI. **Key:** `initialize()(uuid session, messages/traces/timings/preview/draft/audio/asr)`, `refresh()=inspect_server()`, `remember(output...)` (append user+`render()`, keep 30/60, preview logic, `make_audio`), `make_audio()` (TTS fail independent), `manual(name,args)` (same MCP boundary + `refresh`), `submit_request(text,spoken)` (preview+`is_confirmation`->`direct confirm_checkout` else `run_turn`, merge timings, preview update). Tabs: Talk (`audio_input`, `sha256/file_id` claim `processed_recording`, `prepare_recording->transcribe->submit_request`, typed form, chat, `audio(autoplay)`, preview confirm/cancel), Shop (search/add/details/cart/remove/refresh/checkout/confirm), Developer (tools JSON, timings, traces, download trace without keys/audio/tokens).
**Connects:** `assistant.run_turn, mcp_client.direct/inspect_server, responses.render, voice.*`.
**Flow:** Mic Stop->claimed once->local STT->Groq+MCP->grounded text+optional VITS->chat.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/assistant.py`
Bounded Groq tool loop. **Key:** `SYSTEM` (Chhattisgarhi/Hindi/En/Roman aliases, STT-error tolerant, spoken numbers/units, resolve->add1, view_cart/price, clarification, refuse_and_refer for diagnosis/dosage, sequential, no free prose), `SAFETY_PATTERN, CONFIRM_PHRASES, QUICK_ACTIONS(view cart/checkout multilingual), _fuzzy_best/_CONFIRM_THRESHOLD80/_QUICK75, is_confirmation() (negation reject), fuzzy_quick_action(), provider_warning(401/403/404/429/400)`, `async run_async(text,language,api_key,session_id,turn_id,history,state_path,client)` (validate length, `AsyncGroq`, `connect()`, `allowed-discover-confirm_checkout`, `tools`, history8, safety->refuse, quick->invoke, else `MAX_ROUNDS` `chat.completions.create(required then auto, no parallel, temp0)` + strict single-call+`jsonschema.validate` else `clarification`, `invoke`, append tool msg, break on referral/clarify/ambiguous/preview/added/removed, visible added/removed+last, `render`, final `view_cart`, timings), `run_turn()=asyncio.run(run_async)`.
**Connects:** `mcp_client.connect/invoke`, `shop.result`, `responses.render`.
**Flow:** Text->safety/quick/LLM->validated single tool->MCP->grounded template (never model prose for advice).

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/shop.py`
JSON facts. **Key:** `money(paise)->₹`, `result(template)/error(code)`, `normalize(NFC+casefold)`, `FUZZY_THRESHOLD70, fuzzy_match(substring or ratio/token_sort)`, `class Shop(path,session_id,turn_id)`: `connection() (FileLock+.lock, version1 check, catalogue.json seed, deepcopy diff, NamedTemp+fsync+os.replace)`, `_product(+price_display), search_products(query,category all/seeds/fertilizers/tools, group aliases बीज/beej/खाद..., scoring exact100/padded95/substring90/fuzz/ngram, top-5 filter), resolve_product(0 unknown/ >1 ambiguous/1 product), get_product_details, check_price(package math), _cart(locked prices, line totals), view_cart, _write(sha256[session,request/turn,name,args] idempotency), add_to_cart(stock+MAX check, clear preview), remove_from_cart(session-owned), checkout(token+snapshot preview, no order), confirm_checkout(token match+snapshot==cart+stock->DEMO-xxx order, stock decrement, replay same), calculate_required_quantity(always unverified_rate_metadata)`.
**Connects:** Used by `mcp_server.py` tools, via `mcp_client` subprocess isolation.
**Flow:** All mutations locked+atomic+idempotent, money paise, preview-bound confirm.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/local_speech.py`
Reuse research models, no notebook/server needed. **Key:** `_LOCK RLock, _SYNTHESIZER cache`; `recognize(pcm16)->str` (`configure_stt, sys.path STT_ROOT, torch threads, cuda check, get_engine().transcribe(fast=False), no_speech filter`); `speak(text)->WAV bytes` (`Synthesizer(checkpoint+config, cuda if TTS_DEVICE), length_scale, soundfile 22050 WAV, LFS-pointer/invalid checks`).
**Connects:** Bridges `STT/src/asr` + `TTS` checkpoints to `voice.py`.
**Flow:** Completed recording->final decode; text->cached VITS->in-mem WAV.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/mcp_client.py`
Transport lifetime. **Key:** `connect(session_id,turn_id,state_path,confirmation_token)` (`StdioServerParameters(python mcp_server.py, env DEMO_* identity, never Groq key)+stdio_client+ClientSession+initialize/list_tools+additionalProperties false`); `invoke(session,schemas,name,args,traces)` (unknown->error, `validate`, `call_tool`, `structuredContent` else JSON text, strip `confirmation_token` in trace); `direct_async/direct`, `inspect_async/inspect_server(search+view_cart health, no key)`.
**Connects:** Spawns `mcp_server.py` per call, used by `app.py/assistant.py/smoke`.
**Flow:** Browser->Python client->separate MCP server->JSON, traces retain evidence.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/mcp_server.py`
Stdio adapter (stdout reserved). **Key:** `FastMCP("Farmer Shopping Demo"), shop=Shop(STATE_PATH,SESSION_ID,TURN_ID)`, `Count/ProductID/Mention` pydantic, `READ/WRITE` annotations; 12 tools: `search_products, resolve_product, get_product_details, check_price, view_cart, add_to_cart, remove_from_cart, checkout, confirm_checkout(host CONFIRM_TOKEN else confirmation_required, model cannot access), calculate_required_quantity(refuse), request_clarification, refuse_and_refer` + `resource shopping://demo/about`; `server.run(stdio)`.
**Connects:** Implements `shop.py` over MCP, identity via env from client.
**Flow:** Model/manual->validated tool->Shop JSON->structured result.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/responses.py`
Grounded templates (draft Chhattisgarhi needs review). **Key:** `LANGUAGES{hne,hi,en}`, `render(output,language)` with `choose(en/hi/cg)`: `product(), cart_text()`, error codes (`unknown_product, unknown_cart_item, insufficient_stock, invalid_quantity, unit_mismatch, empty_cart, stale_checkout, unverified_rate`), `products/ambiguous, product/price, cart/added/removed, checkout_preview (Confirm demo order/डेमो ऑर्डर पक्का करो), order(DEMO-xxx, no payment), referral(KVK), clarification(product/quantity/unit/shopping_only/repeat)`.
**Connects:** Renders `shop/assistant` outputs in `app.py`, never model prose for advice.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/voice.py`
Adapters, no disk. **Key:** `prepare_recording(browser WAV->16k PCM16 WAV)` (`wave validate channels/rate/frames, numpy mean stereo, resample_poly via gcd`), `validate_wav(mono16k16bit, 0.3-45s, RMS>=100)`, `transcribe(audio,api_key,language)->{text,asr_ms,audio_seconds,model,asr_language}` (`recognize(pcm)`), `transcription_error(OOM/Memory/Import/generic)`, `synthesize(text,language)->(bytes,ms)` (`en->ValueError Devanagari only, speak(prepare_speech_text)`).
**Connects:** `local_speech.recognize/speak + speech_text.prepare_speech_text + config limits`.
**Flow:** Mic WAV->normalize->local MMS->text; reply text->Hindi-words->VITS WAV.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/speech_text.py`
VITS vocab fix. **Key:** `_SMALL[0-99] Hindi, number_words(Indian करोड़/लाख/हजार/सौ recursion), prepare_speech_text(₹->words, strip (ID), DEMO-xxx->पहचान स्क्रीन पर देखिए, digits->words, ×->गुना, ;->।)`. Display unchanged, speech expanded.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/smoke_demo.py`
Verification. **Key:** `check_mcp(path)` (12 tools, SEED01 धान resolve, host-injection reject, invalid qty reject, 2 packs=90000 paise, replay idempotent, जैविक खाद ambiguous, TOOL04 stock fail, rate refuse, checkout preview, confirm denied without token, no token in traces, isolation, confirm+replay same, cart cleared); `check_live(path)` (VITS->ffmpeg->transcribe->`run_turn` price->`check_price` trace->reply VITS, needs key+ffmpeg); `main(--live)` JSON report.
**Connects:** Exercises `mcp_client+assistant+voice` on temp JSON.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo/.env.example` (+`.env`)
`GROQ_API_KEY/MODEL, DEMO_STT_DEVICE cuda/DTYPE float16, TTS_VOICE Female/DEVICE cpu/LENGTH 1.0, SPEECH_THREADS 4`.

### Other `demo/` files
`data/catalogue.json` (synthetic products SEED01 etc.), `data/shop.json+.lock` (runtime, atomic), `data/shop.sqlite3` (legacy untouched), `skills/farmer-mcp-demo/SKILL.md`, `skills/demo-verification/SKILL.md` (local guidance), `.claude/skills/run-farmer-demo/driver.py`, `tests/test_*.py` (app/assistant/shop/mcp/config/voice/mms: persistence, recovery, concurrent MCP, invariants, discovery, Groq doubles, audio adapters, mic/cart controls), `__pycache__/.pytest_cache/.gitignore`.

**demo request->response:** `Talk mic Stop (claimed sha256) -> voice.prepare_recording (resample 16k) -> local_speech.recognize (MMS hne final) -> assistant.run_turn (Groq picks 1 validated MCP tool) -> mcp_client stdio -> mcp_server->shop.py JSON (locked paise, idempotent) -> responses.render (hne/hi/en) -> voice.synthesize (numbers->Hindi, VITS 22050) -> chat+autoplay. Manual Shop buttons use `direct()` same MCP path. Checkout needs current preview token + explicit `Confirm demo order/डेमो ऑर्डर पक्का करो` phrases (fuzzy, negation-guarded); model lacks `confirm_checkout`.*

---

## 5. `demo2/` — IIIT-NR helpdesk (`/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/`)

Turn-based (no barge-in/telephony), local Ollama `qwen3.5:9b` default, Groq explicit, Whisper `small` for hi/en/hinglish + MMS `hne` experimental, VITS hi + Edge en/hinglish opt-in, deterministic verbalization, bounded workers, 24h retention.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/README.md`
Run `bash run.sh` (`conda run -n minor streamlit run app.py`), layout, use (provider/sidebar, Stop->auto answer+citations+audio, follow-up, New vs Delete), routing table, `verbalization.py domain-pronunciation-2` (₹90000->नब्बे हजार, 3.5%->तीन दशमलव पाँच, NEGATION map, unknown Latin fail-safe), online opt-in, lazy models, Whisper cpu/int8 default + `auto` cuda fallback (`libcublas` mismatch), config table (`OLLAMA_*, DEMO2_*, KB_DIR/STATE, HISTORY 10/12000, RAG cache 2000/64MiB/1h`), retention/queues/audio-retry, KB releases shared pointer, verification (316 tests:37 demo2+279 agent), smoke commands, troubleshooting, JEV opt-in.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/requirements.txt`
`streamlit1.49.1, edge-tts7.2.8, soundfile, scipy, dotenv, faster-whisper1.2.1`; sibling supplies torch/transformers/TTS/agent.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/settings.py`
Sibling resolver, no mutation. **Key:** `ROOT, CODE_ROOT(DEMO2_CODE_ROOT), AGENT_ROOT/STT_ROOT/TTS_ROOT, DATA_ROOT, STT_LANGUAGE hne/DEVICE cpu/WHISPER small/TTS_DEVICE cpu/SPEECH_THREADS4, SAMPLE16k/MAX30s/12MB/MAX_TEXT2000/SPEECH4000/HISTORY12/MIN0.3s/SILENCE_RMS0.002/CHUNK220/PAUSE0.12s, VOICES Female/Male, INPUT_LANGUAGES(Hindi/English/Hinglish/Chhattisgarhi exp), EDGE_VOICES en-Neerja/Prabhat hi-Swara/Madhur, EDGE_TIMEOUT45s, QUEUE3/60s/TURN120s/RETENTION86400/MAINT300s/VOICE_CACHE2/6GB/MAX_REC128`; `configure_agent()` (check `graph.py`, load agent `.env`, resolve `KB_DIR/CHROMA`, redirect `CHECKPOINT/TICKETS/RAG/ESCALATIONS` to `DATA_ROOT`, `REMINDERS false, HISTORY10, NUMBA/MPL`), `configure_stt()` (auto/cpu/cuda, load `STT/.env STT_*`, set `STT_DEVICE/LANGUAGE/MMS_DTYPE/INITIAL_PROMPT IIIT...`).

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/app.py`
Reviewed-text-before-audio UI. **Key:** `conversation=new_session()`, `manager()`, sidebar (provider ollama/groq, recording lang, voice, speed0.7-1.4, spoken, online opt-in, autoplay, student_id/email/category, New/Delete, Runtime status `runtime_health()+stats`), `submit(question,turn_id,data)`->`runtime.submit`, mic/upload (`audio_input/file_uploader wav/flac`, `sha256 recording:`, `snapshot`, `submit("",recording_id,data)`, `Retry transcription`), `chat_input`, `@st.fragment(0.5s) conversation()` (delete_pending, job_ids, user/assistant messages, `LABELS queued/transcribing/reasoning/routing/retrieval/answer/review/speech`, Cancel, error map, ticket caption, unavailable, View sources file/page/url/period/audience/conflict/scope/quote, audio autoplay/download/Spoken text, Retry/Speak audio, timings queue/STT/agent/text/speech/total + `rag_metrics` + `stage_ms`).
**Connects:** `settings, workflow.new_session, agent_bridge.valid_profile_email, health.runtime_health, jobs.manager/TERMINAL`.
**Flow:** Voice/upload/type->JobManager->fragment polls snapshot->text first, audio when ready.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/workflow.py`
Legacy sync path (jobs.py is active). **Key:** `new_session()->{id,turns,consumed_audio}`, `speak_turn(turn,voice,speed)` (audio-only retry, no graph replay), `run_turn(session,question,profile...)` (idempotent turn_id, `agent_bridge.ask`, timings, optional speak), `consume_recording(session,recording_id,data,language)` (claim before `speech.transcribe`).
**Connects:** `agent_bridge.ask + speech.*`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/speech.py`
Completed-turn speech, serialized. **Key:** `_LOCK, _SYNTHESIZER/_VOICE/_WHISPER/_SYNTHESIZERS LRU, _DIGITS, SpeechError`; `decode_audio(data)` (12MB, `soundfile`, 0.3-30s, ≤2ch/192k, resample to 16k); `transcribe(data,language)` (RMS silence->"", Whisper `small` beam5 vad_filter hi/en/hinglish(None) else MMS `get_engine(fast=False)`); `prepare_speech(text,voice)` (`verbalization.normalize hindi`, A-Z reject, `config.json characters+punctuations` support check, Devanagari required); `_chunks(220 chars, sentence split)`, `synthesize(text,voice,length_scale0.7-1.5)` (bounded CPU2/GPU1 cache+weight budget, `length_scale`, chunk+pause concat, stdout suppress, 22050 WAV); `_edge_audio(text,voice,speed)` (`edge_tts Communicate rate +/-%, 45s`), `make_audio(text,language,voice,speed,provider,allow_online)` (hindi->local VITS `1/speed`, else Edge needs consent, `verbalization.normalize`), `online_audio()` (subprocess `online_voice.py` with hard timeout, `operations.remaining`).
**Connects:** `settings.configure_*, verbalization.normalize, assistant.operations.check`.
**Flow:** WAV/FLAC->16k float->Whisper/MMS->agent text->deterministic Hindi/Edge text->VITS/Edge WAV/MP3.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/agent_bridge.py`
Grounded helpdesk adapter. **Key:** `_LOCK, valid_profile_email()->assistant.dialogue.valid_email`, `get_graph()->configure_agent()+assistant.graph.build_graph (lru, close on exit)`, `ask(question,session_id,profile,provider,turn_id)->graph.invoke(HumanMessage, student_id/email/category, thread_id+llm_provider)->{answer_text,response_status,sources,language,ticket_id,reminder_id,rag_metrics,llm_error}`, `render_hindi/render_speech()` (LLM pronunciation JSON, facts preserved, numbers identical, no markdown/URLs).
**Connects:** Single graph/SQLite for all browsers, called by `jobs.py/workflow.py/smoke.py`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/storage.py`
Retention/durable results/backups. **Key:** `DATABASES(conversations,tickets,rag_cache,sessions)`, `connection(.25s timeout)`, `class Store(root,retention86400,clock)`: `register(expires+deleted+tombstone)`, `session_ids`, `acquire_runtime(runtime.lock flock)`, `request(session,turn,payload sha256 fingerprint, idempotent reuse else request_conflict)`, `complete(persist reviewed text sans audio)`, `_erase_rows(checkpoints/writes/action_requests/tickets/cache_owners/requests)`, `delete(tombstone+expire backups+erase)`, `compact(keep 2 checkpoints)`, `_expire_backups`, `maintain(expired/deleted/legacy grace/orphans/tickets by timestamp/cache expiry/tombstone expiry)`, `backup(sqlite backup API+sha256+24h)`, `restore_into(empty dest, sha256+integrity, apply tombstones)`.
**Connects:** Owned by `jobs.JobManager`, CLI `ops.py`, shares lock with app.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/jobs.py`
Bounded workers, no Streamlit in workers. **Key:** `TERMINAL{complete,failed,cancelled}`, `dataclass Job(...)`, `class JobManager(store, runtime_lock, condition, queue, jobs, counters, speech_pool1, worker+maintenance threads)`: `submit(admit once, conversation_busy, QUEUE_CAPACITY3+1 busy, Store.request fingerprint, durable reuse->complete else queue, bound 128 finished)`, `snapshot(copy+queue/turn timeout->failed)`, `cancel(suppress late, queued->cancelled)`, `delete(drain+Store.delete)`, `backup(idle only)`, `_loop(queue-> _run)`, `_run(Operation deadline, transcribing->speech.transcribe, reasoning->agent_bridge.ask, complete+compact, reviewed_text_seconds, speech_pool _speak else complete; error map no_speech/expired/storage/invalid/turn_failed)`, `_speak(Operation, make_audio, audio_error SpeechError vs generic, speech_seconds)`, `retry_audio(reuse text+provider)`, `retry(same identity)`, `stats/close/_maintenance(every MAINT300s)`, `manager()->configure_agent+JobManager lru`.
**Connects:** `speech, agent_bridge, storage.Store, assistant.operations`.
**Flow:** Submit->queued (60s)->transcribe->reasoning (120s total)->publish text->speech (45s)->complete; Cancel suppresses late but native keeps slot.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/health.py`
Read-only manifests. **Key:** `verified_release(root,hash)->kb.integrity.verify`, `environment_summary(python/platform/torch/ollama/stt/tts/whisper/data)`, `dependency_check(streamlit/torch/faster_whisper/TTS/edge_tts/chroma/sentence_transformers/pdfplumber)`, `runtime_health()->configure_agent+active_release+integrity bound/legacy, chunks/cutoffs/evidence, sources_unassigned/overdue, JEV mode/artifact/activation/backend, voices exist, env+deps`.
**Connects:** Sidebar Runtime status + `ops.py status`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/ops.py`
Operator CLI (stop app first). **Key:** `status/maintain/backup/restore --data/--backup/--destination` (`runtime_health+storage bytes/integrity/rows`, `Store(...).acquire_runtime()->maintain/backup/restore_into`).
**Connects:** `health+storage+settings`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/verbalization.py`
Deterministic pronunciation, `VERSION domain-pronunciation-2`. **Key:** `_SMALL0-99, _MONTHS, LEXICON(IIIT->आईआईआईटी, B.Tech->बीटेक, JoSAA->जोसा...), HINGLISH(roman->Devanagari), NEGATION(not->नहीं, non-refundable->गैर-वापसी योग्य...)`, `cardinal(Indian units)`, `_words(longest-first regex)`, `normalize(text,language)` (NFC, unicode digits->ASCII, strip `*_\`#`, ₹/% handling, lexicon, negation/hinglish, dates->`cardinal day MONTH year`, minus->ऋण/से, numbers with grouping->words+दशमलव, symbols).
**Connects:** Used by `speech.prepare_speech/make_audio`, never LLM rewrite. Preserves negation/order.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/online_voice.py`
Isolated Edge worker. **Key:** stdin JSON `{text,voice,speed}` -> `speech._edge_audio` -> stdout MP3, stderr type only. Allows parent hard timeout without logging text.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/smoke.py`
Explicit checks, no tickets. `tts` (hi greeting Female/Male 22050 WAV), `online/hinglish` (Edge MP3), `stt/mms` (transcribe Female.wav hi vs hne-exp), `agent/pipeline` (fixed `बी टेक प्रवेश...` -> `ask` needs `answered+sources`, pipeline adds STT+TTS roundtrip). Writes `data/smoke/`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/run.sh`
`conda run -n minor streamlit run app.py "$@"`.

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2/.env.example`
`LLM ollama/qwen3.5:9b/8192, OLLAMA_*, DEMO2_STT cpu/small/TTS cpu/threads4/LANGUAGE hne, HISTORY10/12000, RAG cache true/3600/2000/128KiB/0.1s/64MiB, KB_STATE override, JEV off/cpu2/10s, QUEUE3/60/120/RETENTION86400/MAINT300/VOICE2/6GB, CHECKPOINT0.25s`.

### Docs/configs
`KNOWLEDGE_BASE.md` (active release `20260922...` 222 chunks/613 records, paths, `kb_pipeline refresh/ranks/extract/build/evaluate/activate/rollback`, no `build_index.py`, fresh checkout needs LFS/models), `OPERATIONS.md` (127.0.0.1 bound, 1 reasoning+1 speech, queue3, timeouts, retry-audio, 24h/tombstone logically not forensic, backup SHA+24h, `compatibility-constraints.txt`, JEV off, Edge consent, VITS rights), `VALIDATION.md` (Oct26 316 pass 37+279, health `20260927...` 224/611/758, smoke TTS/Edge/verbal, Sep local/memory/KB/history), `OFFLINE_INFORMATION_NEEDED.md` (46 Q checklist scholarships/loans/spots/academics/hostel/placements, not policy), `compatibility-constraints.txt` (protobuf 4.25.8 + otel/chroma pins, preserve torch/TTS), `pytest.ini`, `.streamlit/config.toml`, `tests/test_demo.py (17 audio/verbal/UI) + test_operations.py (12 queue/timeout/compaction) + browser_harness.py`, `evaluation/upgrade-20260930/*.json`, `data/` (`conversations/rag_cache.sqlite, upgrade-20260930 wheels/jev-r3/critical/caches, smoke/`) — runtime/ignored artifacts.

**demo2 request->response:** `Mic Stop/Upload (0.3-30s ≤12MB, sha recording:) or typed (≤2000ch) + profile/provider/voice/speed/online -> jobs.submit (fingerprint idempotent, queue3, per-conversation 1) -> reasoning thread: speech.transcribe (Whisper hi/en/hinglish or MMS hne, silence->no_speech) -> agent_bridge.ask (LangGraph: classify->retrieve(E5+BM25+RRF, exact JoSAA sidecar, cache)->generate->grounding review->finalize, history10, rag_metrics) -> Store.complete (text only) -> speech_pool: verbalization.normalize -> VITS hi (22050 WAV, length_scale=1/speed) or Edge en/hinglish MP3 (consent+45s subprocess) -> fragment shows text immediately, audio when ready; Retry audio reuses text/provider, no graph replay; Delete tombstones + purges backups.*

---

## 6. `Institute-voice-agent/` (`/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/`)

### `/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/README.md`
LLM layer guide: `institute-assistant` standalone RAG + `voice-orchestrator` glue. Prerequisites `minor`+STT+Ollama `qwen3.5:9b`. Steps: `setup_local.py`, `ask_kb.py/run_cli.py` before voice, `voice-orchestrator/.env STT_WS_BASE_URL` must match STT port, `orchestrator.py` prints `[STT FINAL]/[ASSISTANT]`, TTS placeholder comment. Limits: manual login, cross-lingual untested, SMTP placeholders.

### `voice-orchestrator/`
- **`/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/voice-orchestrator/orchestrator.py`**: Thin loop, no ASR/LLM. **Key:** `load_dotenv(.env)+institute .env`, `build_graph()`, `SAMPLE16k/CHUNK40ms`, `_mic_callback/_send_mic_audio`, `main()` (prompt id/email/category, `STT_WS_BASE_URL/student_id`, `sounddevice+websockets(ping None)`, `partial` print, `final`->`graph.invoke(HumanMessage, student/thread_id)`->print reply, `# TTS PLUGS IN RIGHT HERE`). **Flow:** Mic binary->STT WS->final->graph text reply (TTS one-liner future).
- **`/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/voice-orchestrator/requirements.txt`**: `-r ../institute-assistant/requirements.txt`, `-e ../institute-assistant`, `websockets14.1/sounddevice/dotenv`.
- **`.env.example/.gitignore`**: `STT_WS_BASE_URL=ws://localhost:8000/ws/stt`, `INSTITUTE_ASSISTANT_ENV_PATH`.

### `institute-assistant/` — shared reasoning
- **`/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/institute-assistant/README.md`**: LangGraph+Ollama(default)/Groq+Chroma, en/hi/hinglish (+hne exp->hi), Demo2 speech adapter, history10/cache2000/1h, E5 embeddings 350/50 + SQLite sidecar 611 JoSAA rows, grounding review+quote validation, tickets local drafts, reminders disabled, `kb_pipeline bootstrap/refresh/ranks/extract/build/evaluate/activate/rollback`, `evaluate_helpdesk --live`, speech contract table (`answer_text/sources/ticket/language/rag_metrics`).
- **`/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/institute-assistant/requirements.txt`**: `pdfplumber/bs4/opencv, langchain/chroma/sentence-transformers, langgraph/sqlite/groq/httpx, dotenv/numpy`.
- **`/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/institute-assistant/run_cli.py`**: Text CLI (`model_identity`, prompts id/email/category, `uuid thread_id`, `/new//quit`, `MAX_QUESTION`, `graph.invoke->answer_text+sources`, close checkpointer).
- **`/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/institute-assistant/ask_kb.py`**: Retrieval-only debugger (`retrieve(question,category)` print file/page/score/text).
- **`/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/institute-assistant/build_index.py`**: Legacy guard (refuses if verified release active, else `ingest.build_index()`).
- **`/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/institute-assistant/kb_pipeline.py`**: Verified KB CLI (`bootstrap/refresh/ranks/extract/build/evaluate/activate/rollback/report/source-status`, `merge_records(blocks+josaa+manual+sources)`).
- **`/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/institute-assistant/setup_local.py`**: Downloads matching `tokenizer.json` (`llama3.1/qwen3/qwen3.5` pinned revisions), validates, checks `ollama serve+pull`.
- **`setup.py, evaluate_helpdesk.py (--live --provider --case --cache-benchmark, blocks writes), jev_pipeline.py, check_reminders.py, review_tickets.py, repair_audit_evidence.py, kb_gap_report.py`**: Maintenance/eval/training utilities.
- **`assistant/` core:**
  - `config.py`: `Settings` (KB/CHROMA/TOP6/FETCH32/DIST1.5/CONTEXT14k/HISTORY10/12000/RAG cache/KB E5 rev/OCR/ranks, CATEGORIES, JEV off, LLM ollama/qwen3.5 vs groq, CHECKPOINT/TICKETS/GAP/SMTP/OFFICE_EMAILS + validation).
  - `state.py`: `AssistantState` (messages+student/language/intent/category/query/chunks/answer/status/sources/ticket/reminder/pending/confirmed/history/date/release/metrics/error, serializable).
  - `graph.py`: `build_graph(checkpointer)` (`classify->retrieve->generate->finalize`, `classify->escalate/handle_reminder->finalize`).
  - `nodes.py`: `ROUTING/ANSWER/REVIEW_PROMPTS`, `classify_intent_node` (reset, cheap hi/thanks, `try_route` else `invoke_json RoutingDecision`, exact_rank_followup), `retrieve_node` (pin release, `RagCache` retrieval hit/miss), `generate_answer_node` (eligible/year filter, context budget, `select_policy` deterministic else draft cache+`GroundedAnswer`+review, quote `source_quote`+`Evidence` validation), `escalate/handle_reminder/finalize_turn (history trim+resolved_query)/route_after`.
  - `llm.py`: `selected_provider/model_identity/_tokenizer/_messages/evidence_spans/generation_schema/prompt_tokens/prepare_payload(budget history+evidence)/_local_client/_invoke_local(Ollama chat+grammar+digest)/RoutingDecision/Evidence/GroundedAnswer/get_llm(ChatGroq)/invoke_json(Groq 429 one retry within budget)`.
  - `retrieval.py`: `RetrievedChunk`, `get_release_engine(active_release+verify)`, BM25+semantic RRF (`retrieve()`), year/category preference.
  - `dialogue.py`: `COPY en/hi/hinglish say(), language_hint, valid_email, normalize_category`.
  - `cache.py`: `RagCache (SQLite LFU 2000/64MiB/1h, cache_key sha, telemetry hit/miss/bypass/put/evict)`.
  - `operations.py`: `Operation(deadline/cancelled/progress/attempts)+operation_context/check/remaining/record_attempt (numeric allowlist only)`.
  - `history.py, evidence.py, ingest.py, extract.py, db.py, action_requests.py, notify.py, report.py, metrics.py, telemetry.py, gap_analysis.py`.
  - `kb/`: `common/active_release, sources/refresh, josaa/collect_ranks, extraction/extract_all, releases/build/activate/rollback, evaluation/evaluate_release, search/SearchEngine (E5+BM25+exact), structured, integrity/verify, policies/select, provenance, embeddings, reporting`.
  - `jev/`: `runtime.try_route, training/data/evaluation/paired_benchmark, english_* (recovery/policy/model/data/audit/freeze/holdout/normalization/v3_*), vendor/model, common` — opt-in classifiers, default off.
- **`knowledge_base/{admissions,academics,hostel,cg_counselling,general}/README + PDFs (B TECH_2026, JOSAA, ACF2026, NIRF, FAQs, AR_2022_23)`**: Sources (folder READMEs not indexed).
- **`kb_state/{sources/reviews/releases/20260930.../active.json/facts.sqlite/chroma/validation...}+kb_sources.json`**: Immutable versioned releases shared by CLI+Demo2 via pointer.
- **`tests/test_*.py (helpdesk/retrieval/rank_followup/memory_cache/local_provider/llm/kb_pipeline/jev*/ingest/delivery/audit_upgrade/conftest)`**: 279 tests, temp DBs/fake embeddings/mocked LLMs.
- **`docs/LOCAL_INFERENCE.md, LOCAL_MODEL_VALIDATION.md, KB_*.md, OPEN_JEV*.md, ENGLISH_ROUTER*.md`**: Setup/validation guides.

**Institute request->response (text/voice):** `Q (CLI typed / orchestrator STT final / Demo2 transcribed) + {student_id/email/category, thread_id uuid, llm_provider} -> build_graph.invoke -> classify_intent (smalltalk/out_of_scope/clarify/handoff/reminder vs knowledge+English query rewrite+followup) -> retrieve (pinned release, E5 semantic+BM25 RRF, JoSAA exact, cache) -> generate (context budget, policy deterministic or LLM draft+grounding review, quote verification) -> escalate/reminder (explicit confirm only, local SQLite draft) -> finalize (history trim) -> {answer_text (speak this), sources (display only), ticket/reminder ids, language, rag_metrics} -> Demo2 speech / orchestrator print / CLI print.*


</task_result>
</task>
```

**Tool: task**

**Input:**
```json
{
  "description": "Explore idea and app docs",
  "prompt": "In /run/media/rtx/Files/Study/Semester 5/Minor/idea and /run/media/rtx/Files/Study/Semester 5/Minor/app, explore every file recursively: docs/, proposal.txt, DEMO2_*.md, conversations/, presentation/, WEB_APP_SPECIFICATION if exists. For each file report purpose, architecture choices, scope. READ-ONLY, do not edit.",
  "subagent_type": "explore"
}
```

**Output:**
```
<task id="ses_f0272cde7ffeIISjfjxw4VI3qz" state="completed">
<task_result>
**READ-ONLY recursive exploration completed — no edits made.**
**Roots scanned:** `/run/media/rtx/Files/Study/Semester 5/Minor/idea` (14 files) + `/run/media/rtx/Files/Study/Semester 5/Minor/app` (1 file). All requested categories found in `idea/`; `app/` contains only `README.md`.

### 1. Inventory — absolute paths

```
idea/AGENTS.md
idea/proposal.txt (1735 lines, text export of PDF)
idea/Chhattisgarhi_Voice_Shopping_Assistant_Proposal2.pdf (33 pages, same content as proposal.txt)
idea/DEMO2_IMPROVEMENT_REPORT.md (192 lines)
idea/DEMO2_TECHNICAL_AUDIT.md (439 lines)
idea/docs/WEB_APP_SPECIFICATION.md (468 lines)
idea/docs/OPEN_JEV_FAILURE_ANALYSIS_AND_RECOVERY.md (596 lines)
idea/presentation/DEMO2_KNOWLEDGE_BASE_RESULTS.md (178 lines)
idea/conversations/PROJECT_WORK_PLAN.md (756 lines)
idea/conversations/mcp-tool-surface.md (581 lines)
idea/conversations/2026-09-05-demo-verification.md (64 lines)
idea/conversations/2026-09-05-microphone-conversation.md (33 lines)
idea/conversations/2026-09-06-local-sts-json-demo.md (65 lines)
idea/conversations/2026-09-06-stt-gpu-memory-fix.md (30 lines)
app/README.md (16 lines)
```

No `docs/`, `conversations/`, `presentation/`, `proposal.txt`, `DEMO2_*.md` under `app/`.

### 2. File-by-file: Purpose / Architecture / Scope

#### A. Governance + Proposal

**`/run/media/rtx/Files/Study/Semester 5/Minor/idea/AGENTS.md` — 548 lines**
* **Purpose:** Repository-wide authority for humans + coding agents. Overrides proposal where conflicted; defines thesis, priorities, done-criteria.
* **Architecture choices:** Reusable streaming S2S core **separate** from shopping-adapter; explicit typed contracts `AudioChunk/Transcript/TranslationResult/Interpretation/ToolCall/ToolResult/ResponseText/AudioResponseChunk/VoiceTrace`; cascade `capture+VAD→gateway decode→MMS-hne ASR→Devanagari cleanup→NLLB hne_Deva MT→safety+intent→validated tool→PostgreSQL→response MT/template→VITS TTS→stream`; state-machine with `idle/listening/speech_detected/processing/responding/interrupted/failed/recovering` + barge-in cancellation; LLM as router only, never source of truth; `conda env minor` Python 3.11.15, React+TS+Vite, FastAPI, PostgreSQL, Silero VAD.
* **Scope:** Level1=already-demonstrated streaming MMS+VITS; Level2=MVP 50-100 items, search/details/price/`CALCULATE_REQUIRED_QUANTITY`/add/remove/view/simulated-checkout/spoken reply/KVK refusal/instrumentation/minimal responsive UI; Level3 explicitly NOT MVP: UPI, multi-vendor, seller dashboards, logistics/OTP, diagnosis/dosage, profiling, broad multilingual.

**`/run/media/rtx/Files/Study/Semester 5/Minor/idea/proposal.txt` + `.pdf` — identical**
* **Purpose:** Formal B.Tech Minor Proposal Autumn 2026, 16 weeks to mid-Dec 2026, IIIT, Prof. Santosh Kumar, students Punyansh Thakur/Harsh Dadsena/Aakash Sen. Motivation, RQ1-5, FR1-18, NFRs, evaluation.
* **Architecture choices:** Cascaded Option A recommended over end-to-end multimodal Option B; local/open default `MMS mms-1b-all+hne / NLLB-200-distilled-600M hne_Deva via CTranslate2 / Coqui VITS male+female / local open-weight tool-calling LLM / FastAPI / PostgreSQL+Supabase free / Flutter mobile / Opus+8s timeout`; Bhashini/hosted LLM only if confirmed; deterministic Python/SQL quantity calc from IGKV-verified metadata, no LLM arithmetic; no RAG for catalogue; JWT auth; VoiceLogs table.
* **Scope:** Same 3-levels; MVP must-have FR1-14, should-have FR15-16, could-have FR17-18; excludes payments, live inventory, seller/logistics, open agronomy advice. **Superseded detail:** Flutter/APK — `AGENTS.md` + work-plan override to web-only.

#### B. Web spec + app stub

**`/run/media/rtx/Files/Study/Semester 5/Minor/idea/docs/WEB_APP_SPECIFICATION.md`**
* **Purpose:** Product/UI/UX + front-end implementation reference for MVP web client. Replaces Flutter with web, same voice-first research scope.
* **Architecture choices:** `React+TS+Vite strict / app/features/voice,catalogue,cart,auth,help/components/services/hooks/types/styles/test`; `audioCapture/voiceTransport/turnController/audioPlayback/catalogueApi/cartApi` separation; `AudioWorklet + MediaRecorder.isTypeSupported()` fallback, `getUserMedia` secure-context, `bufferedAmount` backpressure, `sessionId/conversationId/turnId/idempotencyKey`; versioned `VoiceTurnStart/VoiceEvent{progress/transcript/clarification/action_result/safety_refusal/audio/error}`; REST for data, WS/SSE for voice; FastAPI serves `dist/` same-origin; IndexedDB/service-worker only for shell+recent catalogue, never authoritative cart/price/auth; money decimal, pre-recorded Chhattisgarhi failure cue.
* **Scope:** 4 destinations Home/Speak, Products, Cart, Help&settings; 7 MVP tasks + safety refusal; WCAG 2.2 AA, Chromium primary, Firefox checked, mobile responsive; 5s speech-to-audio target, 8s timeout; Non-goals: landing pages, payments, maps, ratings, dashboards, chat history.

**`/run/media/rtx/Files/Study/Semester 5/Minor/app/README.md`**
* **Purpose:** Placeholder stub for web client directory.
* **Architecture choices:** Defers to `../idea/docs/WEB_APP_SPECIFICATION.md`; notes Chromium desktop priority, WebSocket STS for streaming ASR/TTS.
* **Scope:** Voice-first browse/price/cart/simulated-checkout + fixed KVK refusal; no implementation yet.

#### C. DEMO2 — institute-helpdesk adaptation (not shopping)

**`/run/media/rtx/Files/Study/Semester 5/Minor/idea/DEMO2_TECHNICAL_AUDIT.md` — 29-30 Sep 2026**
* **Purpose:** Read-only audit of Demo2 supervised helpdesk on 32GB/8GB RTX4060 laptop. Verdict: useful supervised demo, not unattended service. No code changed.
* **Architecture choices:** `Browser WAV/FLAC→Streamlit session/dedup→Whisper-small CPU/int8 or MMS-hne experimental→bridge lock→cheap dialogue/JEV-off/routing LLM→pin KB release+cache+hybrid E5-small+BM25-RRF or exact cutoff SQL→draft LLM→grounding-review LLM→verbalization→VITS CPU or Edge online→render`; `Ollama qwen3.5:9b Q4_K_M, 8k ctx, temp0`; `Chroma+SQLite, 224 chunks/758 blocks/611 JoSAA rows, release 20260927T010544717749Z`; preserved locks, WAL, exact citation validation.
* **Scope:** 18 findings F01-F18 P1/P2/P3; JEV off, 24.34% warm /38.49% repeat saving in 12-answer diagnostic only; 92/93 recall@6, 42/42 cutoffs; under-5s original goal unmet, proposes p50 text ≤20s/p95 ≤45s pilot SLO; roadmap correctness→latency→JEV visibility→retention→reproducibility→managed LAN.

**`/run/media/rtx/Files/Study/Semester 5/Minor/idea/DEMO2_IMPROVEMENT_REPORT.md` — Oct 2026**
* **Purpose:** Implementation report claiming all 18 audit findings addressed, 316 tests passing.
* **Architecture choices:** `jobs.py JobManager FIFO cap3+1 active, 120s turn/60s queue/45s speech timeouts, threading.Event cancel`; decoupled text render `@st.fragment 0.5s` + `demo-speech` pool; `_SYNTHESIZERS OrderedDict LRU size2` CPU VITS; `verbalization.py v2` Indian numbering+negation lexicon+`दशमलव`; `structured.py:record_text related_blocks [Page X]`; `search.py` Hindi variant augmentation; `RagCache.telemetry()/maintain()`; `storage.py Reset vs Delete, 2-checkpoint compact, 24h TTL, online backup`; `health.py release-hash+JEV+env+8 pkgs`.
* **Scope:** Supervised helpdesk pilot on localhost `127.0.0.1`; 37 Demo2+279 Institute=316 passed; Edge 27kB/2.1s, VITS 22.05kHz float32; remaining: no auth, no HTTPS for LAN, JEV needs 3-trial holdout.

**`/run/media/rtx/Files/Study/Semester 5/Minor/idea/presentation/DEMO2_KNOWLEDGE_BASE_RESULTS.md` — 22 Sep 2026**
* **Purpose:** Presentation update for KB rebuild `20260922T095421217856Z`.
* **Architecture choices:** `Official sources→text/table/OCR(Tesseract EN/HI)+figure crops→review/provenance→Chroma E5-small normalized query:/passage: 350/50 + SQLite exact lookup→versioned release→Groq draft+review→Demo2 text/speech`; immutable releases+atomic pointer+rollback; BM25+RRF+short-parent restore.
* **Scope:** 117Q (39 EN/HI/Hinglish), 93 answerable, 92/93=98.92% recall@6, 42/42 cutoffs, 11.4ms median/13.8ms p95 warm retrieval, 611 JoSAA rows 2022-2026, 222 chunks/757 blocks/613 records, 82 mocked tests; 7 live answers blocked by Groq limits; explicitly NOT Chhattisgarhi ASR/agri task success.

#### D. JEV research

**`/run/media/rtx/Files/Study/Semester 5/Minor/idea/docs/OPEN_JEV_FAILURE_ANALYSIS_AND_RECOVERY.md` — 26 Sep 2026**
* **Purpose:** Post-mortem why `kyegomez/open-jev` 4.84M-param random-init pilot failed; survey public alternatives; recovery plan. Recommendation: keep existing router, checkpoint disabled.
* **Architecture choices:** Typed intent/category/language/rewrite classifier as optional fast-path before LLM routing; byte-BPE 1341/8192, 128w/4-head/3-state/2-q/4-readout/8-slot, 512 ctx, AdamW lr3e-4 b16 seed42, 13ep best8, 19.4MB, CPU 4-thr, thresholds prob≥0.80/conf≥0.60/rewrite≤0.05; distinguishes TypeSafe hosted vs kyegomez vs openjev.sh vs `Zefan-Cai/Open-Jev-2B LoRA on Qwen3.5-2B`; suggests SetFit/multilingual embedding, RouteLLM, reranking cookbooks.
* **Scope:** Text routing EN/HI/Hinglish institute domain only, no Chhattisgarhi speech gain; 184 bases→1104 train rows, 20 families calib/test; 233/336=69.35% intent but 2/14=14.29% accepted precision, 0 accepted knowledge, 0% live coverage, 49 vs 49 LLM calls; 7-step recovery: label repair→bigger family-diverse dataset→pretrained baselines→offline Zefan eval→controlled ablations→freeze policy→fresh benchmark.

#### E. Conversations — build logs + contracts

**`/run/media/rtx/Files/Study/Semester 5/Minor/idea/conversations/PROJECT_WORK_PLAN.md` — 7 Sep-29 Nov 2026**
* **Purpose:** Executable 12-week plan (360-432 person-hrs), 3 checkpoints, ownership, demo script, risks, artifacts. Web-only.
* **Architecture choices:** Modular FastAPI monolith + bounded workers, not microservices; stack table React+TanStack Query+reducer+fetch/Abort+native WS v1 JSON+binary+`getUserMedia/MediaRecorder/AudioWorklet/idb`/FastAPI+Pydantic+PostgreSQL+SQLAlchemy+Alembic+Docker/`llama.cpp` quantized intent+JSON-schema+Pydantic guards+VITS/Vitest+Playwright/pytest/`jiwer`; single-laptop demo `Chromium→localhost FastAPI serving dist+REST+WS+workers+PG`; 4 VRAM modes.
* **Scope:** CP1 7Sep-4Oct walking slice search+price; CP2 5Oct-1Nov feature-complete freeze; CP3 2-29Nov evaluated RC, buffer 30Nov; 10-step demo search→checkout+clarify+safety+barge-in+recovery; never-cut S2S/grounding/safety/transactions/recovery/evaluation.

**`/run/media/rtx/Files/Study/Semester 5/Minor/idea/conversations/mcp-tool-surface.md` — design contract, not implemented**
* **Purpose:** Canonical `shopping.v1` 11-function contract making AGENTS §5 enforceable; stable boundary for speech/backend/web.
* **Architecture choices:** One Python domain layer, two adapters in-process for voice + MCP for dev/eval (latency reason); R1 no IDs/price/stock in inputs, R2 names-in→IDs-out via `resolve_product`, R3 grounded data+`response_template_id` no prose, R4 turn-scoped, R5 server-derived `(session,turn,fn,args)` idempotency, R6 paise int+display, R7 model-visible vs protocol errors; resources Categories + alias lexicon versioned; `calculate_required_quantity` hard-refuses if unverified.
* **Scope:** 6 read-only `search_products/resolve_product/get_product_details/check_price/calculate_required_quantity/view_cart` +3 mutating `add_to_cart/remove_from_cart/checkout(simulated)` +2 control `request_clarification/refuse_and_refer`; maps FR5-10/12, RQ1/3/5/safety; open: 11 vs 8 fns, price/details merge, unverified-compute, multi-turn context.

**`/run/media/rtx/Files/Study/Semester 5/Minor/idea/conversations/2026-09-05-demo-verification.md`**
* **Purpose:** Verify Streamlit/Groq/MCP shopping prototype in `minor`.
* **Architecture choices:** `Streamlit1.49.1/MCP1.12.4/Groq0.37.1/EdgeTTS7.2.8`; `prepare_recording` downmix/resample browser AudioContext→mono16kHz PCM16; JSON control preserved.
* **Scope:** 34 pytest passed, smoke 12 tools/proto `2025-06-18`/₹900 cart/882.8ms; live Groq/Edge/mic/Chhattisgarhi not verified, Hindi fallback/synthetic/simulated.

**`/run/media/rtx/Files/Study/Semester 5/Minor/idea/conversations/2026-09-05-microphone-conversation.md`**
* **Purpose:** Button record/stop UX replacing uploader+Transcribe.
* **Architecture choices:** `code/demo/app.py` Talk→mic→auto-transcribe-submit; shared submit for speech/typed; `You said/AI reply`; recording ID claimed pre-tool for rerun dedup, new recorder key per session.
* **Scope:** 36 tests passed; no browser permission/acoustic/Groq/Edge testing; not streaming/VAD endpointing.

**`/run/media/rtx/Files/Study/Semester 5/Minor/idea/conversations/2026-09-06-local-sts-json-demo.md`**
* **Purpose:** Use `.env` key + local STT/TTS + JSON store, fix actions.
* **Architecture choices:** `Groq openai/gpt-oss-120b` after `llama-3.3-70b 404`; `STT get_engine singleton fast=False hne/MMS`, lazy serialized VITS CPU→PCM16 WAV + Hindi number-word adapter (no Latin/₹ in checkpoint); `demo/data/shop.json` file-lock+fsync+atomic; exact commands bypass Groq but use MCP; typed Streamlit form.
* **Scope:** 45 tests, pip check clean, MCP 12 tools, live VITS→MMS→Groq→VITS 5.1s+5.8s+2.7s+1.0s one-run, Chromium search/add×2/₹900/preview/order; routing still needs internet; mic quality manual.

**`/run/media/rtx/Files/Study/Semester 5/Minor/idea/conversations/2026-09-06-stt-gpu-memory-fix.md`**
* **Purpose:** Fix CUDA OOM float32 MMS transfer, keep GPU per request.
* **Architecture choices:** `DEMO_STT_DEVICE=cuda DEMO_STT_DTYPE=float16`, `STT_MMS_DTYPE` reduced-precision before CUDA, float inputs/int masks/eval/no-grad; TTS stays CPU; sidebar device; fail loudly not silent CPU.
* **Scope:** 49 tests, RTX4060 1849/1890MiB short, 2277MiB peak 45s, VITS-input MMS via handler; functional/memory only, not accuracy; killed stale :8502 1960MiB, running :8501.

### 3. Cross-cutting synthesis

* **Thesis consistency:** S2S voice quality/measurability/safety/traceability > shopping UI/marketplace. All normative docs agree.
* **Divergence to track:** Proposal Flutter vs current web-only; shopping MVP vs Demo2 institute helpdesk + JEV text-routing (domain transfer, not Chhattisgarhi evidence); MCP thin-adapter vs in-process voice path for latency.
* **Budgets/limits:** ₹0, student laptop, Opus, 5s target/8s timeout, PostgreSQL ACID, paise ints, fixed KVK refusal, no RAG for catalogue.

</task_result>
</task>
```

---

## Assistant (Plan · Muse Spark 1.3 Free · 108.5s)

_Thinking:_

Structuring a working/ folder plan with file list, outlines, and flow documentation while checking tool and format tradeoffs.

**Tool: question**

**Input:**
```json
{
  "questions": [
    {
      "header": "Doc format",
      "question": "What format do you want inside idea/presentation/working/?",
      "options": [
        {
          "label": "Markdown series",
          "description": "Multiple .md files (overview + per-module + flows + diagrams) – best for viva + Git"
        },
        {
          "label": "Single big README",
          "description": "One exhaustive end-to-end document"
        },
        {
          "label": "Slides + notes",
          "description": "PPTX/slide-style + speaker notes for presentation"
        }
      ]
    },
    {
      "header": "Audience depth",
      "question": "Who is the primary audience for this explanation?",
      "options": [
        {
          "label": "Professors / viva",
          "description": "Emphasize why choices, research questions, evaluation, safety"
        },
        {
          "label": "Developers",
          "description": "Emphasize functions, contracts, code paths, how to run/modify"
        },
        {
          "label": "Both balanced",
          "description": "Cover viva rationale + dev-level function reference"
        }
      ]
    },
    {
      "header": "Diagrams",
      "question": "Should I include request-to-response sequence/mermaid diagrams as code + rendered description?",
      "options": [
        {
          "label": "Yes with diagrams",
          "description": "Mermaid + ASCII flows for every path"
        },
        {
          "label": "Text only",
          "description": "No diagrams, prose explanation only"
        }
      ]
    }
  ]
}
```

**Output:**
```
User has answered your questions: "What format do you want inside idea/presentation/working/?"="Markdown series", "Who is the primary audience for this explanation?"="Both balanced", "Should I include request-to-response sequence/mermaid diagrams as code + rendered description?"="use mermaid as much as possible". You can now continue with the user's answers in mind.
```

---

## Assistant (Plan · Muse Spark 1.3 Free · 18.5s)

_Thinking:_



## Plan: `idea/presentation/working/` end-to-end explanation

**Status:** Plan mode is ACTIVE, so I have only read and mapped the code. No folder/files created yet. To execute, switch to build mode.

**What I verified (read-only):**
* Root `Minor/` = `app/` (1 stub README) + `code/` (STT service, TTS VITS Male/Female, `Speech2Speech.ipynb`, `demo/` Kisan-Saathi shopping, `demo2/` IIIT-NR helpdesk, `Institute-voice-agent/` LangGraph RAG + voice glue) + `idea/` (AGENTS, proposal PDF/txt, `docs/WEB_APP_SPECIFICATION.md`, `DEMO2_*`, `docs/OPEN_JEV*`, `conversations/*`, `presentation/DEMO2_KNOWLEDGE_BASE_RESULTS.md`).
* Audio contracts: `16kHz mono PCM16 no-header` into STT everywhere; TTS out `22050Hz WAV` via Coqui VITS (`length_scale`, not `speed=`).
* 4 distinct request→response paths to document, not one.

### Proposed folder structure

```text
idea/presentation/working/
├── 00-INDEX.md                  # map + how to read + 30-sec project pitch
├── 01-overview-and-thesis.md    # S2S core vs shopping adapter, L1/L2/L3 scope, RQs
├── 02-request-to-response-master.md  # 4 flows + mermaid end-to-end
├── 03-stt-service-deepdive.md  # config.py, schemas.py, vad.py, asr.py, session.py, server.py, telephony_adapter.py, run.py
├── 04-tts-models-deepdive.md    # VITS Female/Male, config.json, Synthesizer, length_scale, tests
├── 05-notebook-bench.md         # Speech2Speech.ipynb 16 cells + outputs/
├── 06-demo-shopping.md          # demo/config, app, assistant(Groq loop), shop(JSON), mcp_server/client, voice/local_speech/speech_text/responses, smoke
├── 07-demo2-helpdesk.md         # settings, app+fragment, jobs(bounded workers), storage(24h), speech+verbalization, agent_bridge, health/ops/online_voice
├── 08-institute-agent.md        # institute-assistant graph/nodes/llm/retrieval/cache/kb_pipeline + voice-orchestrator/orchestrator.py
├── 09-web-client-spec.md        # app/README + WEB_APP_SPECIFICATION (AudioWorklet, WS protocol, state machine)
├── 10-architecture-decisions.md # why cascade, MMS-hne vs Whisper, Silero, VITS, FastAPI WS+ThreadPool, Streamlit, MCP stdio, JSON vs Postgres, deterministic verbalization, local-first zero-budget
└── diagrams/
    ├── stt-sequence.mmd
    ├── demo-turn.mmd
    ├── demo2-turn.mmd
    └── orchestrator-loop.mmd
```

Each file: purpose → key functions/classes → inputs/outputs → connects-to → request→response snippet → why this choice.

### Key flows to trace with mermaid

1. **STT microservice:** `mic/WAV/Twilio mu-law → telephony_adapter → server.py WS `/ws/stt/{id}` (auth/capacity/idle) → session.py SILENCE/SPEAKING + VAD 512-frame + windowed PARTIAL/full FINAL → asr.py Whisper/MMS → STTEvent JSON → LLM`.
2. **`demo/` shopping turn:** `Streamlit mic Stop (sha claim) → voice.prepare_recording → local_speech.recognize(MMS hne) → assistant.run_turn(Groq validated single tool) → mcp_client stdio → mcp_server → shop.py (paise, FileLock atomic, idempotent) → responses.render → voice.synthesize(VITS) → autoplay`.
3. **`demo2/` helpdesk turn:** `mic/upload/typed → jobs.submit (fingerprint, queue 3) → speech.transcribe (Whisper hi/en/hinglish, MMS hne-exp) → agent_bridge.ask (classify→retrieve E5+BM25 RRF pinned release→generate+review) → storage.complete → verbalization.normalize → VITS hi / Edge en (opt-in) → fragment text-first`.
4. **`voice-orchestrator` + notebook:** `mic 40ms binary → STT WS FINAL → graph.invoke → print (TTS plug point)`; notebook `record → stream WS → make_response → length_scale synth`.

### Execution steps (for build mode)
1. Create `idea/presentation/working/` + `diagrams/`.
2. Write `00`→`10` in order, deriving `oldString` only from reads already done, verifying function names/paths above.
3. Add 4 `.mmd` mermaid files + embed in `02`.
4. Final `ls` + markdown link check, no code changes.

Confirm to proceed in build mode, or adjust file list first?


---

## User

continue

---

## Assistant (Plan · Muse Spark 1.3 Free · 44.8s)

_Thinking:_

Drafting a detailed non-executing plan and expanding the outline without running edits or write tools.

_Thinking:_

Expanding the non-executing plan with per-file outlines and mermaid diagrams while keeping to analysis only.

## Detailed Plan — `idea/presentation/working/` (Markdown series, Both audiences, Mermaid-heavy)

> No files created — plan mode is active. This is the build-ready spec to execute once you switch to build mode.

### 0. Target

Create folder:

`/run/media/rtx/Files/Study/Semester 5/Minor/idea/presentation/working/`

Goal: end-to-end, function-by-function explanation: what each file/folder does, how everything connects, request → response flow, architecture choice + why.

Existing `idea/presentation/` currently only has `DEMO2_KNOWLEDGE_BASE_RESULTS.md`. New `working/` will not touch it.

### 1. Full inventory already mapped (read-only)

**`code/STT/stt-service/`:**
`src/config.py` (Settings), `src/schemas.py` (STTEvent/EventType), `src/vad.py` (SpeechDetector, 512-frame, residual), `src/asr.py` (ASREngine, FasterWhisperEngine, ChhattisgarhiMMSEngine, clean_mms_devanagari, get_engine), `src/session.py` (SttSession SILENCE/SPEAKING, windowed PARTIAL, FINAL, _EXECUTOR), `src/server.py` (lifespan warm, /health, /ws/stt/{id}, auth/capacity/idle/auto-flush), `src/telephony_adapter.py` (mulaw_8k_to_pcm16_16k), `run.py`, `requirements.txt`, `Dockerfile`, `.env.example`, `README.md`, `tests/test_client_wav.py`, `tests/test_client_mic.py`, `test_mms_speed.py`

**`code/TTS/chattisgarhi-tts-models/`:**
`Female/best_model.pth + config.json (num_chars 114)`, `Male/best_model.pth + config.json (num_chars 106)`, `indictts.ipynb (4 cells)`, `test_speed.py`, `test_speed2.py`, `test_speed_override.py`, `output.wav/outputslow.wav`, `README.md` + `code/TTS/indic_tts_out.wav`

**`code/Speech2Speech.ipynb` (16 cells):** `record_from_microphone`, `load_wav_as_pcm16`, `stt_health/subprocess`, `Synthesizer load`, `transcribe_pcm16 (40ms)`, `make_response`, `synthesize_response`, `stop_stt_service` + `speech2speech_outputs/`

**`code/demo/` Kisan Saathi shopping:** `AGENTS.md`, `README.md`, `config.py (configure_stt)`, `app.py (initialize/refresh/remember/make_audio/manual/submit_request)`, `assistant.py (SYSTEM, run_async/run_turn, is_confirmation, fuzzy_quick_action)`, `shop.py (Shop, search/resolve/details/check_price/view_cart/add/remove/checkout/confirm/calculate, paise, FileLock atomic, idempotency sha)`, `local_speech.py (recognize/speak)`, `mcp_client.py (connect/invoke/direct/inspect_server)`, `mcp_server.py (12 tools FastMCP stdio)`, `responses.py (render)`, `voice.py (prepare_recording/validate/transcribe/synthesize)`, `speech_text.py (prepare_speech_text, number_words)`, `smoke_demo.py`, `requirements.txt`, `.env.example`, `data/catalogue.json/shop.json`, `tests/`, `skills/`

**`code/demo2/` IIIT-NR helpdesk:** `README.md`, `requirements.txt`, `settings.py (configure_agent/configure_stt)`, `app.py (conversation fragment, submit)`, `workflow.py (new_session/run_turn/consume_recording/speak_turn legacy)`, `jobs.py (JobManager, submit/snapshot/cancel/delete/backup/_loop/_run/_speak/retry_audio)`, `storage.py (Store register/request/complete/delete/compact/maintain/backup/restore_into)`, `speech.py (decode_audio/transcribe/prepare_speech/synthesize/_edge_audio/make_audio/online_audio)`, `verbalization.py (normalize, cardinal, LEXICON, NEGATION)`, `agent_bridge.py (get_graph/ask/render_hindi/render_speech)`, `health.py`, `ops.py`, `online_voice.py`, `smoke.py`, `run.sh`, `.env.example`, `KNOWLEDGE_BASE.md/OPERATIONS.md/VALIDATION.md`, `tests/test_demo.py/test_operations.py`, `evaluation/`, `data/`

**`code/Institute-voice-agent/`:**
`voice-orchestrator/orchestrator.py (mic 40ms → STT WS → graph.invoke → print, TTS plug point)`, `requirements.txt`, `.env.example`
`institute-assistant/`: `run_cli.py`, `ask_kb.py`, `build_index.py`, `kb_pipeline.py`, `setup_local.py`, `assistant/config.py/state.py/graph.py (classify→retrieve→generate→finalize)/nodes.py/llm.py/retrieval.py (E5+BM25 RRF)/dialogue.py/cache.py (RagCache)/operations.py/history.py/evidence.py/ingest.py/...`, `assistant/kb/*`, `assistant/jev/*`, `knowledge_base/*/`, `kb_state/releases/active.json`, `tests/ (279)`, `docs/LOCAL_INFERENCE.md etc.`

**`app/README.md` + `idea/docs/WEB_APP_SPECIFICATION.md`** (React+TS+Vite, AudioWorklet/MediaRecorder, turnController, VoiceTurnStart/VoiceEvent)

**`idea/` governance:** `AGENTS.md`, `proposal.txt/.pdf`, `DEMO2_TECHNICAL_AUDIT.md`, `DEMO2_IMPROVEMENT_REPORT.md`, `docs/OPEN_JEV*`, `conversations/PROJECT_WORK_PLAN.md/mcp-tool-surface.md/2026-09-0*`

### 2. Files to create in build mode

```text
working/
├── 00-INDEX.md
├── 01-overview-and-thesis.md
├── 02-request-to-response-master.md
├── 03-stt-service-deepdive.md
├── 04-tts-models-deepdive.md
├── 05-notebook-bench.md
├── 06-demo-shopping.md
├── 07-demo2-helpdesk.md
├── 08-institute-agent.md
├── 09-web-client-spec.md
├── 10-architecture-decisions.md
└── diagrams/
    ├── stt-sequence.mmd
    ├── demo-turn.mmd
    ├── demo2-turn.mmd
    └── orchestrator-loop.mmd
```

**Per-file spec:**

* `00-INDEX.md` — 30-sec pitch, repo map, L1/L2/L3 levels, how to read 01→10, run commands (`cd code/demo2; bash run.sh`, `cd code/STT/stt-service; python run.py`, `streamlit run app.py`), env `minor` note.
* `01-overview-and-thesis.md` — Both audiences: research thesis, S2S core vs shopping adapter, priority order, novelty / non-novelty, users/operating conditions.
* `02-request-to-response-master.md` — 4 mermaid sequence diagrams embedded + ASCII fallback + audio contracts table (16k PCM16 in / 22050 out, 40ms chunks, 512-frame VAD, WAV/FLAC limits). This is the “from request to response” hub.
* `03-stt-service-deepdive.md` — file-by-file: Settings fields table, STTEvent table, SpeechDetector residual logic, FasterWhisper (beam1 fast vs beam5 final, no_speech filter) vs MMS-1B hne (adapter, dtype, clean_mms_devanagari), SttSession state machine + PARTIAL_WINDOW trick + ThreadPool, server auth/semaphore/idle/flush, telephony mulaw→16k, run/tests/Docker.
* `04-tts-models-deepdive.md` — VITS arch from config.json (sample_rate 22050, multilingual_cleaners, add_blank, use_sdp, num_chars diff), Synthesizer usage, why `length_scale` not `speed=`, Male vs Female, LFS note, speed tests conclusion.
* `05-notebook-bench.md` — cell-by-cell walkthrough of Speech2Speech.ipynb functions above, how it proves STT→response→TTS without LLM.
* `06-demo-shopping.md` — Turn trace: mic Stop sha-claim → prepare_recording resample → recognize(get_engine fast=False) → Groq loop (safety/quick/MAX_ROUNDS4, single-call validate, no parallel) → MCP stdio isolation → Shop paise/FileLock/idempotency → render templates → speak (Hindi numbers) → autoplay. Cover checkout token + confirm phrases + negation guard, manual Shop path via direct().
* `07-demo2-helpdesk.md` — Turn trace: submit → JobManager queue3/busy → transcribe (Whisper-small hi/en/hinglish vs MMS hne-exp, RMS silence) → agent_bridge.ask (LangGraph nodes) → Store.complete (text-only) → speech_pool make_audio (verbalization.normalize deterministic, VITS 1/speed vs Edge opt-in subprocess) → fragment text-first. Cover retry_audio (no replay), cancel suppression, 24h retention/tombstone/backup, health/ops.
* `08-institute-agent.md` — graph.py nodes (classify/retrieve/generate/finalize/escalate), llm.py providers (Ollama qwen3.5:9b default vs Groq), retrieval.py (pinned release, E5 350/50 + BM25 RRF + JoSAA exact + RagCache), state.py AssistantState, kb_pipeline releases, orchestrator.py mic loop + TTS plug line.
* `09-web-client-spec.md` — WEB_APP_SPEC: destinations, AudioWorklet vs MediaRecorder fallback, getUserMedia secure-context, bufferedAmount, session/turn/idempotency, VoiceEvent types, REST vs WS, IndexedDB non-authoritative, money decimal, failure cue, WCAG/Chromium.
* `10-architecture-decisions.md` — Table: Choice | Alternative | Why (cascade vs E2E multimodal, local-first zero-budget, MMS-hne vs Whisper, Silero ONNX singleton, Coqui VITS, FastAPI WS + run_in_executor, Streamlit demo velocity, MCP stdio process isolation, JSON FileLock vs Postgres, deterministic verbalization vs LLM rewrite, bounded 1+1 workers + timeouts, fixed KVK refusal, turn IDs/idempotency/cancellation).
* `diagrams/*.mmd` — mermaid `sequenceDiagram` for each flow in §2, referenced from `02` + relevant deepdive.

### 3. Build-mode execution checklist
1. `ls idea/presentation/` to confirm parent.
2. `mkdir working + diagrams` (single command).
3. Write `00` → `10` + 4 `.mmd` (12 writes).
4. Verify links + `ls -R working/`.

Say `approve plan` + switch out of plan mode to execute.

---

## User

approve plan and execute it

---

## Assistant (Build · Nemotron 3 Ultra Free · 22.1s)

_Thinking:_

The user approved the plan and wants me to execute it. I need to create the working folder and all the markdown files with detailed explanations. Let me start by creating the directory structure and then writing all the files.

I'll create the files one by one, starting with the folder structure and then the content

**Tool: bash**

**Input:**
```json
{
  "command": "mkdir -p \"/run/media/rtx/Files/Study/Semester 5/Minor/idea/presentation/working/diagrams\""
}
```

**Output:**
```
(no output)
```

---

## Assistant (Build · Nemotron 3 Ultra Free · 60.1s)

_Thinking:_

Good, the directory structure is created. Now I'll write all the markdown files. Let me start with the index and then go through each file in order.

**Tool: write**

**Input:**
```json
{
  "filePath": "/run/media/rtx/Files/Study/Semester 5/Minor/idea/presentation/working/00-INDEX.md",
  "content": "# Chhattisgarhi Voice Shopping Assistant — End-to-End Documentation\n\n**Project:** Minor Project, Semester 5, IIIT  \n**Students:** Punyansh Thakur, Harsh Dadsena, Aakash Sen  \n**Supervisor:** Prof. Santosh Kumar  \n**Environment:** Conda `minor` (Python 3.11.15), React+TypeScript+Vite, FastAPI, PostgreSQL\n\n---\n\n## 30-Second Pitch\n\nWe built a **fully local, streaming Speech-to-Speech (S2S) pipeline** for Chhattisgarhi (ISO `hne`) that:\n- Accepts spoken Chhattisgarhi → transcribes with **Meta MMS-1B + hne adapter** (Silero VAD for boundaries)\n- Translates to English via **NLLB-200 distilled** → interprets intent/entities with constrained LLM → executes grounded tool calls on PostgreSQL\n- Constructs response → translates back to Chhattisgarhi → synthesizes with **Coqui VITS (Male/Female)** → streams audio back\n- All with **barge-in/interruption**, **idempotent transactions**, **safety boundary** (fixed KVK refusal for diagnosis/dosage), and **per-stage observability**\n\nThe agricultural shopping demo (50–100 seed/fertilizer items) is the **evaluation environment**, not the novelty. The reusable S2S core is.\n\n---\n\n## Repository Map\n\n```\nMinor/\n├── app/                          # Web client (React+TS) — spec only, not implemented yet\n│   └── README.md\n├── code/                         # All runnable code\n│   ├── STT/stt-service/          # FastAPI WebSocket microservice (MMS/Whisper + Silero VAD)\n│   ├── TTS/chattisgarhi-tts-models/  # Pre-trained VITS Male/Female checkpoints (Coqui)\n│   ├── Speech2Speech.ipynb       # End-to-end notebook bench (mic/WAV → STT WS → TTS)\n│   ├── demo/                     # Kisan Saathi: Streamlit + Groq + MCP + local STT/TTS, JSON store\n│   ├── demo2/                    # IIIT-NR helpdesk: Streamlit + Ollama/Groq + Whisper/MMS + VITS/Edge\n│   └── Institute-voice-agent/    # LangGraph RAG text helpdesk + thin voice orchestrator\n├── idea/                         # Governance, specs, audits, work plan\n│   ├── AGENTS.md                 # Authority: thesis, priorities, scope L1/L2/L3, conventions\n│   ├── proposal.txt/.pdf         # Formal B.Tech proposal (superseded by AGENTS.md on Flutter→web)\n│   ├── docs/\n│   │   ├── WEB_APP_SPECIFICATION.md    # Web client spec (replaces Flutter)\n│   │   └── OPEN_JEV_FAILURE_ANALYSIS_AND_RECOVERY.md\n│   ├── DEMO2_TECHNICAL_AUDIT.md\n│   ├── DEMO2_IMPROVEMENT_REPORT.md\n│   ├── presentation/\n│   │   ├── DEMO2_KNOWLEDGE_BASE_RESULTS.md\n│   │   └── working/                    # ← YOU ARE HERE\n│   └── conversations/                # Build logs: work plan, MCP contract, mic UX, local STS demo\n```\n\n---\n\n## How to Read This Documentation\n\n| File | Audience | Start Here If... |\n|------|----------|------------------|\n| `01-overview-and-thesis.md` | Both | You need the research framing, scope levels, why decisions |\n| `02-request-to-response-master.md` | Both | You want **all 4 request→response flows** with mermaid diagrams |\n| `03-stt-service-deepdive.md` | Dev | You need function-level detail on STT microservice |\n| `04-tts-models-deepdive.md` | Dev | You need VITS model structure, `length_scale`, inference code |\n| `05-notebook-bench.md` | Dev | You want to run/understand the end-to-end notebook |\n| `06-demo-shopping.md` | Dev | You work on the shopping demo (Groq + MCP + JSON) |\n| `07-demo2-helpdesk.md` | Dev | You work on the helpdesk (Ollama + bounded workers + 24h retention) |\n| `08-institute-agent.md` | Dev | You need LangGraph RAG + voice orchestrator |\n| `09-web-client-spec.md` | Both | You implement the React web client |\n| `10-architecture-decisions.md` | Viva | You need a table of every choice with alternatives + rationale |\n| `diagrams/*.mmd` | Both | You want standalone mermaid files for slides |\n\n---\n\n## Quick Start Commands\n\n```bash\n# Activate env (REQUIRED for all Python work)\nconda activate minor\n\n# 1. STT microservice (port 8000)\ncd code/STT/stt-service\ncp .env.example .env          # edit STT_LANGUAGE=hne for Chhattisgarhi\npip install -r requirements.txt\npython run.py                 # serves ws://localhost:8000/ws/stt/{id} + GET /health\n\n# 2. Shopping demo (port 8501)\ncd code/demo\npip install -r requirements.txt\ncp .env.example .env          # needs GROQ_API_KEY\nstreamlit run app.py\n\n# 3. Helpdesk demo (port 8501)\ncd code/demo2\nbash run.sh                   # conda run -n minor streamlit run app.py\n\n# 4. Voice orchestrator (needs STT running)\ncd code/Institute-voice-agent/voice-orchestrator\ncp .env.example .env          # set STT_WS_BASE_URL\npython orchestrator.py        # mic → STT WS → graph.invoke → prints reply\n\n# 5. Notebook bench\ncd code\njupyter notebook Speech2Speech.ipynb  # select 'minor' kernel\n```\n\n---\n\n## Scope Levels (from AGENTS.md)\n\n| Level | Status | What It Is |\n|-------|--------|------------|\n| **L1** | Demonstrated | Streaming 16k PCM WS, Silero VAD, MMS-hne ASR, pluggable ASREngine, Devanagari cleanup, VITS Male/Female, `length_scale`, Whisper fallback, telephony adapter |\n| **L2** | **Current MVP** | Evaluated Chhattisgarhi S2S + small agri catalogue: search, details, price, `CALCULATE_REQUIRED_QUANTITY`, add/remove/view cart, simulated checkout, spoken reply, KVK refusal, instrumentation, minimal responsive UI |\n| **L3** | Future | UPI/payments, multi-vendor sync, seller dashboards, logistics/OTP, unsupervised crop diagnosis, pesticide dosage, farmer profiling, broad multilingual |\n\n---\n\n## Audio Contracts (Hard Protocol)\n\n| Direction | Format | Where Enforced |\n|-----------|--------|----------------|\n| **Client → STT** | 16 kHz, mono, 16-bit PCM, **no WAV header** | `schemas.py`, `session.py`, `telephony_adapter.py`, `voice.py`, `demo/local_speech.py` |\n| **STT → LLM** | JSON `STTEvent` (text frames) | `schemas.py::EventType` = `SESSION_STARTED`, `SPEECH_STARTED`, `PARTIAL`, `FINAL`, `ERROR`, `SESSION_ENDED`, `SESSION_REJECTED` |\n| **TTS → Client** | 22.05 kHz WAV (float32) | `Synthesizer.save_wav`, `speech.py::synthesize`, `local_speech.speak` |\n| **Twilio → STT** | 8 kHz mu-law (G.711) base64 JSON | `telephony_adapter.py::mulaw_8k_to_pcm16_16k` |\n\n> **Never** change sample rate/encoding without updating all clients + adapter simultaneously.\n\n---\n\n## Key Invariants (Do Not Break)\n\n1. **Singletons**: `_ENGINE_SINGLETON` (asr), `_MODEL_SINGLETON` (vad), `_EXECUTOR` (session) — one per process\n2. **Async safety**: All blocking ASR/TTS in `loop.run_in_executor(_EXECUTOR, ...)` — never on event loop\n3. **Config only in `config.py`** — no `os.getenv` elsewhere\n4. **STTEvent additive only** — downstream LLM services depend on exact shape\n5. **Money = paise (int)** — no binary floating point for prices\n6. **Idempotency keys**: `(session, turn, fn, args)` SHA-256 on every mutating tool\n6. **Safety**: Fixed KVK refusal template — LLM never improvises dosage/advice\n7. **Environment**: All Python in `conda minor` — no venv, no system Python\n\n---\n\n## Next: `01-overview-and-thesis.md` → research framing"
}
```

**Output:**
```
Wrote file successfully.
```

---

## Assistant (Build · Nemotron 3 Ultra Free · 350.4s)

_Thinking:_

Good, now let me write the remaining files. I'll continue with 01-overview-and-thesis.md, then the others

_Thinking:_

Good, now let me write the next file - overview and thesis.

_Thinking:_

Now let me create the rest of the files in order. I'll continue with 01-overview-and-thesis.md

**Tool: write**

**Input:**
```json
{
  "filePath": "/run/media/rtx/Files/Study/Semester 5/Minor/idea/presentation/working/01-overview-and-thesis.md",
  "content": "# Overview & Research Thesis\n\n## Core Thesis\n\n> **Can a predominantly open-source, locally runnable, cascaded Speech-to-Speech (S2S) system support accurate, useful, and safe voice interaction in Chhattisgarhi under realistic student-compute and connectivity constraints?**\n\nThe agricultural shopping demo is the **reference implementation and evaluation environment** — it supplies real state, structured tools, safety constraints, and end-to-end user tasks. It is **not** the main novelty.\n\nThe **novelty** is the careful integration and empirical evaluation of a reusable, streaming, interruption-aware voice-to-voice layer for a low-resource language, including:\n\n1. Spontaneous Chhattisgarhi speech input (not Hindi/English-first)\n2. Observable cascade with measurable per-stage error sources\n3. Agricultural/shopping vocabulary adaptation + code-switch handling\n4. Informal speech → schema-valid grounded actions\n5. Spoken Chhattisgarhi response generation\n6. Interruption/barge-in + useful feedback during multi-second inference\n7. Hard boundary: transactional help only, no agronomic advice\n8. Reusable architecture: shopping domain = adapter around S2S core\n\n---\n\n## What Is Novel vs. Not Novel\n\n| Novel (Our Contribution) | Not Novel (Prior Work) |\n|---------------------------|------------------------|\n| Chhattisgarhi-first voice pipeline integration | ASR (MMS, Whisper), MT (NLLB), TTS (VITS), LLM tool-calling |\n| Observable cascaded error measurement | Agricultural e-commerce concepts |\n| Domain vocabulary adaptation for hne | WebSocket audio streaming |\n| Spoken response in Chhattisgarhi | FastAPI, PostgreSQL, React |\n| Barge-in + recovery in low-resource S2S | Silero VAD, Coqui TTS |\n| Safety boundary enforcement via templates | JSON file locking, idempotency |\n\n**Description:** Research prototype — not production marketplace, not medical/agri advisor, not statistically validated deployment.\n\n---\n\n## Priority Order (When Choices Compete)\n\n1. **End-to-end Chhattisgarhi voice-to-voice quality & natural interaction**\n2. **Measurability, reproducibility, honest stage-by-stage evaluation**\n3. **Safety, deterministic execution, privacy, traceability**\n4. **Clean separation: reusable voice core vs. domain-specific behavior**\n5. **Correct shopping workflow & transactional state**\n6. **Web UI polish / e-commerce feature expansion**\n\n> Do NOT optimize catalogue UI, payments, marketplace, or vendor ops at the expense of ASR, MT, orchestration, TTS, latency, barge-in, recovery, or evaluation.\n\n---\n\n## Users & Operating Conditions\n\n| User | Constraint |\n|------|------------|\n| Smallholder farmer, mainly Chhattisgarhi | Voice for entire task, limited digital literacy |\n| Code-switcher (Chhattisgarhi ↔ Hindi) | Avoids typing/menu navigation |\n| Rural, intermittent 3G/4G | Needs visible/audible progress, clear recovery |\n\n**Assumptions:**\n- Ordinary laptop/desktop browsers (Chromium primary, Firefox checked)\n- Variable microphones, background noise\n- Informal/incomplete utterances, hesitations, accents\n- Unstable networks\n- **NOT assumed:** studio speech, constant broadband, high digital literacy, English literacy, identical codec behavior\n\n---\n\n## Scope Levels (Formal)\n\n### Level 1: Preliminary Work (Already Demonstrated)\n\n- FastAPI + WebSockets streaming 16 kHz PCM\n- Silero VAD for speech boundaries + barge-in events\n- Meta MMS `facebook/mms-1b-all` + `hne` adapter for ASR\n- Pluggable `ASREngine` + shared inference workers\n- Devanagari CTC cleanup for detached matras\n- Coqui-TTS VITS with custom Male/Female Chhattisgarhi checkpoints\n- Model-level speech pacing via `length_scale`\n- English-only `faster-whisper` fallback\n- Telephony adapter for 8 kHz mu-law (extensibility evidence)\n\n> **L1 does NOT establish:** calibrated WER, production latency, agri vocab performance, translation quality, safe tool calling, web integration, user usability.\n\n### Level 2: Current Minor Project MVP (Deliverable)\n\n| Capability | Status |\n|------------|--------|\n| Product search & browsing | ✅ |\n| Product details & price queries | ✅ |\n| Deterministic quantity calculation (verified metadata) | ✅ |\n| Add/remove cart | ✅ |\n| View cart + total | ✅ |\n| Simulated checkout (no payment) | ✅ |\n| Spoken Chhattisgarhi responses | ✅ |\n| Safety refusal + KVK referral (diagnosis/dosage) | ✅ |\n| Voice, intent, outcome, latency instrumentation | ✅ |\n| Minimal responsive web UI (confirm text, products, cart) | 📋 Spec only (`WEB_APP_SPECIFICATION.md`) |\n\n### Level 3: Future Work (NOT Current Deliverable)\n\n- Real UPI / payment gateway\n- Live multi-vendor inventory sync\n- Seller dashboards\n- Delivery routing, tracking, OTP\n- Unsupervised crop diagnosis / pesticide recommendation\n- Production-scale farmer profiling/analytics\n- Broad multilingual beyond evaluated Chhattisgarhi path\n\n> Keep architecture open to L3, but don't let speculative generality block strong Chhattisgarhi S2S MVP.\n\n---\n\n## Research Questions (Implementation Must Help Answer)\n\n| # | Question |\n|---|----------|\n| RQ1 | How accurately can informal Chhattisgarhi speech become correct shopping intents/entities (product, crop, quantity, unit, area)? |\n| RQ2 | How much error is contributed by ASR, forward MT, intent/entity extraction, domain execution, response MT, TTS respectively? |\n| RQ3 | Can constrained tool calling produce valid grounded operations without inventing products, state, prices, quantities, advice? |\n| RQ4 | What end-to-end and per-stage latency does a zero-budget local pipeline have vs. API-assisted option (if available)? |\n| RQ5 | Does voice-first interaction improve task completion/usability for Chhattisgarhi speakers with limited digital literacy vs. text search? |\n| RQ6 | How intelligible, natural, interruption-tolerant, recoverable is the **complete spoken interaction** (not just intermediate text)? |\n\n> RQ6 makes S2S emphasis explicit: pipeline fails if ASR transcript looks correct but user cannot complete spoken task or understand spoken result.\n\n---\n\n## Proposed Technology Baseline (Default Unless Measurements Justify Change)\n\n| Layer | Default | Notes |\n|-------|---------|-------|\n| Web client | React + TypeScript + Vite | Browser mic, voice state, WS transport, playback, confirmations |\n| API/Orchestrator | Python + FastAPI | REST for resources; WS/SSE for streaming |\n| VAD | Silero VAD (ONNX) | Configurable thresholds, evaluate on representative audio |\n| Chhattisgarhi ASR | Meta MMS 1B + `hne` adapter | Existing baseline; no WER claim until measured |\n| ASR Comparison | SraVaani-1.0 | Benchmark candidate, not MVP dependency |\n| Translation | NLLB-200 distilled 600M, `hne_Deva` | Measure translation drift as own failure source |\n| Intent/Entities | Local instruction-tuned, tool-capable | Strict schemas; no paid provider assumed |\n| TTS | Coqui-TTS VITS, existing checkpoints | Preserve Male/Female + pacing controls |\n| Database | PostgreSQL | Transactions + referential integrity required |\n| Optional APIs | Bhashini/hosted LLM only if confirmed | Comparison path, never hidden dependency |\n\n> Zero-allocated budget. Prefer open-source + locally runnable. Never add paid/access-controlled service as required path without explicit approval, documented fallback, updated scope/cost docs.\n\n---\n\n## Next: `02-request-to-response-master.md` → all 4 flows with mermaid"
}
```

**Output:**
```
Wrote file successfully.
```

---

## Assistant (Build · Nemotron 3 Ultra Free · 577.2s)

_Thinking:_

Now let me create the master request-to-response file with all 4 flows and mermaid diagrams.

_Thinking:_

Good. Now let me create the master request-to-response file with mermaid diagrams for all 4 flows.

_Thinking:_

Now let me create the request-to-response master file with mermaid diagrams.

_Thinking:_

Now let me create the master request-to-response file with all 4 flows and mermaid diagrams.

_Thinking:_

Now I'll write the master request-to-response file with all 4 flows and mermaid diagrams.

---

## User

continue

---

## Assistant (Build · Muse Spark 1.3 Free)

---

