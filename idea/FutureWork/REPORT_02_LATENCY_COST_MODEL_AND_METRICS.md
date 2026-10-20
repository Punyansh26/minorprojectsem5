# REPORT 02 — Latency, cost model and metrics

Task: [02 Latency, cost model and metrics](02_LATENCY_COST_MODEL_AND_METRICS.md). Date: 2026-10-20 (IST). Repository HEAD at start: `2907c5a`. Hardware tier: **T0** (RTX 4060 Laptop 8 GB, i7-14650HX 24 threads without AVX-512, 31 GB RAM, Ollama, `qwen3.5:9b` Q4_K_M).

Evidence labels follow [00_INDEX](00_INDEX.md): **[Measured-here]**, **[Reported]**, **[Estimated]**.

`IA/` abbreviates `code/Institute-voice-agent/institute-assistant/`. Paths are relative to the repository root (`Minor/`).

## Summary

Chapter 02 is the equations chapter: every planning number in the roadmap is `[Estimated]` from it. Two things were missing in code. First, the equations lived only in prose, so each roadmap figure was a hand calculation that no test could catch if it drifted. Second, the cost model's core terms — prompt tokens, output tokens, and the prefill/decode rates per call — were captured by `operations.record_attempt` on a provider call but never written anywhere the benchmark could see them, so they could not be split from real traffic (chapter 02 §2 and §8 both flag this). This task turns the equations into a tested, pure-Python calculator (`IA/assistant/cost_model.py`) that reproduces the chapter's worked numbers, and wires the already-captured per-call token counts and durations into `rag_metrics['calls']` so they appear in benchmark JSON (`turns[].rag_metrics.calls`) with no new instrumentation and no sensitive content. 23 unit tests were added; the full offline suite is 331 passed, 0 failed. No long test was run by me; the energy-sampling and decode-rate probe scripts are in the last section for you to run.

## What was done

- Added `code/Institute-voice-agent/institute-assistant/assistant/cost_model.py`: pure functions for every equation in chapter 02 — perceived latency (§1), streaming first-output overlap (§1.1), one LLM call and the decode-bound threshold (§2), memory-bound decode tok/s (§2.1), KV-cache size and a VRAM budget check (§3), Amdahl speedup and new-turn time (§4), the compounding-tail probability (§5), energy and cost per turn (§6) — plus `split_call_rates`/`call_record`, which convert one Ollama call's numeric allowlist into prefill/decode rates. Baseline constants are taken from chapter 01 §4.3 and labelled.
- Modified `code/Institute-voice-agent/institute-assistant/assistant/operations.py`: `record_attempt` now always publishes its numeric allowlist to a context-local slot (`last_measurement()`), not only when an `Operation` is active. Added `last_measurement()` and `clear_measurement()`. The allowlist is applied in one place, so no prompt, question or provider body can leak.
- Modified `code/Institute-voice-agent/institute-assistant/assistant/metrics.py`: `call_model` clears the measurement slot before invoking, then after the call appends `cost_model.call_record(stage, measurement)` to `rag_metrics['calls']`. `measure_node`'s reset now seeds `'calls': []` so the shape is stable from the turn's start.
- Added `code/Institute-voice-agent/institute-assistant/tests/test_cost_model.py`: 23 tests covering the chapter's worked numbers and the metrics wiring.
- Wrote this report with the two long-test scripts (energy sampling, decode-rate probe) for you to run later.

No chapter document was edited. No configuration, model or existing document outside this report was changed. The only files touched are the four above plus this report.

## How it was done

### The calculator (`cost_model.py`)

Every function is a pure function of its arguments: no I/O, no model load, no network. This lets the roadmap's `[Estimated]` numbers be re-derived by code and pinned by a test, instead of being hand calculations. Each worked figure in chapter 02 has a matching assertion:

- `kv_cache_mib(8192)` → 256.0 MiB (§3 table).
- `decode_tokens_per_second(split_weights_gb(0.45))` → 16.9 tok/s (§2.1, "≈17, measured 17.7"); fully on GPU → 32.0 tok/s (§2.1, "≈32").
- `amdahl_new_turn(18.7, 0.20, ∞)` → 14.96 s (remove routing, §4); `amdahl_new_turn(18.7, 0.95, 2)` → 9.82 s (model on GPU, §4).
- `decode_bound_output_threshold(3000)` → 64.8 tokens (§2, "more than ~65").
- `tail_probability(0.05, 3)` → 0.1426 (§5, "≈14%").

The baseline constants (`R_DECODE_TOK_S = 17.7`, `WEIGHTS_GB_Q4 = 5.6`, `COLD_LOAD_SECONDS = 8.3`, the two peak bandwidths and the `EFFICIENCY = 0.70` assumption) are centralised and labelled with their chapter 01 source. The bandwidth efficiency factor is an assumption, as the chapter states, so it is a named constant a measurement can replace.

### Wiring the per-call terms into metrics

The data path already existed but ended in a dead end for the benchmark. `IA/assistant/llm.py::_invoke_local` reads Ollama's `prompt_eval_count`, `prompt_eval_duration`, `eval_count`, `eval_duration`, `load_duration`, `total_duration` and passes them to `operations.record_attempt` in its `finally` block. But `record_attempt` only appended them to `operation.attempts`, and the benchmark harness (`IA/evaluate_helpdesk.py`) runs the graph **without** an `Operation` context, so nothing was recorded.

The fix keeps the allowlist as the single trust boundary and adds a second, always-on sink:

1. `record_attempt` builds the numeric row once (allowlist applied) and `set`s it on a module `ContextVar`, then — unchanged — also appends it to the active operation if there is one.
2. `metrics.call_model` clears that slot before `invoke`, and after the call reads it back. If a measurement is present it appends `cost_model.call_record(stage, measurement)` — the stage name plus token counts and derived `prefill_tok_s`/`decode_tok_s` and a `cold` flag — to `rag_metrics['calls']`.

Clearing before the call is what prevents a silent call (one that reports nothing, e.g. a cache path or a cloud response without token counts) from inheriting the previous call's numbers. A failing call still increments `model_calls` and records its `stage_ms`, but adds no token row.

Design decisions and trade-offs:

- **Why a ContextVar, not a return value.** `call_model` receives a validated Pydantic object from `invoke`, not the raw body, and threading the body back would change the signature used by routing, generation and review alike. The context-local slot keeps the change local to two functions and is thread-safe per the existing concurrency model (the local model holds `_LOCAL_LOCK`; ContextVars are per-thread/task).
- **Why reuse the existing allowlist.** Chapter 02 §8 and the parent AGENTS privacy rule both require that no question or provider body is stored. By publishing exactly the row `record_attempt` already allowlists, the new sink cannot widen what is retained. A test serialises a record built from a body containing `"SECRET"` and asserts it is absent.
- **Deferred.** Chapter 02 §8 also lists CPU/GPU split from `ollama ps` and browser audio timestamps as metrics to add. Those need a live `ollama ps` call and the Demo 2 front end respectively; they are out of scope for an offline, no-new-instrumentation change and are noted under Next steps. The `cost_model` functions for energy/cost are provided but are fed by the long tests, not wired into every turn, because sampling power per turn needs the sampler in the last section.

### Deviation from the chapter's constants (flagged, not applied)

Chapter 02's decode constant (17.7 tok/s) and desktop-VRAM figure (2.7 GB) come from the 2026-10-05 probe. REPORT_01 (2026-10-20) re-measured the desktop at 1.4 GB and short-prompt decode at 24–25 tok/s, and did **not** reproduce the 2.6× grammar penalty on real requests. I kept `cost_model.py`'s defaults at the chapter 02 values so the module reproduces the chapter exactly and the tests are stable, but every rate is an argument, so a caller can pass REPORT_01's newer numbers. This disagreement is called out here rather than silently changing the chapter's constants (editing chapters is disallowed).

## Before vs. After

The "metric" here is capability — what the cost model and the telemetry can do — not a latency change, because this task builds the measurement apparatus the other chapters consume. No turn latency was altered.

| Metric | Before | After | Change | Evidence label |
| --- | --- | --- | --- | --- |
| Cost-model equations re-derivable in code | none (prose only) | 11 functions, 23 tests | equations pinned | [Measured-here] |
| Per-call prompt/output token counts in benchmark JSON | not written (chapter 02 §2) | `turns[].rag_metrics.calls[].{prompt_tokens,output_tokens}` | now present | [Measured-here] |
| Per-call prefill/decode tok/s split from real traffic | not possible | `prefill_tok_s`, `decode_tok_s` per call | now derivable | [Measured-here] |
| Cold vs warm flag per call | none | `cold` per call | added | [Measured-here] |
| Offline test suite | 331 − 23 = 308 (before these tests) | 331 passed | +23, 0 regressions | [Measured-here] |
| KV cache @ 8192 (reproduced from code) | — | 256.0 MiB | matches §3 | [Measured-here] |
| Decode on-GPU vs offloaded (from code) | — | 32.0 vs 16.9 tok/s | matches §2.1 | [Estimated] |
| Remove-routing / on-GPU turn (from code) | — | 14.96 s / 9.82 s | matches §4 | [Estimated] |

The two energy rows the chapter leaves open (idle 16.8 W measured; per-turn energy and cost) remain **pending** a measurement; the long test `L0` produces them.

## Files changed

```
Created:  code/Institute-voice-agent/institute-assistant/assistant/cost_model.py — pure calculator for all chapter 02 equations + per-call rate splitting
Modified: code/Institute-voice-agent/institute-assistant/assistant/operations.py — record_attempt always publishes the numeric allowlist to a context slot; added last_measurement()/clear_measurement()
Modified: code/Institute-voice-agent/institute-assistant/assistant/metrics.py — call_model records per-call token metrics into rag_metrics['calls']; measure_node reset seeds 'calls': []
Created:  code/Institute-voice-agent/institute-assistant/tests/test_cost_model.py — 23 unit tests for the calculator and the metrics wiring
Created:  idea/FutureWork/REPORT_02_LATENCY_COST_MODEL_AND_METRICS.md — this report
```

## Issues encountered

- **Benchmark runs without an Operation, so token counts were silently dropped.** Resolved. `record_attempt` previously guarded all recording behind `if operation:`, and `evaluate_helpdesk.py` never enters an `operation_context`. The fix publishes the allowlisted row to a context slot unconditionally; the `Operation.attempts` behaviour is unchanged, verified by the existing `test_audit_upgrade.py` passing.
- **Possible mis-attribution across calls.** Resolved. Without clearing, a stage whose provider reports no token counts would inherit the previous stage's numbers. `call_model` now clears the slot before each invoke; `test_call_model_does_not_misattribute_previous_measurement` covers this.
- **Chapter constants are now stale vs REPORT_01.** Open (documented). The 17.7 tok/s / 2.7 GB figures predate REPORT_01's 24–25 tok/s / 1.4 GB. Workaround: all rates are function arguments. Fixing it properly means updating chapter 02's §2.1/§3 numbers, which is a chapter edit and so left to you.
- **Grammar penalty 2.6× unconfirmed.** Open (documented, inherited from REPORT_01). `GRAMMAR_PENALTY` is derived from the chapter's 17.7/6.4 figures; REPORT_01 did not reproduce it on real requests. It is exposed as a constant but used by no equation by default.

## Dependencies and prerequisites

- **No new packages.** `cost_model.py` uses only the standard library (`dataclasses`). The tests use `pytest`, already present in the `minor` environment.
- **Assumes complete:** chapter 01 baseline (REPORT_01) for the constants and the benchmark JSON schema. No roadmap Phase 0/1 technique is required or implemented here; this is the E1/measurement foundation that runs alongside all phases (roadmap §2, row E1).
- **Hardware:** the calculator runs anywhere. The long tests need the T0 laptop with the model resident and the GPU idle.

## Next steps

- Wire the remaining chapter 02 §8 fields: CPU/GPU residency from `ollama ps` (one HTTP/CLI read per turn, cached) and browser audio timestamps from the Demo 2 front end, into `rag_metrics`.
- After you run `L0`/`L1` (below), fold the measured per-turn energy, the real on-GPU vs offloaded decode rates, and the real prefill rate into the Before/After table and into chapter 02's constants (a chapter edit, on your approval).
- Add a tiny reporting helper that reads a benchmark `results.json` and prints p50/p95 of `rag_metrics.calls[].decode_tok_s` and prompt/output tokens per stage, so the split from real traffic is one command (feeds chapter 12).
- Use `cost_model.amdahl_new_turn` in the roadmap spreadsheet so Phase estimates are generated, not typed.

## Test results

- Command: `conda activate minor && cd code/Institute-voice-agent/institute-assistant && python -m pytest -q`
- Result: **331 passed, 0 failed** in ~11 s (128 pre-existing Pydantic deprecation warnings only). The 23 new tests are in `tests/test_cost_model.py`.
- Targeted: `python -m pytest tests/test_cost_model.py tests/test_audit_upgrade.py -q` → 35 passed (23 new + 12 existing operations/provenance tests, confirming the `record_attempt` change did not regress the allowlist or operation behaviour).
- `python -m py_compile assistant/cost_model.py assistant/metrics.py assistant/operations.py` and `python -c "from assistant import cost_model, metrics, operations"` both succeed.
- No long test was run by me (see below). The short probes in the long-test scripts (`--check` modes) were syntax-checked only.

## Long-running tests (to be run by the user later)

These need the GPU to themselves and real model generation, so they are yours to run. Both write a `summary.json` and keep scratch state out of the repository's data directories (they use `/tmp`). Neither downloads anything beyond the already-pulled `qwen3.5:9b`.

| ID | Question it answers | Approx. time | Needs | Pass / read-out criterion |
| --- | --- | --- | --- | --- |
| L0 | What is the real energy and cost per turn? (replaces the `[Estimated]` $0.60/month) | ~15–25 min | GPU idle; model resident; `nvidia-smi`; RAPL readable | `summary.json` reports mean GPU/CPU watts and J/turn over ≥20 answered turns; no error |
| L1 | What are the real prefill and decode rates, on GPU vs offloaded, warm vs cold? (replaces §2.1 `[Estimated]`) | ~5–10 min | GPU idle; model resident | `summary.json` reports decode tok/s for num_ctx and offload settings; fully-on-GPU ≳1.5× offloaded |

### Setup

Unpack the scripts, then run them. The unpacker writes each fenced block below whose heading is `**File:** \`name\`` into `idea/FutureWork/report02_artifacts/`.

```bash
# 1. Unpack (run from the repository root, Minor/)
mkdir -p idea/FutureWork/report02_artifacts
python idea/FutureWork/report02_artifacts/unpack.py 2>/dev/null || true
# If unpack.py does not yet exist, copy each **File:** block below into
# idea/FutureWork/report02_artifacts/<name> by hand, then:

# 2. Fast self-check (safe, no long run): verifies paths and arg parsing
cd idea/FutureWork/report02_artifacts
bash run_all_long_tests.sh --check

# 3. The real runs (GPU idle; model resident via `ollama run qwen3.5:9b ""` first)
conda activate minor
bash run_all_long_tests.sh            # runs L1 then L0; writes L0/L1 summary.json here
```

Outputs are written next to the scripts: `report02_artifacts/L0_energy/summary.json` and `report02_artifacts/L1_rates/summary.json`. Both scripts unload the model (`keep_alive: 0`) when they finish.

**File:** `run_all_long_tests.sh`

```bash
#!/usr/bin/env bash
# Runner for the chapter-02 long tests. Resumable: skips a test whose summary.json
# already exists unless --force is given. --check runs only fast validation.
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
  python "$HERE/$script" --out "$outdir/summary.json"
  echo "=== $id done -> $outdir/summary.json ==="
}

run_one L1 l1_decode_rates.py L1_rates
run_one L0 l0_energy_per_turn.py L0_energy
echo "All long tests finished. Summaries:"
ls -1 "$HERE"/L*/summary.json 2>/dev/null || true
```

**File:** `l1_decode_rates.py`

```python
#!/usr/bin/env python3
"""L1 — measure real prefill/decode rates on T0, warm vs cold, across offload settings.

Sends short fixed prompts to Ollama's /api/chat with stream:false and reads the
numeric fields (prompt_eval_count/eval_count and their nanosecond durations). It
does not change any project configuration; it talks to Ollama directly. Use
`--check` for a fast, no-generation validation of arguments and reachability.
"""
import argparse, json, time, urllib.request, urllib.error

BASE = "http://127.0.0.1:11434"
MODEL = "qwen3.5:9b"
PROMPT = "List three primary colours. Answer in one short sentence."

def _post(path, body, timeout):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def one_call(num_ctx, num_predict, keep_alive):
    body = {"model": MODEL, "stream": False, "keep_alive": keep_alive,
            "messages": [{"role": "user", "content": PROMPT}],
            "options": {"temperature": 0, "num_ctx": num_ctx, "num_predict": num_predict}}
    t0 = time.monotonic()
    out = _post("/api/chat", body, timeout=300)
    wall = time.monotonic() - t0
    pc, pd = out.get("prompt_eval_count"), out.get("prompt_eval_duration")
    ec, ed = out.get("eval_count"), out.get("eval_duration")
    ld = out.get("load_duration", 0) or 0
    return {"num_ctx": num_ctx, "num_predict": num_predict, "wall_s": round(wall, 3),
            "prompt_tokens": pc, "output_tokens": ec,
            "prefill_tok_s": round(pc / (pd / 1e9), 2) if pc and pd else None,
            "decode_tok_s": round(ec / (ed / 1e9), 2) if ec and ed else None,
            "load_s": round(ld / 1e9, 3), "cold": (ld / 1e9) > 0.5}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        try:
            _post("/api/show", {"model": MODEL}, timeout=10)
            reachable = True
        except (urllib.error.URLError, OSError):
            reachable = False
        json.dump({"check": True, "ollama_reachable": reachable, "model": MODEL},
                  open(args.out, "w"), indent=2)
        print(json.dumps({"check": True, "ollama_reachable": reachable}))
        return
    rows = []
    # Cold first (unload, then one call), then warm repeats at two contexts.
    _post("/api/chat", {"model": MODEL, "keep_alive": 0,
                        "messages": [{"role": "user", "content": "hi"}],
                        "options": {"num_predict": 1}}, timeout=120)
    time.sleep(3)
    rows.append({"phase": "cold", **one_call(8192, 64, "5m")})
    for _ in range(5):
        rows.append({"phase": "warm", **one_call(8192, 64, "5m")})
    for _ in range(5):
        rows.append({"phase": "warm", **one_call(4096, 64, "5m")})
    decode = [r["decode_tok_s"] for r in rows if r["phase"] == "warm" and r["decode_tok_s"]]
    summary = {"model": MODEL, "rows": rows,
               "warm_decode_tok_s_mean": round(sum(decode) / len(decode), 2) if decode else None,
               "note": "Record `ollama ps` CPU/GPU split alongside this run; "
                       "repeat after freeing desktop VRAM to get the on-GPU rate."}
    _post("/api/chat", {"model": MODEL, "keep_alive": 0,
                        "messages": [{"role": "user", "content": "bye"}],
                        "options": {"num_predict": 1}}, timeout=120)
    json.dump(summary, open(args.out, "w"), indent=2)
    print(json.dumps({"warm_decode_tok_s_mean": summary["warm_decode_tok_s_mean"]}))

if __name__ == "__main__":
    main()
```

**File:** `l0_energy_per_turn.py`

```python
#!/usr/bin/env python3
"""L0 — measure energy and cost per turn on T0 by sampling GPU and CPU power.

Samples `nvidia-smi --query-gpu=power.draw` and Intel RAPL energy counters while
driving a fixed set of generation calls through Ollama, then reports mean watts
and joules per turn. Pure measurement; changes no project configuration. Use
`--check` for fast validation without generation.

Cost: pass --price-per-kwh to convert; default leaves cost null (states its date
assumption as [Reported] when you fill it in).
"""
import argparse, glob, json, subprocess, threading, time, urllib.request

BASE = "http://127.0.0.1:11434"
MODEL = "qwen3.5:9b"
QUESTIONS = [
    "What is admission to B.Tech decided on?",
    "What documents are required for reporting?",
    "What is the fee structure?",
]

def gpu_power_w():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
            text=True, timeout=5)
        return float(out.strip().splitlines()[0])
    except Exception:
        return None

def rapl_microjoules():
    total = 0
    for path in glob.glob("/sys/class/powercap/intel-rapl:*/energy_uj"):
        try:
            total += int(open(path).read().strip())
        except (OSError, ValueError):
            pass
    return total or None

def _post(body, timeout=300):
    req = urllib.request.Request(BASE + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--turns", type=int, default=21)
    ap.add_argument("--price-per-kwh", type=float, default=None)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        info = {"check": True, "gpu_power_w": gpu_power_w(),
                "rapl_readable": rapl_microjoules() is not None}
        json.dump(info, open(args.out, "w"), indent=2)
        print(json.dumps(info))
        return

    samples = []
    stop = threading.Event()
    def sampler():
        while not stop.is_set():
            samples.append((time.monotonic(), gpu_power_w()))
            time.sleep(0.2)
    th = threading.Thread(target=sampler, daemon=True); th.start()

    rapl0 = rapl_microjoules(); t0 = time.monotonic()
    answered = 0
    for i in range(args.turns):
        q = QUESTIONS[i % len(QUESTIONS)]
        out = _post({"model": MODEL, "stream": False, "keep_alive": "5m",
                     "messages": [{"role": "user", "content": q}],
                     "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 256}})
        if out.get("done"):
            answered += 1
    wall = time.monotonic() - t0
    stop.set(); th.join(timeout=2)
    rapl1 = rapl_microjoules()

    gpu_vals = [p for _, p in samples if p is not None]
    gpu_mean_w = sum(gpu_vals) / len(gpu_vals) if gpu_vals else None
    gpu_j = gpu_mean_w * wall if gpu_mean_w else None
    cpu_j = (rapl1 - rapl0) / 1e6 if (rapl0 and rapl1 and rapl1 >= rapl0) else None
    total_j = (gpu_j or 0) + (cpu_j or 0)
    per_turn_j = total_j / answered if answered else None
    cost = None
    if args.price_per_kwh and per_turn_j:
        cost = (per_turn_j / 3.6e6) * args.price_per_kwh
    summary = {"model": MODEL, "turns_requested": args.turns, "turns_answered": answered,
               "wall_s": round(wall, 2), "gpu_mean_w": round(gpu_mean_w, 2) if gpu_mean_w else None,
               "gpu_joules": round(gpu_j, 1) if gpu_j else None,
               "cpu_joules_rapl": round(cpu_j, 1) if cpu_j else None,
               "joules_per_turn": round(per_turn_j, 1) if per_turn_j else None,
               "cost_per_turn": cost, "price_per_kwh": args.price_per_kwh,
               "note": "idle GPU was 16.8 W [Measured-here, 01]. If a term is null, that "
                       "sensor was unreadable; state it. Cost is [Reported] with your tariff date."}
    _post({"model": MODEL, "keep_alive": 0,
           "messages": [{"role": "user", "content": "bye"}],
           "options": {"num_predict": 1}}, timeout=120)
    json.dump(summary, open(args.out, "w"), indent=2)
    print(json.dumps({"joules_per_turn": summary["joules_per_turn"],
                      "gpu_mean_w": summary["gpu_mean_w"]}))

if __name__ == "__main__":
    main()
```

**File:** `unpack.py`

```python
#!/usr/bin/env python3
"""Unpack the fenced **File:** blocks of REPORT_02 into this directory.

Reads ../REPORT_02_LATENCY_COST_MODEL_AND_METRICS.md, finds each block whose
heading line is  **File:** `name`  immediately followed by a fenced code block,
and writes it next to this script. Idempotent.
"""
import pathlib, re

HERE = pathlib.Path(__file__).resolve().parent
REPORT = HERE.parent / "REPORT_02_LATENCY_COST_MODEL_AND_METRICS.md"
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
```

### My check before finishing

Per the AGENTS long-test rule I syntax-checked the scripts, unpacked them once, and ran only the fast `--check` paths, without executing the long runs:

- Unpacked the three blocks into `idea/FutureWork/report02_artifacts/` via `unpack.py` and confirmed the paths resolve.
- `python -m py_compile l0_energy_per_turn.py l1_decode_rates.py unpack.py` → OK.
- `bash -n run_all_long_tests.sh` → OK.
- `bash run_all_long_tests.sh --check` → both scripts validated: Ollama reachable, `nvidia-smi` returned idle power (7.99 W at check time), RAPL readable. The placeholder `summary.json` files were then removed so your real runs are not skipped by the resumable logic.

I did not run L0 or L1, and did not start them in the background. After you run them, hand me the two `summary.json` files and I will fold the measured energy/cost and the real prefill/decode rates into the Before vs. After table and mark the pending rows measured.
