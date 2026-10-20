# REPORT 01 — Baseline and current architecture

Task: [01 Baseline and current architecture](01_BASELINE_AND_CURRENT_ARCHITECTURE.md). Date: 2026-10-20 (IST). Repository HEAD: `870e93c`. Hardware tier: **T0** (RTX 4060 Laptop 8 GB, i7-14650HX 24 threads without AVX-512, 31 GB RAM, Ollama 0.32.6, `qwen3.5:9b`).

Evidence labels follow [00_INDEX](00_INDEX.md): **[Measured-here]**, **[Reported]**, **[Estimated]**.

## Summary

Task 01 is a measurement task, so no product code was changed. I checked every code reference and number in chapter 01 against the repository at HEAD, recomputed the 120-turn benchmark statistics from the raw JSON, repeated the hardware and Ollama probes, and measured the speech stages that chapter 01 listed as "not measured" (verbalization, retrieval on the served release, VITS, Whisper, and five composed voice turns).

- **Reproduced:** every number in §4.1 (turn, stage and call-count statistics) matches the raw data exactly.
- **Not reproduced:** the "2.6× slower grammar" claim. On three real production requests the quote-enum grammar costs the same per token as no grammar (≈50 ms/token). Its real cost is a longer output, in one of three cases. This affects the executive summary and recommendation #4 in `00_INDEX.md`.
- **Moved since the chapter was written:**
  - The desktop now takes 1.4 GB of VRAM (was 2.7 GB), so the model sits 70–75% on GPU (was 55%) and decodes at 24–25 tok/s on short prompts (was 17.7).
  - Demo 2 now serves the new `kbb` knowledge-base release by default, not the legacy `kb_state` release that the chapter describes. That release has an empty critical-policy list, so optimisation O6 is inactive on the live system.
  - A FastAPI + Next.js front end appeared on 2026-10-19/20. Its "streaming" endpoint replays a finished answer word by word and does not stream tokens.
- **First speech numbers:** warm VITS synthesis has a real-time factor of about 0.16 (first sentence chunk ≈1.05 s). Whisper-small on CPU ran at about 0.22× real time, but with large unexplained outliers (2 of 9 clips took 11.6 and 16.4 s). Composed voice turns took 25.7 s (warm, short answer) to 74 s (long answer). The LLM agent accounts for most of that time.

## What was done

- Read chapters 00 and 01, `AGENTS.md`, the parent `idea/AGENTS.md`, and the code behind every reference in chapter 01 §1–3 and §7 (see "How it was done").
- Recomputed §4.1 from `code/demo2/data/upgrade-20260930/{baseline,candidate}/results.json` and `results-warmup.json`.
- Repeated the §4.3 probes: hardware, VRAM, Ollama CPU/GPU split, cold load, prefill, prefix reuse, decode speed, grammar cost.
- Replayed three real production generation requests with and without the quote-enum grammar.
- Measured verbalization, retrieval (served `kbb` release), VITS (cold, warm, second voice, first chunk, memory), and Whisper (CPU and `auto` device).
- Ran five composed voice turns on the live configuration with scratch state.
- Ran the repository test suites.
- Saved the scripts and raw results in `idea/FutureWork/report01_artifacts/` so the numbers can be regenerated.
- Wrote this report, including runnable scripts for the long tests that you will run later (last section).

No application code, configuration, model, or chapter document was modified (chapters 00 and 01 stay as they are, by instruction). The only existing file I edited is `idea/FutureWork/AGENTS.md`, to record the long-test rule. `git status` before and after shows only the pre-existing modifications to `00_INDEX.md` and `01_…md` and the untracked `AGENTS.md`, plus the new files listed under "Files changed".

## How it was done

### Verification of chapter 01 (code)

All 27 referenced source and data paths exist. The claims below were confirmed by reading the code.

| Claim in chapter 01 | Code evidence |
| --- | --- |
| `stream: False`, `think: False`, temperature 0, `repeat_penalty` 1.0, `num_ctx` 8192, `num_predict` 1600 | `llm.py::_invoke_local` (lines 175–200), `config.py` |
| `GET api/tags` before every model call; one global `RLock` | `llm.py::_invoke_local` |
| Grammar = JSON schema plus per-source `oneOf` quote enum | `llm.py::generation_schema`, `evidence_spans` |
| Review runs on every `answered` result, including draft-cache hits | `nodes.py::generate_answer_node`: the review call follows both branches |
| Critical-policy path = deterministic draft + 9B `CriticalReview` | `nodes.py` (`select_policy`, `call_model(… CriticalReview …)`) |
| Cache is exact-key SQLite, TTL 3600 s, 2000 entries, 64 MB, evicts by `ORDER BY hits, accessed` (least-frequently-used) | `cache.py`, `config.py` |
| RRF with k = 60 | `kb/search.py:148`, `retrieval.py:197`, `kbb/config.py: rrf_k = 60` |
| BM25 label error (chapter says "k1 = 2.5" is mislabelled) | `kb/search.py:139`: numerator 2.5, denominator 1.5·(0.25 + 0.75·L/avg), so k1 = 1.5, b = 0.75. Confirmed. |
| Chunk 350 / overlap 50 tokens | `config.py: KB_CHUNK_TOKENS`, `KB_OVERLAP_TOKENS` |
| Queue capacity 3 plus 1 active, 60 s queue timeout, 120 s turn timeout, one speech worker | `jobs.py::JobManager`, `settings.py` |
| Whisper beam 5, `vad_filter`, `no_speech_prob < 0.6`, 4 threads, RMS gate 0.002 | `speech.py::transcribe`, `settings.py` |
| VITS 220-char chunks, 0.12 s pause, voice cache of 2, CPU | `speech.py::_chunks`, `synthesize`, `settings.py` |
| Edge TTS only with explicit opt-in | `speech.py::make_audio` raises `SpeechError` unless `allow_online` |
| Streaming STT service not used by Demo 2 | `demo2/*.py` imports only `src.asr`, never `session.py` or `vad.py` |
| Documented numbers (36.36% coverage, 17.018 → 16.318 s, 5.122 → 2.641 s, 25.882 → 12.687 s, 52/48 and 32/68 splits, 23.711 and 34.187 s medians, 11.4/13.8 ms, 42/42, 92/93, 10/93, 3.65/4.51 s, 27,072 B) | Present in the cited `docs/*.md` and `VALIDATION.md` |

### Recomputed benchmark (§4.1)

`idea/FutureWork/report01_artifacts/fw01_recompute.py` (numpy, linear-interpolated percentiles) reproduces every §4.1 value. For example:

- Baseline turn p50/p95/max is 17.20 / 28.09 / 40.53 s, and the candidate is 14.51 / 30.39 / 44.30 s.
- Answered turns: 18.68 / 29.90 s (n = 78) and 17.49 / 40.44 s (n = 86).
- Call mixes are 78/13/29 and 58/44/18.

The first-turn figures (30.9 s with 11.2 s routing, and 35.9 s with 11.9 s) come from `baseline/results-warmup.json` and `candidate/results-warmup.json`. Chapter 01 does not name that source.

Extra statistics:

- The review call is a median 39.6% (baseline) / 39.9% (candidate) of the turn on 3-call turns.
- The median of the three model-stage sums on answered turns is 18.6 s (baseline).
- Per-language turn p50 is 17.0 / 17.1 / 17.6 s (English / Hindi / Hinglish, baseline).
- All 120 baseline and 120 candidate turns used `router_path = "llm"`.

### Hardware and Ollama probes (§4.3), repeated

Script `fw01_probe.py`, with the production options (`think: false`, `num_ctx` 8192, temperature 0). It measures prefill and decode from Ollama's own counters.

### Grammar replay

`fw01_grammar.py` ran three real questions through `agent_bridge.ask` and captured the generation request body. It replayed each body twice with the real `oneOf` quote-enum grammar and twice with the enum replaced by a plain `{source_id, quote}` object. The enum sizes were 495, 214 and 422 entries (40–71 kB of enum text). The runs had a warm prompt cache, so prefill is not comparable. The comparison is decode ms per token.

### Speech stages

`fw01_speech.py` ran with `DEMO2_DATA_DIR` set to a scratch directory:

- Verbalization: `verbalization.normalize` over the 78 answered baseline answers, 50 repetitions each.
- Retrieval: the real `assistant.retrieval.retrieve` on all 120 benchmark questions against the served `kbb` release.
- TTS: `speech.make_audio` on Hindi answers from the baseline (cold and warm), plus a second voice and the first sentence chunk.
- ASR: `speech.transcribe` on the VITS output of those answers (the only local source of Hindi speech).

`fw01_followup.py` isolated why `auto` falls back to CPU and re-scored retrieval on required terms. `fw01_e2e.py` ran five composed voice turns.

### Limits of the speech measurements

- ASR input is synthetic VITS speech, not microphone or native speech. The WER values (≈0.82) therefore say nothing about real accuracy. They are reported only because they show that the transcripts are too poor to drive the agent.
- In the composed turns the agent therefore receives the reference question text, and ASR is timed separately on the audio of the same question.
- English and Hinglish speech could not be tested, because the only local voice is Hindi VITS and Edge TTS is online. I did not use online services.

## Before vs. After

The "Before" column is chapter 01 as written (or the earlier recorded measurement). The "After" column is today's value.

### Reproduction of existing numbers

| Metric | Before (doc 01) | After (2026-10-20) | Change | Evidence label |
| --- | --- | --- | --- | --- |
| Baseline turn p50 / p95 / max (s) | 17.2 / 28.1 / 40.5 | 17.20 / 28.09 / 40.53 | none (reproduced) | [Measured-here] raw JSON recomputed |
| Candidate turn p50 / p95 / max (s) | 14.5 / 30.4 / 44.3 | 14.51 / 30.39 / 44.30 | none | [Measured-here] |
| Baseline answered p50 / p95 (n = 78) | 18.7 / 29.9 | 18.68 / 29.90 | none | [Measured-here] |
| Routing / generation / review p50 (s) | 3.80 / 7.18 / 7.41 | 3.795 / 7.177 / 7.413 | none | [Measured-here] |
| Retrieval p50 / p95 in the benchmark (ms) | 50 / 66 | 49.7 / 65.5 | none | [Measured-here] |
| Warm-up first turn (s) | 30.9 / 35.9 | 30.88 / 35.92 (`results-warmup.json`) | none, but source file now named | [Measured-here] |

### Hardware and model serving (T0)

| Metric | Before (doc 01, 2026-10-05) | After (2026-10-20) | Change | Evidence label |
| --- | --- | --- | --- | --- |
| VRAM used by desktop before model load | 2737 MiB | 1415–1437 MiB | −1.3 GB | [Measured-here] |
| Model split (CPU/GPU) | 45% / 55% | 25.5% / 74.5% (probe) and 30% / 70% (composed turns) | CPU share roughly halved | [Measured-here] |
| Decode, free text, short prompt | 17.7 tok/s | 24.2–25.3 tok/s (39.6–41.3 ms/token) | +37–43% | [Measured-here] |
| Decode, real 4.6–4.97k-token generation prompt | not measured | ≈50 ms/token (≈20 tok/s) | new | [Measured-here] |
| Cold model load | 8.3 s | 8.38 s | none | [Measured-here] |
| Prefill, cold (prompt length differs) | 1120 ms for 920 tokens | 1271 ms for 1316 tokens (≈1035 tok/s) | comparable | [Measured-here] |
| Identical prompt repeated | 111–138 ms | 78 ms | prefix fully reused | [Measured-here] |
| Same system prompt, different user message | 732 ms (≈35% saved) | 469 ms (≈63% saved; prompt shape differs) | reuse exists but partial | [Measured-here] |
| First token of system prompt changed | 1015 ms | 1180 ms | no reuse | [Measured-here] |
| Return to original prompt after another | 589 ms | 507 ms | slot partly overwritten | [Measured-here] |
| Quote-enum grammar penalty (per token) | 2.6× (157 vs 61 ms/token, synthetic 300-entry enum) | **1.0×** on 3 real payloads (50.1–51.5 enum vs 49.3–51.5 no-enum ms/token); 1.2× on a synthetic 300-entry enum | **claim not reproduced** | [Measured-here] |

Grammar replay detail (`fw01_grammar_result.json`, warm prompt cache):

| Case | Enum entries / chars | Decode tokens (enum / no enum) | ms per token (enum / no enum) |
| --- | --- | --- | --- |
| `tuition_english` | 495 / 71,214 | 73 / 73 | 50.1, 50.8 / 49.3, 51.5 |
| `cg_income_sc_english` | 214 / 40,534 | 367 / 197 | 51.5, 50.9 / 50.6, 51.3 |
| `semester1_fee_hindi` | 422 / 60,360 | 90 / 90 | 50.3, 50.5 / 50.4, 51.1 |

The enum does not slow tokens. In one of three cases it forces longer verbatim quotes, which means more tokens (367 vs 197). That is a cost in output length, not in speed. Replaying the same request body means prefill was served from the cache, so these runs say nothing about how the enum affects the prompt side.

### Speech and retrieval stages that were "not measured" (T0, scratch state)

| Stage | Before | After | Evidence label |
| --- | --- | --- | --- |
| Verbalization (`verbalization.normalize`), 78 answers | slide: 4.2 ms; README: < 5 ms | p50 0.22 ms, p95 0.42 ms, max 0.49 ms | [Measured-here] |
| Retrieval engine initialisation, `kbb` release (integrity check, BM25 build, E5 load) | 3.5 s / 2.8 s (benchmark warm-up, legacy release) | 2.9 s, then first query 35 ms | [Measured-here] |
| Retrieval warm, 120 benchmark questions, `kbb` release | 11.4 / 13.8 ms (legacy release, `VALIDATION.md`) | p50 23.2 ms, p95 118 ms, max 122 ms | [Measured-here] |
| Retrieval split | not reported | 69 of 120 under 50 ms (42 exact-rank SQL lookups plus others); 43 of 120 at 100–123 ms (semantic path with CPU query embedding) | [Measured-here] |
| Retrieval answerability proxy | 92/93 recall@6 (legacy release, different metric) | required terms present in top-3 / top-6 / top-8 passages: 93 / 95 / 96 of 96 (not comparable to 92/93) | [Measured-here] |
| VITS first load plus first synthesis (Female, CPU) | greeting 3.65 s (2026-09-18); 14.39 s cold (2026-09-30) | 14.13 s for 6.5 s of audio; process RSS 1.13 → 2.24 GB | [Measured-here] |
| VITS warm synthesis | 0.86–0.92 s for 6.3–6.7 s audio (2026-09-30) | p50 1.39 s over 9 answers of 63–194 chars (6.2–13.8 s audio); RTF p50 0.157; ≈85 chars/s | [Measured-here] |
| VITS first sentence chunk | not measured | 0.76–1.50 s (p50 1.05 s) for 63–126 chars | [Measured-here] |
| VITS second voice | 1.66 s cold, 0.92 s warm (2026-09-30) | 2.18 s cold, 1.43 s warm; RSS 3.12 GB with both voices | [Measured-here] |
| Hindi answers the local voice can speak | not measured | 18 of 23 unique answered Hindi answers (78%); 5 rejected for Latin letters (e.g. "Mess Advance", "PM Vidyalaxmi") | [Measured-here] |
| Whisper small, CPU int8, cold (load + first clip) | 2.10 s on one 6.3 s clip (2026-09-30) | 3.17 s on a 6.5 s clip | [Measured-here], synthetic audio |
| Whisper small, CPU int8, warm | 450–750 ms (README) | p50 1.99 s for 5–14 s clips (RTF ≈0.22); 2 of 9 clips took 11.6 s and 16.4 s | [Measured-here], synthetic audio |
| Whisper `DEMO2_STT_DEVICE=auto` (the value in `demo2/.env`) | README: "CPU int8" | CUDA model loads, then transcription fails (`libcublas.so.12` not found); code falls back to CPU int8. Effective device: CPU | [Measured-here] |
| Whisper WER on synthetic Hindi speech | slide: 45% → 12% (Chhattisgarhi) | mean 0.82 on VITS audio; not a valid system WER | [Measured-here], caveated |
| MMS-1B `hne` ASR | slide 1850 ms; README 2.2 GB fp16 on CUDA | **not measured**: `facebook/mms-1b-all` is not in the local Hugging Face cache; the demo default would run it on CPU float32 | open |
| Composed voice turn, warm, short answer | slide: 21.2 s; README: 13–28 s | ASR 1.4 s + agent 23.1 s + TTS 1.2 s = text at 24.4 s, audio complete at 25.7 s (n = 1) | [Measured-here] |
| Composed voice turn, cold first turn | slide: 20–40 s | ASR 3.1 s + agent 38.2 s (routing 14.8 s incl. model load) + TTS 1.2 s = 42.5 s | [Measured-here] |
| Composed voice turns, other three | not measured | 74.4 s (long income-certificate answer: agent 54.5 s, ASR 16.9 s); 42.4 s; 15.2 s (insufficient evidence, one model call) | [Measured-here] |

Composed-turn detail (`fw01_e2e_result.json`, synthetic Hindi questions, reference text sent to the agent):

| # | Case | ASR (s) | Agent (s) | Model calls | TTS (s) | Audio complete (s) |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | `semester1_fee_hindi` (cold) | 3.1 | 38.2 | 3 | 1.2 | 42.5 |
| 1 | `classes_hindi` | 1.4 | 23.1 | 3 | 1.2 | 25.7 |
| 2 | `cg_income_sc_hindi` | 16.9 | 54.5 | 3 | 3.0 | 74.4 |
| 3 | `loan_repayment_hindi` | 10.0 | 30.4 | 3 | 2.0 | 42.4 |
| 4 | `reporting_checklist_hindi` | 8.9 | 5.0 | 1 (insufficient) | 1.4 | 15.2 |

These are five single runs on a loaded laptop, not a distribution. The agent is 72–90% of every answered turn. The ASR times on turns 2–4 (8.9–16.9 s for 4–9 s clips) are in the same outlier range as the two slow clips in the isolated run. They coincide with the 9B model being resident, but I did not isolate whether that is contention or decoder loops on synthetic speech.

### Status of chapter 01 claims

| Chapter 01 claim | Status |
| --- | --- |
| §4.1 benchmark values | **Confirmed**, exactly |
| "Nothing streams" | **Still true for latency.** A simulated word-replay SSE endpoint now exists (see Issues, #3) |
| §3 O6 critical-policy shortcut removes the generation call | **True in code and in the Sept 30 candidate run; inactive on the live `kbb` release** (empty rule list) |
| §3 O4/O5 describe the legacy `SearchEngine` and `kb_state` | **Outdated for Demo 2:** the default is the `kbb` engine (see Issues, #2) |
| "No speech benchmark exists" | **Partly wrong:** `demo2/evaluate_speech.py` and `data/upgrade-20260930/clone-speech/results.json` (2026-09-30) hold VITS and Whisper timings on synthetic speech. What does not exist is any real microphone or native-speaker measurement, and `VALIDATION.md` says so |
| "About 2.7 GB of VRAM already taken, 45–52% on CPU" | **True on 2026-10-05; 1.4 GB and 25–30% today.** The split depends on what the desktop is doing |
| "2.6× grammar penalty" | **Not reproduced** (see above) |
| Prefix reuse only for byte-identical prompts | **Refined:** reuse of the shared system prefix is partial (≈63% of prefill saved when only the user message changes), none when the first token changes |
| BM25 "k1 = 2.5" is mislabelled | **Confirmed** (k1 = 1.5, b = 0.75) |
| Two test totals coexist (316 vs 159) | **Confirmed, and both are now stale** (see Test results) |
| README stage latency table | **Not reproduced:** it lists review as 3–5 s warm (measured 6.8–7.4 s median, up to 25 s), STT at 450–750 ms warm (measured ≈2 s on CPU), and "MMS fp16 on CUDA, ≈2.2 GB" (the demo runs on CPU) |

## Files changed

```
Created:  idea/FutureWork/REPORT_01_BASELINE_AND_CURRENT_ARCHITECTURE.md — this report
Created:  idea/FutureWork/report01_artifacts/fw01_recompute.py — benchmark percentile recomputation
Created:  idea/FutureWork/report01_artifacts/fw01_recompute_result.json — output of the above
Created:  idea/FutureWork/report01_artifacts/fw01_probe.py — hardware / Ollama prefill, decode, synthetic-grammar probe
Created:  idea/FutureWork/report01_artifacts/fw01_probe_result.json — output of the above
Created:  idea/FutureWork/report01_artifacts/fw01_grammar.py — replay of real generation requests with and without the quote enum
Created:  idea/FutureWork/report01_artifacts/fw01_grammar_result.json — output of the above
Created:  idea/FutureWork/report01_artifacts/fw01_speech.py — verbalization, retrieval, VITS, Whisper measurements
Created:  idea/FutureWork/report01_artifacts/fw01_speech_result.json — output of the above
Created:  idea/FutureWork/report01_artifacts/fw01_followup.py — Whisper CUDA fallback check; required-term retrieval check
Created:  idea/FutureWork/report01_artifacts/fw01_ret2.py — retrieval latency split (exact-SQL vs semantic)
Created:  idea/FutureWork/report01_artifacts/fw01_e2e.py — five composed voice turns
Created:  idea/FutureWork/report01_artifacts/fw01_e2e_result.json — output of the above
Modified: idea/FutureWork/AGENTS.md — added the rule that long tests are written as scripts in the report and run by the user
```

Pre-existing, not touched by me: modified `00_INDEX.md` and `01_BASELINE_AND_CURRENT_ARCHITECTURE.md`; untracked `AGENTS.md`. Scratch state lived in `/tmp/fw01_*` and was removed afterwards.

To rerun: the scripts hard-code `/tmp` scratch paths and expect to run from `code/demo2` with the `minor` environment; `fw01_recompute.py` takes the benchmark directory as an argument and runs from the repository root.

## Issues encountered

1. **Grammar penalty not reproduced (open, affects `00_INDEX.md`).** The chapter's 2.6× figure came from one synthetic 300-entry enum on a 45/55 split. My synthetic enum gave 1.2×. Three real production requests gave 1.0×. The executive summary line "The quote-enum JSON grammar made decoding 2.6× slower", the matching entry in Top-10 #4 ("Removes the 2.6× grammar penalty [Measured-here]"), and §4.3 / §7 of chapter 01 should be reworded: the grammar costs output length (verbatim quotes of up to 1500 characters), not per-token speed. Chapters 00 and 01 were deliberately not edited; this report is the record of the correction.
2. **Demo 2 now serves a different knowledge base from the one chapter 01 describes (open, documentation).**
   - `settings.configure_agent` defaults `DEMO2_KB_BACKEND` to `kbb` and points `KB_STATE_DIR` at `code/knowledgebaseenhanced/data/kbb/serving`. The active release is `20261014T005813186766Z` (122 documents, 2055 evidence blocks, 5153 retrieval units: 3378 row, 750 section, 643 table, 382 page; 611 cutoff and 722 structured records; `intfloat/multilingual-e5-small`; RRF k = 60; BM25 in memory).
   - A cross-encoder reranker (`BAAI/bge-reranker-v2-m3`, cached locally) is configured but disabled (`rerank: False`).
   - `policies.json` in that release contains `{"rules": []}`, so the deterministic critical-policy path is inactive.
   - The benchmark in §4.1 ran on the legacy `kb_state` release. Whether the same turn-time profile holds on the `kbb` release has not been measured. The comment block in `demo2/.env` ("Defaults share institute-assistant/kb_state") is stale.
   - Chapter 01 §1, §2, §3 (O4–O6) and §5 describe the legacy path only.
3. **Front end and "streaming" endpoint (open, documentation).** `code/demo2/api_server.py` (FastAPI) and `app/voiceagent` (Next.js) arrived in commits `63f13b8` to `870e93c` (2026-10-19/20). `GET /api/turns/{session}/{turn}/stream` waits until the full `answer_text` exists, then emits it word by word with a 20 ms sleep per word. The docstring says "token/word-by-word inferencing output", but nothing is generated incrementally. This adds a typing effect, not lower latency. The model call is still `stream: False`. Chapter 01 should list the new front end and state this limitation, because it is easy to mistake for streaming in a demonstration.
4. **Whisper `auto` falls back to CPU only after a failed CUDA attempt (open).** With `DEMO2_STT_DEVICE=auto` in `demo2/.env`, `WhisperModel(device="cuda")` loads, then the first transcription fails for lack of `libcublas.so.12`; the code catches this and reloads on CPU. Effective behaviour is CPU int8, as the README says, but the first call pays a wasted GPU load and a CUDA context. If CUDA 12 cuBLAS were installed, Whisper would claim GPU memory the 9B model needs; the 70% (vs 74.5%) GPU share seen in the composed run suggests the voice process already takes some. I did not isolate that effect.
5. **Whisper tail latency (open).** In the isolated run, 2 of 9 warm clips took 11.6 s and 16.4 s (RTF 1.7–1.8) against about 2 s for the rest; transcripts of those clips had WER 0.94 and 1.0. Likely cause: beam-5 decoding loops on synthetic speech. I could not confirm this with real speech, so the effect on real recordings is unknown.
6. **MMS Chhattisgarhi ASR not measured (open, blocked).** `facebook/mms-1b-all` is not in the local Hugging Face cache (only `Systran/faster-whisper-small` and `BAAI/bge-reranker-v2-m3`). Measuring it needs a download of several GB, which I did not start without your approval. In Demo 2 it would run on CPU float32 by default, not CUDA fp16 as the README states.
7. **Not measured: English and Hinglish speech paths, and any native or microphone speech.** The only local voice is Hindi VITS, and Edge TTS needs the network. No ASR accuracy figure here should be quoted for the system.
8. **Composed turns used the reference question text, not the transcript.** Synthetic ASR WER was about 0.82, so feeding the transcript would have measured garbage input. The ASR time was measured on the same audio.
9. **Retrieval timing split.** 43 of 120 questions take 100–123 ms and the rest under 50 ms. The embedder call took 111 ms for a new text and 6 ms when repeated; I found no query cache in `kbb/index.py` and did not isolate the cause (possibly CPU kernel set-up for a new input shape).
10. **`jiwer` is not installed.** I wrote a small word-error-rate function in `fw01_speech.py` instead of installing a package.
11. **Resolved:** chapter 01 gave the first-turn warm-up figures without naming the source. They are in `results-warmup.json`.

## Dependencies and prerequisites

- No packages were installed or changed in the `minor` environment. Versions seen: `torch 2.13.0+cu130` (the README badge says 2.1.2), `faster-whisper 1.2.1`, `ctranslate2 4.8.1`, `TTS 0.22.0`, `chromadb 0.5.23`, `numpy 1.26.4`.
- No earlier phase is assumed. Task 01 is the baseline.
- Hardware: T0 only. Ollama must be running with `qwen3.5:9b`. The model was unloaded after each probe, so the machine is back in its original state.
- Re-measurements depend on desktop VRAM. The values above were taken with 1.4 GB used by the desktop session.

## Next steps

Chapters 00 and 01 are left unchanged on purpose (instruction from the project owner). Every correction and new finding is recorded in this report only.

1. **Run the long tests** in the last section of this report (`L0`–`L7`). They replace the open measurements below and are designed to be run by you, not by an agent.
2. **Benchmark on the live `kbb` release (L1).** This gives a turn-time baseline that matches what the demo serves today. Deciding whether to author critical-policy rules for the `kbb` release is a Task 06 matter.
3. **Task 05 (LLM serving):**
   - Start from the new T0 floor of about 24 tok/s at short prompts and about 20 tok/s at 5k context, not 17.7.
   - Use the GPU-share sweep (L7) to re-estimate the benefit of fitting the whole model on the GPU.
   - Use the grammar replay (L6) to confirm that the cost of the quote format is output length, then measure a shorter format (source ID plus span index).
4. **Task 12 (evaluation):** record real microphone and native Hindi/Hinglish/Chhattisgarhi clips and run L4. Until then, ASR latency and accuracy remain unmeasured, and the Whisper tail-latency issue (L3) cannot be settled on real speech.
5. **MMS-1B `hne` (L2):** needs a multi-GB download; run it with `ALLOW_DOWNLOAD=1` when you are ready.
6. **Decide on `DEMO2_STT_DEVICE`.** Set it to `cpu` explicitly, or install CUDA 12 cuBLAS and re-check the VRAM impact before enabling GPU Whisper.

## Test results

Commands, run at HEAD with the `minor` environment and no test-created changes in `git status`:

```bash
cd code/demo2 && python -m pytest -q -p no:cacheprovider                              # 44 passed in 4.08 s
cd code/Institute-voice-agent/institute-assistant && python -m pytest -q -p no:cacheprovider   # 309 passed in 11.09 s
cd code/knowledgebaseenhanced && python -m pytest -q -p no:cacheprovider               # 41 passed in 3.21 s
```

- **394 tests passed, 0 failed** across Demo 2, the institute assistant and the `kbb` package.
- Not run: `code/demo` (Kisan Saathi, 49 tests collected) and `code/STT/stt-service` (no tests collected; collection took 103 s).
- The totals in `README.md` and `VALIDATION.md` ("316" and "159") are stale. The current counts for the same two suites are 44 + 309 = 353.
- The measurement scripts themselves are not unit tests. Their outputs are the JSON files in `report01_artifacts/`.
- Long tests (the 120-turn benchmark, MMS, real-speech evaluation and others) were **not run by me**. Their scripts are in the last section; you will run them.

## Long-running tests (to be run by the user later)

I did not run anything in this section. The scripts are complete and were only syntax-checked (`py_compile`, `bash -n`) and unpacked once to confirm the paths resolve. Each test closes a gap named in "Issues encountered" or "Next steps".

### Tests, cost and pass criteria

| ID | Question it answers | Approx. time | Needs | Pass / read-out criterion |
| --- | --- | --- | --- | --- |
| L0 | Do all five test suites pass at the current HEAD? | 5 min | `minor` env | All pass. Reference: demo2 44, institute-assistant 309, kbb 41 (all passed on 2026-10-20); `code/demo` has 49 collected; `STT/stt-service` collected none. Record any failure. |
| L1 | What is the turn-time and answer-quality baseline on the **live `kbb` release**? (Issue #2) | about 40 min | Ollama + `qwen3.5:9b`, GPU idle | `errors = 0`; `false_answer_on_unanswerable` not higher than the legacy baseline; `answerable_answered_rate` not lower than the legacy baseline; `critical_policy_turns = 0` (confirms the empty rule list). Turn p50 is reported against 17.2 s (legacy baseline) and 14.5 s (legacy candidate), with no threshold. |
| L2 | How fast and how large is MMS-1B `hne` on CPU float32 and on CUDA fp16? (Issue #6) | 10 min plus download | Several GB download; `ALLOW_DOWNLOAD=1` | Read-out only: load time, RSS, GPU delta, warm RTF per clip. Timing is valid; WER on synthetic speech is not. |
| L3 | Is the Whisper tail latency (10–17 s on short clips) caused by temperature fallback? (Issue #5) | about 15 min | LLM unloaded | Hypothesis holds if `no_temperature_fallback` has `n_rtf_over_1 = 0` and `n_temperature_fallback = 0` while `production` shows both greater than 0, with `wer_mean` not worse. |
| L4 | What are real-speech latency, WER and CER per language? (Issue #7) | recording time plus 10 min | Your recordings and `manifest.tsv` | Read-out only: per-language p50/p95 seconds, RTF, mean WER and CER, and the count of empty transcripts. |
| L5 | What is the distribution of composed voice turns (ASR + agent + TTS)? | about 30–45 min | Ollama, GPU idle | Read-out: p50/p95 of `text_ready_s` and `audio_done_s`; the agent's share of the turn; the rate of answers the local voice cannot speak. |
| L6 | Does the quote-enum grammar slow decoding per token across 20 real requests? (Issue #1) | about 30 min | Ollama | Penalty absent if the median `ms_per_token` ratio (enum / no enum) is between 0.9 and 1.1. The median decode-token ratio shows the output-length cost. |
| L7 | How do decode and prefill speed change with the share of the model on the GPU, at 1.3k and 4.5k context? | about 10 min | Ollama | Read-out: the tok/s curve and where it flattens. This is the evidence for Task 05 recommendation #1. |

Conditions that change the answers, and that you should note when you run them: how much VRAM the desktop uses (the runner prints it to `results/preflight.txt`), whether a browser or other GPU applications are open, and whether the laptop is on mains power. L1, L5, L6 and L7 need the GPU idle apart from the desktop session.

### Setup

Run from the repository root `Minor/`. The scripts are stored as code blocks in this file. Unpack them with this command, which writes them to `idea/FutureWork/report01_artifacts/long_runs/scripts/`:

```bash
python3 - <<'EOF'
import re, pathlib
report = pathlib.Path("idea/FutureWork/REPORT_01_BASELINE_AND_CURRENT_ARCHITECTURE.md").read_text()
target = pathlib.Path("idea/FutureWork/report01_artifacts/long_runs/scripts")
target.mkdir(parents=True, exist_ok=True)
for name, body in re.findall(r"\*\*File:\*\* `([^`]+)`\n\n```[a-z]*\n(.*?)\n```", report, re.S):
    (target / name).write_text(body + "\n")
    print("wrote", name)
EOF
```

Then:

```bash
cd idea/FutureWork/report01_artifacts/long_runs/scripts
bash run_all_long_tests.sh                       # L0 L1 L3 L5 L6 L7, about 2 hours in total
bash run_all_long_tests.sh L1                    # one test only (L1 is resumable with --resume)
ALLOW_DOWNLOAD=1 bash run_all_long_tests.sh L2   # MMS download, several GB
bash run_all_long_tests.sh L4                    # after creating results/L4_recordings/manifest.tsv
```

Outputs go to `idea/FutureWork/report01_artifacts/long_runs/results/`: one folder per test with `summary.json` (and raw `rows.jsonl` or `results.json`), plus `logs/` and `preflight.txt`. Scratch state for Demo 2 stays under `results/<test>_scratch/`, so the repository's `code/demo2/data/` is not touched. To fold results into this report later, give the `summary.json` files to the agent.

**File:** `run_all_long_tests.sh`

```bash
#!/usr/bin/env bash
# Run the Task 01 long tests one after another and keep a log per test.
#   bash run_all_long_tests.sh                 # L0 L1 L3 L5 L6 L7
#   bash run_all_long_tests.sh L1 L7           # selected tests only
#   ALLOW_DOWNLOAD=1 bash run_all_long_tests.sh L2   # MMS download (several GB)
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../../../.." && pwd)"
RES="$HERE/../results"
PY="${PY:-$HOME/miniconda3/envs/minor/bin/python}"
MODEL="${OLLAMA_MODEL:-qwen3.5:9b}"
OLLAMA="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
mkdir -p "$RES/logs"
cd "$HERE"

unload() { curl -s "$OLLAMA/api/generate" -d "{\"model\":\"$MODEL\",\"keep_alive\":0}" >/dev/null 2>&1; sleep 2; }

preflight() {
  {
    date -Is; echo "repo head: $(git -C "$REPO" rev-parse --short HEAD)"; echo "python: $PY"
    curl -s "$OLLAMA/api/ps" || echo "OLLAMA NOT REACHABLE"; echo
    nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
    nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
    echo "load average: $(cut -d' ' -f1-3 /proc/loadavg)"; df -h "$RES" | tail -1
  } | tee "$RES/preflight.txt"
  curl -sf "$OLLAMA/api/tags" >/dev/null || { echo "Start ollama serve first."; exit 1; }
  echo "Close browsers/Telegram/Steam first for comparable numbers; record what stays open."
}

L0() {  # all test suites (about 5 min; the STT collection alone takes ~100 s)
  for d in code/demo2 code/Institute-voice-agent/institute-assistant code/knowledgebaseenhanced code/demo code/STT/stt-service; do
    echo "== $d"; (cd "$REPO/$d" && timeout 1200 "$PY" -m pytest -q -p no:cacheprovider 2>&1 | tail -4)
  done
}
L1() {  # 120-turn benchmark on the live kbb release (about 40 min); resumable
  unload
  OUTDIR="$RES/L1_kbb_benchmark"; mkdir -p "$OUTDIR"
  ( cd "$REPO/code/demo2" && "$PY" evaluate_upgrade.py --agent-root ../Institute-voice-agent/institute-assistant \
      --kb-state ../knowledgebaseenhanced/data/kbb/serving --cases evaluation/upgrade-20260930/cases.json \
      --output "$OUTDIR/results.json" --resume ) && "$PY" L1_stats.py "$OUTDIR/results.json"
  ollama_ps_after=$(curl -s "$OLLAMA/api/ps"); echo "$ollama_ps_after" > "$OUTDIR/ollama_ps_after.json"; unload
}
L2() {  # MMS-1B hne; downloads weights only with ALLOW_DOWNLOAD=1
  unload; flag=""; [ "${ALLOW_DOWNLOAD:-0}" = "1" ] && flag="--allow-download"
  "$PY" L2_mms_hne.py $flag
}
L3() { unload; "$PY" L3_whisper_tail.py; }
L4() { unload; "$PY" L4_real_speech_eval.py; }
L5() { "$PY" L5_voice_turns.py; }
L6() { "$PY" L6_grammar_replay.py; }
L7() { "$PY" L7_gpu_layers_sweep.py; }

TESTS=("$@"); [ ${#TESTS[@]} -eq 0 ] && TESTS=(L0 L1 L3 L5 L6 L7)
preflight
for t in "${TESTS[@]}"; do
  echo "=== $t started $(date -Is)" | tee -a "$RES/logs/run.log"
  start=$SECONDS; "$t" 2>&1 | grep -vE "^ >|^ \||Warning" | tee "$RES/logs/$t.log"
  echo "=== $t finished in $((SECONDS - start)) s (exit ${PIPESTATUS[0]})" | tee -a "$RES/logs/run.log"
done
unload
echo "Done. Summaries: $RES/*/summary.json   Logs: $RES/logs"
```

**File:** `lt_common.py`

```python
"""Shared helpers for the Task 01 long-running tests. Import only; never run directly."""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

# scripts -> long_runs -> report01_artifacts -> FutureWork -> idea -> Minor
REPO = Path(__file__).resolve().parents[5]
CODE = REPO / "code"
DEMO2 = CODE / "demo2"
RESULTS = Path(__file__).resolve().parents[1] / "results"
CASES = DEMO2 / "evaluation/upgrade-20260930/cases.json"
OLLAMA = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")


def pct(values, q):
    return float(np.percentile(np.asarray(list(values), dtype=float), q)) if len(list(values)) else float("nan")


def edit_distance(ref, hyp):
    row = list(range(len(hyp) + 1))
    for i in range(1, len(ref) + 1):
        prev, row[0] = row[0], i
        for j in range(1, len(hyp) + 1):
            cur = row[j]
            row[j] = min(row[j] + 1, row[j - 1] + 1, prev + (ref[i - 1] != hyp[j - 1]))
            prev = cur
    return row[len(hyp)]


def normalize_text(text):
    # Do not use \w: it drops Devanagari vowel signs (combining marks).
    return re.sub(r"\s+", " ", re.sub(r"[.,!?;:\"'()\[\]।]", " ", text.casefold())).strip()


def wer(ref, hyp):
    r, h = normalize_text(ref).split(), normalize_text(hyp).split()
    return edit_distance(r, h) / max(len(r), 1)


def cer(ref, hyp):
    r, h = normalize_text(ref).replace(" ", ""), normalize_text(hyp).replace(" ", "")
    return edit_distance(list(r), list(h)) / max(len(r), 1)


def smi_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip()
    return int(out.splitlines()[0]) if out else None


def ollama_post(path, body, timeout=900):
    req = urllib.request.Request(OLLAMA + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = json.loads(response.read())
    data["_wall_s"] = time.monotonic() - started
    return data


def ollama_ps():
    data = json.loads(urllib.request.urlopen(OLLAMA + "/api/ps", timeout=10).read())
    return [{"name": m["name"], "size_gb": round(m["size"] / 1e9, 2), "vram_gb": round(m["size_vram"] / 1e9, 2),
             "gpu_pct": round(100 * m["size_vram"] / m["size"], 1), "context": m.get("context_length")}
            for m in data.get("models", [])]


def ollama_unload():
    try:
        ollama_post("/api/generate", {"model": MODEL, "keep_alive": 0}, timeout=60)
    except Exception as error:  # already unloaded or server down; callers re-check with ollama_ps
        print("unload warning:", type(error).__name__, flush=True)
    time.sleep(2)


def env_snapshot():
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    return {"date": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "git_head": head, "gpu_mem_used_mib": smi_mib(),
            "ollama_ps": ollama_ps(), "loadavg": os.getloadavg()}


def setup_demo2(tag, extra_env=None):
    """Point every Demo 2 store at a scratch directory, then import settings and speech."""
    scratch = RESULTS / f"{tag}_scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ["DEMO2_DATA_DIR"] = str(scratch)
    os.environ.update(extra_env or {})
    os.chdir(DEMO2)
    for path in (str(DEMO2),):
        if path not in sys.path:
            sys.path.insert(0, path)
    import settings as cfg
    cfg.configure_agent()
    if str(cfg.AGENT_ROOT) not in sys.path:
        sys.path.insert(0, str(cfg.AGENT_ROOT))
    import speech
    return cfg, speech


def read_jsonl(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def append_jsonl(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_cases():
    return json.loads(CASES.read_text())


def speakable_hindi_cases(cfg_speech):
    """Answerable Hindi benchmark questions that the local VITS voice can read (no Latin letters)."""
    speech = cfg_speech
    out = []
    for case in load_cases():
        if case["language"] == "hindi" and case["expected"] == "answerable":
            try:
                speech.prepare_speech(case["question"], "Female")
            except Exception:
                continue
            out.append(case)
    return out
```

**File:** `L1_stats.py`

```python
"""L1 statistics: compare a new 120-turn benchmark run with the recorded legacy-release runs.
Usage: python L1_stats.py RESULTS_JSON   (expects RESULTS_JSON's sibling *-warmup.json)"""
import json
import sys
from collections import Counter
from pathlib import Path

from lt_common import CASES, DEMO2, normalize_text, pct

OLD = DEMO2 / "data/upgrade-20260930"


def stats(path):
    rows = json.loads(Path(path).read_text())
    cases = {c["id"]: c for c in json.loads(CASES.read_text())}
    answered = [r for r in rows if r["response_status"] == "answered"]
    stage = lambda key: [r["rag_metrics"]["stage_ms"][key] for r in rows if key in (r.get("rag_metrics") or {}).get("stage_ms", {})]
    three = [r for r in rows if (r.get("rag_metrics") or {}).get("model_calls") == 3]
    answerable = [r for r in rows if cases[r["id"]]["expected"] == "answerable"]
    unanswerable = [r for r in rows if cases[r["id"]]["expected"] != "answerable"]
    term_ok = 0
    term_n = 0
    for r in answerable:
        terms = cases[r["id"]].get("required_terms") or []
        if r["response_status"] == "answered" and terms:
            text = normalize_text(r["answer_text"] + " " + " ".join(s["quote"] for s in r.get("sources") or []))
            term_n += 1
            term_ok += all(normalize_text(t) in text for t in terms)
    warm = Path(path).with_name(Path(path).stem + "-warmup.json")
    return {
        "n": len(rows),
        "turn_s_p50_p95_max": [round(pct([r["seconds"] for r in rows], 50), 2), round(pct([r["seconds"] for r in rows], 95), 2),
                               round(max(r["seconds"] for r in rows), 2)],
        "answered_n": len(answered),
        "answered_s_p50_p95": [round(pct([r["seconds"] for r in answered], 50), 2), round(pct([r["seconds"] for r in answered], 95), 2)],
        "routing_s_p50": round(pct(stage("routing_model"), 50) / 1000, 2),
        "retrieval_ms_p50_p95": [round(pct(stage("retrieval"), 50), 1), round(pct(stage("retrieval"), 95), 1)],
        "generation_s_p50_p95_n": [round(pct(stage("generation_model"), 50) / 1000, 2), round(pct(stage("generation_model"), 95) / 1000, 2), len(stage("generation_model"))],
        "review_s_p50_p95_n": [round(pct(stage("review_model"), 50) / 1000, 2), round(pct(stage("review_model"), 95) / 1000, 2), len(stage("review_model"))],
        "model_calls": dict(sorted(Counter((r.get("rag_metrics") or {}).get("model_calls") for r in rows).items(), key=lambda kv: str(kv[0]))),
        "status": dict(Counter(r["response_status"] for r in rows)),
        "critical_policy_turns": sum(bool((r.get("rag_metrics") or {}).get("critical_policy")) for r in rows),
        "errors": sum(r["response_status"] == "error" for r in rows),
        "answerable_answered_rate": round(sum(r["response_status"] == "answered" for r in answerable) / max(len(answerable), 1), 3),
        "false_answer_on_unanswerable": sum(r["response_status"] == "answered" for r in unanswerable),
        "required_terms_in_answer_or_quotes": [term_ok, term_n],
        "review_share_of_turn_median_3call": round(float(pct([r["rag_metrics"]["stage_ms"]["review_model"] / 1000 / r["seconds"] for r in three], 50)), 3) if three else None,
        "warmup": json.loads(warm.read_text()) if warm.exists() else None,
    }


if __name__ == "__main__":
    new_path = Path(sys.argv[1])
    summary = {"new_kbb_run": stats(new_path), "recorded_legacy_baseline": stats(OLD / "baseline/results.json"),
               "recorded_legacy_candidate": stats(OLD / "candidate/results.json")}
    (new_path.parent / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
```

**File:** `L2_mms_hne.py`

```python
"""L2: Meta MMS-1B 'hne' (Chhattisgarhi) ASR latency and memory on CPU float32 and CUDA float16.
Needs facebook/mms-1b-all: several GB of downloads. Pass --allow-download to permit network access;
without it the script runs offline and stops with a clear message if the weights are not cached.
Input is synthetic VITS speech (the only local Chhattisgarhi audio): timing is meaningful, WER is not.
Usage: python L2_mms_hne.py [--allow-download] [--devices cpu,cuda] [--reps 3]"""
import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
import psutil
import soundfile as sf

from lt_common import CODE, RESULTS, DEMO2, ollama_unload, pct, smi_mib

parser = argparse.ArgumentParser()
parser.add_argument("--allow-download", action="store_true")
parser.add_argument("--devices", default="cpu,cuda")
parser.add_argument("--reps", type=int, default=3)
parser.add_argument("--child", action="store_true")
parser.add_argument("--device", default="cpu")
args = parser.parse_args()
out = RESULTS / "L2_mms_hne"
clip_dir = out / "clips"

if args.child:
    os.chdir(CODE / "STT/stt-service")
    sys.path.insert(0, ".")
    process = psutil.Process()
    before_mib, started = smi_mib(), time.perf_counter()
    from src.asr import ChhattisgarhiMMSEngine
    engine = ChhattisgarhiMMSEngine()
    result = {"device": args.device, "load_s": round(time.perf_counter() - started, 1), "rss_gb": round(process.memory_info().rss / 2**30, 2),
              "gpu_mem_delta_mib": (smi_mib() or 0) - (before_mib or 0), "clips": []}
    manifest = json.loads((clip_dir / "manifest.json").read_text())
    for item in manifest:
        audio, rate = sf.read(clip_dir / item["file"], dtype="float32")
        assert rate == 16000
        times = []
        text = ""
        for _ in range(args.reps + 1):  # first call is warm-up
            transcript = engine.transcribe(audio, fast=False)
            times.append(transcript.inference_ms / 1000)
            text = transcript.text
        result["clips"].append({"file": item["file"], "audio_s": item["audio_s"], "first_call_s": round(times[0], 3),
                                "warm_s_median": round(float(np.median(times[1:])), 3), "rtf": round(float(np.median(times[1:])) / item["audio_s"], 3),
                                "text_preview": text[:80]})
    result["rss_gb_after"] = round(process.memory_info().rss / 2**30, 2)
    print("RESULT " + json.dumps(result, ensure_ascii=False))
    sys.exit(0)

# parent: build clips with the local Chhattisgarhi VITS voice, then run one child process per device
from lt_common import setup_demo2
ollama_unload()
cfg, speech = setup_demo2("L2")
base = json.loads((DEMO2 / "data/upgrade-20260930/baseline/results.json").read_text())
texts = []
for row in base:
    if row["response_status"] == "answered" and row["language"] == "hindi" and row["answer_text"] not in texts:
        try:
            speech.prepare_speech(row["answer_text"], "Female")
            texts.append(row["answer_text"])
        except Exception:
            pass
clip_dir.mkdir(parents=True, exist_ok=True)
manifest = []
for index, text in enumerate(texts[:8]):
    audio = speech.make_audio(text, "hindi", "Female")
    pcm = speech.decode_audio(audio["data"])
    name = f"clip{index}.wav"
    sf.write(clip_dir / name, pcm, 16000, subtype="PCM_16")
    manifest.append({"file": name, "audio_s": round(len(pcm) / 16000, 2), "reference": audio["spoken_text"]})
(clip_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
results = []
for device in args.devices.split(","):
    env = {**os.environ, "STT_LANGUAGE": "hne", "STT_DEVICE": device, "STT_MMS_DTYPE": "float16" if device == "cuda" else "float32"}
    if not args.allow_download:
        env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    cmd = [sys.executable, __file__, "--child", "--device", device, "--reps", str(args.reps)]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=str(DEMO2))
    line = next((l for l in proc.stdout.splitlines() if l.startswith("RESULT ")), None)
    if line:
        results.append(json.loads(line[7:]))
    else:
        results.append({"device": device, "error": (proc.stderr or proc.stdout)[-600:]})
        print(f"{device}: failed. If the model is not cached, re-run with --allow-download.\n{(proc.stderr or '')[-400:]}", flush=True)
(out / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
print(json.dumps(results, ensure_ascii=False, indent=1))
```

**File:** `L3_whisper_tail.py`

```python
"""L3: why do some Whisper-small CPU decodes take 10-17 s? Compare production settings with variants.
Hypothesis to test: faster-whisper's temperature fallback re-decodes low-confidence output several times.
Usage: python L3_whisper_tail.py [--clips 12] [--reps 3]   (unload the LLM first; the runner does this)"""
import argparse
import json
import time

import numpy as np

from lt_common import DEMO2, RESULTS, append_jsonl, env_snapshot, pct, read_jsonl, setup_demo2, wer

parser = argparse.ArgumentParser()
parser.add_argument("--clips", type=int, default=12)
parser.add_argument("--reps", type=int, default=3)
args = parser.parse_args()
cfg, speech = setup_demo2("L3")
from faster_whisper import WhisperModel

out = RESULTS / "L3_whisper_tail"
rows_path = out / "rows.jsonl"
PROMPT = "IIIT Naya Raipur, admissions, hostel, fees, प्रवेश, शुल्क"
base = json.loads((DEMO2 / "data/upgrade-20260930/baseline/results.json").read_text())
texts, seen = [], set()
for row in base:
    if row["response_status"] == "answered" and row["language"] == "hindi" and row["answer_text"] not in seen:
        seen.add(row["answer_text"])
        try:
            speech.prepare_speech(row["answer_text"], "Female")
            texts.append(row["answer_text"])
        except Exception:
            pass
clips = []
for text in texts[: args.clips]:
    audio = speech.make_audio(text, "hindi", "Female")
    clips.append((audio["spoken_text"], speech.decode_audio(audio["data"])))
print(f"{len(clips)} synthetic clips, {sum(len(c[1]) for c in clips) / 16000:.0f} s of audio", flush=True)

model = WhisperModel(cfg.WHISPER_MODEL, device="cpu", compute_type="int8", cpu_threads=cfg.SPEECH_THREADS)
production = dict(language="hi", beam_size=5, vad_filter=True, condition_on_previous_text=False, initial_prompt=PROMPT)
configs = {
    "production": production,
    "no_temperature_fallback": {**production, "temperature": 0.0},
    "beam1": {**production, "beam_size": 1},
    "beam1_no_fallback": {**production, "beam_size": 1, "temperature": 0.0},
    "no_vad": {**production, "vad_filter": False},
    "no_prompt": {**production, "initial_prompt": None},
}
model.transcribe(clips[0][1], **production)  # warm-up, not recorded
done = {(r["config"], r["clip"], r["rep"]) for r in read_jsonl(rows_path)}
meta = env_snapshot()
for name, options in configs.items():
    for index, (reference, audio) in enumerate(clips):
        for rep in range(args.reps):
            if (name, index, rep) in done:
                continue
            started = time.perf_counter()
            segments, info = model.transcribe(audio, **options)
            segments = list(segments)
            seconds = time.perf_counter() - started
            text = " ".join(s.text.strip() for s in segments if s.no_speech_prob < 0.6)
            row = {"config": name, "clip": index, "rep": rep, "audio_s": round(len(audio) / 16000, 2), "seconds": round(seconds, 3),
                   "rtf": round(seconds / (len(audio) / 16000), 3), "segments": len(segments), "chars": len(text),
                   "wer": round(wer(reference, text), 3),
                   "max_segment_temperature": max((s.temperature for s in segments), default=None),
                   "max_compression_ratio": round(max((s.compression_ratio for s in segments), default=0), 2)}
            append_jsonl(rows_path, row)
            print(name, row, flush=True)
summary = {"meta": meta, "configs": {}}
for name in configs:
    rs = [r for r in read_jsonl(rows_path) if r["config"] == name]
    summary["configs"][name] = {"n": len(rs), "seconds_p50": round(pct([r["seconds"] for r in rs], 50), 2),
        "seconds_p95": round(pct([r["seconds"] for r in rs], 95), 2), "seconds_max": max(r["seconds"] for r in rs),
        "rtf_p50": round(pct([r["rtf"] for r in rs], 50), 3), "n_rtf_over_1": sum(r["rtf"] > 1 for r in rs),
        "n_temperature_fallback": sum((r["max_segment_temperature"] or 0) > 0 for r in rs),
        "wer_mean": round(float(np.mean([r["wer"] for r in rs])), 3)}
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
print(json.dumps(summary, ensure_ascii=False, indent=1))
```

**File:** `L4_real_speech_eval.py`

```python
"""L4: ASR latency and accuracy on REAL recordings (microphone, native speakers).
Recording recipe (16 kHz mono, 3-12 s each, quiet room and one noisy setting; >= 30 clips per language, >= 3 speakers):
    arecord -f S16_LE -r 16000 -c 1 -d 8 results/L4_recordings/hi_001.wav
Create results/L4_recordings/manifest.tsv with a header line and tab-separated rows:
    path<TAB>language<TAB>reference<TAB>speaker
    hi_001.wav<TAB>Hindi<TAB>प्रवेश के लिए शुल्क कितना है<TAB>spk1
language is one of: Hindi, English, Hinglish, Chhattisgarhi (experimental). The reference is what was SAID (not a cleaned text).
Chhattisgarhi uses MMS (see L2; needs the cached weights). Usage: python L4_real_speech_eval.py"""
import csv
import json
import time

from lt_common import RESULTS, cer, env_snapshot, ollama_unload, pct, setup_demo2, wer

ollama_unload()
cfg, speech = setup_demo2("L4")
folder = RESULTS / "L4_recordings"
manifest = folder / "manifest.tsv"
if not manifest.exists():
    raise SystemExit(f"Create {manifest} first (see the docstring).")
rows = list(csv.DictReader(manifest.open(encoding="utf-8"), delimiter="\t"))
warmed, results = set(), []
for row in rows:
    language = row["language"]
    data = (folder / row["path"]).read_bytes()
    if language not in warmed:  # one untimed warm-up per language path (model load)
        started = time.perf_counter()
        speech.transcribe(data, language)
        results.append({"language": language, "warmup_s": round(time.perf_counter() - started, 2), "path": row["path"], "warmup": True})
        warmed.add(language)
    started = time.perf_counter()
    text = speech.transcribe(data, language)
    seconds = time.perf_counter() - started
    import io
    import soundfile as sf
    duration = sf.info(io.BytesIO(data)).duration
    results.append({"language": language, "path": row["path"], "speaker": row.get("speaker", ""), "audio_s": round(duration, 2),
                    "seconds": round(seconds, 3), "rtf": round(seconds / duration, 3), "wer": round(wer(row["reference"], text), 3),
                    "cer": round(cer(row["reference"], text), 3), "empty": not text, "hypothesis": text})
    print(results[-1], flush=True)
summary = {"meta": env_snapshot(), "languages": {}}
for language in sorted({r["language"] for r in results}):
    rs = [r for r in results if r["language"] == language and not r.get("warmup")]
    summary["languages"][language] = {"n": len(rs), "seconds_p50": pct([r["seconds"] for r in rs], 50), "seconds_p95": pct([r["seconds"] for r in rs], 95),
        "rtf_p50": pct([r["rtf"] for r in rs], 50), "wer_mean": sum(r["wer"] for r in rs) / len(rs), "cer_mean": sum(r["cer"] for r in rs) / len(rs),
        "empty_transcripts": sum(r["empty"] for r in rs)}
(RESULTS / "L4_real_speech_eval").mkdir(parents=True, exist_ok=True)
(RESULTS / "L4_real_speech_eval/rows.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
(RESULTS / "L4_real_speech_eval/summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
print(json.dumps(summary, ensure_ascii=False, indent=1))
```

**File:** `L5_voice_turns.py`

```python
"""L5: distribution of composed voice turns on the live Demo 2 configuration (synthetic Hindi questions).
ASR is timed on the question audio; the agent receives the REFERENCE question text because ASR on synthetic
speech is too inaccurate to drive it. TTS is timed on the real answer. Resumable.
Usage: python L5_voice_turns.py [--repeats 2] [--limit 0]"""
import argparse
import io
import json
import time
import uuid

import soundfile as sf

from lt_common import RESULTS, append_jsonl, env_snapshot, ollama_ps, ollama_unload, pct, read_jsonl, setup_demo2, wer

parser = argparse.ArgumentParser()
parser.add_argument("--repeats", type=int, default=2)
parser.add_argument("--limit", type=int, default=0, help="0 = all speakable answerable Hindi cases")
args = parser.parse_args()
cfg, speech = setup_demo2("L5")
import agent_bridge
from lt_common import speakable_hindi_cases

out = RESULTS / "L5_voice_turns"
rows_path = out / "rows.jsonl"
cases = speakable_hindi_cases(speech)
cases = cases[: args.limit] if args.limit else cases
print(f"{len(cases)} cases x {args.repeats} repeats", flush=True)
done = {(r["id"], r["rep"]) for r in read_jsonl(rows_path)}
meta = env_snapshot()
for rep in range(args.repeats):
    for case in cases:
        if (case["id"], rep) in done:
            continue
        audio = speech.make_audio(case["question"], "hindi", "Female")["data"]
        row = {"id": case["id"], "rep": rep, "question_audio_s": round(sf.info(io.BytesIO(audio)).duration, 2)}
        started = time.perf_counter()
        transcript = speech.transcribe(audio, "Hindi")
        row["asr_s"] = round(time.perf_counter() - started, 3)
        row["asr_wer_synthetic"] = round(wer(case["question"], transcript), 3)
        started = time.perf_counter()
        result = agent_bridge.ask(case["question"], str(uuid.uuid4()), {}, provider="ollama")
        row["agent_s"] = round(time.perf_counter() - started, 3)
        metrics = result["rag_metrics"]
        row.update(status=result["response_status"], language=result["language"], calls=metrics.get("model_calls"),
                   stage_ms={k: round(v) for k, v in metrics["stage_ms"].items()}, answer_chars=len(result["answer_text"] or ""))
        try:
            started = time.perf_counter()
            reply = speech.make_audio(result["answer_text"], result["language"], "Female")
            row["tts_s"] = round(time.perf_counter() - started, 3)
            row["answer_audio_s"] = round(sf.info(io.BytesIO(reply["data"])).duration, 2)
        except Exception as error:  # SpeechError: Latin letters or unsupported symbols; or online-only language
            row["tts_s"], row["speech_unavailable"] = None, type(error).__name__
        row["text_ready_s"] = round(row["asr_s"] + row["agent_s"], 3)
        row["audio_done_s"] = round(row["text_ready_s"] + (row["tts_s"] or 0), 3)
        row["ollama_ps"] = ollama_ps()
        append_jsonl(rows_path, row)
        print(json.dumps({k: row[k] for k in ("id", "rep", "asr_s", "agent_s", "tts_s", "status", "calls")}, ensure_ascii=False), flush=True)
rows = read_jsonl(rows_path)
warm = [r for r in rows if not (r["id"] == rows[0]["id"] and r["rep"] == 0)]
answered = [r for r in warm if r["status"] == "answered"]
summary = {"meta": meta, "n_turns": len(rows), "n_answered_excluding_first": len(answered),
           "asr_s_p50_p95_max": [pct([r["asr_s"] for r in warm], 50), pct([r["asr_s"] for r in warm], 95), max(r["asr_s"] for r in warm)],
           "agent_s_p50_p95_max_answered": [pct([r["agent_s"] for r in answered], 50), pct([r["agent_s"] for r in answered], 95), max(r["agent_s"] for r in answered)] if answered else None,
           "text_ready_s_p50_p95_answered": [pct([r["text_ready_s"] for r in answered], 50), pct([r["text_ready_s"] for r in answered], 95)] if answered else None,
           "audio_done_s_p50_p95_answered": [pct([r["audio_done_s"] for r in answered if r["tts_s"]], 50), pct([r["audio_done_s"] for r in answered if r["tts_s"]], 95)] if answered else None,
           "share_agent_of_audio_done_p50": pct([r["agent_s"] / r["audio_done_s"] for r in answered], 50) if answered else None,
           "speech_unavailable_rate_answered": sum(bool(r.get("speech_unavailable")) for r in answered) / max(len(answered), 1),
           "ollama_gpu_pct_values": sorted({p["gpu_pct"] for r in rows for p in r["ollama_ps"]})}
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
print(json.dumps(summary, ensure_ascii=False, indent=1))
ollama_unload()
```

**File:** `L6_grammar_replay.py`

```python
"""L6: is the quote-enum grammar slower per token? Replay real generation requests with/without the enum.
Prefill is cached on replay, so only decode speed and decode length are compared.
Usage: python L6_grammar_replay.py [--cases 20] [--reps 2]"""
import argparse
import copy
import json
import uuid

import numpy as np

from lt_common import RESULTS, append_jsonl, env_snapshot, load_cases, ollama_post, ollama_unload, pct, read_jsonl, setup_demo2

parser = argparse.ArgumentParser()
parser.add_argument("--cases", type=int, default=20)
parser.add_argument("--reps", type=int, default=2)
args = parser.parse_args()
cfg, speech = setup_demo2("L6", {"RAG_CACHE_ENABLED": "false"})
import agent_bridge
from assistant import llm

out = RESULTS / "L6_grammar_replay"
rows_path = out / "rows.jsonl"
captured = []
client = llm._local_client(llm.settings.OLLAMA_BASE_URL, llm.settings.OLLAMA_TIMEOUT_SECONDS)
original_post = client.post


def spy(url, *a, **k):
    if "json" in k and str(url).endswith("api/chat"):
        captured.append(copy.deepcopy(k["json"]))
    return original_post(url, *a, **k)


client.post = spy


def without_enum(fmt):
    fmt = copy.deepcopy(fmt)
    fmt["$defs"]["Evidence"] = {"type": "object", "properties": {"source_id": {"type": "integer"}, "quote": {"type": "string"}},
                               "required": ["source_id", "quote"], "additionalProperties": False}
    return fmt


answerable = [c for c in load_cases() if c["expected"] == "answerable"]
step = max(len(answerable) // args.cases, 1)
selected = answerable[::step][: args.cases]
done = {r["id"] for r in read_jsonl(rows_path)}
meta = env_snapshot()
for case in selected:
    if case["id"] in done:
        continue
    captured.clear()
    result = agent_bridge.ask(case["question"], str(uuid.uuid4()), {}, provider="ollama")
    generation = [b for b in captured if "oneOf" in json.dumps(b["format"].get("$defs", {}).get("Evidence", {}))]
    if not generation:
        append_jsonl(rows_path, {"id": case["id"], "skipped": "no quote-enum request (status %s)" % result["response_status"]})
        continue
    body = generation[0]
    options = body["format"]["$defs"]["Evidence"]["oneOf"]
    row = {"id": case["id"], "language": case["language"], "status": result["response_status"],
           "enum_entries": sum(len(o["properties"]["quote"]["enum"]) for o in options),
           "enum_chars": sum(len(q) for o in options for q in o["properties"]["quote"]["enum"]), "enum": [], "no_enum": []}
    for rep in range(args.reps):
        for label, fmt in (("enum", body["format"]), ("no_enum", without_enum(body["format"]))):
            replay = copy.deepcopy(body)
            replay["format"] = fmt
            data = ollama_post("/api/chat", replay)
            tokens, ms = data.get("eval_count", 0), data.get("eval_duration", 0) / 1e6
            row[label].append({"prompt_tokens": data.get("prompt_eval_count"), "decode_tokens": tokens, "decode_ms": round(ms),
                               "ms_per_token": round(ms / tokens, 2) if tokens else None})
    append_jsonl(rows_path, row)
    print(json.dumps({k: row[k] for k in ("id", "enum_entries", "enum", "no_enum")}), flush=True)
rows = [r for r in read_jsonl(rows_path) if "enum" in r]
ratio = [np.mean([x["ms_per_token"] for x in r["enum"]]) / np.mean([x["ms_per_token"] for x in r["no_enum"]]) for r in rows]
token_ratio = [np.mean([x["decode_tokens"] for x in r["enum"]]) / max(np.mean([x["decode_tokens"] for x in r["no_enum"]]), 1) for r in rows]
summary = {"meta": meta, "n_cases": len(rows), "enum_entries_range": [min(r["enum_entries"] for r in rows), max(r["enum_entries"] for r in rows)],
           "ms_per_token_ratio_enum_over_no_enum": {"p50": pct(ratio, 50), "p95": pct(ratio, 95), "max": max(ratio)},
           "decode_token_ratio_enum_over_no_enum": {"p50": pct(token_ratio, 50), "p95": pct(token_ratio, 95), "max": max(token_ratio)},
           "n_cases_enum_decodes_more_than_1p2x_tokens": sum(t > 1.2 for t in token_ratio)}
(out / "summary.json").write_text(json.dumps(summary, indent=1))
print(json.dumps(summary, indent=1))
ollama_unload()
```

**File:** `L7_gpu_layers_sweep.py`

```python
"""L7: decode/prefill speed versus the share of the 9B model on the GPU (num_gpu sweep) at two context sizes.
Quantifies what freeing VRAM (task 05) can buy on this laptop. Usage: python L7_gpu_layers_sweep.py [--layers 0,8,16,24,28,32,99]"""
import argparse
import json

from lt_common import MODEL, RESULTS, env_snapshot, ollama_ps, ollama_post, ollama_unload, smi_mib

parser = argparse.ArgumentParser()
parser.add_argument("--layers", default="0,8,16,24,28,32,99")
parser.add_argument("--reps", type=int, default=3)
args = parser.parse_args()
paragraph = ("You answer questions about a university using only the numbered sources supplied by the user. "
             "Quote exact spans, never paraphrase numbers, and refuse when evidence is missing. ")
SHORT, LONG = paragraph * 40, paragraph * 135   # about 1.3k and 4.5k prompt tokens


def chat(system, user, predict, layers):
    return ollama_post("/api/chat", {"model": MODEL, "stream": False, "think": False, "keep_alive": "10m",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "options": {"temperature": 0, "num_ctx": 8192, "num_gpu": layers, "num_predict": predict}})


out = RESULTS / "L7_gpu_layers_sweep"
out.mkdir(parents=True, exist_ok=True)
summary = {"meta": env_snapshot(), "runs": []}
for layers in [int(x) for x in args.layers.split(",")]:
    ollama_unload()
    run = {"num_gpu": layers, "gpu_mem_before_mib": smi_mib()}
    try:
        load = chat(SHORT, "Hello", 1, layers)
        run["load_s"] = round(load["load_duration"] / 1e9, 2)
        run["ps"] = ollama_ps()
        run["gpu_mem_loaded_mib"] = smi_mib()
        for label, system in (("short_ctx", SHORT), ("long_ctx", LONG)):
            decode, prefill_cold, prefill_repeat, tokens = [], None, [], None
            for rep in range(args.reps):
                data = chat(system, f"Write a long story about a farmer. Variant {rep}.", 64, layers)
                tokens = data.get("prompt_eval_count")
                decode.append(round(data["eval_duration"] / data["eval_count"] / 1e6, 2))
                if rep == 0:
                    prefill_cold = round(data["prompt_eval_duration"] / 1e6)
                else:
                    prefill_repeat.append(round(data["prompt_eval_duration"] / 1e6))
            run[label] = {"prompt_tokens_last": tokens, "decode_ms_per_token": decode, "decode_tok_s_median": round(1000 / sorted(decode)[len(decode) // 2], 2),
                          "prefill_ms_first": prefill_cold, "prefill_ms_later": prefill_repeat}
    except Exception as error:  # e.g. out of memory at high num_gpu
        run["error"] = f"{type(error).__name__}: {str(error)[:200]}"
    summary["runs"].append(run)
    print(json.dumps(run), flush=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
ollama_unload()
print("DONE")
```

