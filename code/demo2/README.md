# IIIT-NR voice helpdesk — demo2

Streamlit connects the existing institute helpdesk to local speech recognition, the supplied
VITS voices, and online English/Hinglish voices. Stop recording to receive an automatic
spoken answer with citations. You can also upload WAV/FLAC audio or type questions.

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
Allow microphone access in your browser. Recording works on localhost or HTTPS; a plain
HTTP LAN address does not provide browser microphone permission. Autoplay may require
pressing Play once in your browser.

The expected layout is:

```text
code/
  demo2/                         this app
  Institute-voice-agent/
    institute-assistant/         agent code, .env, knowledge_base, chroma_index
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
| Institute answer | Existing LangGraph/Groq agent, existing Chroma index and grounding review |
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

Normal inference keeps microphone audio local. Transcripts and answer context go to Groq.
English/Hinglish answer pronunciation text also goes to the selected online speech service.
The first use of an uncached model needs internet access. Whisper `small` was downloaded
during verification; the existing MMS and embedding caches are reused.

Conversations/checkpoints and local staff-review drafts are stored in `demo2/data`, separately
from the original project's databases. Browser audio remains in session memory; downloads
are explicit. The UI retains the most recent 12 turns. Starting a new conversation does not
erase previous SQLite checkpoints. The existing Chroma index is reused; stop the app before
rebuilding it with the source project's tooling.

Student details are optional and self-reported. Staff-review actions only create local drafts;
the graph never sends email. Reminders are explicitly disabled in this demo.

If audio fails, the answer remains available. **Retry audio** retries only speech, without
repeating the agent or creating duplicate action drafts. Online synthesis runs in a child
process with a 45-second timeout. Model loading and inference are serialized for this local
demo; it is not a multi-worker deployment.

## Verify

```bash
conda activate minor
python -m pytest -q
python smoke.py tts       # both local voices; creates data/smoke/{Female,Male}.wav
python smoke.py stt       # transcribes the Female WAV with Whisper
python smoke.py mms       # transcribes the same WAV with original MMS
python smoke.py online    # fixed English phrase through online TTS
python smoke.py hinglish  # fixed Hinglish phrase; uses Groq and online TTS
python smoke.py agent     # fixed public admissions question with sources
python smoke.py pipeline  # local question speech -> STT -> grounded agent -> reply speech
```

Live smoke checks use fixed public questions, make provider calls, and write samples under
`data/smoke`. They do not request staff review or reminders. See `VALIDATION.md` for results.
The automated suite uses mocked providers and no model downloads. Source-agent regression
tests can be run with `python -m pytest -q` in `institute-assistant`.

For missing dependencies, inspect installed versions before installing `requirements.txt`.
The sibling agent/STT dependencies and Coqui `TTS==0.22.0` are already present in `minor`.
Do not replace the shared model stack. Missing VITS checkpoints must be retrieved through
the original TTS repository's Git LFS setup; tiny pointer files are not model weights.

Browser input and test behavior use Streamlit's documented
[audio recorder](https://docs.streamlit.io/develop/api-reference/widgets/st.audio_input) and
[AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).
