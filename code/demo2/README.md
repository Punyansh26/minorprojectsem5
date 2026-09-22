# IIIT-NR voice helpdesk — demo2

Streamlit connects the existing institute helpdesk to local speech recognition, the supplied
VITS voices, and online English/Hinglish voices. Stop recording to receive an automatic
spoken answer with citations. You can also upload WAV/FLAC audio or type questions.

## Current database — 22 September 2026

**The new knowledge base is already built and active for Demo 2. Start the app normally;
you do not need to run `python build_index.py`.** That is the legacy builder and refuses
to run while a verified release is active.

The activated release, `20260922T095421217856Z`, contains **222 vector chunks** and
**611 official JoSAA cutoff records**. It also includes reviewed institute documents,
Chhattisgarh scholarship information and PM-Vidyalaxmi conditions. Some current institute
policies remain unverified; see the [offline collection checklist](OFFLINE_INFORMATION_NEEDED.md).

| Documentation | Purpose |
| --- | --- |
| [Knowledge-base guide](KNOWLEDGE_BASE.md) | Check the active database, add sources, review extraction, rebuild and roll back |
| [Validation record](VALIDATION.md) | Latest retrieval/code results and separately dated speech checks |
| [Offline questions](OFFLINE_INFORMATION_NEEDED.md) | Collect missing information with supporting documents |
| [Presentation results](../../idea/presentation/DEMO2_KNOWLEDGE_BASE_RESULTS.md) | Metrics, language breakdown, architecture and research limitations |

## Run

Use the existing **minor** environment. No new environment or shared model-library upgrade
is needed on this machine.

```bash
cd "/run/media/rtx/Files/Study/Semester 5/Minor/code/demo2"
bash run.sh
```

Alternatively:

```bash
conda activate minor
streamlit run app.py
```

Open **http://localhost:8501**. If the port is occupied, use `bash run.sh --server.port 8502`.
`run.sh` selects the existing `minor` environment and starts Streamlit from this folder.
Allow microphone access in your browser. Recording works on localhost or HTTPS; a plain
HTTP LAN address does not provide browser microphone permission. Autoplay may require
pressing Play once in your browser.

The expected layout is:

```text
code/
  demo2/                         this app
  Institute-voice-agent/
    institute-assistant/         agent code, .env, knowledge_base, kb_state
  STT/stt-service/               original MMS engine and STT settings
  TTS/chattisgarhi-tts-models/    Female/ and Male/ configs and checkpoints
  Speech2Speech.ipynb            source of the VITS inference/audio-conversion approach
```

The app imports the sibling projects; it does not copy the large model checkpoints or
require the notebook/STT server to run. `DEMO2_CODE_ROOT` can point to a different parent.

## Use

1. Select the recording language and Female/Male voice in the sidebar.
2. Record one question, leaving a brief pause, then stop. Each recording is submitted once.
3. Read the recognized question and answer, inspect **View sources**, or replay/download audio.
4. Ask a follow-up by voice or text. **New conversation** starts independent agent memory.

For cutoff questions, include the year, counselling authority, round, branch, quota,
category and seat pool when known. For example: “What are the opening and closing ranks
for 2026 JoSAA round 5 CSE SC All India Gender-Neutral?” Published historical cutoffs do
not predict a future allotment. **View sources** shows quotations, page references,
official links and document periods where available.

Recording language controls recognition. The existing agent determines the answer language
from the recognized/typed text. Hinglish recognition can produce Devanagari, in which case
the agent may answer in Hindi; Roman Hindi typed questions can receive Hinglish replies.
Chhattisgarhi is an experimental recording option and uses the original MMS `hne` adapter;
the agent uses Hindi as its response fallback.

Recordings must be 0.3–30 seconds and at most 12 MB. Stereo is downmixed and audio resampled
to 16 kHz. Silence does not trigger an agent call. Audio upload supports WAV/FLAC.
The demo is turn-based: it does not implement continuous listening, barge-in, or telephony.

## Speech and answer routing

| Stage | Implementation |
| --- | --- |
| Hindi/English/Hinglish STT | Local multilingual Faster Whisper `small`, with VAD |
| Chhattisgarhi STT | Original `src.asr.get_engine()` MMS singleton with `hne` adapter |
| Institute answer | LangGraph/Groq agent, shared verified Chroma/SQLite release and grounding review |
| Hindi audio | Supplied local Coqui VITS Female/Male model, 22050 Hz WAV |
| English audio | Online Edge Neerja/Prabhat voice, MP3 |
| Hinglish audio | Hindi/English pronunciation rendering, then online Swara/Madhur voice, MP3 |

VITS cannot pronounce Latin text and digits reliably. Hindi speech rendering transliterates
Latin names through Groq and expands digits individually (for example 120 becomes “एक दो शून्य”).
Hinglish rendering converts Roman Hindi words to Devanagari while retaining English words.
Numeric sequences must remain unchanged by rendering or synthesis is rejected. The original
answer and source quotations remain visible; expand **Spoken text** to inspect the actual
pronunciation text. This check does not establish semantic equivalence of every translated word.

Models load lazily and are reused. VITS speed uses `length_scale`, as in the notebook.
Whisper selects CUDA when available, but `auto` falls back to CPU/int8 if CTranslate2 cannot
load compatible CUDA libraries. This fallback is needed on the tested machine, where Torch
CUDA works but CTranslate2 cannot find `libcublas.so.12`. MMS can still use Torch CUDA.
No Torch/CUDA/Transformers packages are replaced to fix that mismatch.

## Configuration and data

An optional `.env` can be made from `.env.example`. Existing process variables take priority,
followed by `demo2/.env`, then the institute agent's `.env` for Groq/agent settings.
Never put real keys in `.env.example` or commit `.env`.

| Setting | Default |
| --- | --- |
| `DEMO2_CODE_ROOT` | Parent directory of demo2 |
| `DEMO2_DATA_DIR` | `demo2/data` |
| `DEMO2_STT_DEVICE` | `auto` (`cpu` and `cuda` also accepted) |
| `DEMO2_WHISPER_MODEL` | `small` |
| `DEMO2_TTS_DEVICE` | `cpu` |
| `DEMO2_SPEECH_THREADS` | `4` |
| `DEMO2_STT_LANGUAGE` | `hne` for the experimental MMS path |
| `KB_DIR` | Sibling agent's `knowledge_base`; relative values resolve against the agent directory |
| `KB_STATE_DIR` | `kb_state` beside the resolved `KB_DIR`; use an absolute path if overriding |

Normal inference keeps microphone audio local. Transcripts and answer context go to Groq.
English/Hinglish answer pronunciation text also goes to the selected online speech service.
The first use of an uncached model needs internet access. Whisper `small` was downloaded
during verification; the existing MMS and embedding caches are reused.

Conversations/checkpoints and local staff-review drafts are stored in `demo2/data`, separately
from the original project's databases. Browser audio remains in session memory; downloads
are explicit. The UI retains the most recent 12 turns. Starting a new conversation does not
erase previous SQLite checkpoints.

`knowledge_base/` contains source files. The actual vector database and structured facts
live in `institute-assistant/kb_state/releases/`; `kb_state/active.json` selects the release
shared by Demo 2 and the text CLI. New releases are built separately and activated
atomically. Running retrieval follows the pointer on its next call; code or environment
changes still require restarting the app. The original index is retained for rollback.
Downloaded sources, models and release databases are ignored by Git, so a fresh checkout
needs the runtime artifacts or a reviewed rebuild. See [setup and maintenance](KNOWLEDGE_BASE.md).

Student details are optional and self-reported. Staff-review actions only create local drafts;
the graph never sends email. Reminders are explicitly disabled in this demo.

If audio fails, the answer remains available. **Retry audio** retries only speech, without
repeating the agent or creating duplicate action drafts. Online synthesis runs in a child
process with a 45-second timeout. Model loading and inference are serialized for this local
demo; it is not a multi-worker deployment.

## Verify

Recorded on 22 September: **13 Demo 2 tests and 69 agent tests passed**. The retrieval
benchmark found supporting evidence for **92/93 answerable questions (98.92%)** and passed
**42/42 cutoff checks**. Warm retrieval median/p95 was **11.4/13.8 ms**, excluding LLM and
speech. All seven attempted live answer checks hit Groq rate limits; these retrieval
results do not establish generated-answer accuracy. See [validation details](VALIDATION.md).

Run the following from `code/demo2`:

```bash
conda activate minor
python -m pytest -q
python smoke.py tts       # both local voices; creates data/smoke/{Female,Male}.wav
python smoke.py stt       # needs Female.wav from the tts check above
python smoke.py mms       # uses the same WAV with original MMS
python smoke.py online    # fixed English phrase through online TTS
python smoke.py hinglish  # fixed Hinglish phrase; uses Groq and online TTS
python smoke.py agent     # fixed public admissions question with sources
python smoke.py pipeline  # local question speech -> STT -> grounded agent -> reply speech
```

Smoke checks use fixed public questions and write samples under `data/smoke`. The online,
Hinglish, agent and full-pipeline checks need provider access; local checks may need an
initial model download. They do not request staff review or reminders. See
[VALIDATION.md](VALIDATION.md) for dated results.
The automated suite uses mocked providers and no model downloads. Source-agent regression
tests can be run with `python -m pytest -q` in `institute-assistant`.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Unsure whether the database is built | Follow the read-only [active-release check](KNOWLEDGE_BASE.md#check-the-active-release); no rebuild is needed for the installed release |
| `build_index.py` refuses to run | Use the reviewed `kb_pipeline.py` workflow; the refusal protects the old rollback index |
| New PDF does not appear in answers | Copying it alone is insufficient: register, extract, review, build, evaluate and activate |
| Answer service is rate-limited | Allow the provider quota to recover and retry later; rebuilding the database will not fix a Groq quota |
| Current spot round or college aid cannot be verified | Check the offline checklist; fetched JoSAA ranks and general scheme rules do not fill those gaps |
| Answer is visible but no audio plays | Inspect the speech error and use **Retry audio**; check browser autoplay and online voice availability |
| Whisper cannot load CUDA libraries | Keep `DEMO2_STT_DEVICE=auto` for the documented CPU fallback, or set `cpu` and restart |

For missing dependencies, inspect installed versions before installing `requirements.txt`.
The sibling agent/STT dependencies and Coqui `TTS==0.22.0` are already present in `minor`.
Do not replace the shared model stack. Missing VITS checkpoints must be retrieved through
the original TTS repository's Git LFS setup; tiny pointer files are not model weights.

Browser input and test behavior use Streamlit's documented
[audio recorder](https://docs.streamlit.io/develop/api-reference/widgets/st.audio_input) and
[AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).
