# REPORT 03 — Speech input and turn-taking

Task: [03 Speech input and turn-taking](03_SPEECH_INPUT_AND_TURN_TAKING.md). Date: 2026-10-20 (IST). Hardware tier: **T0** (RTX 4060 Laptop 8 GB, i7-14650HX 24 threads without AVX-512, 31 GB RAM). Roadmap row: **B2, Phase 1** ([13](13_ROADMAP_AND_PRIORITISATION.md)) — "Wire `stt-service` (Silero VAD, partials) into Demo 2; semantic end-of-turn model".

Evidence labels follow [00_INDEX](00_INDEX.md): **[Measured-here]**, **[Reported]**, **[Estimated]**.

Paths are relative to the repository root (`Minor/`). `stt-service` abbreviates `code/STT/stt-service/`.

## Summary

Chapter 03's two smallest, dependency-free wins both live in the existing streaming microservice, not in Demo 2. First, the service's partial loop was a _windowed re-decode_ (re-transcribe the last 6 s each 700 ms and emit the whole window), so earlier words could be silently rewritten by a later partial — it was not a prefix-committing stream (chapter 03 §2.3). I added **LocalAgreement-2** as a pure, tested committer (`src/prefix_commit.py`) and wired it into `session.py`, so `PARTIAL` events now carry a stable, append-only `committed_text` plus a revisable `pending_text`, off by default so existing consumers that read `text` are untouched. Second, finalisation was a pure silence timer that cannot distinguish a thinking pause from a finished turn (chapter 03 §3.2). I added a **semantic EOU gate** (`src/turn_detector.py`, vedants254-style ONNX via the already-present `onnxruntime`) behind the rule `silence_ms ≥ min_silence AND (p_complete ≥ τ OR silence_ms ≥ max_silence)`, with a `max_silence` safety cap and **graceful degradation**: disabled by default, and when the model/onnxruntime are absent or inference errors, the rule reduces _exactly_ to today's silence endpoint. 28 new unit tests pass; existing collection is unaffected and the server still imports. No model was downloaded and no long test was run by me — the streaming-residual, EOU-sweep, and MMS-latency long tests are scripted in the last section for you to run. The full streaming-into-Demo-2 WebRTC front end (chapter 03 §9 option B) is **deferred** with reasons below.

## What was done

- **Created `stt-service/src/prefix_commit.py`** — `PrefixCommitter` (LocalAgreement-N), `longest_common_prefix`, and the `CommitResult` dataclass. Pure Python, no third-party imports, whitespace-token based. Commits the longest common prefix that agreed across the last `N` partials; never un-commits on a divergent re-decode.
- **Created `stt-service/src/turn_detector.py`** — `SemanticTurnDetector` (lazy, thread-safe ONNX session; graceful degrade to `available=False`/`p_complete=None`), the `EouResult` dataclass, the pure `should_finalize(...)` decision function, and a `get_turn_detector()` process singleton. Implements the vedants254 input contract (last 8 s @ 16 kHz, left-padded to `[1, 128000]`) and coerces logit-or-probability outputs.
- **Modified `stt-service/src/config.py`** — added `PREFIX_COMMIT_ENABLED` (default off), `PREFIX_COMMIT_N` (2); `EOU_ENABLED` (off), `EOU_MODEL_PATH` (""), `EOU_THRESHOLD` (0.5), `EOU_MIN_SILENCE_MS` (300), `EOU_MAX_SILENCE_MS` (defaults to the legacy `STT_EOS_SILENCE_MS`). All env-overridable. The legacy `END_OF_SPEECH_SILENCE_MS` is kept for backward compatibility (other code reads it) but is no longer the endpoint used by `session.py`.
- **Modified `stt-service/src/schemas.py`** — `STTEvent` gained optional `committed_text=""`, `pending_text=""`, `eou_prob=None`. All default to the inert value, so every existing consumer and serialised shape is backward compatible.
- **Modified `stt-service/src/session.py`** — imports the two new modules; `__init__` creates the per-session committer and an EOU-probability cache; both reset on speech start and on finalize; the `should_finalize` block is replaced by an EOU probe (run off the event loop in the existing `_EXECUTOR`) feeding the pure `eou_should_finalize()`; `_emit_partial` populates `committed_text`/`pending_text` when enabled; `_finalize` attaches `eou_prob`; new `_probe_eou()` skips the model below `MIN_FINAL_AUDIO_MS`.
- **Modified `stt-service/.env.example`** — documented all seven new knobs with their defaults and the degradation contract.
- **Created three unit-test files** — `tests/test_prefix_commit.py`, `tests/test_turn_detector.py`, `tests/test_session_wiring.py` (28 tests total).
- **Wrote this report** with the three long-test scripts (`L0` streaming residual + correction rate, `L1` EOU τ-sweep, `L2` MMS `hne` CPU partial/final latency) for you to run later.

No chapter document was edited. Demo 2 source was not modified (see the deferral note in "How it was done").

## How it was done

### LocalAgreement-2 (chapter 03 §2.1, §2.3)

The committer keeps the already-committed token list and the last `N−1` uncommitted tails. On each new full partial hypothesis `H_t` it commits the longest common prefix of the current tail with the recent tails (with `N=2`, that is `LCP(H_t, H_{t−1})` beyond what is already committed). Two design points matter for correctness:

- **Monotonic, never-shrinking commit.** If a re-decode of the sliding window disagrees _inside_ the already-committed region (e.g. the window slid past committed audio), we align on the committed prefix and only consider tokens _after_ it, so a committed prefix is never retracted. `test_commit_never_shrinks_on_divergent_redecode` pins this.
- **Latency vs flicker is the single knob `N`.** `N=1` commits immediately (lowest latency, highest correction risk); `N=2` is the recommended T0 default; `N=3` waits for three agreements. Commit delay ≈ `(N−1)·PARTIAL_INTERVAL_MS` (chapter 03 §2.1). `test_n1_*`/`test_n3_*` cover both extremes.

The raw `text` field is left exactly as before; `committed_text`/`pending_text` are additive. This is why the feature can ship off-by-default with zero risk to the current Demo 2 batch path or any WS client.

### Semantic EOU gate (chapter 03 §3.2)

The decision is a pure function so it is fully unit-testable without audio:

```
finalize  ⟺  utterance_ms ≥ max_utterance_ms
          ∨  ( silence_ms ≥ min_silence_ms
               ∧ ( (eou_p ≥ τ)  ∨  silence_ms ≥ max_silence_ms ) )
```

When `eou_p is None` the semantic clause is false and the rule collapses to `silence_ms ≥ max_silence_ms`. Because `EOU_MAX_SILENCE_MS` defaults to the legacy `STT_EOS_SILENCE_MS` (400 ms in the committed `.env`, 600 ms default), **endpointing with EOU off is bit-for-bit the old behaviour** — confirmed by `test_legacy_finalize_on_silence_when_eou_disabled` and `test_no_model_reduces_to_silence_cap`. The `min_silence` floor (300 ms) is below `max_silence`, so it never blocks a legitimate finalize on the legacy path.

The model itself is loaded lazily, once per process, inside a lock, and only when `EOU_ENABLED` and a `EOU_MODEL_PATH` are set. Every failure mode — no `onnxruntime`, missing file, bad opset, inference exception — is caught and turned into `available=False`/`p_complete=None`. The probe runs in the existing `_EXECUTOR` thread pool (same place as blocking ASR), so it never blocks the asyncio loop, and is skipped entirely below `MIN_FINAL_AUDIO_MS` where there is no completion signal.

Key decisions and trade-offs:

- **vedants254 over Smart-Turn / LiveKit.** Per chapter 03 §3.2 it is the only candidate that explicitly covers English/Hindi/Hinglish, is MIT-licensed, runs on CPU from ONNX, and needs no transcript. The loader is model-agnostic (any single-input ONNX returning one logit/probability works), so Smart-Turn v3 is a drop-in by swapping the path.
- **No weights bundled or downloaded by code.** The module only _reads_ a path. Fetching the ONNX is a long test (`L1`) the user runs, per the AGENTS no-download rule.
- **`eou_prob` surfaced on FINAL.** This is the observability hook chapter 03 §12 asks for (sweep τ, plot false-cut/added-delay); `L1` uses it.

### Why Demo 2 WebRTC wiring was deferred

Chapter 03 §9 ranks option A (`streamlit-webrtc` in-app) and B (a small FastAPI/WebRTC front end) as low/medium effort, and the roadmap puts B2 at Phase 1. The _turn-taking logic_ (this task's core) is the part that is dependency-free and testable; the _transport_ is a separate, medium-effort piece that (i) pulls in `streamlit-webrtc`/`aiortc` or a second server process, (ii) needs a browser mic and human speech to exercise, and (iii) overlaps the concurrency/transport work owned by [10](10_THROUGHPUT_CONCURRENCY_AND_TELEPHONY.md). Making "the smallest coherent change that delivers a measurable optimization" (AGENTS §3) means landing and testing the prefix-commit + EOU logic now, behind flags, and leaving the transport wiring as the explicit next step. Demo 2's batch `st.audio_input` path is unchanged and keeps working. This is a deliberate deviation from a literal reading of B2 ("wire into Demo 2"), flagged here per AGENTS §3.

## Before vs. After

The measurable latency wins (ASR residual, end-of-turn dead air) require recorded speech and the EOU weights, so they are produced by the long tests and are **pending** until you run them. What changed _now_ is the capability and the correctness of the streaming contract.

| Metric                                                     | Before                                                                       | After                                                  | Change                        | Evidence label                      |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------ | ----------------------------- | ----------------------------------- |
| Partial transcript stability                               | windowed re-decode; earlier words can be rewritten (chapter 03 §2.3)         | append-only `committed_text` via LocalAgreement-2      | flicker-free committed prefix | [Measured-here] (logic, unit tests) |
| End-of-turn decision                                       | pure silence timer only                                                      | silence floor + semantic `p_complete ≥ τ` + safety cap | semantic gate available       | [Measured-here] (logic, unit tests) |
| Endpointing when EOU disabled                              | `silence_ms ≥ EOS`                                                           | identical (`silence_ms ≥ max_silence`, default = EOS)  | no change (verified)          | [Measured-here]                     |
| New STT unit tests                                         | 0 collectible unit tests (only WS clients / MMS probe)                       | 28 passing                                             | +28                           | [Measured-here]                     |
| Graceful degradation (no model)                            | n/a                                                                          | `available=False`, falls back to silence timer         | never regresses               | [Measured-here]                     |
| ASR residual (6 s utterance)                               | whole clip (unmeasured; `VALIDATION.md` has no speech benchmark)             | last ≤1 s streaming pass                               | **pending** `L0`              | [Estimated] chapter 03 §2           |
| EOU false-cut rate @ τ                                     | n/a                                                                          | target ≤5%                                             | **pending** `L1`              | [Reported] ~6% @0.5 [R302]          |
| EOU added delay vs oracle                                  | n/a                                                                          | target median ≤300 ms                                  | **pending** `L1`              | [Estimated] chapter 03 §10          |
| Streaming correction rate (committed tokens later changed) | n/a (no commit concept)                                                      | target ≤ small (LocalAgreement-2)                      | **pending** `L0`              | [Estimated] chapter 03 §12          |
| MMS `hne` CPU partial/final latency                        | slide 1850 ms (unverified, [01](01_BASELINE_AND_CURRENT_ARCHITECTURE.md) §6) | —                                                      | **pending** `L2`              | [Reported]/unverified               |

## Files changed

```
Created:  code/STT/stt-service/src/prefix_commit.py — LocalAgreement-N prefix committer (pure, no deps)
Created:  code/STT/stt-service/src/turn_detector.py — semantic EOU ONNX detector + pure should_finalize() + singleton
Modified: code/STT/stt-service/src/config.py — added prefix-commit (2) and EOU (5) env-overridable knobs
Modified: code/STT/stt-service/src/schemas.py — STTEvent gained optional committed_text/pending_text/eou_prob
Modified: code/STT/stt-service/src/session.py — wired committer + EOU gate into the partial/finalize state machine
Modified: code/STT/stt-service/.env.example — documented the seven new knobs and the degradation contract
Created:  code/STT/stt-service/tests/test_prefix_commit.py — 13 tests for LocalAgreement-N
Created:  code/STT/stt-service/tests/test_turn_detector.py — 11 tests for the EOU decision + degradation
Created:  code/STT/stt-service/tests/test_session_wiring.py — 4 session-integration tests (fake ASR, stub VAD)
Created:  idea/FutureWork/REPORT_03_SPEECH_INPUT_AND_TURN_TAKING.md — this report
```

## Issues encountered

- **`Settings` is a frozen dataclass, so tests cannot `monkeypatch.setattr` a field on the instance.** Resolved. Tests that need a flag flipped build a tweaked copy with `dataclasses.replace(module.settings, EOU_ENABLED=True)` and patch the _module-global_ `settings` binding (`src.turn_detector.settings` / `src.session.settings`). This mirrors how REPORT_02's tests handle module-level singletons and keeps the production object immutable.
- **The legacy endpoint constant `END_OF_SPEECH_SILENCE_MS` is now unused by `session.py`.** Open (intentional, documented). It is retained in `config.py` for backward compatibility because other code and docs reference it, and because `EOU_MAX_SILENCE_MS` inherits its env var (`STT_EOS_SILENCE_MS`) as the default, so the committed `.env` (400 ms) continues to drive endpointing unchanged. Removing it would be a wider change than this task warrants.
- **The committed `.env` points `STT_LANGUAGE=hne` and `STT_DEVICE=cuda`.** Noted, not changed. The EOU model is language-agnostic at the audio level; MMS `hne` runs via Torch CUDA while Whisper partials are English-only in the current config. The prefix committer is tokeniser-agnostic (whitespace words), which is correct for both Whisper and the MMS Devanagari output after `clean_mms_devanagari`.
- **No in-repo speech benchmark exists** (`code/demo2/VALIDATION.md`; [01](01_BASELINE_AND_CURRENT_ARCHITECTURE.md) §6). Open (inherited). Every latency win in the Before/After table is therefore `[Estimated]`/`pending` until `L0`–`L2` run. This is the gap the long tests close.
- **Demo 2 streaming transport not wired.** Open (deferred by design, see "How it was done"). Workaround: the batch path is unchanged; the streaming service now carries the turn-taking improvements and is ready for the transport task.

## Dependencies and prerequisites

- **No new packages for the core logic.** `prefix_commit.py` is standard library only. `turn_detector.py` imports `numpy` (already a dependency) and `onnxruntime` _lazily_ — `onnxruntime 1.28.0` is already in the `minor` env (verified), and if it were absent the detector simply degrades.
- **The EOU weights are not installed.** Running the EOU path for real needs the vedants254 ONNX file fetched to a local path and `STT_EOU_MODEL_PATH` pointed at it (long test `L1`). Nothing is downloaded by the service or by me.
- **Assumes complete:** the existing `stt-service` (O18) with Silero VAD and faster-whisper, which predates this task. No other Phase 0/1 row is required. This is roadmap B2.
- **Hardware:** the unit tests run anywhere. `L0`/`L1`/`L2` want the T0 laptop; `L2` needs the MMS weights and is CPU-heavy.

## Next steps

- **Wire the transport (chapter 03 §9 option B).** Stand up the small FastAPI/WebRTC front end (or `streamlit-webrtc`) so Demo 2 subscribes to `partial`/`final`/`speech_started`; the turn-taking logic is already in place. Pairs with [10](10_THROUGHPUT_CONCURRENCY_AND_TELEPHONY.md).
- **Preemptive routing/retrieval on the committed prefix (chapter 03 §4, roadmap C4).** Now unblocked: `committed_text` is the stable signal to trigger `classify_intent_node`/`retrieve_node` early, gating generation on the final. Keep it idempotent/rollback-safe.
- **Barge-in in Demo 2 (chapter 03 §5).** The service already emits `interrupt_previous_response`; wire it to cancel the TTS job via `demo2/jobs.py::JobManager` once the transport exists.
- **Calibrate τ per language** after `L1`, and set a per-language threshold (chapter 03 §3.2).
- **Entity post-correction + institute `initial_prompt` (chapter 03 §6)** — separate, grounding-sensitive change; keep conservative so it never rewrites cutoff-bearing names.
- After you run `L0`–`L2`, hand me the `summary.json` files and I will fold the measured residual latency, correction rate, EOU false-cut/added-delay curve, and MMS latency into the Before/After table and mark the pending rows measured.

## Test results

- Command: `conda activate minor && cd code/STT/stt-service && python -m pytest tests/test_prefix_commit.py tests/test_turn_detector.py tests/test_session_wiring.py -q`
- Result: **28 passed, 0 failed** in ~1 s (one pre-existing Pydantic v2 deprecation warning from `schemas.py`, unrelated to this change).
- Collection: `python -m pytest --collect-only -q` collects the 28 new tests cleanly; the pre-existing `tests/test_client_wav.py`/`test_client_mic.py` (manual WS clients) and root `test_mms_speed.py` (model probe) contribute no unit tests, as before.
- Sanity: `python -m py_compile src/prefix_commit.py src/turn_detector.py src/session.py src/config.py src/schemas.py` and `python -c "import src.server"` both succeed, confirming the session wiring did not break the server import.
- No long test was run by me (see below). The long-test scripts' fast `--check` paths were syntax-checked and dry-run only.

## Long-running tests (to be run by the user later)

These need recorded speech, a model download, and/or the CPU to themselves, so they are yours to run. Each writes a `summary.json`, keeps scratch state in `/tmp`, and starts the STT service itself where needed (and stops it afterwards). Nothing here runs during normal CI.

| ID  | Question it answers                                                                                            | Approx. time                     | Needs                                                                       | Pass / read-out criterion                                                                                                      |
| --- | -------------------------------------------------------------------------------------------------------------- | -------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| L0  | What is the streaming ASR residual latency, and the LocalAgreement-2 correction rate, vs the whole-clip final? | ~10–20 min                       | A running STT service; 5–20 mono-16k-WAV utterances in `L0_streaming/wavs/` | `summary.json` reports median residual (final-pass) latency < whole-clip latency and committed-token correction rate; no error |
| L1  | What is the EOU false-cut rate and added delay, swept over τ, on labelled turns?                               | ~15–30 min + one-time download   | vedants254 ONNX at `$EOU_MODEL`; labelled turns in `L1_eou/turns.jsonl`     | `summary.json` reports false-cut rate and median added delay per τ; pick τ with false-cut ≤5%                                  |
| L2  | What is the real MMS `hne` CPU partial/final latency on T0? (replaces the unverified 1850 ms slide)            | ~5–15 min + one-time model fetch | `facebook/mms-1b-all` reachable; ≥1 `hne` WAV in `L2_mms/wavs/`             | `summary.json` reports mean partial/final inference ms on CPU                                                                  |

### Setup

````bash
# 1. Unpack the scripts (run from the repository root, Minor/)
mkdir -p idea/FutureWork/report03_artifacts
python idea/FutureWork/report03_artifacts/unpack.py 2>/dev/null || \
  python - <<'PY'
import pathlib,re
rep=pathlib.Path("idea/FutureWork/REPORT_03_SPEECH_INPUT_AND_TURN_TAKING.md").read_text()
out=pathlib.Path("idea/FutureWork/report03_artifacts");out.mkdir(parents=True,exist_ok=True)
for name,body in re.findall(r"\*\*File:\*\*\s*`([^`]+)`\s*\n+```[a-zA-Z0-9]*\n(.*?)\n```",rep,re.DOTALL):
    if name!="unpack.py": (out/name).write_text(body+"\n")
print("bootstrapped unpack via inline fallback")
PY

# 2. Fast self-check (safe, no long run / no download): validates paths + arg parsing
cd idea/FutureWork/report03_artifacts
bash run_all_long_tests.sh --check

# 3. The real runs (provide inputs first; see each script's header for the exact paths)
conda activate minor
#   L0/L2 want WAVs; L1 wants the ONNX + turns.jsonl:
#   export EOU_MODEL=/path/to/voice-turn-detection.onnx
bash run_all_long_tests.sh            # runs L0, L1, L2; writes <id>/summary.json here
````

Outputs are written next to the scripts: `report03_artifacts/L0_streaming/summary.json`, `L1_eou/summary.json`, `L2_mms/summary.json`.

**File:** `run_all_long_tests.sh`

```bash
#!/usr/bin/env bash
# Runner for the chapter-03 long tests. Resumable: skips a test whose summary.json
# already exists unless --force. --check runs only fast validation (no downloads,
# no model loads, no long runs).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK=0; FORCE=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK=1 ;;
    --force) FORCE=1 ;;
    *) echo "unknown arg: $arg"; exit 2 ;;
  esac
done

run_one() {
  local id="$1"; local script="$2"; local outdir="$HERE/$3"
  mkdir -p "$outdir"
  if [[ "$CHECK" == 1 ]]; then
    python "$HERE/$script" --check --out "$outdir/summary.json"
    return
  fi
  if [[ -f "$outdir/summary.json" && "$FORCE" == 0 ]]; then
    echo "$id: summary.json exists, skipping (use --force to re-run)"; return
  fi
  echo "=== $id starting ==="
  python "$HERE/$script" --out "$outdir/summary.json" || echo "$id: FAILED (see output)"
  echo "=== $id done -> $outdir/summary.json ==="
}

run_one L0 l0_streaming_residual.py L0_streaming
run_one L1 l1_eou_sweep.py          L1_eou
run_one L2 l2_mms_latency.py        L2_mms
echo "All long tests finished. Summaries:"
ls -1 "$HERE"/L*/summary.json 2>/dev/null || true
```

**File:** `l0_streaming_residual.py`

```python
#!/usr/bin/env python3
"""L0 — streaming ASR residual latency + LocalAgreement-2 correction rate.

Streams each WAV in L0_streaming/wavs/ to a RUNNING stt-service over the
WebSocket, real-time-paced, with STT_PREFIX_COMMIT_ENABLED=true. For each
utterance it records:
  - residual latency: wall time from the last audio chunk sent to the FINAL
    event (this is the "last-chunk" pass that streaming should shrink vs a
    whole-clip transcribe);
  - correction rate: fraction of committed tokens (committed_text) that the
    FINAL transcript did NOT keep as a prefix (LocalAgreement-2 should keep
    this small).

Start the service first, e.g.:
    cd code/STT/stt-service
    STT_PREFIX_COMMIT_ENABLED=true STT_LANGUAGE=en python run.py
Then:
    python l0_streaming_residual.py --out L0_streaming/summary.json

--check validates args + input folder + websockets import; it does NOT connect,
stream, or need a server.
"""
import argparse, asyncio, glob, json, os, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE / "L0_streaming" / "wavs"
URL = os.environ.get("STT_URL", "ws://127.0.0.1:8000/ws/stt/l0")
CHUNK_MS = 40


def _lcp_tokens(a, b):
    out = []
    for x, y in zip(a, b):
        if x != y:
            break
        out.append(x)
    return out


async def _stream_one(path, url):
    import soundfile as sf
    import websockets
    data, sr = sf.read(path, dtype="int16")
    if sr != 16000:
        return {"wav": os.path.basename(path), "error": f"expected 16k, got {sr}"}
    if data.ndim > 1:
        data = data[:, 0]
    raw = data.tobytes()
    bpc = int(sr * CHUNK_MS / 1000) * 2

    committed = ""
    final_text = None
    last_send = None
    final_ts = None

    async with websockets.connect(url, ping_interval=None) as ws:
        async def receiver():
            nonlocal committed, final_text, final_ts
            async for msg in ws:
                ev = json.loads(msg)
                if ev["type"] == "partial" and ev.get("committed_text"):
                    committed = ev["committed_text"]
                elif ev["type"] == "final":
                    final_text = ev.get("text", "")
                    final_ts = time.monotonic()
                    break
        rt = asyncio.create_task(receiver())
        for i in range(0, len(raw), bpc):
            await ws.send(raw[i:i + bpc])
            last_send = time.monotonic()
            await asyncio.sleep(CHUNK_MS / 1000)
        await ws.send(json.dumps({"action": "stop"}))
        try:
            await asyncio.wait_for(rt, timeout=30)
        except asyncio.TimeoutError:
            rt.cancel()

    residual_ms = (final_ts - last_send) * 1000 if (final_ts and last_send) else None
    ct = committed.split()
    ft = (final_text or "").split()
    kept = len(_lcp_tokens(ct, ft))
    corr = (len(ct) - kept) / len(ct) if ct else 0.0
    return {"wav": os.path.basename(path), "residual_ms": round(residual_ms, 1) if residual_ms else None,
            "committed_tokens": len(ct), "corrected_tokens": len(ct) - kept,
            "correction_rate": round(corr, 4), "final_text_len": len(ft)}


async def _run(out):
    wavs = sorted(glob.glob(str(WAV_DIR / "*.wav")))
    rows = []
    for w in wavs:
        rows.append(await _stream_one(w, URL))
    res = [r["residual_ms"] for r in rows if r.get("residual_ms")]
    corr = [r["correction_rate"] for r in rows if "correction_rate" in r]
    res.sort()
    summary = {"url": URL, "n_wavs": len(wavs), "rows": rows,
               "median_residual_ms": res[len(res) // 2] if res else None,
               "mean_correction_rate": round(sum(corr) / len(corr), 4) if corr else None,
               "note": "residual = last-chunk-send -> FINAL wall time; compare to a whole-clip "
                       "transcribe of the same WAV. LocalAgreement-2 target: low correction rate."}
    json.dump(summary, open(out, "w"), indent=2)
    print(json.dumps({"median_residual_ms": summary["median_residual_ms"],
                      "mean_correction_rate": summary["mean_correction_rate"]}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        try:
            import websockets, soundfile  # noqa: F401
            imports_ok = True
        except Exception as e:  # pragma: no cover
            imports_ok = f"{type(e).__name__}: {e}"
        info = {"check": True, "wav_dir": str(WAV_DIR), "wav_dir_exists": WAV_DIR.is_dir(),
                "n_wavs": len(glob.glob(str(WAV_DIR / "*.wav"))), "imports_ok": imports_ok}
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        json.dump(info, open(args.out, "w"), indent=2)
        print(json.dumps(info))
        return
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    asyncio.run(_run(args.out))


if __name__ == "__main__":
    main()
```

**File:** `l1_eou_sweep.py`

```python
#!/usr/bin/env python3
"""L1 — EOU false-cut rate and added delay, swept over the threshold tau.

Loads the vedants254-style ONNX model at $EOU_MODEL and runs the stt-service
SemanticTurnDetector directly on labelled turns, offline (no server, no audio
device). Each line of L1_eou/turns.jsonl is:
    {"wav": "path/to/clip.wav", "complete": true|false}
where `complete` is the ground-truth "was the turn actually finished at the end
of this clip". For a sweep of tau it computes, treating `p_complete >= tau` as
"declare done":
    - false-cut rate   = P(declared done | NOT complete)
    - missed rate      = P(declared NOT done | complete)  (these fall back to the
                         silence cap -> added dead air)
Pick the smallest tau with false-cut <= 5% (chapter 03 §12).

Run:
    export EOU_MODEL=/path/to/voice-turn-detection.onnx
    python l1_eou_sweep.py --out L1_eou/summary.json

--check validates onnxruntime import, the model path, and the turns file WITHOUT
loading the model or running inference.
"""
import argparse, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STT_ROOT = HERE.parent.parent.parent / "code" / "STT" / "stt-service"
TURNS = HERE / "L1_eou" / "turns.jsonl"
TAUS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]


def _load_turns():
    rows = []
    with open(TURNS) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    model = os.environ.get("EOU_MODEL", "")

    if args.check:
        try:
            import onnxruntime  # noqa: F401
            ort_ok = True
        except Exception as e:  # pragma: no cover
            ort_ok = f"{type(e).__name__}: {e}"
        info = {"check": True, "eou_model_env": model, "model_exists": bool(model) and os.path.isfile(model),
                "turns_file": str(TURNS), "turns_exists": TURNS.is_file(), "onnxruntime_ok": ort_ok,
                "stt_root_exists": STT_ROOT.is_dir()}
        json.dump(info, open(args.out, "w"), indent=2)
        print(json.dumps(info))
        return

    if not model or not os.path.isfile(model):
        json.dump({"error": f"EOU_MODEL not found: {model!r}"}, open(args.out, "w"), indent=2)
        print("EOU_MODEL not set or missing"); sys.exit(1)

    # Reuse the service's own detector so we test the shipped code path.
    sys.path.insert(0, str(STT_ROOT))
    os.environ["STT_EOU_ENABLED"] = "true"
    os.environ["STT_EOU_MODEL_PATH"] = model
    import importlib, dataclasses
    import src.config as config_mod
    importlib.reload(config_mod)
    import src.turn_detector as td
    importlib.reload(td)
    import soundfile as sf
    import numpy as np

    det = td.SemanticTurnDetector()
    turns = _load_turns()
    probs = []
    for t in turns:
        audio, sr = sf.read(t["wav"], dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        r = det.predict(np.asarray(audio, dtype=np.float32))
        probs.append((r.p_complete, bool(t["complete"])))

    sweep = []
    for tau in TAUS:
        fp = sum(1 for p, c in probs if p is not None and p >= tau and not c)
        n_neg = sum(1 for _, c in probs if not c)
        fn = sum(1 for p, c in probs if (p is None or p < tau) and c)
        n_pos = sum(1 for _, c in probs if c)
        sweep.append({"tau": tau,
                      "false_cut_rate": round(fp / n_neg, 4) if n_neg else None,
                      "missed_rate": round(fn / n_pos, 4) if n_pos else None})
    ok = [s for s in sweep if s["false_cut_rate"] is not None and s["false_cut_rate"] <= 0.05]
    summary = {"model": model, "n_turns": len(turns), "sweep": sweep,
               "recommended_tau": (min(s["tau"] for s in ok) if ok else None),
               "note": "recommended_tau = smallest tau with false-cut <= 5% (chapter 03 §12). "
                       "Add per-language turns to calibrate a per-language tau."}
    json.dump(summary, open(args.out, "w"), indent=2)
    print(json.dumps({"recommended_tau": summary["recommended_tau"]}))


if __name__ == "__main__":
    main()
```

**File:** `l2_mms_latency.py`

```python
#!/usr/bin/env python3
"""L2 — real MMS `hne` CPU partial/final latency on T0 (replaces the 1850 ms slide).

Loads the stt-service ChhattisgarhiMMSEngine on CPU and times `transcribe` for
each WAV in L2_mms/wavs/, separately for fast=True (partial) and fast=False
(final). This is the number chapter 03 §7/§8 and REPORT_01 §6 flag as unverified.

Run (model downloads on first use; CPU-heavy):
    python l2_mms_latency.py --out L2_mms/summary.json

--check validates torch/transformers import and the WAV folder WITHOUT loading
the 1B model.
"""
import argparse, glob, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STT_ROOT = HERE.parent.parent.parent / "code" / "STT" / "stt-service"
WAV_DIR = HERE / "L2_mms" / "wavs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    if args.check:
        try:
            import torch, transformers  # noqa: F401
            imports_ok = True
        except Exception as e:  # pragma: no cover
            imports_ok = f"{type(e).__name__}: {e}"
        info = {"check": True, "wav_dir": str(WAV_DIR), "wav_dir_exists": WAV_DIR.is_dir(),
                "n_wavs": len(glob.glob(str(WAV_DIR / "*.wav"))), "imports_ok": imports_ok,
                "stt_root_exists": STT_ROOT.is_dir()}
        json.dump(info, open(args.out, "w"), indent=2)
        print(json.dumps(info))
        return

    sys.path.insert(0, str(STT_ROOT))
    # Force CPU + hne so we measure the T0-relevant path.
    os.environ["STT_DEVICE"] = "cpu"
    os.environ["STT_LANGUAGE"] = "hne"
    import importlib
    import src.config as config_mod
    importlib.reload(config_mod)
    import src.asr as asr_mod
    importlib.reload(asr_mod)
    import soundfile as sf
    import numpy as np

    engine = asr_mod.ChhattisgarhiMMSEngine()
    rows = []
    for w in sorted(glob.glob(str(WAV_DIR / "*.wav"))):
        audio, sr = sf.read(w, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        audio = np.asarray(audio, dtype=np.float32)
        t0 = time.monotonic(); p = engine.transcribe(audio, fast=True)
        t1 = time.monotonic(); f = engine.transcribe(audio, fast=False)
        t2 = time.monotonic()
        rows.append({"wav": os.path.basename(w), "dur_s": round(len(audio) / sr, 2),
                     "partial_ms": round((t1 - t0) * 1000, 1), "final_ms": round((t2 - t1) * 1000, 1),
                     "partial_text_len": len(p.text), "final_text_len": len(f.text)})
    pm = [r["partial_ms"] for r in rows]; fm = [r["final_ms"] for r in rows]
    summary = {"device": "cpu", "language": "hne", "n_wavs": len(rows), "rows": rows,
               "mean_partial_ms": round(sum(pm) / len(pm), 1) if pm else None,
               "mean_final_ms": round(sum(fm) / len(fm), 1) if fm else None,
               "note": "compares against the unverified 1850 ms slide (REPORT_01 §6). "
                       "First WAV includes one-time warmup; report warm numbers separately if needed."}
    json.dump(summary, open(args.out, "w"), indent=2)
    print(json.dumps({"mean_partial_ms": summary["mean_partial_ms"],
                      "mean_final_ms": summary["mean_final_ms"]}))


if __name__ == "__main__":
    main()
```

**File:** `unpack.py`

````python
#!/usr/bin/env python3
"""Unpack the fenced **File:** blocks of REPORT_03 into this directory.

Reads ../REPORT_03_SPEECH_INPUT_AND_TURN_TAKING.md, finds each block whose
heading line is  **File:** `name`  immediately followed by a fenced code block,
and writes it next to this script. Idempotent.
"""
import pathlib, re

HERE = pathlib.Path(__file__).resolve().parent
REPORT = HERE.parent / "REPORT_03_SPEECH_INPUT_AND_TURN_TAKING.md"
text = REPORT.read_text(encoding="utf-8")
pattern = re.compile(r"\*\*File:\*\*\s*`([^`]+)`\s*\n+```[a-zA-Z0-9]*\n(.*?)\n```", re.DOTALL)
count = 0
for name, body in pattern.findall(text):
    if name == "unpack.py":
        continue
    (HERE / name).write_text(body + "\n", encoding="utf-8")
    count += 1
    print("wrote", name)
print(f"unpacked {count} files into {HERE}")
````

### My check before finishing

Per the AGENTS long-test rule I syntax-checked the scripts, unpacked them once, and ran only the fast `--check` paths — no downloads, no model loads, no streaming, no long runs. See the "Test results" above for the exact commands and outcomes recorded at authoring time. I did not run `L0`, `L1`, or `L2`, and did not start them in the background. After you run them, hand me the three `summary.json` files and I will fold the measured residual latency, correction rate, EOU false-cut/added-delay curve, and MMS `hne` latency into the Before vs. After table and mark the pending rows measured.
