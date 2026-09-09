# Local STT Service

A production-shaped, fully local speech-to-text microservice for a voice-assistant agent.
No external STT API calls — audio comes in over a WebSocket, transcripts go out over the
same WebSocket, everything runs on your own hardware.

Built for: streaming (not batch), multi-user concurrency, and a clean event contract so
your teammate's LangChain/LLM service can plug straight in.

**v2 changes** (merged in after comparing against another draft):
- Partial transcripts now use a sliding window (`STT_PARTIAL_WINDOW_MS`) instead of re-transcribing
  the entire growing utterance every time — long utterances no longer get slower with every partial.
- `speech_started` events now carry `interrupt_previous_response: true` — the explicit barge-in
  signal your TTS/LLM teammate needs to stop talking when the caller starts speaking again.
- Added auth (`STT_API_KEY`), a concurrency cap with graceful rejection (`STT_MAX_CONCURRENT_SESSIONS`),
  and idle-session cleanup (`STT_IDLE_TIMEOUT_S`) — see "Deploying for a real clinic" below.
- Added domain vocabulary biasing (`STT_INITIAL_PROMPT`) and a telephony adapter
  (`src/telephony_adapter.py`) for real phone calls via Twilio, not just browser mic input.

## Architecture

```
 caller audio (16kHz PCM16)
        │  binary WebSocket frames
        ▼
 ┌─────────────────────────────────────────────┐
 │  src/server.py   (FastAPI WebSocket)         │
 │       │                                      │
 │       ▼                                      │
 │  src/session.py  (per-caller state machine)  │
 │       │              │                       │
 │       ▼              ▼                       │
 │  src/vad.py      src/asr.py                  │
 │  (Silero VAD)    (faster-whisper, in a       │
 │                   shared thread pool)         │
 └─────────────────────────────────────────────┘
        │  JSON text WebSocket frames (STTEvent)
        ▼
   your teammate's LangChain LLM service
```

- **VAD (`src/vad.py`)** — Silero VAD decides when the caller starts/stops talking.
  Runs on every audio frame; it's what triggers partial transcripts and end-of-utterance finals.
- **ASR (`src/asr.py`)** — `faster-whisper` (CTranslate2 Whisper) does the actual transcription.
  Abstracted behind an `ASREngine` interface — swapping in NVIDIA Parakeet-TDT later for
  production is a new class + one line change, not a rewrite.
- **Session (`src/session.py`)** — the state machine tying VAD + ASR together per connection:
  buffers audio while the caller speaks, emits `partial` events periodically, emits one `final`
  event when it detects the caller stopped talking (or hits a safety max-length cap).
- **Server (`src/server.py`)** — FastAPI WebSocket endpoint. Model is loaded **once** at
  startup and shared across every concurrent connection.

## Setup

```bash
cd stt-service
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # edit if you want to change model size/device/etc.
```

First run will download the Whisper model weights (small.en ≈ 500MB) — one-time, cached
afterward in `~/.cache/huggingface`.

## Run the server

```bash
python run.py
```

You should see:
```
Loading ASR model 'small.en' on cpu (int8)...
Model loaded. Server ready.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Health check: `curl http://localhost:8000/health`

## Test it

**Option A — with your microphone (most realistic test):**
```bash
python tests/test_client_mic.py
```
Speak into your mic; you'll see `PARTIAL` lines update live and a `FINAL` line print once
you pause.

**Option B — with a WAV file (no mic needed, good for CI/repeatable tests):**
```bash
python tests/test_client_wav.py path/to/audio.wav
```
File must be mono/16kHz/16-bit PCM. Convert with:
```bash
ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 audio.wav
```

## Integration contract (read this with your LangChain teammate)

Connect: `ws://<host>:8000/ws/stt/{session_id}`

**You send** (binary frames): raw 16-bit PCM, mono, 16kHz — no WAV header, just samples.
Any chunk size works; 20–100ms per frame is typical for a live mic/telephony stream.

**You receive** (JSON text frames), each shaped like `src/schemas.py::STTEvent`:

```json
{"type": "session_started", "session_id": "abc123"}
{"type": "speech_started",  "session_id": "abc123", "interrupt_previous_response": true}
{"type": "partial", "session_id": "abc123", "text": "book an appointment for", "confidence": 0.87}
{"type": "final",   "session_id": "abc123", "text": "book an appointment for tomorrow at 5pm",
 "start_ms": 1200, "end_ms": 3400, "confidence": 0.93, "utterance_id": 1}
{"type": "session_rejected", "session_id": "abc123", "error_message": "Server at capacity. Please try again shortly."}
```

**`speech_started` with `interrupt_previous_response: true` is your barge-in signal.** If your
TTS teammate's audio is still playing when the patient starts talking again, this event is the
cue to stop playback immediately — otherwise the assistant talks over the patient, which is the
single fastest way a voice agent feels broken to a real caller.

**`session_rejected`** means the server was at its concurrency limit or auth failed — the
connection will close right after. Your orchestration layer (whatever answers the phone call)
should catch this and either queue the caller or fail over to another instance — see
"Deploying for a real clinic" below.

**Rule of thumb for the LLM side:** only act on `"type": "final"` events — feed `text` from
those into your LangChain chain/agent as the user's turn. Use `partial` events only if you
want a live "user is typing/talking..." style UI; never trigger LLM generation on a partial,
it's unstable and will change.

To end a session cleanly (flushes any trailing buffered speech as a final before closing):
send a text frame `{"action": "stop"}`, or simply close the socket — the server auto-flushes
on disconnect either way.

A minimal async consumer on the LangChain side looks like:

```python
import asyncio, json, websockets

async def consume():
    async with websockets.connect("ws://localhost:8000/ws/stt/call-42") as ws:
        async for msg in ws:
            event = json.loads(msg)
            if event["type"] == "final":
                user_text = event["text"]
                # response = my_langchain_chain.invoke({"input": user_text})
                # -> hand off to TTS teammate here
```

## Tuning

All knobs are in `.env` / `src/config.py`. The ones you'll actually touch:

| Setting | Effect |
|---|---|
| `STT_MODEL_SIZE` | `tiny.en`/`base.en`/`small.en`/`medium.en`/`large-v3` — bigger = more accurate, slower |
| `STT_DEVICE` + `STT_COMPUTE_TYPE` | `cpu`/`int8` for laptops; `cuda`/`float16` if you have an NVIDIA GPU |
| `STT_EOS_SILENCE_MS` | How long a pause before a turn is considered "finished" (lower = snappier, more risk of cutting people off mid-thought) |
| `STT_PARTIAL_INTERVAL_MS` | How often live partial captions update |

## Deploying for a real clinic (what "production" actually means here)

You said you have no production background — here's the plain-language version of what changes
between "works on my laptop" and "works when a dentist's actual patients are calling it."

### 1. Real phone calls, not just a browser mic
A patient calling a clinic phone number isn't sending 16kHz PCM from a browser — they're on the
telephone network, which is 8kHz mu-law audio. `src/telephony_adapter.py` converts that to the
format this pipeline expects. The usual path: buy/port a number on **Twilio**, point it at a
`<Connect><Stream>` TwiML endpoint (a small WebSocket route you add to `server.py`, sketched in
that file's docstring), and Twilio streams the call audio to you in real time and streams your
assistant's TTS audio back to the caller. This needs a public HTTPS/WSS URL — `ngrok` while
developing, a real domain + TLS certificate once it's live.

### 2. Auth — don't let strangers use your clinic's compute
Set `STT_API_KEY` in production. Without it, anyone who finds your server's address can open
WebSocket connections and burn your CPU/GPU for free. Your telephony adapter (or whatever
component answers the call) should be the only thing holding this key, not something exposed
to the public internet.

### 3. Capacity planning — how many calls can one machine handle?
`STT_MAX_CONCURRENT_SESSIONS` caps simultaneous calls per server process. Rough guide for
`small.en` on int8/CPU: each concurrent transcription pass takes real CPU time, so a decent
8-core laptop-class CPU comfortably handles **~4-8 concurrent calls** before partials start
lagging. A single clinic's phone line rarely has more than 1-3 simultaneous callers, so a
laptop or a small cloud VM is genuinely enough to start. If you outgrow one machine (e.g. one
service handling multiple clinics), that's when you move to a GPU box running Parakeet-TDT
and/or run multiple replicas — not before. Don't over-engineer this on day one.

### 4. Graceful degradation over silent failure
When the server is full, it now sends `session_rejected` and closes cleanly instead of getting
slow for every existing call. Your orchestration layer should treat this as "route this call to
voicemail / a human / retry shortly" — for a clinic, a caller hearing "please hold" beats the
assistant mishearing them because the server was overloaded.

### 5. Idle & dead connections get cleaned up automatically
`STT_IDLE_TIMEOUT_S` closes a session if no audio arrives for that long — protects against a
dropped call silently holding a capacity slot forever (this happens more than you'd expect with
real telephony network hiccups).

### 6. Domain vocabulary — fewer "sorry, can you repeat that?" moments
`STT_INITIAL_PROMPT` (in `.env`) hints Whisper toward your clinic's actual vocabulary — doctor
names, procedure names, insurance terms. Customize it per deployment; it's the cheapest accuracy
win available and it directly reduces failed bookings from misheard names/times.

### 7. Patient data — a note, not a full compliance answer
Voice + appointment data from patients is sensitive. At minimum: don't log raw transcripts or
audio to disk by default, tell the clinic what you retain and for how long, and get patient
consent for the call being handled by an AI system (a short recorded disclosure at call start is
standard practice for this kind of system). If this ever handles real patient data at scale,
that's worth an actual conversation with someone who knows healthcare-data regulation in your
state/country — this codebase deliberately doesn't store anything by default so you're not
inheriting a compliance problem by accident.

### 8. Further scaling (only once you actually need it)
- **Better model on GPU**: implement `ParakeetEngine(ASREngine)` in `src/asr.py` (same interface,
  swap one line in `get_engine()`) once you're on hardware with an NVIDIA GPU.
- **Batch multiple callers' inference together**: NVIDIA Triton Inference Server, once you have
  enough simultaneous calls that per-caller inference stops being the efficient unit of work.
- **Horizontal scale**: run N replicas of this container behind a load balancer with session
  affinity (a call's WebSocket must stay pinned to one instance for its duration).

## Project structure

```
stt-service/
├── src/
│   ├── config.py       # all tunables, env-var driven
│   ├── schemas.py      # the STTEvent contract — read this first
│   ├── vad.py          # Silero VAD wrapper
│   ├── asr.py          # ASREngine interface + faster-whisper implementation
│   ├── session.py      # per-caller state machine (the core logic)
│   ├── server.py       # FastAPI WebSocket entrypoint (auth, capacity, idle timeout)
│   └── telephony_adapter.py  # real phone calls (Twilio Media Streams) -> pipeline audio format
├── tests/
│   ├── test_client_mic.py   # talk to your own server live
│   └── test_client_wav.py   # repeatable test with a WAV file
├── requirements.txt
├── .env.example
├── Dockerfile
└── run.py
```
