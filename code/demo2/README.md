# IIIT-NR voice helpdesk — demo2

Streamlit connects the existing institute helpdesk to local speech recognition, the supplied
VITS voices, and online English/Hinglish voices. Stop recording to receive an automatic
spoken answer with citations. You can also upload WAV/FLAC audio or type questions.

Reasoning defaults to **Qwen3.5 9B through Ollama**. Groq remains an explicit sidebar
choice. On the tested 32 GB RAM / 8 GB RTX 4060 system, local answers commonly took
20–50 seconds; an exact repeated question took 12.7 seconds with cached retrieval and
draft reuse. See [measured results and limits](VALIDATION.md).

## Active knowledge and runtime

Use **Runtime status** in the sidebar or `python ops.py status` to inspect the current
release, content integrity, router mode, source ownership, system environment, package versions,
and store sizes. These values come from the active pointer; a document's build date is not its policy review date.
See the comprehensive [technical audit implementation report](../../idea/DEMO2_IMPROVEMENT_REPORT.md) for
measured audit upgrades (F01–F18), test suites, verbalization v2, cache telemetry, and multi-page citation attribution.

The verified store contains exact JoSAA cutoff rows and technically reviewed reporting,
fee, eligibility and public-scheme evidence. Institute staff must still resolve conflicting
years and sign off current applicability. Never use the legacy `build_index.py` while a
verified release is active. Build, evaluate and activate through `kb_pipeline.py`.

| Documentation | Purpose |
| --- | --- |
| [Technical Audit Implementation Report](../../idea/DEMO2_IMPROVEMENT_REPORT.md) | Full October 2026 report on audit findings F01–F18, benchmarks, test results and operational readiness |
| [Local model setup](../Institute-voice-agent/institute-assistant/docs/LOCAL_INFERENCE.md) | Prepare Ollama/tokenizer, select Groq and recover from local model errors |
| [Operations and recovery](OPERATIONS.md) | Concurrency, admission queues, retention/deletion, backup/restore drills and status monitoring |
| [Knowledge-base guide](KNOWLEDGE_BASE.md) | Check the active database, add sources, review extraction, rebuild and roll back |
| [Validation record](VALIDATION.md) | Latest 316-test suite results, retrieval checks and speech pipeline verifications |
| [Offline questions](OFFLINE_INFORMATION_NEEDED.md) | Collect missing information with supporting documents |
| [Presentation results](../../idea/presentation/DEMO2_KNOWLEDGE_BASE_RESULTS.md) | Metrics, language breakdown, architecture and research limitations |

## Run

Use the existing **minor** environment. No new environment or shared model-library upgrade
is needed on this machine.
Prepare the Ollama model/tokenizer once using the
[local inference guide](../Institute-voice-agent/institute-assistant/docs/LOCAL_INFERENCE.md).
Keep Ollama running while using local reasoning. Restart Demo 2 after changing model configuration.

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

1. Keep **Answer model → Local · Ollama** for local reasoning, or explicitly select **Groq · Cloud**.
   Select the recording language and Female/Male voice in the sidebar.
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
| Institute answer | LangGraph agent with local Ollama by default or explicitly selected Groq; shared verified release and grounding review |
| Hindi audio | Supplied local Coqui VITS Female/Male model, 22050 Hz WAV |
| English audio | Opt-in online Edge Neerja/Prabhat voice, MP3 |
| Hinglish audio | Hindi/English pronunciation rendering, then opt-in online Swara/Madhur voice, MP3 |

Speech uses deterministic verbalization (`verbalization.py`, version `domain-pronunciation-2`)
with an extensive academic/admissions domain lexicon and typed number/date/percentage verbalization.
For example, ₹90,000 becomes “नब्बे हजार रुपये” in Indian numbering format, and percentages like 3.5%
deterministically render with explicit decimal words (“तीन दशमलव पाँच प्रतिशत”).
Crucially, it includes an explicit Hindi `NEGATION` mapping ("non-refundable" -> "गैर-वापसी योग्य",
"refundable" -> "वापसी योग्य", "excluding" -> "को छोड़कर", "including" -> "सहित", "not" -> "नहीं")
to prevent semantic drift or meaning reversal during synthesis. It does not ask an LLM to translate
answers for pronunciation. Unknown Latin words in Hindi fail safely to visible text instead of
silently dropping words. Hinglish retains unknown English words and normalizes only known Hindi words.
**Spoken text** shows the actual input to synthesis. Native-speaker listening and recognition tests
remain necessary.

English/Hinglish speech is **off until the browser session explicitly enables it**.
The switch discloses that answer text leaves the laptop. Hindi synthesis is local.

Models load lazily and are reused. Up to two CPU VITS voices remain cached within the configured weight budget; GPU speech keeps only one. VITS speed uses `length_scale`, as in the notebook.
Whisper defaults to CPU/int8 to reserve GPU memory for local reasoning. An explicit `auto` override selects CUDA when available and falls back to CPU/int8 if CTranslate2 cannot
load compatible CUDA libraries. This fallback is needed on the tested machine, where Torch
CUDA works but CTranslate2 cannot find `libcublas.so.12`. MMS can still use Torch CUDA.
No Torch/CUDA/Transformers packages are replaced to fix that mismatch.

## Configuration and data

An optional `.env` can be made from `.env.example`. Existing process variables take priority,
followed by `demo2/.env`, then the institute agent's `.env` for Groq/agent settings.
Never put real keys in `.env.example` or commit `.env`.

| Setting | Default |
| --- | --- |
| `OLLAMA_MODEL` | `qwen3.5:9b` |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` |
| `OLLAMA_NUM_CTX` | `8192` |
| `DEMO2_CODE_ROOT` | Parent directory of demo2 |
| `DEMO2_DATA_DIR` | `demo2/data` |
| `DEMO2_STT_DEVICE` | `cpu` (`auto` and `cuda` also accepted) |
| `DEMO2_WHISPER_MODEL` | `small` |
| `DEMO2_TTS_DEVICE` | `cpu` |
| `DEMO2_SPEECH_THREADS` | `4` |
| `DEMO2_STT_LANGUAGE` | `hne` for the experimental MMS path |
| `KB_DIR` | Sibling agent's `knowledge_base`; relative values resolve against the agent directory |
| `KB_STATE_DIR` | `kb_state` beside the resolved `KB_DIR`; use an absolute path if overriding |

The browser selector starts on Local; it controls each session independently.
`LLM_PROVIDER` controls the CLI/report default. The existing `GROQ_API_KEY` and
`GROQ_CHAT_MODEL` apply when Groq is explicitly selected. Full provider settings are
documented in the [local model guide](../Institute-voice-agent/institute-assistant/docs/LOCAL_INFERENCE.md).

Normal inference keeps microphone audio local. In Local mode, transcripts and answer context stay on the configured Ollama server (localhost by default); Groq receives them only when you explicitly select Groq.
English/Hinglish pronunciation text goes to the online voice service only after explicit session consent.
The first use of an uncached model needs internet access. Whisper `small` was downloaded
during verification; the existing MMS and embedding caches are reused.

Conversations/checkpoints and local staff-review drafts are stored in `demo2/data`, separately
from the original project's databases. Browser audio remains in session memory; downloads
are explicit. The UI retains the most recent 12 turns. The reasoning window separately uses
up to `HISTORY_TURNS=10` previous complete question/answer pairs, bounded by
`HISTORY_MAX_CHARS=12000`. Routing, answering and grounding review share that history and
the resolved questions from earlier turns. Increase k in `.env` and restart if longer
context is needed; large histories can increase provider token use. **New conversation**
creates independent memory. **Delete conversation** cancels/drains its work and erases its
checkpoints, local drafts, request results and owned cache entries. Sessions expire after
24 hours; maintenance runs every five minutes and after restart. Managed backups share
that 24-hour limit and cannot restore deleted sessions. These are logical deletions, not
forensic secure erasure. See [operations and recovery](OPERATIONS.md).

Frequent exact queries reuse evidence and eligible answer drafts from
`demo2/data/rag_cache.sqlite` (or `DEMO2_DATA_DIR`), independently of the CLI cache. Entries
expire after one hour; the cache retains up to 2,000 entries, preferring frequently used
ones, with a 64 MiB aggregate payload limit. KB release, date, model/prompt and effective context changes prevent stale reuse.
Draft hits still run grounding review: they skip one generation call, while retrieval hits
skip search. Repeated wording in a different conversation context can therefore miss the
draft cache. Errors and action results are never cached. `RAG_CACHE_ENABLED=false` disables
reuse; other limits are documented in `.env.example`. Restarting keeps unexpired entries.
No KB rebuild or new dependency is needed for memory/caching changes.

The adapter returns optional `rag_metrics` (cache outcomes, history pairs, logical model
calls and timings) for evaluation. Metrics never contain student messages or profile values.

`knowledge_base/` contains source files. The actual vector database and structured facts
live in `institute-assistant/kb_state/releases/`; `kb_state/active.json` selects the release
shared by Demo 2 and the text CLI. New releases are built separately and activated
atomically. Running retrieval follows the pointer on its next call; code or environment
changes still require restarting the app. The original index is retained for rollback.
Downloaded sources, models and release databases are ignored by Git, so a fresh checkout
needs the runtime artifacts or a reviewed rebuild. See [setup and maintenance](KNOWLEDGE_BASE.md).

Student details are optional and self-reported. Staff-review actions only create local drafts;
the graph never sends email. Reminders are explicitly disabled in this demo.

Reviewed text is displayed before synthesis finishes. If audio fails, the answer remains available. **Retry audio** retries only speech, without
repeating the agent or creating duplicate action drafts. Online synthesis runs in a child
process with a 45-second timeout. Model loading and inference are serialized for this local
demo. One reasoning worker admits at most three waiting requests and preserves each conversation’s order. Queue wait is limited to 60 seconds; the answer deadline is 120 seconds including queueing. Cancel suppresses late results, but a native call may keep its resource until it returns. See [operations](OPERATIONS.md).

## Verify

The October 2026 technical audit implementation passes **37 Demo2 tests and 279 shared-agent tests (316 total passing, 0 failures)**, covering:
- Resampling, silence, boundary conditions, and audio decoding.
- Verbalization v2 with domain lexicon, negation protection, and decimal formatting.
- Non-blocking text rendering before speech synthesis, and audio-only retry without re-entering the graph.
- Bounded admission queue, timeouts, and cooperative task cancellation.
- Hard conversation deletion with tombstones, 2-checkpoint compaction, and online backup/restore drills.
- Multi-evidence block citation page attribution (`[Page X]`).
- Multilingual query augmentation for Hindi loan inquiries.
- Cache telemetry counters and live hit-rate reporting.

See the comprehensive [technical audit implementation report](../../idea/DEMO2_IMPROVEMENT_REPORT.md) for full metrics.

Earlier historical milestones:
- The 30 September upgrade passed **33 Demo2 tests and 276 shared-agent tests**, introducing worker decoupling and SQLite retention.
- The 23 September local-provider change passed **17 Demo 2 tests and 142 agent tests**, establishing local Ollama inference.
- The 23 September memory/cache change passed **15 Demo 2 tests and 116 agent tests**.
- The 22 September release passed **13 Demo 2 tests and 69 agent tests** with 98.92% recall on 117 benchmark questions. See [validation details](VALIDATION.md).

Run the following from `code/demo2`:

```bash
conda activate minor
python -m pytest -q
python smoke.py tts       # both local voices; creates data/smoke/{Female,Male}.wav
python smoke.py stt       # needs Female.wav from the tts check above
python smoke.py mms       # uses the same WAV with original MMS
python smoke.py online    # fixed English phrase through online TTS
python smoke.py hinglish  # explicit consent for the fixed public online speech check
python smoke.py agent     # fixed public admissions question with sources
python smoke.py pipeline  # local question speech -> STT -> grounded agent -> reply speech
```

Smoke checks use fixed public questions and write samples under `data/smoke`. The online and Hinglish audio checks need internet for Edge TTS. Agent and Hindi pipeline
checks use the selected reasoning provider; Local requires a running Ollama server. Local
checks may need an initial model/tokenizer download. They do not request staff review or reminders. See
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

The protobuf/telemetry compatibility repair is pinned in `compatibility-constraints.txt` and was tested in a temporary Conda clone before application. See [recovery and reproducibility](OPERATIONS.md). For missing dependencies, inspect installed versions before installing `requirements.txt`.
The sibling agent/STT dependencies and Coqui `TTS==0.22.0` are already present in `minor`.
Do not replace the shared model stack. Missing VITS checkpoints must be retrieved through
the original TTS repository's Git LFS setup; tiny pointer files are not model weights.

Browser input and test behavior use Streamlit's documented
[audio recorder](https://docs.streamlit.io/develop/api-reference/widgets/st.audio_input) and
[AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).

## Optional local Open Jev routing

The shared helpdesk supports an opt-in, locally trained Open Jev classifier.
It defaults off and preserves the selected answer model, citations and grounding
review. Follow the [training and activation guide](../Institute-voice-agent/institute-assistant/docs/OPEN_JEV.md)
and check the [pilot results](../Institute-voice-agent/institute-assistant/docs/OPEN_JEV_VALIDATION.md).
No separate Demo 2 model or training run is required.
The [English recovery guide](../Institute-voice-agent/institute-assistant/docs/ENGLISH_ROUTER_RECOVERY.md)
provides training for the shared pretrained router. Hindi/Hinglish retain LLM
routing and rewriting; training stops before activation.
