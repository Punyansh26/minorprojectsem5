# REPORT 10 — Throughput, Concurrency and Telephony

## Summary

Chapter 10 recommends, for the current laptop tier (T0), keeping the one-worker admission
queue and adding two cheap, local queue improvements — **short-turn priority** and
**deadline-aware shedding** — plus concurrency observability, and it specifies load-test
methods and a fully local telephony path. This task implements the Demo2-applicable parts:
a two-class priority queue and an opt-in deadline-aware shedding admission check in
`code/demo2/jobs.py`, gated by new `code/demo2/settings.py` knobs, with new observability
gauges surfaced through `JobManager.stats()` (already exposed over `/api/health`). All changes
are non-destructive and reorder *when* turns run or shed overload earlier — they never touch
grounding (verbatim quotes, release-bound caches, exact SQL cutoffs). Telephony (§5), engine
parallelism/continuous batching (§2–§3), GPU co-residency/MPS (§4), and security hardening
(§6) are **out of Demo2 scope** (they live in the LLM engine, the STT service, or a reverse
proxy, not in `code/demo2/`) and are documented here rather than implemented. The §9 load
tests are **long tests** and appear as runnable scripts at the end of this report for the user
to run; every throughput number in chapter 10 is `[Estimated]`/`[Reported]` and remains so
until those runs produce measurements.

## What was done

- **`code/demo2/settings.py`** — added five Task-10 knobs with positive-value validation:
  - `SHORT_TURN_PRIORITY_ENABLED` (`DEMO2_SHORT_TURN_PRIORITY`, default **true**)
  - `SHORT_TURN_MAX_CHARS` (`DEMO2_SHORT_TURN_MAX_CHARS`, default **40**)
  - `PREDICTED_HEAVY_TURN_SECONDS` (`DEMO2_PREDICTED_HEAVY_TURN_SECONDS`, default **18.7**, the measured answered-turn mean S from 01 §4.1)
  - `PREDICTED_SHORT_TURN_SECONDS` (`DEMO2_PREDICTED_SHORT_TURN_SECONDS`, default **1.0**)
  - `DEADLINE_SHEDDING_ENABLED` (`DEMO2_DEADLINE_SHEDDING`, default **false**, opt-in)
- **`code/demo2/jobs.py`** — the §1.4 improvements:
  - Module-level `predict_short_turn(text, max_chars)` — a conservative text heuristic that
    flags only near-certain trivial turns (greetings, thanks, yes/no, very short no-question
    utterances, in English and Devanagari). A voice recording (text unknown at admission) is
    never flagged.
  - Module-level `predicted_service_seconds(is_short)` — the planning estimate S used for
    shedding and observability.
  - `Job.short_turn: bool` field; `JobManager.priority` second deque.
  - `submit()` now classifies the turn, optionally applies deadline-aware shedding to heavy
    turns, routes short turns to the priority deque, and increments `admitted:short` /
    `admitted:normal` / `overload_predicted` counters.
  - `_loop()` waits on either deque and **drains the priority deque first**.
  - `stats()` now also returns live `gauge:*` fields (queue/priority depth, active jobs,
    capacity, executing count, overload rate) alongside the existing cumulative counters.
- **`code/demo2/tests/test_throughput.py`** — new test module, 31 tests: predictor unit tests,
  priority ordering, priority-disabled FIFO fallback, recording-always-heavy, deadline shedding
  (opt-in), shedding-disabled capacity behaviour, `stats()` gauges, overload-rate, and an
  end-to-end prioritised short turn driven through the real worker.

## How it was done

### Short-turn priority (§1.4, implemented, on by default)

The chapter's intuition is that regex/learned-router turns (greetings, thanks, yes/no) finish
in ≪1 s with 0 LLM calls, so a two-class queue lets them jump ahead of a ~18 s knowledge turn.
Classification happens in `submit()`, which is the **only** admission point and runs *before*
any STT or model work. The agent's real router (`router_path`) is computed *inside*
`agent_bridge.ask`, i.e. after admission, so it is unavailable here; the predictor is therefore
a deliberately cheap and conservative text heuristic:

- An exact match (after lowercasing and trimming trailing punctuation) against a small set of
  greeting/thanks/yes-no markers → short.
- Otherwise, a turn is short only if it is within `SHORT_TURN_MAX_CHARS`, has no `?`, and starts
  with one of those markers.
- Any voice recording is heavy (its transcript is unknown at admission).

Erring toward "heavy" is the safe direction: a mis-flagged heavy turn would wrongly jump the
queue, whereas a mis-flagged short turn merely loses the priority it could have had. `_loop`
drains `self.priority` before `self.queue`, feeding the **same single reasoning worker** — this
is scheduling only, not a second model slot (T0 keeps `OLLAMA_NUM_PARALLEL=1`, per §2's T0
caveat that parallelism is a net loss on 8 GB).

### Deadline-aware shedding (§1.4, implemented, opt-in / off by default)

`submit()` estimates predicted completion for a heavy admission as
`ahead + S_heavy`, where `ahead` is the summed predicted service of jobs already queued or
executing and `S_heavy = PREDICTED_HEAVY_TURN_SECONDS`. If that exceeds
`QUEUE_TIMEOUT_SECONDS`, the turn is rejected immediately with the same `"busy"` error the hard
capacity cap already raises, incrementing a new `overload_predicted` counter — instead of
admitting it and letting it fail `queue_timeout`/`deadline_exceeded` later after spending STT.
Short turns bypass the check (they always fit). This is strictly a fast-`busy` policy on top of
the existing capacity cap; it never interrupts a running turn (native calls are not
interruptible, consistent with `operations.py`).

**Design decision — default OFF.** With shedding on by default, the existing contract test
`tests/test_operations.py::test_fifo_capacity_same_session_and_cancellation` fails: it admits
four heavy turns (1 executing + 3 queued) under the pure-capacity contract, but
`3·18.7 + 18.7 = 74.8 s > 60 s` would shed the fourth. Rather than rewrite an existing
behavioural contract, shedding is **opt-in** (`DEMO2_DEADLINE_SHEDDING=true`). Short-turn
priority stays on by default because it breaks nothing. This keeps the default admission
behaviour byte-for-byte compatible while making the chapter's improvement available to an
operator who wants it. The decision is reversible via the env var.

### Observability (§7, implemented)

The chapter notes `JobManager.stats()`/`self.counters` already track `overload` and router
paths, and asks to "surface queue depth and `overload` rate as gauges". `stats()` now appends
`gauge:queue_depth`, `gauge:priority_depth`, `gauge:queue_depth_total`, `gauge:active_jobs`,
`gauge:queue_capacity`, `gauge:executing`, and `gauge:overload_rate` (shed / offered). These
flow unchanged through the existing `/api/health` endpoint, which already calls `rt.stats()`.
No new endpoint was added. The gauges carry no student content — only depths and coarse stage
counts — consistent with the privacy boundary.

### What was deliberately **not** implemented (out of Demo2 scope)

| Chapter area | Why not in Demo2 | Where it belongs |
| --- | --- | --- |
| §2 Ollama/llama-server parallel slots, `-np`/`-cb` | The engine owns slots; §2 explicitly says **keep `NUM_PARALLEL=1` on T0** (RAM multiplier → more CPU offload → slower). Relaxing `_LOCAL_LOCK` to a semaphore is a change to `IA/assistant/llm.py`, outside `code/demo2/`. | LLM serving (05), engine launch flags |
| §3 PagedAttention / RadixAttention / chunked prefill | vLLM/SGLang serving engines; T2 only; not applicable at 8 GB for a 9B at useful batch. | LLM serving (05), T2 infra |
| §4 GPU co-residency / MPS / Triton | Device placement already set to CPU for speech in `settings.py`; the big T0 win (free desktop VRAM) is an OS/display change, not code. | OS config, 02/05 |
| §5 Telephony (Asterisk/FreeSWITCH/LiveKit SIP, G.711 resample, AEC, DTMF) | The converter (`telephony_adapter.py`) and the orchestrator live in `code/STT/` and `code/Institute-voice-agent/`, not Demo2. Demo2 has no SIP front end. | STT service, voice-orchestrator |
| §6 Security (auth/TLS/rate limiting) | Belongs at a reverse proxy / the STT service (`STT_API_KEY`); Demo2's `jobs.py` admission already sheds overload, which is the one piece that *is* in scope and is tuned here. | reverse proxy, STT service |

These are recorded here as **out of scope (not Demo2)** per the FutureWork AGENTS.md rule,
rather than implemented in a sibling project.

### Grounding

No change touches `evidence.py::source_quote`, `cache.py`, or `facts.sqlite`. The admission
layer reorders when turns run and sheds overload earlier; the turn body — retrieval, grounding
verification, exact cutoffs — is identical. The full Demo2 suite (including every grounding and
storage test) passes unchanged.

## Before vs. After

| Metric | Before | After | Change | Evidence label |
| --- | --- | --- | --- | --- |
| Queue classes | 1 (single FIFO) | 2 (priority + normal), priority drained first | +1 class | [Measured-here] code |
| Trivial-turn wait behind a heavy turn | up to ~S ≈ 18.7 s | ≈ 0 (jumps the line) | −~18.7 s p50 for trivial turns | [Estimated] §1.4 |
| Heavy-turn throughput | unchanged | unchanged (same single worker) | 0% | [Estimated] §1.4 |
| Overload handling | capacity cap only (admit 4, shed 5th) | + optional deadline predictor (fast `busy` before STT) | earlier, cheaper shedding when enabled | [Measured-here] test |
| Observability gauges in `stats()` | 0 (`overload`/router counters only) | 7 live `gauge:*` fields | +7 | [Measured-here] test |
| Demo2 test count | 90 passing | 121 passing (+31 new) | +31 | [Measured-here] pytest |
| T0 answered turns/hour (comfort, ρ=0.7) | ~135/h | ~135/h (mixed traffic higher: trivial turns bypass the heavy queue) | qualitative gain on mixed traffic | [Estimated] §8 |

Capacity figures (turns/hour, concurrent calls) are chapter-level `[Estimated]` from the
single-turn S and queueing theory; this task did not run a multi-user benchmark (that is a long
test — see the last section). No new `[Measured-here]` throughput number is claimed.

## Files changed

```
Modified: code/demo2/settings.py            — added 5 Task-10 knobs (short-turn priority, predicted service times, opt-in deadline shedding) + validation
Modified: code/demo2/jobs.py                — predict_short_turn()/predicted_service_seconds(); Job.short_turn; JobManager.priority deque; submit() classification + shedding; _loop() priority drain; stats() live gauges
Created:  code/demo2/tests/test_throughput.py — 31 unit/integration tests for the above
Created:  idea/FutureWork/REPORT_10_THROUGHPUT_CONCURRENCY_AND_TELEPHONY.md — this report
```

No files were deleted. No sibling project was modified. No chapter documents were edited.

## Issues encountered

- **Default-on deadline shedding broke an existing contract test.** With
  `DEADLINE_SHEDDING_ENABLED=true` by default, `test_operations.py::
  test_fifo_capacity_same_session_and_cancellation` failed because the predictor sheds the 4th
  heavy turn that the pure-capacity contract admits. **Resolved** by making deadline shedding
  **opt-in** (default false) via `DEMO2_DEADLINE_SHEDDING`; short-turn priority (which breaks
  nothing) stays on. The existing test passes untouched. Open consideration: if the user wants
  shedding on by default, that existing test's expectation would need updating — flagged, not
  done.
- **Predictor cannot use the agent's real router at admission.** `router_path` is computed
  inside `agent_bridge.ask` (post-admission), so the admission-time predictor is a text
  heuristic, not the learned router. **Resolved** by making it conservative (recordings and any
  uncertain turn are heavy). This can under-prioritise a trivial turn phrased unusually, but it
  never mis-prioritises a heavy one. Not a correctness risk — only a scheduling hint.
- **Tests needed the agent import path.** The end-to-end test's worker imports
  `assistant.operations` lazily inside `_run`; the test prepends `settings.AGENT_ROOT` to
  `sys.path` (as `jobs.manager()` does in the live app). **Resolved.**
- No grounding, storage, or regression issues. Full suite green (121 passed).

## Dependencies and prerequisites

- **No new packages** added to the `minor` environment for the implemented code. Demo2 pins
  (`compatibility-constraints.txt`, `requirements.txt`) are unchanged.
- The **long** load-test scripts need extra packages the user installs when running them:
  `locust` (MIT, text path) and `websockets` + `soundfile`/`numpy` (voice path, already in
  `minor`). These are **not** added to Demo2 requirements because load tooling is not a runtime
  dependency.
- Assumes the measured baseline S ≈ 18.7 s from chapter 01 §4.1 as the heavy-turn planning
  estimate; it is a tunable setting, not a hard-coded constant.
- Hardware: implementation and short tests run on T0 (RTX 4060 Laptop, i7-14650HX, 31 GB RAM).
  The long load tests need the GPU idle (the 9B reasoning model) and a running Demo2 API server.

## Next steps

- Run the §9 load tests (below) to replace the `[Estimated]` capacity figures with
  `[Measured-here]` ones: the text-path knee (max λ with p95 ≤ budget) and the voice-path
  `session_rejected` behaviour.
- If the measured timeout/shedding behaviour supports it, consider flipping
  `DEMO2_DEADLINE_SHEDDING` on by default and updating the one capacity contract test.
- Unblocked follow-ups (other chapters): §2 engine slots + `_LOCAL_LOCK`→semaphore once the
  model fits fully on GPU (requires 02/05 VRAM work); the learned router could feed a better
  short-turn signal once 09's Hindi/Hinglish router lands.
- Telephony (§5) and security (§6) remain future work in the STT service / a reverse proxy,
  outside Demo2.

## Test results

Short tests (run by me, in the `minor` env, from `code/demo2/`):

```
python -m pytest tests/test_throughput.py -q
# -> 31 passed

python -m pytest tests/ -q
# -> 121 passed  (was 90 before this task; +31 new; no regressions)

python -m py_compile jobs.py settings.py
# -> clean
```

The new `tests/test_throughput.py` covers: the predictor (trivial vs heavy, both scripts),
short-turn priority ordering, priority-disabled FIFO fallback, recording-always-heavy, opt-in
deadline shedding (shed + not-shed-for-short), shedding-disabled capacity, the `stats()` gauges,
the overload rate, and an end-to-end prioritised short turn completing through the real worker.

No **long** tests were run by me. They are in the next section for the user.

## Long-running tests (to be run by the user later)

These answer "what is the real multi-user capacity and overload behaviour?" — the one thing the
chapter marks as entirely `[Estimated]` because no multi-user run exists. They need the GPU to
themselves (the 9B model) and a running Demo2 API server, so they are long tests for the user.

| ID | Question it answers | ~Run time | Needs | Pass / read-out criterion |
| --- | --- | --- | --- | --- |
| L0 | Does short-turn priority cut trivial-turn wait under mixed load, with no heavy-turn regression? | 20–40 min | GPU idle, Demo2 API server up, `locust` | trivial-turn p50 wait ≪ heavy-turn p50; heavy-turn p95 within budget; read `summary.json` |
| L1 | Where is the text-path throughput knee (max λ with p95 ≤ budget), and is overload shed (429) not silently slow? | 30–60 min | GPU idle, Demo2 API server up, `locust` | knee λ documented; 429 rate rises at overload; no turn silently exceeds the turn budget |
| L2 | Voice-path: ASR partial lag and `session_rejected` rate up to `STT_MAX_CONCURRENT_SESSIONS` | 20–40 min | STT service up, recorded 16 kHz WAV, `websockets` | sessions beyond cap rejected cleanly; partial lag recorded; read `summary.json` |

L0/L1 are Demo2-native (text path through `/api/turns/text`). L2 targets the **existing** STT
service read-only (no modification), per the chapter's §9 voice-path method.

### Setup

1. Save the fenced scripts below into a scratch directory **outside** the repo's data dirs,
   e.g. `~/fw10_loadtest/`. Each script is preceded by a `**File:** `name`` line.
2. Start the Demo2 API server in one terminal (GPU idle otherwise):
   ```bash
   conda activate minor
   cd "code/demo2"
   uvicorn api_server:app --host 127.0.0.1 --port 8000
   ```
   (L2 additionally needs the STT service: `cd code/STT/stt-service && python run.py`.)
3. Install load tooling into `minor` (not added to Demo2 requirements):
   ```bash
   conda activate minor
   pip install locust websockets soundfile numpy
   ```
4. Run everything and collect `summary.json` files:
   ```bash
   cd ~/fw10_loadtest
   bash run_all_long_tests.sh
   ```
   Outputs are written under `~/fw10_loadtest/out/<test-id>/` (never into the repo).

After running, hand me the `summary.json` files and I will fold the measured numbers into this
report as an addendum, replacing the `[Estimated]` capacity rows with `[Measured-here]`.

### Scripts

**File:** `run_all_long_tests.sh`

```bash
#!/usr/bin/env bash
# FutureWork 10 — long load tests. Resumable: each test writes out/<id>/summary.json and skips
# if that file already exists. Keeps all scratch outside the repo. Does NOT start the servers
# (start them yourself per the Setup section) and does NOT pull any model.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${FW10_OUT:-$HERE/out}"
BASE_URL="${DEMO2_BASE_URL:-http://127.0.0.1:8000}"
STT_URL="${STT_WS_URL:-ws://127.0.0.1:8001/ws}"
mkdir -p "$OUT"

run_one () {
  local id="$1"; shift
  if [ -f "$OUT/$id/summary.json" ]; then
    echo "[$id] summary.json exists — skipping (delete it to re-run)"; return 0
  fi
  mkdir -p "$OUT/$id"
  echo "[$id] starting: $*"
  ( "$@" ) ; local rc=$?
  echo "[$id] exit=$rc"
  return 0
}

# L0 — mixed-traffic priority effect (low arrival rate, mixed short/heavy)
run_one L0 locust -f "$HERE/locust_text.py" --headless \
  -u 6 -r 1 -t 20m --host "$BASE_URL" \
  --csv "$OUT/L0/l0" --json 2>"$OUT/L0/locust.log" \
  --mix mixed --out "$OUT/L0/summary.json"

# L1 — throughput knee sweep (ramp users to find p95 budget breach / 429 rise)
run_one L1 locust -f "$HERE/locust_text.py" --headless \
  -u 20 -r 1 -t 40m --host "$BASE_URL" \
  --csv "$OUT/L1/l1" --json 2>"$OUT/L1/locust.log" \
  --mix heavy --out "$OUT/L1/summary.json"

# L2 — voice-path concurrency against the existing STT service (read-only)
run_one L2 python "$HERE/ws_voice_load.py" \
  --url "$STT_URL" --wav "${FW10_WAV:-$HERE/sample_16k.wav}" \
  --sessions 8 --out "$OUT/L2/summary.json"

echo "All done. Summaries under: $OUT"
```

**File:** `locust_text.py`

```python
"""FutureWork 10 §9 text-path load test for Demo2's /api/turns/text admission path.

Each virtual user opens a session, submits a turn, then polls GET /api/session/{id} until the
turn reaches a terminal stage (complete/failed/cancelled) or a local deadline. Records wait +
service latency, the HTTP 429 overload rate, and the final per-class latency split. A custom
--mix flag chooses the traffic blend; --out writes a compact summary.json at quit.

Read-only w.r.t. the repo: it only calls the running API; it writes summary.json to --out.
"""
import json
import time
import uuid
import random
from locust import HttpUser, task, events, between

# Trivial turns the short-turn predictor should prioritise, and heavy knowledge turns.
SHORT_TURNS = ["thanks", "hello", "yes", "ok", "namaste", "thank you", "bye"]
HEAVY_TURNS = [
    "What are the B.Tech admission requirements for CSE?",
    "How much is the hostel fee per semester?",
    "What was the JoSAA closing rank for ECE in 2024?",
    "Explain the fee refund policy for first-year students.",
    "What documents are needed at reporting?",
]

_LAT = {"short": [], "heavy": []}
_CODES = {}
_MIX = "mixed"
_OUT = "summary.json"
POLL_DEADLINE_S = 180.0


@events.init_command_line_parser.add_listener
def _add_args(parser):
    parser.add_argument("--mix", choices=["mixed", "heavy", "short"], default="mixed",
                        help="traffic blend")
    parser.add_argument("--out", default="summary.json", help="summary json path")


@events.test_start.add_listener
def _start(environment, **_):
    global _MIX, _OUT
    _MIX = environment.parsed_options.mix
    _OUT = environment.parsed_options.out


@events.test_stop.add_listener
def _stop(environment, **_):
    def pct(xs, p):
        if not xs:
            return None
        s = sorted(xs)
        return round(s[min(len(s) - 1, int(p / 100 * len(s)))], 3)
    summary = {
        "mix": _MIX,
        "counts": {k: len(v) for k, v in _LAT.items()},
        "latency_seconds": {
            cls: {"p50": pct(xs, 50), "p95": pct(xs, 95), "p99": pct(xs, 99),
                  "max": round(max(xs), 3) if xs else None}
            for cls, xs in _LAT.items()
        },
        "http_codes": _CODES,
        "overload_429_rate": round(_CODES.get(429, 0) / max(1, sum(_CODES.values())), 4),
    }
    with open(_OUT, "w") as fh:
        json.dump(summary, fh, indent=2)
    print("WROTE", _OUT, json.dumps(summary))


class HelpdeskUser(HttpUser):
    wait_time = between(1, 4)

    def on_start(self):
        r = self.client.post("/api/session/new", json={}, name="session/new")
        self.session_id = r.json()["session_id"] if r.ok else None

    @task
    def one_turn(self):
        if not self.session_id:
            self.on_start()
            return
        if _MIX == "short":
            question, cls = random.choice(SHORT_TURNS), "short"
        elif _MIX == "heavy":
            question, cls = random.choice(HEAVY_TURNS), "heavy"
        else:
            if random.random() < 0.5:
                question, cls = random.choice(SHORT_TURNS), "short"
            else:
                question, cls = random.choice(HEAVY_TURNS), "heavy"
        turn_id = str(uuid.uuid4())
        t0 = time.monotonic()
        r = self.client.post("/api/turns/text", name="turns/text",
                             json={"session_id": self.session_id, "turn_id": turn_id,
                                   "question": question, "provider": "ollama",
                                   "spoken": False, "input_language": "English"})
        _CODES[r.status_code] = _CODES.get(r.status_code, 0) + 1
        if r.status_code == 429:  # overload shed — expected under load, not an error
            return
        if not r.ok:
            return
        deadline = time.monotonic() + POLL_DEADLINE_S
        while time.monotonic() < deadline:
            s = self.client.get(f"/api/session/{self.session_id}", name="session/poll")
            if not s.ok:
                time.sleep(0.5)
                continue
            turns = {t["id"]: t for t in s.json().get("turns", [])}
            stage = (turns.get(turn_id) or {}).get("stage")
            if stage in {"complete", "failed", "cancelled"}:
                _LAT[cls].append(time.monotonic() - t0)
                return
            time.sleep(0.5)
        _LAT[cls].append(time.monotonic() - t0)  # timed out locally; record anyway
```

**File:** `ws_voice_load.py`

```python
"""FutureWork 10 §9 voice-path load test against the EXISTING STT service (read-only).

Opens N concurrent WebSocket sessions, streams a 16 kHz mono PCM WAV in ~20 ms frames to each,
and records ASR partial lag and the session_rejected rate up to STT_MAX_CONCURRENT_SESSIONS.
It does NOT modify the STT service or Demo2; it only connects to the running service and writes
summary.json to --out. Requires: websockets, soundfile, numpy (all in the `minor` env).
"""
import argparse
import asyncio
import json
import time

import numpy as np
import soundfile as sf

try:
    import websockets
except ImportError as exc:  # pragma: no cover - user installs when running
    raise SystemExit("pip install websockets soundfile numpy") from exc


def load_pcm16(path, target_rate=16000):
    audio, rate = sf.read(path, dtype="float32", always_2d=False)
    if getattr(audio, "ndim", 1) > 1:
        audio = audio.mean(axis=1)
    if rate != target_rate:  # simple linear resample; fidelity is not the metric here
        n = int(round(len(audio) * target_rate / rate))
        audio = np.interp(np.linspace(0, len(audio), n, endpoint=False),
                          np.arange(len(audio)), audio).astype("float32")
    return (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()


async def one_session(url, pcm, frame_bytes, results, idx):
    t0 = time.monotonic()
    first_partial = None
    rejected = False
    try:
        async with websockets.connect(url, max_size=None) as ws:
            async def sender():
                for off in range(0, len(pcm), frame_bytes):
                    await ws.send(pcm[off:off + frame_bytes])
                    await asyncio.sleep(0.02)  # ~20 ms real-time pacing
                await ws.send(json.dumps({"type": "eos"}))
            send_task = asyncio.create_task(sender())
            try:
                async for message in ws:
                    if isinstance(message, bytes):
                        continue
                    try:
                        event = json.loads(message)
                    except ValueError:
                        continue
                    etype = event.get("type", "")
                    if etype == "session_rejected":
                        rejected = True
                        break
                    if "partial" in etype and first_partial is None:
                        first_partial = time.monotonic() - t0
                    if etype in {"final", "session_closed"}:
                        break
            finally:
                send_task.cancel()
    except Exception as exc:
        results[idx] = {"error": type(exc).__name__}
        return
    results[idx] = {"rejected": rejected, "first_partial_s": first_partial,
                    "total_s": round(time.monotonic() - t0, 3)}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8001/ws")
    ap.add_argument("--wav", required=True)
    ap.add_argument("--sessions", type=int, default=8)
    ap.add_argument("--out", default="summary.json")
    args = ap.parse_args()

    pcm = load_pcm16(args.wav)
    frame_bytes = int(16000 * 0.02) * 2  # 20 ms of 16-bit mono
    results = [None] * args.sessions
    await asyncio.gather(*(one_session(args.url, pcm, frame_bytes, results, i)
                           for i in range(args.sessions)))

    lags = [r["first_partial_s"] for r in results if r and r.get("first_partial_s") is not None]
    summary = {
        "sessions": args.sessions,
        "rejected": sum(1 for r in results if r and r.get("rejected")),
        "errors": sum(1 for r in results if r and r.get("error")),
        "first_partial_lag_s": {
            "min": round(min(lags), 3) if lags else None,
            "mean": round(sum(lags) / len(lags), 3) if lags else None,
            "max": round(max(lags), 3) if lags else None,
        },
        "detail": results,
    }
    with open(args.out, "w") as fh:
        json.dump(summary, fh, indent=2)
    print("WROTE", args.out, json.dumps(summary))


if __name__ == "__main__":
    asyncio.run(main())
```

### My pre-flight check of the scripts

I syntax-checked every script and confirmed the runner parses, but did **not** run any load
test (no server started, no model pulled):

```
python -m py_compile locust_text.py ws_voice_load.py   # clean
bash -n run_all_long_tests.sh                           # clean
python ws_voice_load.py --help                          # prints usage, exits 0
```

The locust file uses only the public `/api/session/new`, `/api/turns/text`, and
`/api/session/{id}` contract verified in `api_server.py`; the voice script uses only the STT
WebSocket event names (`partial`, `final`, `session_rejected`, `session_closed`) from the STT
service README. Adjust `--url`/`STT_WS_URL` and `--wav`/`FW10_WAV` to your service port and a
recorded 16 kHz WAV before running L2.
