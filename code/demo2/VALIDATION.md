# Demo 2 validation record

## Local default and voice pipeline — 2026-09-23

The current reasoning provider is Ollama `qwen3.5:9b` (Q4_K_M), with an 8192-token
context. Groq is available through explicit per-session sidebar selection. Local
requests never fall back to Groq automatically.

| Check | Recorded result | Scope |
| --- | --- | --- |
| Automated suites | **142 agent + 17 Demo 2 = 159 passed** | Isolated state and mocked providers |
| Full local behavior run before follow-up fix | **22/25 passed** | Two category/round follow-up failures and one reporting-checklist abstention |
| Final targeted local recheck | **5/5 cases, 12 turns passed** | CG follow-up, loan exclusion and English/Hindi/Hinglish rank chains |
| Exact-repeat cache check | **25.882 s → 12.687 s** | Three → two model calls; grounding review retained |
| Hindi voice pipeline | **Passed**, two answer sources, 22,050 Hz / 7.47 s WAV | Synthesized question → Whisper → Ollama → VITS; Groq key empty and model downloads disabled |

The final recheck had a 23.711-second median per turn. Answers commonly took 20–50
seconds with partial CPU offloading on the 8 GB RTX 4060. These measurements do not
establish speed or quality parity with Groq. The full 25-case suite was not rerun after
the narrow follow-up fix; the targeted recheck is not a claim of 25/25 correctness.

The reporting-document question still abstains because indexed JoSAA pages contain
the checklist heading without its entries. This needs reviewed source extraction.
English/Hinglish audio still uses online Edge TTS; the completed Hindi smoke test
does not measure physical microphone accuracy or listening quality. The attempted
live Groq check remained rate-limited.

See the [local setup guide](../Institute-voice-agent/institute-assistant/docs/LOCAL_INFERENCE.md)
and [full local validation report](../Institute-voice-agent/institute-assistant/docs/LOCAL_MODEL_VALIDATION.md)
for configuration, model comparisons and saved evaluation records. Earlier dated
results below describe their original provider and code state.

## Conversation memory and cache — 2026-09-23

The shared agent now uses configurable complete-pair history (Demo 2 default: 10 previous
pairs) and persistent exact retrieval/draft caching. Every cached draft still receives a
grounding review. **116 agent tests and 15 Demo 2 tests passed (131 total).** No speech model,
dependency stack, source corpus or active knowledge release was changed.

One live exact-repeat sample returned the same cited ranks in **5.122 seconds cold** and
**2.641 seconds warm**, using **3 versus 2 logical model calls**. Both retrieval and draft
caches hit on the warm turn. The cold sample includes model initialization, and these two
observations are not a general performance benchmark. Earlier follow-ups resolved the
correct changed category/round, but the final review encountered a provider rate limit.
The spaced Hindi chain passed. Traced Hinglish rejections exposed skipped rank-basis lines
in model quotations; a narrow verified-cutoff source-span repair now passes the captured
failure replay and rejects altered or reordered evidence.
The final live Hinglish rerun passed all three turns with the correct retained dimensions,
answer language and source rows.

See the [memory/cache validation report](../Institute-voice-agent/institute-assistant/docs/RAG_MEMORY_CACHE_VALIDATION.md)
for commands, source inspection, limitations and further live follow-up results. The dated
knowledge-base and speech results below describe earlier runs.

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
