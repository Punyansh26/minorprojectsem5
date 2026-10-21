# LLM Layer — Institute Voice Assistant

For the current browser voice helpdesk, use [Demo 2](../demo2/README.md).
Its shared reasoning layer now defaults to local Ollama; see
[local inference setup](institute-assistant/docs/LOCAL_INFERENCE.md).
The default model is Qwen3.5 9B; Groq remains an explicit alternative. See
[validation and measured latency](institute-assistant/docs/LOCAL_MODEL_VALIDATION.md).
The WebSocket orchestrator described below is a separate integration.

This folder has two parts that work together:

```
Institute-voice-agent/
├── institute-assistant/   RAG + LangGraph agent (retrieval, escalation, reminders)
└── voice-orchestrator/    Glue: connects your STT service -> the agent -> (TTS, once wired)
```

`institute-assistant` is a complete, independently testable system on its own (you can ask
it questions by typing, no voice needed). `voice-orchestrator` is the thin layer that
connects it to a live STT service over WebSocket.

## Prerequisites

- The existing `minor` Conda environment (Python 3.11). Preserve its speech/model dependencies.
- Your own STT service already running (whatever setup you have).
- Ollama and the configured local model; a Groq key is optional for explicit cloud use.

## Step 1 — Set up `institute-assistant`

```bash
cd institute-assistant
conda activate minor
ollama pull qwen3.5:9b
python setup_local.py
```

Ollama must be running first, either through its system service or `ollama serve` in
another terminal. The configured machine already has the model and tokenizer installed.

Use `.env.example` for new installations; preserve an existing `.env` and its Groq settings.
Local mode needs no Groq key.

The reviewed knowledge-base release is already active on this machine; no index rebuild is
needed for this provider change. Follow the institute-assistant README for fresh installations
or reviewed source updates.

**Test it standalone first**, before touching voice at all:

```bash
python ask_kb.py      # raw retrieval only, no LLM
python run_cli.py     # full agent — type questions, get grounded answers
```

If this works, the agent itself is fine — anything that breaks later is in the voice wiring, not here.

## Step 2 — Set up `voice-orchestrator`

```bash
cd ../voice-orchestrator
conda activate minor
python -m pip install -r requirements.txt
# For a new installation only; preserve an existing .env:
cp -n .env.example .env
```

Edit `.env` — **set `STT_WS_BASE_URL` to match your own STT service's actual host/port**
(check what your STT server prints on startup, e.g. `ws://localhost:8000/ws/stt` or
whatever port yours runs on — this is the #1 thing that goes wrong, a port mismatch).

## Step 3 — Run the full voice loop

**Terminal 1**: start your STT service as you normally do.

**Terminal 2**:

```bash
cd voice-orchestrator
conda activate minor
python orchestrator.py
```

Log in with a test student ID/email/category, then speak a real question. You should see:

```
[STT FINAL] <your transcribed question>
[ASSISTANT] <grounded answer with source citation>
```

This separate orchestrator prints the reply as text. Demo 2 already provides synthesized
browser replies using local Hindi VITS and online English/Hinglish Edge voices.

## Optional — Add TTS to the WebSocket orchestrator

Open `voice-orchestrator/orchestrator.py` and find this exact comment block near the bottom
of the `main()` loop:

```python
# --- TTS PLUGS IN RIGHT HERE, once your teammate's model is ready ---
```

Replace that comment with your actual synthesis + playback call, e.g. (adjust paths/params
to match your actual setup):

```python
wav = tts.tts(text=reply)
sd.play(np.array(wav), samplerate=22050)
sd.wait()
```

Load your `Synthesizer` once near the top of `main()` (not inside the loop, or it'll reload
the model on every single reply). Nothing else in the file needs to change for this addition.

## Known limitations (be aware, not necessarily blockers)

- **No real login** — student ID/email/category are typed in manually (`run_cli.py` and
  `orchestrator.py` both prompt for them). A real login system would feed these in instead.
- **Cross-lingual retrieval is untested** — a Chhattisgarhi spoken question against our
  English-language documents may retrieve poorly. Worth testing together once voice+TTS
  works end-to-end; not yet solved.
- **Escalation emails need real config** — `institute-assistant/.env` has placeholder office
  emails and no SMTP credentials set by default; drafts still work, sending needs setup
  (see that project's own README for details).

## If something breaks

- `ModuleNotFoundError` → wrong/no conda env active, or `pip install -r requirements.txt`
  didn't finish — re-run it and read the full output, don't skip errors partway through.
- `ConnectionRefusedError` in `orchestrator.py` → `STT_WS_BASE_URL` in `voice-orchestrator/.env`
  doesn't match your STT server's actual port.
- For model-library installation failures, verify that `minor` is active and inspect the
  existing versions before changing dependencies.
