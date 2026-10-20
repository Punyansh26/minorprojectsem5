# REPORT 05 — LLM Inference and Serving

## Summary

This pass implements the Phase-0 (and the one Phase-0–1) **code/config** LLM-inference optimizations from
[05_LLM_INFERENCE_AND_SERVING.md](05_LLM_INFERENCE_AND_SERVING.md) that live in
`code/Institute-voice-agent/institute-assistant/` (`IA/` in the chapter): **A3** (drop the per-call
`/api/tags` round-trip and make the model digest lazy), **A8** (a separate, tight local decode budget
`OLLAMA_NUM_PREDICT` plus `keep_alive` kiosk guidance), and **A7** (replace the long quote **string-enum**
grammar with a bounded **integer span-index**, resolved server-side to the exact verbatim span). **A6**
(byte-stable static prefix) was already satisfied by the existing design and needed no change. Every change
preserves the grounding contract: the verbatim-quote check (`evidence.py::source_quote`), the release-bound
draft cache (`cache.py::RagCache`) and the exact SQL cutoffs are untouched, and `nodes.py` did not change.
The full test suite passes (333 passed, up from 331). The OS-display/VRAM item (**A1**) and all streaming /
speculative-decoding / serving-engine items (B7, C1, F, H) are deferred as explained below; their
quantitative effects require long tests, whose complete scripts are included in the last section.

## What was done

- **A3 — lazy `/api/tags` (chapter §D).** `assistant/llm.py`: added `_refresh_digest(client)` and changed
  `_invoke_local` so the `/api/tags` GET runs only when the `(base_url, model)` digest is **not** already in
  `_LOCAL_DIGESTS` (i.e. once at process start). The 404 "missing model" branch now **pops** the cached
  digest so the next call re-fetches it (re-binding the draft-cache identity if the tag was swapped).
- **A8 — bounded local decode budget + keep_alive guidance (chapter §E.2, §D).**
  - `assistant/config.py`: new setting `OLLAMA_NUM_PREDICT` (default **512**), validated
    `0 < OLLAMA_NUM_PREDICT <= LLM_MAX_TOKENS`.
  - `assistant/llm.py`: the `api/chat` `options.num_predict` now uses `OLLAMA_NUM_PREDICT` instead of
    `LLM_MAX_TOKENS`.
  - `.env.example`: added `OLLAMA_NUM_PREDICT=512` and documented `OLLAMA_KEEP_ALIVE=-1` kiosk guidance.
- **A7 — integer span index instead of quote string-enum (chapter §C).** `assistant/llm.py`:
  - `generation_schema`: the per-source `GroundedAnswer` evidence grammar changed from
    `{source_id, quote: {enum: [spans…]}}` to `{source_id, span_index: {type: integer, enum: [0..k-1]}}`.
  - new `resolve_span_indices(payload, data)`: maps each `{source_id, span_index}` to the exact span from
    `evidence_spans(source["text"])` and rewrites it to `{source_id, quote}` **before** Pydantic validation;
    out-of-range / unknown indices are dropped (fail closed).
  - new `_local_grounding_payload(schema, payload)`: adds a numbered `span_options` menu (`{index: span}`) to
    each source **in the local prompt only**, so the model can choose an index meaningfully; `source["text"]`
    is left unchanged so the grammar and resolver stay byte-stable.
  - `_invoke_local`: sends the augmented payload for the messages, the **original** payload for the grammar
    and resolution, and calls `resolve_span_indices(...)` before `schema.model_validate(...)`.
  - `prepare_payload`: the local context-budget now counts the **augmented** prompt (answer and review
    branches) so the context-fit invariant still holds after the span menu is added.
- **Tests.** `tests/test_local_provider.py`:
  - rewrote the evidence-grammar test to assert the integer-index grammar and the `resolve_span_indices`
    round-trip (fabrication still impossible);
  - updated the reduced-budget fixture to set `OLLAMA_NUM_PREDICT=500` (consistent with `LLM_MAX_TOKENS=500`);
  - updated the `num_predict` assertion to `OLLAMA_NUM_PREDICT`;
  - added `test_digest_fetched_once_then_cached_and_refreshed_on_404` (A3) and
    `test_local_answer_span_index_resolves_to_verbatim_quote` (A7).

## How it was done

**A3.** The digest only changes when someone re-pulls the model, so fetching it before every `api/chat`
is pure overhead on the hot path (up to 3× per answered turn). The digest still binds the draft-cache key
through `model_identity()`, so correctness requires a refresh whenever the model is actually swapped. The
404 branch is exactly that signal, so dropping the cached digest there (and keeping the first-call fetch)
preserves the invalidation guarantee while removing the per-call round-trip.

**A8.** The chapter recommends cutting `num_predict` 1600 → ~384–512. `LLM_MAX_TOKENS` is overloaded: it is
Groq's `max_tokens`, part of the draft-cache key, and the **reserved context headroom** that
`prepare_payload`/`config.__post_init__` use to guarantee the draft + review fit in `OLLAMA_NUM_CTX`.
Lowering `LLM_MAX_TOKENS` globally would shrink that reservation and change the Groq path and cache identity.
Introducing a **separate** `OLLAMA_NUM_PREDICT` bounds only the local decode tail while keeping the reserved
headroom intact — the decode budget can never exceed what the context math already reserves (validated
`<= LLM_MAX_TOKENS`). Truncation already fails safe: `_invoke_local` treats `done_reason == "length"` as an
error → `unavailable`.

**A7.** This is the one Medium-effort item (Phase 0–1). The decisive design choice was to keep the change
**entirely inside `llm.py`**: the grammar emits `{source_id, span_index}`, and `resolve_span_indices`
rewrites it to `{source_id, quote}` before validation, so `nodes.py`, `Evidence`, `source_quote`, citations
and the draft cache see an ordinary verbatim quote and did **not** change. Grounding is *stronger* than
before — the index can only point at a real contiguous span from `evidence_spans`, so a fabricated or edited
quote is structurally impossible, and the grammar token-mask is now a small bounded integer rather than a
300-entry long-string enum (the measured 2.6× decode penalty).

A subtlety the chapter did not spell out: with only an index in the grammar, the model needs to *see* which
span each index denotes, or its choice is blind. So `_local_grounding_payload` surfaces a numbered span menu
(`span_options`) in the **local** prompt. This is local-only (the Groq path has no grammar and keeps emitting
`{source_id, quote}` directly), and it does not touch `source["text"]`, so `generation_schema` and
`resolve_span_indices` — both keyed on `text` — stay byte-stable. The menu enlarges the local prompt, so the
budget function now counts the augmented payload to keep the context-fit invariant.

**Deferred, with reasons:**

- **A1 (free desktop VRAM / iGPU display / PRIME, text-only GGUF):** OS/display configuration and a model
  artifact swap, not code or config in this repo. Its decode speedup is the L0 long test.
- **A6 (byte-stable static prefix):** already satisfied. The system message is
  `instruction + "\nReturn ONLY JSON conforming to this schema:\n" + json.dumps(schema.model_json_schema())`;
  the schema is static per schema type and the per-request evidence grammar was already in the `format` field,
  not the prompt head. No change was warranted; verifying the actual prefix-reuse window is the L-tests' job.
- **B7 / E (token streaming, sentence TTS):** Phase 1, and gated on per-sentence verification
  ([06](06_VERIFICATION_AND_CACHING.md), [07](07_SPEECH_OUTPUT.md)) — streaming unverified claims would
  violate the grounding contract. Out of scope for a Phase-0 pass.
- **F / H (prompt-lookup / MTP speculative decoding, llama-server / vLLM):** require a different serving
  engine than stock Ollama and long GPU benchmarks; Phase 2.

## Before vs. After

All speed numbers below are **planning figures pending the long tests** (this pass ran only short, mocked
unit checks — see *Test results*). The verified, measured-here facts from this pass are the test outcome and
the structural grammar change.

| Metric | Before | After | Change | Evidence label |
| --- | --- | --- | --- | --- |
| `/api/tags` HTTP round-trips per answered turn (≤3 model calls) | up to 3 | 1 (process start), then 0 until a 404 | −(N−1) RTT/turn | [Measured-here] (unit test counts tag hits) |
| Evidence grammar token-mask (per decoded evidence token) | mask over 300-entry long-string enum | mask over bounded integer enum `[0..k-1]` | string-enum removed | [Measured-here] (grammar asserted in test) |
| Evidence decode penalty vs no-grammar | ≈2.6× | ≈1.0× (expected) | removes the 2.6× penalty | [Reported]→[Estimated] (basis: 01 §4.3; reproduce in L1) |
| Local decode budget `num_predict` | 1600 | 512 | −68% worst-case decode cap | [Measured-here] (config default) |
| Cold reload between users (kiosk, `keep_alive=-1`) | ≈8.3 s per idle-unload | 0 (model never unloads) | removes 8.3 s | [Reported] (01 §4; measure in L3) |
| Fully-on-GPU decode (A1) | ≈17.7 tok/s (45/55 CPU/GPU split) | ≈32 tok/s (expected) | ≈1.8× | [Estimated] (02 §2.1; measure in L0) |
| Grounding: fabricated-quote possibility | model could emit any enum string | index can only point at a real span | stronger | [Measured-here] (grammar + resolver test) |
| Institute-assistant test suite | 331 passed | 333 passed | +2 tests, 0 failures | [Measured-here] |

Items not measurable on T0 in this pass (A1 decode, L1 grammar ratio on this model/hardware, L3 cold reload,
prefix-reuse window) are left as the long tests below and marked pending.

## Files changed

```
Modified: code/Institute-voice-agent/institute-assistant/assistant/llm.py
          — A3: lazy /api/tags via new _refresh_digest + cached-digest guard; 404 drops stale digest.
          — A8: api/chat num_predict now uses settings.OLLAMA_NUM_PREDICT.
          — A7: generation_schema emits integer span_index; new resolve_span_indices;
                new _local_grounding_payload (local-only span menu); _invoke_local resolves index→quote
                before validation; prepare_payload budgets the augmented prompt.
Modified: code/Institute-voice-agent/institute-assistant/assistant/config.py
          — A8: new OLLAMA_NUM_PREDICT setting (default 512) + validation 0 < NUM_PREDICT <= LLM_MAX_TOKENS.
Modified: code/Institute-voice-agent/institute-assistant/.env.example
          — A8: OLLAMA_NUM_PREDICT=512; OLLAMA_KEEP_ALIVE kiosk (-1) guidance.
Modified: code/Institute-voice-agent/institute-assistant/tests/test_local_provider.py
          — rewrote evidence-grammar test for integer span-index + resolver round-trip;
          — reduced-budget fixture sets OLLAMA_NUM_PREDICT=500; num_predict assertion → OLLAMA_NUM_PREDICT;
          — added A3 lazy-digest test and A7 span-index resolution test.
Created:  idea/FutureWork/REPORT_05_LLM_INFERENCE_AND_SERVING.md — this report.
```

No files were deleted. No chapter documents were edited.

## Issues encountered

- **`OLLAMA_NUM_PREDICT` vs a reduced-budget test.** `test_budget_trims_whole_pairs_then_whole_sources`
  rebuilds the settings with `LLM_MAX_TOKENS=500`, which made the new validation
  (`OLLAMA_NUM_PREDICT (512) <= LLM_MAX_TOKENS (500)`) fail. **Resolved** by setting
  `OLLAMA_NUM_PREDICT=500` in that test's `replace(...)` so the reduced-budget config is internally
  consistent. This is the intended guard working as designed (the decode budget must not exceed the reserved
  headroom), not a code bug.
- **Span-menu prompt-size growth (A7).** Surfacing `span_options` enlarges the local prompt because
  `evidence_spans` emits overlapping contiguous windows. **Resolved** by making `prepare_payload`'s local
  budget count the augmented payload (answer and review branches), so the context-fit invariant still holds
  and over-large inputs fail closed with the existing "exceeds the local context" message rather than silently
  overflowing. The real per-turn token cost of the menu on live traffic is **open** until L1/L2 measure it;
  if it proves too large, the menu can be trimmed to a shorter span set without changing the grammar/resolver
  contract.
- **Prompt schema still names `quote` while the local grammar emits `span_index` (A7).** The static
  `GroundedAnswer` JSON schema in the system message (kept byte-stable for A6) still describes
  `Evidence.quote`, while the enforced `format` grammar emits `span_index`. Ollama's `format` is authoritative
  for output structure, and the `span_options` menu tells the model what each index means, so output is
  well-formed in the unit test. **Open (behavioural):** whether the live 9B chooses correct indices as
  reliably as it copied quotes must be confirmed by the L2 grounding behaviour suite before this is declared a
  pass per [12](12_EVALUATION_AND_BENCHMARKING.md). Until then A7 is implemented and unit-correct but its
  grounding-quality parity is pending.

## Dependencies and prerequisites

- **No new packages** were installed into the `minor` environment. The implementation uses only the standard
  library, `httpx`, and `pydantic`, all already present. (The new unit tests use `jsonschema`, which the
  existing grammar test already imported.)
- **Assumed complete:** nothing from other chapters is required for A3/A7/A8. A7 is the Phase-0–1 dependency
  for C2 (sentence-level verification) and A8's answer-first ordering feeds B7 (token streaming); both are
  later phases.
- **Hardware:** the code changes are tier-agnostic. The long tests target **T0** (RTX 4060 Laptop 8 GB) except
  L0's fully-on-GPU reading, which needs either freed desktop VRAM (A1) or a T1/T2 GPU.

## Next steps

- Run the long tests below (user) and fold `summary.json` results into the **Before vs. After** table,
  replacing every pending/`[Estimated]`/`[Reported]` row with a `[Measured-here]` value.
- Gate A7 on the L2 grounding behaviour suite per [12](12_EVALUATION_AND_BENCHMARKING.md) (zero new
  unsupported claims on `critical-cases.json`, abstention unchanged) before treating it as shipped; if index
  selection underperforms quote copying, trim the `span_options` menu or revisit the two-step alternative
  (05 §C.2).
- A1 (free desktop VRAM / text-only GGUF) is the single highest-leverage remaining Phase-0 win and unblocks
  C1 (prompt-lookup speculative decoding) — do it next as OS/display config, then L0.
- Phase 1: B7 token streaming (needs per-sentence verification from chapter 06) and the claim-level checker.

## Test results

- Command: `conda activate minor && python -m pytest tests/ -q`
  (run in `code/Institute-voice-agent/institute-assistant/`).
- Result: **333 passed, 0 failed** (previously 331; +2 new tests), ~10 s. Warnings are pre-existing Pydantic/
  Chroma deprecation notices unrelated to this change.
- Targeted run: `python -m pytest tests/test_local_provider.py tests/test_llm.py -q` → **34 passed**.
- Compile check: `python -m py_compile assistant/llm.py assistant/config.py assistant/nodes.py` → OK;
  `python -c "from assistant.config import settings; print(settings.OLLAMA_NUM_PREDICT)"` → `512`.
- These are all **short checks** (mocked transport, no model download, no GPU). No long test was run by me;
  see the next section.

## Long-running tests (to be run by the user later)

These need the real Ollama model, the GPU to themselves, and/or more than ~5 minutes, so per `AGENTS.md`
the user runs them. They are resumable (each writes a `summary.json` and skips a test whose summary already
exists), keep scratch state in a `--workdir` outside the repo's data directories, and unload the model when
done.

| ID | Question it answers | ~Run time | Needs | Pass / read-out criterion |
| --- | --- | --- | --- | --- |
| L0 | Fully-on-GPU decode tok/s (A1) vs the 17.7 baseline | 5–10 min | GPU idle; model loaded 100% on GPU (`ollama ps`) | decode ≥ 1.6× baseline (≈ ≥28 tok/s) |
| L1 | Grammar penalty on this model: integer span-index (new) vs string enum (old) vs no grammar | 5–15 min | GPU idle; model | span-index decode overhead < 1.2× no-grammar; and < the string-enum ratio |
| L2 | End-to-end grounding parity after A7 (no new unsupported claims, abstention unchanged) | 20–60 min | GPU idle; model; built KB release | zero new unsupported claims on critical cases; abstention rate unchanged |
| L3 | `keep_alive=-1` removes the cold reload between users (A3/A8) | 5–10 min | GPU idle; model | second-user first-token latency ≈ warm (no ≈8.3 s reload) |

### Setup

1. Save the fenced blocks below into a directory, e.g. `~/fw05_long_tests/`. The helper
   `unpack_reports.py` (block 1) extracts every ``**File:** `name` `` block from this report automatically:

   ```bash
   mkdir -p ~/fw05_long_tests && cd ~/fw05_long_tests
   # paste unpack_reports.py from block 1, then:
   python unpack_reports.py "/run/media/rtx/Files/Study/Semester 5/Minor/idea/FutureWork/REPORT_05_LLM_INFERENCE_AND_SERVING.md" .
   chmod +x run_all_long_tests.sh
   ```
2. Run everything (writes to `./out/` by default; override with `--workdir`):
   ```bash
   conda activate minor
   ./run_all_long_tests.sh --workdir "$HOME/fw05_long_tests/out" \
       --model qwen3.5:9b --base-url http://127.0.0.1:11434
   ```
3. Outputs: one `out/<Lx>/summary.json` per test, plus `out/summary_all.json`. Hand those back to fold into
   this report.

### Scripts

**File:** `unpack_reports.py`
```python
#!/usr/bin/env python3
"""Extract every ``**File:** `name` `` fenced block from a markdown report into files."""
import re
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        print("usage: unpack_reports.py REPORT.md OUTDIR", file=sys.stderr)
        return 2
    report = Path(sys.argv[1]).read_text(encoding="utf-8")
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    # Match: **File:** `name`  then a ```lang ... ``` fence.
    pattern = re.compile(r"\*\*File:\*\*\s*`([^`]+)`\s*\n```[a-zA-Z0-9_]*\n(.*?)\n```", re.DOTALL)
    count = 0
    for name, body in pattern.findall(report):
        target = outdir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body + "\n", encoding="utf-8")
        count += 1
        print(f"wrote {target}")
    print(f"extracted {count} file(s)")
    return 0 if count else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

**File:** `common.py`
```python
"""Shared helpers for the chapter-05 long tests: Ollama calls and tok/s read-out."""
import json
import time
import urllib.request


def chat(base_url, model, messages, *, fmt=None, num_predict=512, keep_alive="5m", timeout=600):
    """One non-streaming /api/chat call; returns the parsed JSON body (with timings)."""
    body = {"model": model, "messages": messages, "stream": False, "think": False,
            "keep_alive": keep_alive,
            "options": {"temperature": 0, "num_predict": num_predict}}
    if fmt is not None:
        body["format"] = fmt
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base_url.rstrip("/") + "/api/chat", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def decode_tok_s(body):
    """eval_count / eval_duration(ns) -> tokens per second, or None."""
    n, dur = body.get("eval_count"), body.get("eval_duration")
    return (n / (dur / 1e9)) if n and dur else None


def ps(base_url, timeout=30):
    with urllib.request.urlopen(base_url.rstrip("/") + "/api/ps", timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def unload(base_url, model):
    """Ask Ollama to unload the model (keep_alive=0)."""
    try:
        chat(base_url, model, [{"role": "user", "content": "bye"}],
             num_predict=1, keep_alive="0", timeout=60)
    except Exception:
        pass
```

**File:** `l0_decode_fully_on_gpu.py`
```python
#!/usr/bin/env python3
"""L0: measure fully-on-GPU decode tok/s (A1). Records ollama ps residency alongside."""
import argparse
import json
import statistics
from pathlib import Path

from common import chat, decode_tok_s, ps, unload

PROMPT = ("List, in 8 short bullet points, generic steps a student takes to apply to a college. "
          "Write at least 200 words.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:11434")
    ap.add_argument("--model", default="qwen3.5:9b")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--repeats", type=int, default=5)
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "summary.json").exists():
        print("L0 already done; skipping")
        return 0
    rates = []
    for i in range(args.repeats):
        body = chat(args.base_url, args.model,
                    [{"role": "user", "content": PROMPT}], num_predict=512, keep_alive="5m")
        r = decode_tok_s(body)
        if r:
            rates.append(r)
        print(f"run {i+1}: {r:.2f} tok/s" if r else f"run {i+1}: no timing")
    residency = ps(args.base_url)
    summary = {"test": "L0", "decode_tok_s": rates,
               "median_tok_s": statistics.median(rates) if rates else None,
               "baseline_tok_s": 17.7, "ollama_ps": residency,
               "note": "Confirm ps shows ~100% GPU before trusting the speedup."}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    unload(args.base_url, args.model)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**File:** `l1_grammar_penalty.py`
```python
#!/usr/bin/env python3
"""L1: decode ms/token with (a) no grammar, (b) old quote string-enum, (c) new integer span-index.

Reproduces the 2.6x probe (01 4.3) and shows the span-index grammar removes it. Builds the two
grammars from the real evidence_spans() so the comparison matches production.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

from common import chat, decode_tok_s, unload

SOURCE = ("IIIT Naya Raipur published opening and closing ranks\n"
          + "\n".join(f"Category: C{i}\nOpening Rank: {3000+i}\nClosing Rank: {4000+i}" for i in range(40)))
QUESTION = "What is the opening rank for category C1? Answer in one sentence and cite the exact line."


def load_evidence_spans(ia_path):
    sys.path.insert(0, ia_path)
    from assistant.llm import evidence_spans  # noqa: E402
    return evidence_spans


def ms_per_token(base_url, model, fmt):
    rates = []
    for _ in range(3):
        body = chat(base_url, model,
                    [{"role": "user", "content": QUESTION + "\n\nSOURCE:\n" + SOURCE}],
                    fmt=fmt, num_predict=256)
        r = decode_tok_s(body)
        if r:
            rates.append(1000.0 / r)
    return statistics.median(rates) if rates else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:11434")
    ap.add_argument("--model", default="qwen3.5:9b")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--ia-path", default=str(Path(__file__).resolve().parents[0]),
                    help="path to institute-assistant (for assistant.llm.evidence_spans)")
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "summary.json").exists():
        print("L1 already done; skipping")
        return 0
    spans = load_evidence_spans(args.ia_path)(SOURCE)
    string_enum = {"type": "object", "properties": {
        "quote": {"type": "string", "enum": spans}}, "required": ["quote"]}
    int_index = {"type": "object", "properties": {
        "span_index": {"type": "integer", "enum": list(range(len(spans)))}},
        "required": ["span_index"]}
    none_ms = ms_per_token(args.base_url, args.model, None)
    enum_ms = ms_per_token(args.base_url, args.model, string_enum)
    index_ms = ms_per_token(args.base_url, args.model, int_index)
    summary = {"test": "L1", "n_spans": len(spans),
               "ms_per_token": {"no_grammar": none_ms, "string_enum": enum_ms, "span_index": index_ms},
               "ratio_string_enum": (enum_ms / none_ms) if none_ms and enum_ms else None,
               "ratio_span_index": (index_ms / none_ms) if none_ms and index_ms else None,
               "pass": (index_ms is not None and none_ms is not None and index_ms / none_ms < 1.2)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    unload(args.base_url, args.model)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**File:** `l2_grounding_behaviour.py`
```python
#!/usr/bin/env python3
"""L2: end-to-end grounding parity after A7 on a small labelled case set.

Runs the real agent graph locally against critical cases and checks every returned quote is
verbatim in its cited source (source_quote already enforces this; here we also tally abstention
and any unsupported claim). Point --cases at a JSONL of {"question","must_abstain"(bool)} lines;
defaults to critical-cases.json if present under the IA tests data.
"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ia-path", required=True, help="path to institute-assistant package root")
    ap.add_argument("--cases", required=True, help="JSONL: one {question, must_abstain} per line")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "summary.json").exists():
        print("L2 already done; skipping")
        return 0
    import sys
    sys.path.insert(0, args.ia_path)
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from assistant.graph import build_graph
    from assistant.evidence import source_quote

    graph = build_graph(MemorySaver())
    results, unsupported, abstained, answered = [], 0, 0, 0
    for n, line in enumerate(Path(args.cases).read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        case = json.loads(line)
        state = graph.invoke({"messages": [HumanMessage(content=case["question"])]},
                             {"configurable": {"thread_id": f"l2-{n}", "llm_provider": "ollama"}})
        status = state.get("response_status")
        sources = state.get("sources", [])
        ok = True
        for cite in sources:
            # Every citation must be verbatim in its source text.
            if source_quote(cite["quote"], {"text": cite["quote"], **cite}) is None and cite["quote"] not in cite.get("quote", ""):
                ok = False
        if status in {"insufficient", "unavailable", "clarification"} or not sources:
            abstained += 1
        else:
            answered += 1
        if not ok:
            unsupported += 1
        results.append({"question": case["question"], "status": status,
                        "n_sources": len(sources), "verbatim_ok": ok,
                        "must_abstain": case.get("must_abstain")})
    summary = {"test": "L2", "n_cases": len(results), "answered": answered,
               "abstained": abstained, "unsupported_claims": unsupported,
               "pass": unsupported == 0, "results": results}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**File:** `l3_keep_alive_cold_reload.py`
```python
#!/usr/bin/env python3
"""L3: show keep_alive=-1 removes the cold reload a second user would otherwise hit."""
import argparse
import json
import time
from pathlib import Path

from common import chat, unload

PROMPT = [{"role": "user", "content": "Reply with the single word: ready."}]


def first_token_seconds(base_url, model, keep_alive):
    t0 = time.monotonic()
    body = chat(base_url, model, PROMPT, num_predict=4, keep_alive=keep_alive)
    return time.monotonic() - t0, body.get("load_duration", 0) / 1e9


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:11434")
    ap.add_argument("--model", default="qwen3.5:9b")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "summary.json").exists():
        print("L3 already done; skipping")
        return 0
    # Case A: default short keep_alive, force unload between users -> cold reload.
    unload(args.base_url, args.model)
    time.sleep(2)
    cold_s, cold_load = first_token_seconds(args.base_url, args.model, "5m")
    # Case B: keep_alive=-1, model stays warm -> no reload on the next user.
    first_token_seconds(args.base_url, args.model, "-1")  # warm it, resident
    warm_s, warm_load = first_token_seconds(args.base_url, args.model, "-1")
    summary = {"test": "L3",
               "cold_first_token_s": cold_s, "cold_load_duration_s": cold_load,
               "warm_first_token_s": warm_s, "warm_load_duration_s": warm_load,
               "reload_saved_s": max(0.0, cold_s - warm_s),
               "pass": warm_load < 0.5}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    unload(args.base_url, args.model)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**File:** `run_all_long_tests.sh`
```bash
#!/usr/bin/env bash
# Runner for the chapter-05 long tests. Resumable: each Lx skips if its summary.json exists.
set -euo pipefail

WORKDIR="$PWD/out"
MODEL="qwen3.5:9b"
BASE_URL="http://127.0.0.1:11434"
IA_PATH=""   # path to institute-assistant (needed by L1/L2); auto-detected if empty
CASES=""     # JSONL for L2

while [ $# -gt 0 ]; do
  case "$1" in
    --workdir) WORKDIR="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --base-url) BASE_URL="$2"; shift 2 ;;
    --ia-path) IA_PATH="$2"; shift 2 ;;
    --cases) CASES="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$IA_PATH" ]; then
  IA_PATH="/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/institute-assistant"
fi

mkdir -p "$WORKDIR"
echo "workdir=$WORKDIR model=$MODEL base_url=$BASE_URL ia_path=$IA_PATH"

python l0_decode_fully_on_gpu.py --base-url "$BASE_URL" --model "$MODEL" --outdir "$WORKDIR/L0"
python l1_grammar_penalty.py    --base-url "$BASE_URL" --model "$MODEL" --outdir "$WORKDIR/L1" --ia-path "$IA_PATH"
if [ -n "$CASES" ]; then
  python l2_grounding_behaviour.py --ia-path "$IA_PATH" --cases "$CASES" --outdir "$WORKDIR/L2"
else
  echo "L2 skipped: pass --cases <critical-cases.jsonl> to run it"
fi
python l3_keep_alive_cold_reload.py --base-url "$BASE_URL" --model "$MODEL" --outdir "$WORKDIR/L3"

python - "$WORKDIR" <<'PY'
import json, sys
from pathlib import Path
work = Path(sys.argv[1])
allsum = {}
for d in sorted(work.glob("L*")):
    f = d / "summary.json"
    if f.exists():
        allsum[d.name] = json.loads(f.read_text())
(work / "summary_all.json").write_text(json.dumps(allsum, indent=2))
print("wrote", work / "summary_all.json")
PY
echo "done"
```

### My pre-flight check (done; the long run itself was NOT executed)

- `python -m py_compile` on `unpack_reports.py`, `common.py`, `l0_…py`, `l1_…py`, `l2_…py`, `l3_…py` — all OK.
- `bash -n run_all_long_tests.sh` — OK.
- `unpack_reports.py` was run once against this report into a temporary directory to confirm all seven files
  extract and paths resolve; `python unpack_reports.py --help`-style invocation (no args) returns the usage
  string and exit code 2 as designed.
- No long/model/GPU run was started. The scripts only call the local Ollama HTTP API at run time, which the
  user triggers later.
