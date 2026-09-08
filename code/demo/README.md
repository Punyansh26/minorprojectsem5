# Kisan Saathi — local speech + Groq + MCP demo

Speak into the browser microphone, stop recording, and the demo transcribes with
this project's local STT engine, executes shopping tools over real MCP, and speaks
the grounded result with the local Chhattisgarhi VITS checkpoint. Chat routing uses
the Groq key in `demo/.env`. Carts, stock, previews, orders, and retry records are
stored in a JSON file; no database server or SQLite is used.

## Run

```bash
conda activate minor
cd '/run/media/rtx/Files/Study/Semester 5/Minor/code/demo'
python -m streamlit run app.py --server.address 127.0.0.1 --server.headless true --server.fileWatcherType none
```

Open http://localhost:8501. The existing `minor` environment has the speech stack;
if adding demo dependencies, use `python -m pip install -r requirements.txt` in
that environment. Do not replace or upgrade its torch/transformers/TTS stack.

The key is loaded automatically from `.env`, regardless of the shell's working
directory. An exported environment variable takes precedence. A password field
appears only when no key is configured. Never commit `.env`.

`GROQ_CHAT_MODEL=openai/gpt-oss-120b` is the tested routing configuration. The
previous `llama-3.3-70b-versatile` configuration returned HTTP 404 on 2026-09-06;
the replacement was listed by the account's models API and tested with real MCP
calls. Restart Streamlit after editing configuration. Provider quotas still apply;
errors identify unavailable models, invalid keys, connection problems, and rate
limits without printing secrets. Exact “show cart” / “टोकरी दिखाओ” and checkout
commands skip model calls, and successful mutations need no extra model reply call.
Typed requests use a submit form so Send works with the current text without a
separate blur/rerun step.

## Existing speech pipeline integration

`local_speech.py` imports `../STT/stt-service/src/asr.py::get_engine()` and uses its
final decoding (`fast=False`) on completed microphone recordings. It loads STT
configuration from `../STT/stt-service/.env`, with exported values or `demo/.env`
overrides taking precedence. The demo uses `DEMO_STT_DEVICE=cuda` and
`DEMO_STT_DTYPE=float16`: MMS weights are loaded in reduced precision before GPU
transfer to reduce VRAM use. Floating-point audio inputs use the same precision;
attention masks remain integer. Restart after changing these settings, and run
only one demo/model instance when GPU memory is limited. CUDA must be available;
the demo does not silently switch devices. The supplied configuration selects MMS with the
`hne` Chhattisgarhi adapter. Reply language selection does not switch the STT
model; the sidebar shows the actual recognition language.

TTS uses the same `Synthesizer`, checkpoint/config paths, and `length_scale`
control as `../Speech2Speech.ipynb`. Set `DEMO_TTS_VOICE=Female` or `Male`,
`DEMO_TTS_DEVICE=cpu` or `cuda`, and `DEMO_TTS_LENGTH_SCALE=1.0` in `.env`.
CPU is the default for TTS so it does not compete with MMS for GPU memory.
Models are loaded lazily, cached across Streamlit reruns, and protected by a lock
across browser sessions. First speech use can take tens of seconds. The cached
MMS model and real VITS weights must be present; first-time downloads need internet.

No notebook or STT server needs to be running. Because this is a completed-recording
interface, it uses the existing ASR engine directly; it does not run the notebook's
WebSocket/VAD/partial-transcript loop or provide streaming/barge-in.

Recordings stay in memory and are normalized to mono 16 kHz PCM16. Replies are
in-memory PCM16 WAV at the checkpoint's 22050 Hz output rate. Enable **Spoken
replies** for playback. Numbers and rupee amounts are converted into Hindi words
before synthesis, because the VITS vocabulary lacks Latin digits and `₹`.
Visible text is unchanged. These VITS models use Devanagari: select Hindi or
Chhattisgarhi for spoken replies; English remains available as text.

Audio is processed locally. Groq receives the transcript and recent text context
for shopping interpretation. No Groq Whisper or Edge TTS call is made. With no
Groq key, local transcription and manual shopping still work.

## Try it

1. In **Shop**, search `धान`, add two packs, and inspect the ₹900.00 cart.
2. Select **Checkout**, then **Confirm demo order**. This is a simulated order.
3. In **Talk**, say `धान बीज के दो पैकेट टोकरी में डालो`, then `टोकरी दिखाओ`.
4. The transcript and grounded reply appear automatically after Stop. Each
   recording is claimed before processing so reruns cannot repeat a mutation.
5. Use **MCP proof / Developer** to inspect the 12 discovered tool schemas and
   actual calls. The downloaded trace excludes keys, audio, and confirmation tokens.
6. Check ambiguous `जैविक खाद`, unavailable gloves, and unknown items. Diagnosis,
   treatment, and dosage requests receive a fixed KVK referral.

Checkout confirmation accepts the explicit submitted phrases `Confirm demo order`,
`डेमो ऑर्डर पक्का करो`, or `डेमो ऑर्डर की पुष्टि करें` with a current preview.
A generic “yes” is insufficient. The model cannot access the confirmation tool.

## JSON storage

`data/catalogue.json` contains synthetic fixtures. The runtime file defaults to
`data/shop.json`; override with an absolute `DEMO_STATE_PATH`. Every operation
locks a separate `.lock` file across processes. Writes use a temporary file,
flush/fsync, and atomic replacement. Interrupted writes leave the original intact;
corrupt JSON is reported rather than silently reset. Session ownership, integer
paise, locked cart prices, stock checks, idempotency, and preview-bound confirmation
are preserved across MCP subprocesses.

A fresh JSON path starts fresh stock and carts. **New session** changes browser
identity; it does not reset shared stock or delete orders. Old SQLite files are
left untouched and are not migrated or used. This small-file store is for the
local demo, not a large multiuser deployment.

## Verification

```bash
python -m pytest -q
python -m pip check
python smoke_demo.py
python smoke_demo.py --live
```

Tests cover JSON persistence, failure recovery, concurrent MCP processes, shopping
invariants, actual MCP discovery/schema checks, Groq doubles, provider errors,
audio adapters, and Streamlit microphone/cart controls. The keyless smoke test
uses temporary JSON state. `--live` uses synthetic local VITS audio → local MMS →
Groq/MCP price lookup → local VITS reply, requiring a key and `ffmpeg`.
Browser microphone permission, real playback, and native-speaker speech quality
require manual verification; automated doubles do not establish those results.
