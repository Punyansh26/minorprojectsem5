# Demo 2 validation record

## Latest knowledge-base validation — 2026-09-22

Release `20260922T095421217856Z` was built, evaluated and activated for the shared
institute helpdesk database. Demo 2 was checked against this active release. The results
below come from saved evaluations; the earlier speech checks remain separately dated.

| Check | Recorded result | Scope |
| --- | --- | --- |
| Demo 2 automated suite | **13 passed** | Mocked providers and application/adapter behavior |
| Shared agent automated suite | **69 passed** | Includes source validation, exact cutoff filters, failed-build preservation and rollback |
| Total automated tests | **82 passed** | Software regression tests, not live user trials |
| Retrieval benchmark | **117 cases** | 39 each in English, Hindi and Hinglish |
| Supporting-evidence recall@6 | **92/93 = 98.92%** | Answerable cases with expected evidence and required terms |
| Exact cutoff checks | **42/42 passed** | 30 known-cutoff and 12 unavailable-cutoff scenarios |
| Other unsupported questions | **12 awaiting answer review** | Not counted as passed by the retrieval benchmark |
| Warm retrieval median / p95 | **11.4 / 13.8 ms** | Mixed semantic search and exact lookup; excludes initialization, LLM, STT and TTS |
| Live generated-answer checks | **0/7 completed with expected status** | All seven returned unavailable because of Groq rate limits |

The previous corpus recalled the expected source/page for **10/93 questions (10.75%)**.
The expanded corpus, extraction and retrieval all changed. The old measurement uses a
source/page proxy while the new measurement uses evidence-block IDs and required terms;
this is not an isolated embedding-model comparison or a generated-answer accuracy score.

The answerable language slices were English **31/31**, Hindi **30/31**, and Hinglish
**31/31**. The remaining retrieval miss is `loan_repayment_hindi`. These are development
regression cases, not an independently held-out study. Chhattisgarhi retrieval accuracy,
speech recognition accuracy, listening quality and end-to-end voice latency were not
measured by this rebuild.

### Active data and integration

- **222 vector chunks** and **613 structured records**, including **611 official JoSAA
  cutoff rows** for 2022–2026, are present in the active release.
- Demo 2 resolves the same release as the text CLI through `kb_state/active.json`.
- An exact 2026 JoSAA round 5 CSE/SC/All India/Gender-Neutral query returned its matching
  record with category-rank semantics. An unavailable NTPC query returned no substitute.
- The reviewed scanned academic calendar was retrieved for a mid-term examination query.
- The original index was preserved and backed up before activation. Automated tests cover
  activation, rollback, failed embedding builds and switching from a cached legacy index.
- The latest agent suite recorded 38 Chroma/Pydantic deprecation warnings; all tests passed.

### Evidence review and limits

The fee table, both calendar pages, NIRF summary tables and CG scholarship notice were
visually checked against rendered originals. There are still **267 extraction blocks
awaiting review**. Unreviewed visual interpretations are excluded from factual answers.

The source inventory has 75 entries, including **26 failed fetches**; this is not a count
of 75 successfully verified documents. Institute website timeouts prevented confirmation
of current spot notices, college aid and CG/NTPC cutoffs. Bank-specific rates and current
IIIT-NR eligibility for loan support also remain unverified. General scheme guidelines
must not be treated as an institutional eligibility certificate.

All seven staged live checks—fees, exact cutoff, CG scholarship, loan exclusions, institute
loan eligibility, current spot applications and scanned calendar—were blocked by provider
rate limits. No ticket/reminder writes were permitted. Generated-answer correctness and
abstention on the new corpus therefore remain unvalidated by this live run. The successful
18 September samples below do not remove that limitation.

### Saved evidence and reproduction

- [Rebuild validation report](../Institute-voice-agent/institute-assistant/docs/KB_REBUILD_VALIDATION.md)
- [Evaluation questions and reference evidence](../Institute-voice-agent/institute-assistant/docs/kb_evaluation_cases.json)
- [Saved live results](../Institute-voice-agent/institute-assistant/docs/kb_live_evaluation.json)
- [Code and shared-release checks](../Institute-voice-agent/institute-assistant/docs/kb_code_checks.json)
- [Presentation metrics and environment snapshot](../../idea/presentation/DEMO2_KNOWLEDGE_BASE_RESULTS.md)
- [Maintenance and staged evaluation commands](KNOWLEDGE_BASE.md)
- [Offline information to collect](OFFLINE_INFORMATION_NEEDED.md)

Run `python -m pytest -q` separately in `code/demo2` and the shared agent directory using
the existing `minor` environment. Run `kb_pipeline.py evaluate --release ID` from the agent
directory to measure a selected release; use `evaluate_helpdesk.py --live --release ID`
only when provider access and quota are available. See the maintenance guide for full
commands. No new speech benchmark was run as part of the documentation update.

## Historical component verification — 2026-09-18

The following records the original component checks before the new database release.
Counts and live successes describe that run, not the current corpus validation.

Environment: existing Conda `minor`, Python 3.11. Shared Torch, Transformers and Coqui
versions were preserved. The missing Faster Whisper `small` model was downloaded.

### Automated checks

- **13 demo tests passed**: resampling, silence, malformed/short/long recordings, numeric
  speech-rendering guard, independent conversations, duplicate-turn suppression, consumed
  recording failures, audio-only retry, online voice routing/timeout, automatic CPU fallback
  at model load and inference, and Streamlit text interaction/reset/source display.
- **52 existing agent regression tests passed**, with 33 pre-existing Chroma/Pydantic
  deprecation warnings.

### Real component checks

- Female VITS: valid 22050 Hz WAV, about 3.65 seconds for the fixed greeting.
- Male VITS: valid 22050 Hz WAV, about 4.51 seconds for the fixed greeting.
- Whisper Hindi: produced a nonempty Devanagari transcript from local VITS audio.
- Original MMS `hne`: loaded the cached model on GPU and produced a nonempty transcript.
- English Edge voice: generated 21024 bytes of MP3; Whisper transcribed the generated
  English sentence correctly in this sample.
- Hinglish rendering and Edge voice: generated 26064 bytes of MP3; Whisper returned a
  Devanagari transcript. Some recognition errors occurred in Hindi/Hinglish/MMS samples;
  these checks establish connectivity, not language accuracy or human-listening quality.
- Live agent: the fixed B.Tech admissions question returned `answered` with two sources.
  Its claim about JEE-based merit was checked against the original FAQ page 2 and annual
  report page 21. This is a single sample, not a broad factual-quality evaluation.
- Full Hindi pipeline: VITS question audio -> Whisper -> grounded agent -> pronunciation
  rendering -> VITS response; produced a 358988-byte WAV and two source references.
- Desktop (1440×1050) and mobile (390×844) were rendered in headless Chromium and visually
  inspected. Neither viewport had horizontal overflow. The microphone widget was visible;
  a physical microphone/browser permission interaction was not tested.

### Runtime findings

Torch detects the GPU, but CTranslate2 cannot load `libcublas.so.12` on this machine.
`DEMO2_STT_DEVICE=auto` correctly falls back to CPU/int8 for Whisper while MMS can use
Torch CUDA. Existing model dependencies were not changed.

Sandbox restrictions initially blocked provider calls, model downloads, GPU access, and
local listening sockets. These checks were repeated successfully with approved access.
Provider availability, quotas and first model-load latency still affect actual demo use.
