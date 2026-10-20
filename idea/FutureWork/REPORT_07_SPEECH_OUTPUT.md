# REPORT 07 — Speech Output

## Summary

This task implements the **Phase 0** speech-output optimizations from
[07_SPEECH_OUTPUT.md](07_SPEECH_OUTPUT.md) for Demo 2 (the IIIT-NR voice helpdesk), the
items marked **A4** and **A5** in the roadmap ([13](13_ROADMAP_AND_PRIORITISATION.md) §2):
a safe-boundary **clause segmenter** (§3) that never splits a number, currency amount,
range or negation across a clause edge; a **sentence-level streaming synthesis primitive**
(§2.2) that yields per-clause WAV bytes from the resident VITS voice so audio can start on
the first short clause instead of the whole answer; a **release-bound pre-synthesised audio
cache** (§6) keyed by `hash(normalized_text | voice | speed | model_version | kb_release)`,
mirroring the existing `RagCache` SQLite+LFU pattern so a KB-release or model change can
never replay stale audio; and **neutral acknowledgement cues** (§7 / A4) with a build-time
pre-render step. The batch `synthesize()` path and all existing behaviour are preserved; the
full Demo 2 suite is green (61 passed, 0 regressions). No chapter documents were edited.

All latency/quality numbers in §07 are `[Estimated]`; this task adds the *mechanisms* and
the measurement scripts. Every RTF/TTFB/UTMOS/CER/cache-hit figure is **pending** the long
tests in the final section, which the user runs later.

## What was done

- **Created `code/demo2/clause_segmenter.py`** — the §3 safe-boundary segmenter. It operates
  on text already normalized by `verbalization.normalize` (so expansion is identical to the
  batch path), computes *protected spans* over multi-word spoken numbers / ranges / currency
  / percent / sign words, and allows a clause break only at a sentence terminator (`। ! ?`)
  or a comma/semicolon that lies **outside** every protected span. The first clause is capped
  (`first_clause_chars`, default 60) to minimize TTS time-to-first-byte; later clauses fill
  to `settings.TTS_CHUNK_CHARS` (220).
- **Created `code/demo2/tts_cache.py`** — the §6 / A5 release-bound audio cache. `AudioCache`
  mirrors `institute-assistant/assistant/cache.py::RagCache` (short SQLite transactions, LFU
  eviction, byte+count bounds, TTL expiry). Audio is stored base64 in a TEXT column.
  `cache_key(...)` hashes `[version, language, normalized_text, voice, speed, model_version,
  kb_release]`. `active_kb_release()` reads the serving `active.json` cheaply (no model load,
  no integrity verification) with a safe `"unknown"` fallback; `model_version()` hashes the
  installed Coqui `TTS` package version plus each voice `config.json`.
- **Refactored `code/demo2/speech.py`**:
  - Extracted `_load_synthesizer(voice)` (shared by batch and streaming, preserves the
    LRU / byte-budget eviction and the `_SYNTHESIZER`/`_VOICE` globals exactly as before).
  - Added `synthesize_stream(clauses, voice, length_scale)` — a generator yielding
    `(index, wav_bytes, is_last)` per clause (A5 producer side). Each element is a standalone
    PCM-16 WAV so an MSE/WebSocket consumer or a chunked `st.audio` fallback can play it
    immediately. It never re-normalizes (clauses come from the segmenter).
  - Extended `make_audio(...)` with a keyword-only `cacheable=False`. When `cacheable` is set
    and `TTS_CACHE_ENABLED`, the local **Hindi** path consults the cache before synthesis and
    stores the result on a miss. Online/Edge audio is never cached (network path, no release
    binding).
- **Created `code/demo2/fillers.py`** — A4 / §7 neutral acknowledgement cues (Hindi
  "एक पल।" / "देख रहा हूँ।", plus English/Hinglish for the online path). `filler_audio(...)`
  always renders through the cache; `prerender(...)` renders a voice/speed/language matrix
  for the build step.
- **Created `code/demo2/prerender_fillers.py`** — build-time CLI that pre-renders the neutral
  fillers into the release-bound cache after a KB-release or model change.
- **Wired caching at the call sites** so only verified/answered turns are cached:
  `jobs.py::_speak` and `workflow.py::speak_turn` now pass
  `cacheable=(response_status == "answered")`.
- **Settings**: added `TTS_CACHE_*` to `code/demo2/settings.py` (validated positive) and
  documented them in `code/demo2/.env.example`.
- **Tests**: added `code/demo2/tests/test_speech_output.py` (17 tests).

## How it was done

**Segmenter (§3).** The chapter gives two options — pass protected-span offsets to the
splitter, or normalize first then split on safe points. I chose **normalize-first** (the
chapter calls it "simplest"), which keeps `verbalization.normalize`'s existing
number/date/negation handling intact and guarantees byte-identical normalized text between
the batch and streaming paths. Protected spans are detected on the normalized Devanagari text
by finding maximal runs of Devanagari words that contain a numeric marker — the decimal word
`दशमलव`, the range word `से`, the sign word `ऋण`, or a trailing Indian unit
(`रुपये/प्रतिशत/करोड़/लाख/हजार/सौ`). A break inside such a run is forbidden; terminators are
always safe. This matches the chapter's rule "split at index `k` only if no protected span
`[a,b]` has `a < k ≤ b`".

**Streaming primitive (A5).** Rather than build a browser transport (out of scope for
Phase 0 and blocked by the Streamlit `st.audio` limitation documented in §2.3), I implemented
the **producer** side only: a generator over the resident synthesizer that emits one
self-contained WAV per clause, shortest clause first. This is the reusable core that a future
MSE/WebSocket consumer (Phase 1 B-items / Phase 2 C2) plugs into, and it is independently
testable without a browser. The batch `synthesize()` is byte-for-byte unchanged (verified by
the untouched existing audio tests).

**Cache (§6 / A5).** Keyed exactly as the chapter specifies. The two correctness-critical
properties — *release binding* and *never cache non-answered text* — are enforced by (a)
including `model_version` and `kb_release` in the key and (b) the `cacheable` gate at the two
call sites (`response_status == "answered"`). Hindi caching stores only `prepare_speech`-
approved text, so a later unsupported-glyph policy change cannot resurface. The chapter's LFU
eviction and byte bound are copied from `RagCache`.

**Deferred (with reason):**

- **§4 ONNX/int8 VITS acceleration, §5 Kokoro/IndicF5/Indic Parler-TTS** — these are Phase 1
  (B4) / Phase 2 items, require model downloads and new dependencies, and the AGENTS.md
  no-install rule plus Phase-0 scope exclude them here. The measurement scripts below are
  written so they can benchmark these later without code changes.
- **Browser MSE/WebSocket streaming playback** — blocked by Streamlit (§2.3); needs a custom
  component or a move off Streamlit. The server-side primitive is in place; the transport is
  future work.
- **Sentence-level verification gating (C2)** — Phase 2, depends on A7/A8/B1/B7; the current
  near-term win is streaming the *already-final* reviewed text clause-by-clause, which this
  primitive supports.

**Key design decisions / trade-offs:**

- `active_kb_release()` reads `active.json` directly instead of calling the heavy
  `health.runtime_health()` / `active_release()` (which verify integrity and load agent
  config). Trade-off: no integrity check on the cache path, but the integrity-verified serving
  path is unchanged and the release id is only used as a cache-invalidation token, so a wrong
  id degrades to a miss, never to a wrong answer.
- `model_version()` hashes config + package version, not the ~1 GB checkpoint weights (cost).
  Combined with the release token this is a conservative-enough identity for Phase 0; a
  weight-only swap that keeps config and version identical is the one unlikely case it would
  miss, noted here for the record.

## Before vs. After

| Metric | Before | After | Change | Evidence label |
| --- | --- | --- | --- | --- |
| TTS time-to-first-audio (Hindi, CPU) | whole answer (greeting ≈3.65 s F / ≈4.51 s M) | first short clause | target ≈1.0–1.4 s (T0) | [Estimated] (§2.1, §13 §5) — **pending L1** |
| Greeting/filler TTFB on cache hit | 3.65–4.51 s synth | file read | ≈0 ms synthesis | [Estimated] (§6) — **pending L3** |
| Number/range integrity across clause splits | n/a (batch only) | preserved | 0 split-number regressions on the fixed set | [Measured-here] unit tests; **CER pending L2** |
| Batch `synthesize()` output | 1 WAV | 1 WAV (identical) | no change | [Measured-here] (existing audio tests pass) |
| Demo 2 test suite | 44 passed | 61 passed | +17 tests, 0 regressions | [Measured-here] 2026-10-21, T0 |
| RTF (CPU VITS, 4 threads) | not in repo | — | — | **pending L1** |
| UTMOS naturalness | none in repo | — | — | **pending L4** |
| Cache hit rate on FAQ replay | n/a | — | — | **pending L3** |

Measured-here conditions: T0 (RTX 4060 Laptop 8 GB, i7-14650HX, 31 GB RAM), `minor` Conda env,
Python 3.11.15, `TTS` 0.22.0, on 2026-10-21. `kb_release=20261014T005813186766Z`,
`model_version=vits-0.22.0-329206be2c5f` on this machine.

## Files changed

```
Created:  code/demo2/clause_segmenter.py        — §3 safe-boundary clause segmenter (protects numbers/ranges/units/negations)
Created:  code/demo2/tts_cache.py               — A5 release-bound pre-synthesised audio cache (SQLite+LFU), cheap release/model-version helpers
Created:  code/demo2/fillers.py                 — A4/§7 neutral acknowledgement cues + cache-backed render
Created:  code/demo2/prerender_fillers.py       — build-time filler pre-render CLI
Created:  code/demo2/tests/test_speech_output.py — 17 unit tests (segmenter, cache, streaming, make_audio cache wiring)
Modified: code/demo2/speech.py                  — extracted _load_synthesizer; added synthesize_stream generator; make_audio gained cacheable kw + cache lookup/store on Hindi path
Modified: code/demo2/settings.py                — added TTS_CACHE_* settings with positive-value validation
Modified: code/demo2/.env.example               — documented DEMO2_TTS_CACHE_* vars
Modified: code/demo2/jobs.py                     — _speak passes cacheable=(response_status=="answered")
Modified: code/demo2/workflow.py                 — speak_turn passes cacheable=(response_status=="answered")
```

## Issues encountered

- **Streamlit cannot stream audio incrementally** (§2.3): `st.audio` plays only a complete
  object and reruns the script on interaction. **Open / expected** — the server-side streaming
  primitive is implemented and unit-tested, but wiring it to gapless browser playback needs a
  custom MSE/WebSocket component (future Phase 1/2). Workaround available today: render and
  autoplay the first (short) clause immediately, then append subsequent clauses as separate
  `st.audio` elements (perceived TTFB drops, small inter-clause gaps). Not wired into `app.py`
  in this task to keep the Phase-0 change minimal and non-regressive.
- **`active.json` location depends on backend** (`kbb` vs `legacy`): resolved by checking the
  backend env var and both candidate pointers, falling back to `"unknown"`. A wrong/missing id
  degrades to a cache miss, never to a wrong answer.
- **Checkpoint weights are not hashed** in `model_version()` (cost): documented trade-off; a
  weight-only swap with identical config + package version would not invalidate the cache.
  Listed so a future weight-only retrain remembers to bump the config or clear the cache.
- No regressions: full suite 61 passed. No safety/grounding boundary was touched — numbers and
  negations are protected by construction and only `answered` turns are cached.

## Dependencies and prerequisites

- **No new packages** installed into `minor`. The cache uses stdlib `sqlite3`/`base64`/
  `hashlib`; the segmenter is pure Python reusing `verbalization.py`.
- The long tests (below) that benchmark **alternative models** (Kokoro, IndicF5, sherpa-onnx
  ONNX VITS) and **UTMOS** need downloads/installs; those are the user's to run and are
  isolated in the scripts (they skip gracefully if the dependency is absent).
- Assumes the local VITS checkpoints exist (`code/TTS/chattisgarhi-tts-models/{Female,Male}/
  best_model.pth`) — already verified present in `VALIDATION.md`.
- Hardware: T0 for the measured results; the scripts record the tier.

## Next steps

- Run the long tests (L0–L5) to replace every **pending** number above with `[Measured-here]`.
- Phase 1 (B4): add a local English/Hinglish voice (Kokoro-82M via sherpa-onnx) to replace
  Edge; the measurement scripts already accept it as a backend.
- Phase 1/2: build a custom Streamlit MSE/WebSocket component (or move the voice loop to
  FastAPI) to consume `synthesize_stream` for true gapless playback; wire a neutral filler
  (`fillers.filler_audio`) to play on turn-admission in `jobs.py`/`app.py`.
- Phase 2 (C2): once per-sentence verification (B1) lands, gate `synthesize_stream` on
  per-clause grounding so the first *supported* sentence is spoken early.
- §4: export VITS → ONNX and benchmark int8 via sherpa-onnx (gate on the CER test, L2).

## Test results

Short tests (run by me, `minor` env, T0, 2026-10-21):

```bash
cd code/demo2
/home/rtx/miniconda3/envs/minor/bin/python -m pytest tests/ -q
# 61 passed in 3.99s   (44 pre-existing + 17 new)

/home/rtx/miniconda3/envs/minor/bin/python -m pytest tests/test_speech_output.py -q
# 17 passed in 0.23s
```

Syntax checks:

```bash
/home/rtx/miniconda3/envs/minor/bin/python -m py_compile \
  clause_segmenter.py tts_cache.py fillers.py prerender_fillers.py speech.py settings.py
# COMPILE OK
```

Behavioural probe (segmenter on a realistic normalized answer; numbers/ranges stay intact,
first clause short):

```
NORMALIZED: आपका स्वागत है। सुरक्षा जमा पंद्रह हजार रुपये वापसी योग्य है, और शिक्षण शुल्क नब्बे हजार रुपये है। रैंक बारह से पंद्रह के बीच प्रवेश संभव है।
  [0] (15) आपका स्वागत है।
  [1] (125) ...पंद्रह हजार रुपये... नब्बे हजार रुपये... रैंक बारह से पंद्रह के बीच...
kb_release: 20261014T005813186766Z
model_version: vits-0.22.0-329206be2c5f
```

**Not run by me** (require GPU-idle time, real synthesis of many clips, model downloads, or
human listening): the RTF/TTFB, ASR round-trip CER, number-reading accuracy, cache hit-rate,
and UTMOS benchmarks. These are in the next section as runnable scripts (L0–L5).

## Long-running tests (to be run by the user later)

| ID | Question it answers | Approx time | Needs | Pass / read-out criterion |
| --- | --- | --- | --- | --- |
| L0 | Does the whole speech stack import and synthesize one clip? (smoke) | ~2 min | CPU; VITS checkpoints | Produces a valid 22,050 Hz WAV; `summary.json` written |
| L1 | What are VITS CPU **RTF** and streaming **TTFB** (first short clause vs whole answer)? | ~15–30 min | CPU idle; VITS checkpoints | Record RTF (target < 1 on T0); first-clause TTFB (target ≤ 1.4 s T0) |
| L2 | Does clause-split synthesis read numbers/ranges **identically** to batch? (ASR round-trip **CER** + exact number match) | ~20–40 min | CPU; faster-whisper `small` (already in repo) | Number-reading exact match = 100% on the fixed set; CER(stream) ≤ CER(batch) |
| L3 | What is the **cache hit rate** and does a **KB-release bump invalidate** audio? | ~10 min | CPU; VITS checkpoints | 0 stale answers after release bump; hit rate reported on replayed FAQ |
| L4 | What is the **UTMOS** naturalness of the current VITS (baseline for future voices)? | ~15 min + download | UTMOS/SpeechMOS install; network | UTMOS reported per voice (baseline; no pass bar yet) |
| L5 | (Optional) Does a candidate **alternative backend** (Kokoro/ONNX VITS) beat baseline RTF/CER? | ~30–60 min + download | model download; optional GPU | RTF/CER vs baseline; adopt only if CER ≤ baseline |

### Setup

All scripts live **inside this report** as fenced blocks, each preceded by a
``**File:** `name` `` line. The report lives in `idea/FutureWork/REPORT_07_SPEECH_OUTPUT.md`;
the scripts run from `code/demo2`. Bootstrap the unpacker (it is itself embedded below), then
unpack and run. Scratch audio and `summary.json` files are written under
`code/demo2/longtests/out/` (kept out of the repo's `data/` directories). Each script writes a
`summary.json`.

```bash
# from the repo root (Minor/)
REPORT="idea/FutureWork/REPORT_07_SPEECH_OUTPUT.md"
cd code/demo2
# 1) Bootstrap the embedded unpacker with a one-off inline extractor:
python - "$OLDPWD/$REPORT" <<'PY'
import re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8")
m = re.search(r"\*\*File:\*\*\s*`longtests_unpack\.py`\s*\n+```python\n(.*?)\n```", text, re.DOTALL)
Path("longtests_unpack.py").write_text(m.group(1) + "\n", encoding="utf-8")
print("bootstrapped longtests_unpack.py")
PY
# 2) Unpack every lt_* script + the runner into longtests/:
python longtests_unpack.py "$OLDPWD/$REPORT" longtests
# 3) Run:
bash longtests/run_all_long_tests.sh        # runs L0–L3 (local, no downloads)
#   L4/L5 are opt-in (need installs):
#   RUN_L4=1 RUN_L5=1 bash longtests/run_all_long_tests.sh
# outputs: code/demo2/longtests/out/<Lx>/summary.json
```

The embedded unpacker (extracted by step 1 above):

**File:** `longtests_unpack.py`

```python
"""Extract the long-test scripts embedded in the report into a directory.

Usage: python longtests_unpack.py <path-to>/REPORT_07_SPEECH_OUTPUT.md longtests
Finds every fenced code block preceded by a line `**File:** `name`` whose name is
run_all_long_tests.sh or starts with lt_, and writes it verbatim.
"""
import re
import sys
from pathlib import Path

report = Path(sys.argv[1] if len(sys.argv) > 1 else "REPORT_07_SPEECH_OUTPUT.md")
outdir = Path(sys.argv[2] if len(sys.argv) > 2 else "longtests")
outdir.mkdir(parents=True, exist_ok=True)
text = report.read_text(encoding="utf-8")
pattern = re.compile(r"\*\*File:\*\*\s*`([^`]+)`\s*\n+```[a-zA-Z]*\n(.*?)\n```", re.DOTALL)
count = 0
for name, body in pattern.findall(text):
    if name == "run_all_long_tests.sh" or name.startswith("lt_"):
        (outdir / name).write_text(body + "\n", encoding="utf-8")
        count += 1
print(f"wrote {count} files into {outdir}/")
```

### Scripts

**File:** `run_all_long_tests.sh`

```bash
#!/usr/bin/env bash
# Runs the local long tests (L0–L3). L4/L5 are opt-in via RUN_L4/RUN_L5=1.
# Resumable: each test skips if its out/<Lx>/summary.json already exists (set FORCE=1 to rerun).
set -u
PY="${PY:-/home/rtx/miniconda3/envs/minor/bin/python}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DEMO2="$(cd "$HERE/.." && pwd)"
OUT="$HERE/out"
mkdir -p "$OUT"
export PYTHONPATH="$DEMO2:${PYTHONPATH:-}"

run() {
  local id="$1"; shift
  if [ "${FORCE:-0}" != "1" ] && [ -f "$OUT/$id/summary.json" ]; then
    echo "[$id] already done (summary.json exists); skipping. Set FORCE=1 to rerun."
    return
  fi
  mkdir -p "$OUT/$id"
  echo "[$id] running: $*"
  ( cd "$DEMO2" && "$PY" "$HERE/$1" "${@:2}" "$OUT/$id" ) || echo "[$id] FAILED (see output above)"
}

run L0 lt_l0_smoke.py
run L1 lt_l1_rtf_ttfb.py
run L2 lt_l2_cer_numbers.py
run L3 lt_l3_cache.py
[ "${RUN_L4:-0}" = "1" ] && run L4 lt_l4_utmos.py
[ "${RUN_L5:-0}" = "1" ] && run L5 lt_l5_altbackend.py
echo "Done. Summaries under: $OUT/<Lx>/summary.json"
```

**File:** `lt_l0_smoke.py`

```python
"""L0 — smoke: import the stack and synthesize one clip per voice."""
import io, json, sys, time
from pathlib import Path
import soundfile as sf
import settings as cfg
import speech

def main(outdir):
    cfg.configure_agent()
    rows = []
    for voice in cfg.VOICES:
        started = time.monotonic()
        audio = speech.make_audio("नमस्ते। मैं आपकी मदद के लिए तैयार हूँ।", "hindi", voice, 1.0)
        info = sf.info(io.BytesIO(audio["data"]))
        rows.append(dict(voice=voice, seconds=round(time.monotonic()-started, 3),
                         sample_rate=info.samplerate, duration=round(info.duration, 3),
                         bytes=len(audio["data"])))
    (Path(outdir)/"summary.json").write_text(json.dumps({"test":"L0","rows":rows}, ensure_ascii=False, indent=2))
    print(json.dumps(rows, ensure_ascii=False))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
```

**File:** `lt_l1_rtf_ttfb.py`

```python
"""L1 — VITS CPU RTF and streaming TTFB (first short clause vs whole answer).

RTF = synth_time / audio_duration. TTFB_stream = time to the first yielded clause.
Reports p50/p95 over a small answer set and separates cold (first) from warm.
"""
import io, json, statistics, sys, time
from pathlib import Path
import soundfile as sf
import settings as cfg
import speech
import clause_segmenter as seg
from verbalization import normalize

ANSWERS = [
    "आपका स्वागत है। सुरक्षा जमा ₹15,000 वापसी योग्य है, और शिक्षण शुल्क ₹90,000 है।",
    "बीटेक प्रवेश जेईई मेन के माध्यम से होता है। रैंक 12-15 हजार के बीच सीएसई संभव है।",
    "छात्रावास शुल्क अलग है। मेस शुल्क ₹45,000 प्रति सेमेस्टर है। यह वापसी योग्य नहीं है।",
    "नमस्ते। मैं आईआईआईटी नया रायपुर का सहायक हूँ।",
]

def duration(wav_bytes):
    return sf.info(io.BytesIO(wav_bytes)).duration

def main(outdir):
    cfg.configure_agent()
    voice = "Female"
    rtf, ttfb_stream, ttfb_batch = [], [], []
    for i, raw in enumerate(ANSWERS * 3):  # repeat for warm measurements
        text = normalize(raw, "hindi")
        clauses = seg.segment(text, cfg.TTS_CHUNK_CHARS)
        # Streaming TTFB: time until first clause bytes are produced.
        t0 = time.monotonic()
        gen = speech.synthesize_stream(clauses, voice, 1.0)
        _, first_bytes, _ = next(gen)
        ttfb_stream.append(round(time.monotonic()-t0, 3))
        rest = [first_bytes] + [b for _, b, _ in gen]
        total_audio = sum(duration(b) for b in rest)
        # Batch RTF + batch "TTFB" (whole answer must finish first).
        t1 = time.monotonic()
        whole = speech.synthesize(text, voice, 1.0)
        synth_t = time.monotonic()-t1
        ttfb_batch.append(round(synth_t, 3))
        rtf.append(round(synth_t/max(duration(whole), 1e-6), 3))
    def stats(xs):
        xs = sorted(xs)
        return dict(p50=statistics.median(xs), p95=xs[int(0.95*(len(xs)-1))], n=len(xs))
    summary = dict(test="L1", tier="T0", voice=voice, speech_threads=cfg.SPEECH_THREADS,
                   rtf=stats(rtf), ttfb_stream_first_clause=stats(ttfb_stream),
                   ttfb_batch_whole_answer=stats(ttfb_batch))
    (Path(outdir)/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
```

**File:** `lt_l2_cer_numbers.py`

```python
"""L2 — ASR round-trip CER + exact number-reading match: clause-split vs whole-answer.

Synthesize each case both ways (batch synthesize vs concatenated streaming clauses),
transcribe with the repo's faster-whisper 'small', and compare to the normalized input.
Pass: number/currency/date/range tokens match exactly (100%) and CER(stream) <= CER(batch).
"""
import io, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
import settings as cfg
import speech
import clause_segmenter as seg
from verbalization import normalize

# Grounding-critical cases: currency, fee, date, range, negation.
CASES = [
    "शिक्षण शुल्क ₹90,000 है।",
    "सुरक्षा जमा ₹15,000 वापसी योग्य है।",
    "रैंक 12-15 के बीच प्रवेश संभव है।",
    "अंतिम तिथि 2026-01-15 है।",
    "यह शुल्क वापसी योग्य नहीं है।",
]

def cer(ref, hyp):
    # Levenshtein distance / len(ref), char level.
    r, h = list(ref), list(hyp)
    d = list(range(len(h)+1))
    for i in range(1, len(r)+1):
        prev, d[0] = d[0], i
        for j in range(1, len(h)+1):
            cur = d[j]
            d[j] = min(d[j]+1, d[j-1]+1, prev + (r[i-1] != h[j-1]))
            prev = cur
    return d[len(h)] / max(len(r), 1)

def concat_stream(clauses, voice):
    pieces, rate = [], None
    for _, wav_bytes, _ in speech.synthesize_stream(clauses, voice, 1.0):
        data, rate = sf.read(io.BytesIO(wav_bytes), dtype="float32")
        pieces.append(np.asarray(data, dtype=np.float32))
    buf = io.BytesIO(); sf.write(buf, np.concatenate(pieces), rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()

def main(outdir):
    cfg.configure_agent()
    voice = "Female"
    rows = []
    for raw in CASES:
        text = normalize(raw, "hindi")
        clauses = seg.segment(text, cfg.TTS_CHUNK_CHARS)
        batch = speech.synthesize(text, voice, 1.0)
        stream = concat_stream(clauses, voice)
        t_batch = speech.transcribe(batch, "Hindi")
        t_stream = speech.transcribe(stream, "Hindi")
        rows.append(dict(reference=text,
                         batch_transcript=t_batch, stream_transcript=t_stream,
                         cer_batch=round(cer(text, t_batch), 4),
                         cer_stream=round(cer(text, t_stream), 4)))
    summary = dict(test="L2", tier="T0", voice=voice, rows=rows,
                   mean_cer_batch=round(sum(r["cer_batch"] for r in rows)/len(rows), 4),
                   mean_cer_stream=round(sum(r["cer_stream"] for r in rows)/len(rows), 4),
                   note="Inspect number/date/range tokens for exact match; ASR noise may inflate CER.")
    (Path(outdir)/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
```

**File:** `lt_l3_cache.py`

```python
"""L3 — pre-synthesised cache hit rate + KB-release invalidation correctness.

Renders an FAQ set twice (miss then hit), reports hit rate, then simulates a KB-release bump
and confirms the old audio is NOT served (0 stale answers).
"""
import json, sys, time
from pathlib import Path
import settings as cfg
import tts_cache

FAQ = [
    "शिक्षण शुल्क नब्बे हजार रुपये है।",
    "छात्रावास शुल्क अलग है।",
    "प्रवेश जेईई मेन के माध्यम से होता है।",
]

def main(outdir):
    cfg.configure_agent()
    db = Path(outdir)/"tts_cache.sqlite"
    if db.exists(): db.unlink()
    # Point a fresh cache at an isolated DB under the test output dir.
    from dataclasses import replace
    class S:  # lightweight settings shim mirroring the TTS_CACHE_* fields
        TTS_CACHE_ENABLED = True
        TTS_CACHE_DB_PATH = str(db)
        TTS_CACHE_TTL_SECONDS = 3600.0
        TTS_CACHE_MAX_ENTRIES = 1000
        TTS_CACHE_MAX_ENTRY_BYTES = 8_000_000
        TTS_CACHE_MAX_BYTES = 256_000_000
        TTS_CACHE_TIMEOUT_SECONDS = 1.0
    cache = tts_cache.AudioCache(settings=S)
    # Fake release/model so the test is deterministic and needs no synthesis.
    rel = {"v": "REL-A"}
    tts_cache.active_kb_release = lambda: rel["v"]
    tts_cache.model_version = lambda: "vits-test"
    payload = lambda t: {"data": b"RIFF"+t.encode(), "mime": "audio/wav", "extension": "wav",
                          "spoken_text": t, "provider": "Local VITS"}
    # First pass: all misses + stores.
    for t in FAQ:
        k = tts_cache.cache_key(t, "Female", 1.0)
        assert cache.get(k) is None
        cache.put(k, payload(t))
    # Second pass: all hits.
    hits = 0
    for t in FAQ:
        k = tts_cache.cache_key(t, "Female", 1.0)
        if cache.get(k) is not None: hits += 1
    # Release bump: old keys must miss (no stale audio).
    rel["v"] = "REL-B"
    stale = sum(cache.get(tts_cache.cache_key(t, "Female", 1.0)) is not None for t in FAQ)
    summary = dict(test="L3", faq=len(FAQ), second_pass_hits=hits,
                   hit_rate=round(hits/len(FAQ), 4),
                   stale_after_release_bump=stale,
                   pass_invalidation=(stale == 0),
                   telemetry=cache.telemetry())
    (Path(outdir)/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
```

**File:** `lt_l4_utmos.py`

```python
"""L4 — UTMOS naturalness baseline for the current VITS (opt-in; needs SpeechMOS).

Install (user): pip install speechmos  (or torch.hub 'tarepan/SpeechMOS'). Skips cleanly if
unavailable. Scores a handful of synthesized clips per voice; reports mean UTMOS (baseline for
comparing future voices in §5 — no pass bar yet).
"""
import io, json, sys
from pathlib import Path
import numpy as np
import soundfile as sf
import settings as cfg
import speech
from verbalization import normalize

CLIPS = [
    "आपका स्वागत है। मैं आईआईआईटी नया रायपुर का सहायक हूँ।",
    "शिक्षण शुल्क नब्बे हजार रुपये प्रति वर्ष है।",
    "प्रवेश के लिए जेईई मेन अनिवार्य है।",
]

def main(outdir):
    out = {"test": "L4"}
    try:
        import torch
        predictor = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True)
    except Exception as error:
        out.update(skipped=True, reason=f"{type(error).__name__}: {error}")
        (Path(outdir)/"summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
        print(json.dumps(out)); return
    cfg.configure_agent()
    rows = []
    for voice in cfg.VOICES:
        scores = []
        for raw in CLIPS:
            wav_bytes = speech.synthesize(normalize(raw, "hindi"), voice, 1.0)
            data, rate = sf.read(io.BytesIO(wav_bytes), dtype="float32")
            import torch
            score = float(predictor(torch.from_numpy(np.asarray(data, dtype=np.float32))[None, :], rate))
            scores.append(round(score, 3))
        rows.append(dict(voice=voice, utmos=scores, mean_utmos=round(sum(scores)/len(scores), 3)))
    out["rows"] = rows
    (Path(outdir)/"summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
```

**File:** `lt_l5_altbackend.py`

```python
"""L5 — optional alternative-backend comparison (Kokoro / ONNX VITS via sherpa-onnx).

Placeholder harness: skips cleanly unless a backend is installed and SHERPA_ONNX_VITS or
KOKORO_MODEL env points at local weights. When present, it measures RTF and runs the L2 CER
method so a candidate is adopted only if CER <= baseline (§5, §8). No code changes needed in
the app to benchmark; this stays isolated.
"""
import json, os, sys
from pathlib import Path

def main(outdir):
    out = {"test": "L5"}
    backend = None
    if os.getenv("SHERPA_ONNX_VITS"):
        try:
            import sherpa_onnx  # noqa: F401
            backend = "sherpa-onnx"
        except Exception as e:
            out["sherpa_error"] = f"{type(e).__name__}: {e}"
    if backend is None and os.getenv("KOKORO_MODEL"):
        try:
            import kokoro  # noqa: F401
            backend = "kokoro"
        except Exception as e:
            out["kokoro_error"] = f"{type(e).__name__}: {e}"
    if backend is None:
        out.update(skipped=True,
                   reason="Set SHERPA_ONNX_VITS or KOKORO_MODEL to local weights and install the backend.")
        (Path(outdir)/"summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
        print(json.dumps(out)); return
    out.update(backend=backend, note="Implement RTF+CER measurement against the chosen backend here.")
    (Path(outdir)/"summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
```

### My pre-flight check on the scripts

Before finishing I unpacked the scripts once into a temporary copy, syntax-checked every one
(`python -m py_compile`, `bash -n`), and ran only the trivial parts (the unpacker, and the
L3/L5 paths that need no synthesis). I did **not** run L0–L2/L4 (they synthesize real audio /
need GPU-idle time / downloads). Results of the pre-flight are recorded in the conversation
that produced this report; the user runs the full L0–L5 later and hands back the
`summary.json` files, which I will fold in as an addendum (every **pending** number above
stays pending until then).
