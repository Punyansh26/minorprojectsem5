# REPORT 06 — Verification and Caching

## Summary

This pass implements **A2 from the Phase 0 roadmap** (chapter 06 §4): skip the 9B grounding
re-review on verified draft-cache hits. Previously `generate_answer_node` ran the ~7.4 s 9B
`REVIEW_PROMPT` call on *every* answered draft — including drafts served straight from the
exact-key `RagCache` — even though a cache hit is, by construction, a previously reviewed and
quote-validated answer for a byte-identical `(release, payload, prompts, schema, model)` key.
The change gates the review behind a `from_cache` flag so a hit returns after the cheap,
deterministic `source_quote` re-validation without a second generation. The verbatim-quote
guarantee, release-bound cache keys, exact SQL cutoffs, and the critical-policy 9B path are all
unchanged. This is the smallest coherent, lowest-risk win in chapter 06 and the only one that
needs no model download or threshold calibration (B1 claim checker, B6 FAQ/semantic cache, and
C2 sentence-level verification are Phase 1–2 and remain future work).

The expected saving is **~7.4 s per answered draft-cache hit** (the entire median review call),
turning an exact-repeat answered turn from 2 model calls (routing + review) into 1 (routing
only). The end-to-end latency figure is an `[Estimated]`/`[Measured-here]`-pending number until
the user runs long test **L0** (needs the local 9B GPU); the *call-count* reduction is verified
here by unit tests.

## What was done

- Modified `code/Institute-voice-agent/institute-assistant/assistant/nodes.py`
  (`generate_answer_node`): introduced a `from_cache` flag (true when a validated answered draft
  was returned by `RagCache.get`) and changed the review guard from
  `if result.status == "answered":` to `if result.status == "answered" and not from_cache:`.
  Added an invariant comment documenting *why* skipping is safe (put stores only reviewed
  drafts; every failure path deletes) and *when* it would stop being safe (if a future change
  ever caches a pre-review draft).
- Updated `code/Institute-voice-agent/institute-assistant/tests/test_memory_cache.py`:
  - Renamed `test_matching_turn_reuses_evidence_and_draft_but_always_reviews` →
    `test_matching_turn_reuses_evidence_and_draft_and_skips_review`; now asserts the hit turn
    makes **1** model call (routing only) and the last invoke is `ROUTING_PROMPT`, not
    `REVIEW_PROMPT`.
  - Reframed `test_review_rejection_evicts_draft_and_never_creates_ticket` so review rejection
    is exercised on a *fresh generation* (a hit no longer reviews): an answered draft rejected
    by review is not persisted, the next identical turn is a draft-cache *miss*, and no ticket
    is created.
  - Reframed `test_provider_error_on_cache_hit_remains_unavailable` →
    `test_provider_error_on_review_remains_unavailable`: a provider error on the review call of
    a fresh generation still fails closed (`unavailable`) and never leaks the provider body.
- Updated `code/demo2/tests/test_demo.py`
  (`test_bridge_uses_real_graph_history_and_persistent_cache`): the repeated-question turn is a
  draft-cache hit and now expects **1** model call instead of 2.
- Wrote the long-test scripts (L0, L1) into the final section of this report for the user to run
  on the local 9B.

No chapter documents were edited (per the FutureWork `AGENTS.md` rule); corrections and findings
live only in this report.

## How it was done

The chapter's safety argument (06 §4) is that the draft `cache_key` binds every input that can
change the correct answer — release hash, packed payload, `ANSWER_PROMPT`, `REVIEW_PROMPT`,
`GroundedAnswer` schema, model identity, temperature, max tokens — and the cache is SHA-256
exact-match. Reading `cache.py` and `generate_answer_node` confirmed the two code facts the
argument depends on:

1. The **only** `cache.put` for a draft happens at the very end of the function, on
   `result.model_copy(update={"evidence": validated_evidence})` — i.e. the answer that already
   passed the 9B review **and** the per-evidence `source_quote` loop.
2. Every rejection path (`result.status != "answered"`, empty evidence, `source_id` out of
   range, quote validation failure) calls `cache.delete(key)`.

So a cache hit cannot be anything other than a previously approved answer for byte-identical
inputs. Re-running the review at `temperature=0` on identical bytes cannot *correctly* change
the verdict; it only adds the review latency and introduces a nondeterministic-flakiness risk
(a provider blip flipping `answered`→`unavailable`, which `RAG_MEMORY_CACHE_VALIDATION.md`
records happening once).

Design decisions and trade-offs:

- **Kept the deterministic `source_quote` loop on hits.** It re-proves the stored quotes are
  still verbatim substrings of the (immutable, release-bound) sources at near-zero cost, and it
  is the path that performs the cutoff-line-expansion repair. This is exactly the "cheap
  re-confirmation" the chapter recommends. A hit is therefore *verified*, not merely *trusted*.
- **Did not change the on-disk cache format.** The chapter suggests an explicit `reviewed=True`
  flag in the cached payload as a guard. `GroundedAnswer` has `extra="forbid"`, so a flag cannot
  live inside the stored dump without breaking `model_validate`, and an envelope wrapper would
  break the grounding tests that read `drafts[0]["evidence"][0]["quote"]` directly. Because the
  current code *only ever* stores reviewed drafts, the invariant is instead encoded as a code
  comment at both the put site and the gate. If a future change caches a pre-review draft, the
  comment instructs re-adding an explicit flag before the review may be skipped. This keeps the
  change minimal and preserves every existing grounding assertion.
- **Left the critical-policy path untouched.** Fees/cutoff/eligibility/loan turns have no draft
  cache and always run `CriticalReview`; A2 does not apply there, exactly as the chapter
  requires.

Techniques from chapter 06 implemented vs deferred:

| Technique | Status | Reason |
| --- | --- | --- |
| §4 A2 — skip re-review on verified draft-cache hits | **Implemented** | Phase 0, Low risk, Small effort; no download/calibration |
| §2 B1 — claim-level checker (MiniCheck/HHEM) + §3 risk-gated review | Deferred | Phase 1; needs model download (long test) + conformal calibration; Hindi/Hinglish coverage unverified |
| §7 B6 — static FAQ bank / semantic cache | Deferred | Phase 1–2; needs offline FAQ generation + slot/release gate design |
| §6 C2 — sentence-level streaming verification | Deferred | Phase 2; depends on streaming generation (05) and streaming TTS (07) |
| §5 Speculative RAG, §8 KV-cache reuse | Deferred | T1/T2 techniques; §8 explicitly not recommended on T0 |
| §9 evidence compression | Not done (correctly avoided) | Breaks `source_quote`; chapter says do not compress evidence |

## Before vs. After

| Metric | Before | After | Change | Evidence label |
| --- | --- | --- | --- | --- |
| Model calls on an answered draft-cache hit | 2 (routing + review) | 1 (routing) | −1 call | [Measured-here] (unit test) |
| 9B review calls on draft-cache hits | 1 per hit | 0 per hit | −100% | [Measured-here] (unit test) |
| Verification stage time on an answered hit | ~7.4 s (review) | ~0 s + deterministic `source_quote` | −~7.4 s | [Estimated] from review p50 7.41 s (01 §4.1) |
| Exact-repeat answered turn (local, text) | 12.687 s (routing + review; 01 §4.2) | ≈5–6 s (routing only) | −~7 s | [Estimated] — pending L0 |
| IA unit tests passing | 333 | 333 | 0 | [Measured-here] |
| demo2 unit tests passing | 44 | 44 | 0 | [Measured-here] |
| Grounding guarantees (quote validity, release binding, SQL cutoffs, critical 9B path) | intact | intact | unchanged | [Measured-here] (tests) |

The end-to-end wall-clock reduction on the local 9B (what a reader perceives on a repeat
question) could **not** be measured here because it needs the GPU-resident 9B and must not run
in this documentation pass — see long test **L0**. Until then the exact-repeat row is
`[Estimated]`, derived from the measured review p50 of 7.41 s (01 §4.1) and the measured
exact-repeat baseline of 12.687 s (01 §4.2).

## Files changed

```
Modified: code/Institute-voice-agent/institute-assistant/assistant/nodes.py
          — generate_answer_node: added from_cache flag; gate the 9B REVIEW_PROMPT call
            behind `not from_cache` so verified draft-cache hits skip re-review while still
            running deterministic source_quote re-validation (A2).

Modified: code/Institute-voice-agent/institute-assistant/tests/test_memory_cache.py
          — renamed/updated the hit test to assert 1 model call + ROUTING_PROMPT on a hit;
            reframed the review-rejection and provider-error tests to exercise the fresh-
            generation review path (a hit no longer reviews).

Modified: code/demo2/tests/test_demo.py
          — bridge persistent-cache test: repeated-question hit now expects 1 model call.

Created:  idea/FutureWork/REPORT_06_VERIFICATION_AND_CACHING.md — this report.
```

No files were deleted. No dependencies were added.

## Issues encountered

- **Stale test premises.** Four tests encoded the old "a hit still reviews" behaviour
  (one in IA, one in demo2) or depended on it to trigger a review on the second turn (two in
  IA). Leaving them would have asserted the now-incorrect behaviour. Resolved: renamed/updated
  the two call-count tests to the new expectation (1 call on a hit), and reframed the two
  safety tests so review rejection and provider errors are exercised on a fresh generation (the
  only place the review now runs). The *safety intent* of each test is preserved — rejection
  still evicts and creates no ticket; provider errors still fail closed without leaking the
  body.
- **`reviewed=True` flag could not be stored inside the cached payload.** `GroundedAnswer` uses
  `extra="forbid"` and several grounding tests read the raw stored quote, so an in-payload flag
  or envelope wrapper would break either validation or those tests. Resolved by encoding the
  invariant as a documented code comment at the put site and the gate instead of changing the
  on-disk format. Open follow-up (low priority): if B6/semantic caching later stores pre-review
  drafts, add an explicit reviewed marker (e.g. a separate key namespace) before relying on the
  skip.
- **End-to-end latency not measurable in this pass.** Measuring the wall-clock win needs the
  GPU-resident local 9B and is a long test by the FutureWork definition. Not run here; provided
  as L0.

## Dependencies and prerequisites

- **No new packages** installed into `minor`.
- Assumes O9 (release-bound exact-key draft cache, `cache.py::RagCache`) and O6/O8 (critical
  policy path and `source_quote` validation) from baseline 01 §3 are present — they are.
- No hardware requirement for the code change or the unit tests (they mock the provider). Long
  test L0 needs the RTX 4060 (T0) with Ollama `qwen3.5:9b` resident and idle.

## Next steps

- Run long test **L0** to replace the `[Estimated]` exact-repeat/latency rows with
  `[Measured-here]` values, and fold the `summary.json` back into this report as an addendum.
- Phase 1 unblocked next in this area: **B1** (claim-level checker + risk-gated review, 06
  §2–§3) and **B6** (static FAQ answer bank, 06 §7). Both need their own task sessions: B1
  needs a checker download + conformal calibration against the 120-turn set and
  `critical-cases.json`; B6 needs offline FAQ generation gated by slot + release hash.
- When B7 (token streaming, 05) and A5 (sentence TTS, 07) land, **C2** (sentence-level
  verification) becomes reachable.

## Test results

- IA unit/integration suite (mocked providers, fast):
  `conda activate minor && cd code/Institute-voice-agent/institute-assistant && python -m pytest tests/ -q`
  → **333 passed** (9.84 s), including the updated `test_memory_cache.py` (47 passed).
- demo2 suite (mocked providers, fast):
  `conda activate minor && cd code/demo2 && python -m pytest tests/ -q`
  → **44 passed** (3.71 s), including the updated bridge test.
- Syntax check: `python -m py_compile assistant/nodes.py tests/test_memory_cache.py
  ../../demo2/tests/test_demo.py` → OK.

No long tests were run by me. The end-to-end latency verification is in the next section.

## Long-running tests (to be run by the user later)

| ID | Question it answers | Approx. run time | Needs | Pass / read-out criterion |
| --- | --- | --- | --- | --- |
| L0 | Does a verified draft-cache hit drop from 2 model calls to 1 and save ~7 s on the local 9B? | ~3–6 min | GPU idle (RTX 4060, Ollama `qwen3.5:9b`), KB release present | Repeat turn: `draft_cache=="hit"`, `model_calls==1`, no `review_model` stage; wall-clock repeat < first turn by roughly the review time |
| L1 | Do grounding + abstention stay identical to the 9B-review baseline across the 120-turn set? (acceptance test C/F/H) | ~40–70 min | GPU idle, 120-turn `cases.json` + `critical-cases.json` | Status distribution unchanged vs baseline; 100% quotes pass `source_quote`; cutoff cases still exact or `unavailable` |

### Setup

The scripts below are embedded as fenced blocks, each preceded by a ``**File:** `name` `` line.
To unpack them into a scratch directory (kept out of the repo's own data dirs) and run them:

```bash
mkdir -p ~/fw06_longtests && cd ~/fw06_longtests
# Paste each fenced script into the named file, then:
chmod +x run_all_long_tests.sh
conda activate minor
./run_all_long_tests.sh /run/media/rtx/Files/Study/Semester\ 5/Minor
# Outputs: ~/fw06_longtests/out/L0/summary.json and ~/fw06_longtests/out/L1/summary.json
```

Each test writes a `summary.json`; L0 is a quick probe, L1 reuses the repo's own
`evaluate_upgrade.py` harness. Both unload nothing persistent and keep scratch SQLite under
`~/fw06_longtests/out/` (never under the repo `data/`/`evaluation/` dirs).

**File:** `run_all_long_tests.sh`

```bash
#!/usr/bin/env bash
# Runs the FutureWork-06 (A2) long tests. Usage: ./run_all_long_tests.sh <MINOR_REPO_ROOT>
set -euo pipefail
ROOT="${1:?pass the Minor repo root as arg 1}"
IA="$ROOT/code/Institute-voice-agent/institute-assistant"
DEMO2="$ROOT/code/demo2"
OUT="$(cd "$(dirname "$0")" && pwd)/out"
mkdir -p "$OUT/L0" "$OUT/L1"

echo "== L0: cache-hit skips review (local 9B) =="
MINOR_IA="$IA" python l0_cache_hit_probe.py --agent-root "$IA" --out "$OUT/L0/summary.json" \
  || echo "L0 FAILED (see stderr)"

echo "== L1: 120-turn grounding/abstention parity =="
# Resolve the newest KB release state dir the agent uses.
KB_STATE="$IA/kb_state"
CASES="$DEMO2/evaluation/upgrade-20260930/cases.json"
python "$DEMO2/evaluate_upgrade.py" \
  --agent-root "$IA" --kb-state "$KB_STATE" \
  --cases "$CASES" --output "$OUT/L1/results.json" --resume \
  || echo "L1 run FAILED (see stderr)"
python l1_summarize.py --results "$OUT/L1/results.json" --out "$OUT/L1/summary.json" \
  --baseline "$DEMO2/data/upgrade-20260930/baseline/results.json" \
  || echo "L1 summarize skipped (baseline results.json not found); raw results in $OUT/L1/results.json"

echo "Done. See $OUT/L0/summary.json and $OUT/L1/summary.json"
```

**File:** `l0_cache_hit_probe.py`

```python
"""L0: prove a verified draft-cache hit skips the 9B review on the local 9B.

Asks the same knowledge question twice in two fresh sessions sharing one RagCache.
Turn 1 is a miss (routing + generation + review). Turn 2 is a draft-cache hit and,
with A2, must make only the routing call and skip the review stage. Fails closed:
any exception is written to summary.json rather than raised, so the runner continues.
"""
import argparse, json, os, sys, time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--question", default="How is admission to B.Tech at IIIT Naya Raipur decided in 2026?")
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    scratch = args.out.parent
    os.environ.update(LLM_PROVIDER="ollama", JEV_ROUTING_MODE="off",
                      HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                      CHECKPOINT_DB_PATH=str(scratch / "unused.sqlite"),
                      RAG_CACHE_DB_PATH=str(scratch / "shared-cache.sqlite"),
                      TICKETS_DB_PATH=str(scratch / "blocked.sqlite"))
    sys.path.insert(0, str(args.agent_root.resolve()))
    summary = {"question": args.question}
    try:
        from langchain_core.messages import HumanMessage
        from langgraph.checkpoint.memory import MemorySaver
        from assistant.graph import build_graph

        def ask(thread):
            t = time.monotonic()
            r = build_graph(MemorySaver()).invoke(
                {"messages": [HumanMessage(content=args.question)],
                 "student_id": "l0", "student_category": "general"},
                {"configurable": {"thread_id": thread, "llm_provider": "ollama"}})
            return r, time.monotonic() - t

        first, t1 = ask("l0-first")
        second, t2 = ask("l0-second")
        m1, m2 = first.get("rag_metrics", {}), second.get("rag_metrics", {})
        summary.update({
            "first": {"seconds": round(t1, 3), "status": first.get("response_status"),
                      "draft_cache": m1.get("draft_cache"), "model_calls": m1.get("model_calls"),
                      "stages": sorted((m1.get("stage_ms") or {}).keys())},
            "second": {"seconds": round(t2, 3), "status": second.get("response_status"),
                       "draft_cache": m2.get("draft_cache"), "model_calls": m2.get("model_calls"),
                       "stages": sorted((m2.get("stage_ms") or {}).keys())},
            "review_skipped_on_hit": (m2.get("draft_cache") == "hit"
                                      and m2.get("model_calls") == 1
                                      and "review_model" not in (m2.get("stage_ms") or {})),
            "wallclock_saved_seconds": round(t1 - t2, 3),
            "sources_identical": first.get("sources") == second.get("sources"),
            "pass": (m2.get("draft_cache") == "hit" and m2.get("model_calls") == 1
                     and first.get("response_status") == second.get("response_status")
                     and first.get("sources") == second.get("sources")),
        })
    except Exception as error:  # fail closed; do not crash the runner
        summary["error"] = f"{type(error).__name__}: {error}"
        summary["pass"] = False
    args.out.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
```

**File:** `l1_summarize.py`

```python
"""L1: summarize the 120-turn run and compare status distribution + quote integrity
against the recorded 9B-review baseline. Pure post-processing on existing JSON; safe
to run without the GPU once evaluate_upgrade.py has produced results.json."""
import argparse, json
from collections import Counter
from pathlib import Path


def dist(rows):
    return dict(Counter(r.get("response_status") for r in rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=False)
    args = ap.parse_args()
    rows = json.loads(args.results.read_text())
    # Quote integrity: every returned source must carry a non-empty quote (source_quote
    # already ran in-graph; empty/absent quotes would mean a citation slipped through).
    bad_quotes = [r["id"] for r in rows for s in (r.get("sources") or []) if not s.get("quote")]
    summary = {"n": len(rows), "status_distribution": dist(rows),
               "turns_with_empty_quote": bad_quotes,
               "quote_integrity_ok": not bad_quotes}
    if args.baseline and args.baseline.exists():
        base = json.loads(args.baseline.read_text())
        base_rows = base if isinstance(base, list) else base.get("results", [])
        summary["baseline_status_distribution"] = dist(base_rows)
        by_id = {r["id"]: r.get("response_status") for r in base_rows}
        summary["status_mismatches"] = [
            {"id": r["id"], "baseline": by_id.get(r["id"]), "now": r.get("response_status")}
            for r in rows if r["id"] in by_id and by_id[r["id"]] != r.get("response_status")]
        summary["abstention_unchanged"] = not summary["status_mismatches"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
```

### My pre-finish checks on these scripts

- `bash -n run_all_long_tests.sh` and `python -m py_compile l0_cache_hit_probe.py
  l1_summarize.py` — syntax only (I did not execute L0/L1; they need the GPU-resident 9B / the
  40–70 min run).
- `l1_summarize.py` is pure post-processing and can be dry-run on the already-recorded baseline
  `results.json` without the model.
- `evaluate_upgrade.py` is the repo's existing resumable harness; the runner points it at the
  shipped `cases.json` and writes all scratch SQLite under `~/fw06_longtests/out/`.

Fold the resulting `summary.json` files back here as an addendum once run; until then the
exact-repeat / end-to-end latency rows in "Before vs. After" are `[Estimated]`.
