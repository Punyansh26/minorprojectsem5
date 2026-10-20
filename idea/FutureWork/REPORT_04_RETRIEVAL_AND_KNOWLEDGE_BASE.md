# REPORT 04 — Retrieval and knowledge base

Task: [04 Retrieval and knowledge base](04_RETRIEVAL_AND_KNOWLEDGE_BASE.md). Date: 2026-10-20 (IST). Hardware tier: **T0** (RTX 4060 Laptop 8 GB, i7-14650HX, 31 GB RAM); all retrieval work here runs on the CPU. Roadmap rows: retrieval items of [13](13_ROADMAP_AND_PRIORITISATION.md).

Evidence labels follow [00_INDEX](00_INDEX.md): **[Measured-here]**, **[Reported]**, **[Estimated]**.

Paths are relative to the repository root (`Minor/`). `KBB/` = `code/knowledgebaseenhanced/`. `IA/` = `code/Institute-voice-agent/institute-assistant/`.

## Summary

Chapter 04 describes the legacy `IA/assistant/kb/search.py` engine and its 117-case gate, but Demo 2 serves the **`kbb` release** through `KBB/kbb/release.py::ReleaseSearch` (REPORT_01 Issue 2). I worked on the served path. Measuring it first changed the plan. On the 156-case spot-check set, the served release already passes **137/139** scored cases, and `loan_repayment_hindi` (the chapter's one failing case) **passes**. Recall at 6 is at its ceiling. Ordering is not: only **91 of 127** answerable cases pass on the top-1 hit, and MRR is **0.823** (Hindi 0.785) [Measured-here]. That is the gap the chapter's top-ranked upgrade, a cross-encoder reranker, targets. I made three changes. (1) The spot-check harness now reports ordering metrics (pass@1, pass@3, MRR) overall and per language (§11, rank 3). (2) I added the reranker (§7, rank 1) as a latency-gated module that falls back safely. It is off by default, reads local weights only, runs on the CPU, and keeps the fusion order on any failure. It never touches the policy, exact-cutoff or matched-record paths. (3) I tested the Indic BM25 normalisation (§3, rank 2) and measured **no change on any case**, so I did not ship it. With the flag off, retrieval is **identical case by case** to before. The reranker weights in the local cache are an **incomplete download** (1.2 GB `.incomplete` blob), so measuring the reranker's real effect is a long test (download, then A/B) for you to run. 14 new tests pass. The kbb, institute-assistant and Demo 2 suites all pass (55, 331 and 44 tests).

## What was done

- **Modified `KBB/scripts/spotcheck.py`.** Added `reciprocal_rank()` and `ordering_fields()`. `run_engine` rows now also carry `pass_at_1`, `pass_at_3` and `rr` for answerable cases. `summarize()` adds an `ordering` block (pass@1, pass@3, pass@k, MRR) and a `by_language` split with the same fields. `compare()` adds an ordering table. All additions are new keys, so existing keys and the activation gate (`legacy_origin_pass_rate`) are unchanged.
- **Created `KBB/kbb/rerank.py`.** `Reranker` loads a sentence-transformers `CrossEncoder` lazily with `local_files_only=True` on the CPU. It runs scoring on a single worker thread under a wall-clock budget. It returns `None` (meaning "keep the fusion order") when the model is unavailable, raises, overruns the budget, or is still busy with an abandoned query. `last` records the status and time of each call.
- **Modified `KBB/kbb/release.py`.**
  - `ReleaseSearch.__init__` builds a `Reranker` only when `cfg.retrieval.rerank` is true.
  - Fusion now also records each parent's best-contributing unit text (`best_unit`). This is the text sent to the cross-encoder.
  - The new `_rerank()` reorders the eligible top `rerank_top` parents, puts year-matched blocks first when the question names a year, and appends the untouched fusion tail.
  - Policy-bound spans, exact cutoff rows and matched records are unaffected. The first two return before fusion, and matched records are still added first.
- **Modified `KBB/kbb/config.py`.** `rerank_budget_s` changed from 2.5 to **1.5** s, to match chapter 04 §11 ("CPU reranker latency-gated ≤ 1.5 s"). Comments added. `rerank` is still `False`. It is switched on with `KBB_RETRIEVAL__RERANK=true`.
- **Created `KBB/tests/test_rerank.py`.** 14 tests covering the gate, the wiring and the ordering metrics.
- **Fixed in `REPORT_03`.** The per-file test counts were wrong: the files hold 11 and 4 tests, not 12 and 3. The total of 28 is unchanged.
- **Wrote this report**, including two long tests: `L0` fetches and verifies the reranker weights, and `L1` runs the reranker A/B plus a shortlist-size sweep.

I did not edit any chapter document. I did not modify, rebuild or re-activate any release. All measurements were read-only: I called `ReleaseSearch.search` directly and never called `release.evaluate`, which writes `validation.json`.

## How it was done

### Measured the served path before choosing work

`/tmp/fw04/probe.py` ran every spot-check case through the live `ReleaseSearch` on release `20261014T005813186766Z` and scored the top 1, 3 and 6 hits with the existing `score_case` rule. This took about 6 s on the CPU. The result:

| Finding | Value | Consequence |
| --- | --- | --- |
| Pass@6, scored cases | 137/139; failures `new_established` and `new_curriculum_credits`, both English | recall is at its ceiling |
| `loan_repayment_hindi` | passes | the chapter's failing case does not apply to the served release |
| Answerable pass@1 / pass@3 / pass@6 | 91 / 113 / 125 of 127 | the top hit is often not the expected source |
| MRR, 116 cases that name a source | 0.823 overall; English 0.798, Hindi 0.785, Hinglish 0.895 | ordering is the lever, so reranking is ranked first |

### Indic BM25 normalisation: measured, not shipped

`/tmp/fw04/indic_exp.py` patched the tokeniser used by `kbb.index` (and only BM25 indexing and querying, never verification). It folded nukta (U+093C), chandrabindu to anusvara, and ZWJ/ZWNJ, then re-ran the probe. **Every metric and every per-case row was identical** to the baseline. The kbb tokeniser already applies NFC, Devanagari-digit folding and casefolding, and the dense E5 channel already covers the Hindi cases. This corpus therefore has no lexical-variant misses for the change to fix. Shipping it would add an index/query normalisation contract with no measured benefit, so I left it out (AGENTS: "smallest coherent change that delivers a measurable optimization").

### Reranker design

| Decision | Reason |
| --- | --- |
| Rerank parent ids, scoring each parent's best-matching unit text | kbb fuses by parent. A large table parent would lose its matching row if the reranker saw the parent text truncated to 2000 characters. The best unit is the text that actually matched. Unit text, including any contextual prefix, is retrieval-only and is never displayed, so the `source_quote` verbatim check is unaffected. |
| Rerank after fusion and eligibility, before parent expansion; policy, cutoff and matched-record paths untouched | Chapter 04 §7 placement and risks. Exact paths must stay exact. |
| Year-matched blocks stay above undated ones when the question names a year | Chapter 04 §2 risk. The fusion boost (×2 for a year match) would otherwise be lost. |
| Single worker, budget wait, `busy` skip | Python cannot cancel a running forward pass. An overrun is abandoned, and later queries skip reranking until the worker is free, so latency stays bounded and work cannot pile up. |
| `local_files_only=True` and CPU by default | No download from code (AGENTS rule). No contention for VRAM with the resident 9B LLM (chapter 01 §4.3). |
| Budget of 1.5 s, not 2.5 s | Chapter 04 §11 pass criterion 6. |

### Deferred, with reasons

| Item (chapter §) | Reason |
| --- | --- |
| Embedder swap to Qwen3-Embedding-0.6B / EmbeddingGemma (§5) | Needs a model download and a full release rebuild. The kbb AGENTS file forbids full-corpus batch runs without your explicit approval. Do this after the reranker A/B. |
| Contextual prefixes and late chunking (§4) | Offline LLM pass over the corpus plus a rebuild. Same approval constraint. Chapter 15 owns the ingestion redesign. |
| Predictive prefetch (§10) | Needs the streaming STT path wired into Demo 2. REPORT_03 deferred that transport. |
| Weighted or learned fusion (§2) | Chapter: marginal, and too little data to learn from. `channel_weights` already exists in config for a manual trial. |
| HyDE (§9b) and quantization/MRL (§6) | The chapter recommends against both. Not implemented. |
| Legacy `IA/assistant/kb/search.py` and its evaluator | Not served by Demo 2. I left it unchanged rather than duplicate the reranker into an inactive engine. |

## Before vs. After

| Metric | Before | After | Change | Evidence label |
| --- | --- | --- | --- | --- |
| Pass@6, scored cases, served kbb release, rerank off | 137/139 | 137/139 | identical per case | [Measured-here] 2026-10-20, T0 CPU |
| Answerable pass@1 / pass@3 / pass@6 | not reported by the harness | 91 / 113 / 125 of 127 | now reported | [Measured-here] |
| MRR (116 cases naming a source) | not reported | 0.823 (en 0.798, hi 0.785, hinglish 0.895) | now reported | [Measured-here] |
| Per-language split in the harness | none | `by_language` with pass and ordering fields | added | [Measured-here] |
| Warm retrieval p50 / p95, rerank off | 14.1 / 112.7 ms | 14.9 / 30.6 ms | within run-to-run noise; no code-path change | [Measured-here] |
| Indic BM25 normalisation | — | 0 cases changed | not shipped | [Measured-here] |
| Reranker with the flag on and the current (incomplete) cache | no code | status `unavailable`, fusion order served, 7 hits returned | safe fallback verified | [Measured-here] |
| MRR with reranker (top 20, budget 1.5 s) | 0.823 | **pending `L1`** | — | [Estimated] increase (chapter §7, [R405]) |
| Rerank latency p50 / p95 (20 pairs, CPU) | — | **pending `L1`** | — | [Estimated] 0.3–1.0 s (chapter §7) |
| Test suites | kbb 41, IA 331, demo2 44 | kbb 55, IA 331, demo2 44 | +14, 0 regressions | [Measured-here] |

The p95 difference between the two flag-off runs (112.7 ms and 30.6 ms) came from runs of identical retrieval code. It matches REPORT_01 Issue 9, which found first-seen query shapes costing about 100 ms in the embedder. It is not an effect of this change.

## Files changed

```
Modified: code/knowledgebaseenhanced/scripts/spotcheck.py — pass@1/@3, reciprocal rank, MRR, per-language summary, ordering table
Created:  code/knowledgebaseenhanced/kbb/rerank.py — lazy, latency-gated, fail-safe CPU cross-encoder
Modified: code/knowledgebaseenhanced/kbb/release.py — best-unit tracking in fusion; optional _rerank over the eligible fused head
Modified: code/knowledgebaseenhanced/kbb/config.py — rerank_budget_s 2.5 → 1.5; comments on the flag
Created:  code/knowledgebaseenhanced/tests/test_rerank.py — 14 tests (gate, wiring, ordering metrics)
Modified: idea/FutureWork/REPORT_03_SPEECH_INPUT_AND_TURN_TAKING.md — corrected per-file test counts (11 and 4)
Created:  idea/FutureWork/REPORT_04_RETRIEVAL_AND_KNOWLEDGE_BASE.md — this report
```

## Issues encountered

- **Chapter 04 targets the engine that Demo 2 does not serve.** Open, documented. The chapter's numbers (222 chunks, recall@6 0.9892, `loan_repayment_hindi` failing, TOP_K 6 / FETCH_K 32) describe the legacy `kb_state` release. Demo 2 serves the `kbb` release (2055 evidence blocks, 5153 units), where that case passes. I measured and changed the served path. Correcting chapter 04 is a chapter edit, so I left it to you.
- **The reranker weights are an incomplete download.** Open, and `L0` fixes it. `~/.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3/blobs/` holds only a 1.2 GB `.incomplete` file. REPORT_01 Issue 2 called the model "cached locally", which is not the case. With the flag on, loading fails, the error is caught, and fusion order is served (verified above). The error text from sentence-transformers is unhelpful (`AttributeError: 'NoneType' object has no attribute 'endswith'`). `last["reason"]` records it as-is.
- **The Indic normalisation hypothesis did not hold on this corpus.** Resolved by measurement: zero cases changed, so nothing was shipped.
- **An overrunning rerank keeps a CPU core busy after the query has moved on.** Open, by design. The forward pass cannot be cancelled, so the worker finishes in the background and later queries report `busy` and use fusion order until it does. `L1` reports how often this happens. If it is frequent at the 1.5 s budget, lower `rerank_top` rather than raising the budget.
- **CPU contention with Whisper and VITS.** Open, not measured. Demo 2 runs Whisper int8 and VITS on the same CPU, and the reranker uses torch's default thread count. `L1` measures reranking alone. A serving test with speech running at the same time belongs to chapter 10.
- **Two English spot-check failures** (`new_established`, `new_curriculum_credits`). Open, carried over from before. Neither is caused by this change. `L1` shows whether reranking recovers them.

## Dependencies and prerequisites

- **No new packages.** `sentence-transformers 3.3.1` and `torch` are already in the `minor` environment and are already used by the E5 embedder.
- **The model weights are needed to switch the feature on.** `BAAI/bge-reranker-v2-m3` (Apache-2.0, about 2.3 GB) must be completed in the Hugging Face cache. `L0` does this. Nothing in the code downloads it.
- **Assumes complete:** REPORT_01's finding that Demo 2 serves the kbb release; REPORT_02's metrics. No Phase 0 or 1 dependency is needed for reranking.
- **Hardware:** CPU only on T0 (deliberately). It must not be moved to the GPU while the 9B model is resident.

## Next steps

1. Run `L0`, then `L1`. If `L1` passes (criteria below), enable the reranker for Demo 2 with `KBB_RETRIEVAL__RERANK=true` in `code/demo2/.env`, and record the `rerank_top` that `L1` recommends.
2. Embedder A/B (Qwen3-Embedding-0.6B, §5) as a parallel kbb release, compared with `spotcheck.py --engine release:A --engine release:B`, which now reports MRR and per-language results. Needs your approval for the rebuild.
3. Add harder Hindi and Hinglish cases. Only 1 of the 39 newer cases is Hindi and 4 are Hinglish, so per-language ordering gains are weakly powered.
4. Once streaming STT is wired (REPORT_03 next step), prefetch plus a warm reranker on stable partials (§10). This hides the rerank latency behind the end of the turn.
5. Update chapter 04's baseline section to describe the kbb release (your edit).

## Test results

- `conda activate minor && cd code/knowledgebaseenhanced && python -m pytest -q -p no:cacheprovider` → **55 passed** (41 existing + 14 new) in about 3 s.
- `cd code/Institute-voice-agent/institute-assistant && python -m pytest -q -p no:cacheprovider` → **331 passed** (128 existing deprecation warnings).
- `cd code/demo2 && python -m pytest -q -p no:cacheprovider` → **44 passed**.
- Flag-off regression check: `/tmp/fw04/probe.py` on the live release before and after the change gave **identical per-case rows** (pass@1/3/6 and reciprocal rank for all 156 cases).
- Flag-on degradation check: with `HF_HUB_OFFLINE=1 KBB_RETRIEVAL__RERANK=true`, `ReleaseSearch.search("What is the hostel fee?")` returned 7 hits with reranker status `unavailable`.
- I did not run the long tests `L0` and `L1` (see below).

## Long-running tests (to be run by the user later)

| ID | Question it answers | Approx. time | Needs | Pass / read-out criterion |
| --- | --- | --- | --- | --- |
| L0 | Are the `bge-reranker-v2-m3` weights complete and loadable offline? | 5–20 min (about 2.3 GB, resumable) | network (Hugging Face) | `summary.json`: `complete: true`, `offline_load_ok: true`, sanity score of a relevant pair above an irrelevant one |
| L1 | Does reranking improve ordering without regressions, and at what CPU latency? | 10–20 min | `L0` done; CPU otherwise idle (stop Demo 2 and Ollama generation) | for the recommended config: answerable pass@6 ≥ 125/127 with **no case regressions** vs rerank off, `no_result` cases unchanged, MRR > 0.823, Hindi MRR not lower than 0.785, rerank p95 ≤ 1500 ms, timeout + busy ≤ 5% of queries |

### Setup

```bash
# From the repository root (Minor/)
mkdir -p idea/FutureWork/report04_artifacts
python - <<'PY'
import pathlib, re
rep = pathlib.Path("idea/FutureWork/REPORT_04_RETRIEVAL_AND_KNOWLEDGE_BASE.md").read_text(encoding="utf-8")
out = pathlib.Path("idea/FutureWork/report04_artifacts")
for name, body in re.findall(r"\*\*File:\*\*\s*`([^`]+)`\s*\n+```[a-zA-Z0-9]*\n(.*?)\n```", rep, re.DOTALL):
    (out / name).write_text(body + "\n", encoding="utf-8"); print("wrote", name)
PY
cd idea/FutureWork/report04_artifacts
conda activate minor
bash run_all_long_tests.sh --check     # fast: cache state, paths, imports; no download, no model load
bash run_all_long_tests.sh             # L0 (download) then L1 (A/B); resumable
```

Outputs: `report04_artifacts/L0_fetch/summary.json` and `report04_artifacts/L1_rerank_ab/{summary.json,rows.json,report.md}`. Neither test writes to `code/knowledgebaseenhanced/data/` (no `validation.json`, no activation). Both scripts exit and so release the model when they finish.

**File:** `run_all_long_tests.sh`

```bash
#!/usr/bin/env bash
# Chapter-04 long tests. Resumable: a test with an existing summary.json is skipped unless --force.
# --check runs only fast validation (no download, no model load).
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
  local id="$1" script="$2" outdir="$HERE/$3"
  mkdir -p "$outdir"
  if [[ "$CHECK" == 1 ]]; then
    python "$HERE/$script" --check --out "$outdir/check.json"; return
  fi
  if [[ -f "$outdir/summary.json" && "$FORCE" == 0 ]]; then
    echo "$id: summary.json exists, skipping (use --force)"; return
  fi
  echo "=== $id starting ==="
  python "$HERE/$script" --out "$outdir/summary.json"
  echo "=== $id done -> $outdir/summary.json ==="
}

run_one L0 l0_fetch_reranker.py L0_fetch
run_one L1 l1_rerank_ab.py      L1_rerank_ab
ls -1 "$HERE"/L*/summary.json 2>/dev/null || true
```

**File:** `l0_fetch_reranker.py`

```python
#!/usr/bin/env python3
"""L0 — complete the BAAI/bge-reranker-v2-m3 download and prove it loads offline.

snapshot_download resumes the existing .incomplete blob. Afterwards the model is loaded exactly
as kbb.rerank loads it (CrossEncoder, local_files_only=True, CPU) and one relevant and one
irrelevant pair are scored. --check reports the cache state only (no network, no model load).
"""
import argparse, json, os, time
from pathlib import Path

MODEL = "BAAI/bge-reranker-v2-m3"
CACHE = Path(os.environ.get("HF_HUB_CACHE", Path.home() / ".cache/huggingface/hub")) / "models--BAAI--bge-reranker-v2-m3"


def cache_state():
    blobs = list((CACHE / "blobs").glob("*")) if (CACHE / "blobs").is_dir() else []
    incomplete = [b for b in blobs if b.name.endswith(".incomplete")]
    weights = list(CACHE.glob("snapshots/*/model.safetensors")) + list(CACHE.glob("snapshots/*/pytorch_model.bin"))
    return {"cache_dir": str(CACHE), "blobs": len(blobs), "incomplete_blobs": len(incomplete),
            "incomplete_bytes": sum(b.stat().st_size for b in incomplete),
            "weights_present": bool(weights), "complete": bool(weights) and not incomplete}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    if args.check:
        info = {"check": True, **cache_state()}
        json.dump(info, open(args.out, "w"), indent=2); print(json.dumps(info)); return
    from huggingface_hub import snapshot_download
    t0 = time.monotonic()
    path = snapshot_download(MODEL, allow_patterns=["*.json", "*.safetensors", "*.model", "*.txt", "tokenizer*"])
    fetch_s = time.monotonic() - t0
    os.environ["HF_HUB_OFFLINE"] = "1"
    from sentence_transformers import CrossEncoder
    t1 = time.monotonic()
    ce = CrossEncoder(MODEL, device="cpu", local_files_only=True, max_length=512)
    load_s = time.monotonic() - t1
    good, bad = ce.predict([("What is the hostel fee?", "Hostel fee per semester is Rs. 45,000."),
                            ("What is the hostel fee?", "The library opens at 9 am.")]).tolist()
    summary = {"model": MODEL, "snapshot": path, "fetch_s": round(fetch_s, 1), "load_s": round(load_s, 1),
               "relevant_score": round(good, 4), "irrelevant_score": round(bad, 4),
               "offline_load_ok": True, "sanity_ok": good > bad, **cache_state()}
    json.dump(summary, open(args.out, "w"), indent=2)
    print(json.dumps({k: summary[k] for k in ("complete", "offline_load_ok", "sanity_ok", "load_s")}))


if __name__ == "__main__":
    main()
```

**File:** `l1_rerank_ab.py`

```python
#!/usr/bin/env python3
"""L1 — spot-check A/B of the kbb reranker on the served release (read-only).

Runs the 156-case eval/spotcheck.json through ReleaseSearch with rerank off, then with the
shipped Reranker at rerank_top in {10, 20, 30} under the 1.5 s budget, plus top 20 with a 60 s
budget (quality ceiling without timeouts). Reports pass@1/@3/@k, MRR, per-language results,
per-case regressions vs off, end-to-end search latency, and rerank status and latency.
Never calls release.evaluate (which writes validation.json) and never activates anything.
--check validates paths and imports only.
"""
import argparse, json, os, statistics, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KBB = HERE.parent.parent.parent / "code" / "knowledgebaseenhanced"
CONFIGS = [("off", None, None), ("top10", 10, 1.5), ("top20", 20, 1.5), ("top30", 30, 1.5), ("top20_nobudget", 20, 60.0)]


def pct(values, q):
    values = sorted(values)
    return round(values[int(q * (len(values) - 1))], 1) if values else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    out_dir = Path(args.out).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    active = KBB / "data/kbb/serving/active.json"
    if args.check:
        info = {"check": True, "kbb_root": str(KBB), "active_exists": active.is_file(),
                "cases_exist": (KBB / "eval/spotcheck.json").is_file()}
        try:
            sys.path.insert(0, str(KBB)); sys.path.insert(0, str(KBB / "scripts"))
            import spotcheck, kbb.rerank  # noqa: F401
            info["imports_ok"] = hasattr(spotcheck, "reciprocal_rank")
        except Exception as e:
            info["imports_ok"] = f"{type(e).__name__}: {e}"
        json.dump(info, open(args.out, "w"), indent=2); print(json.dumps(info)); return

    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["HF_HUB_OFFLINE"] = "1"
    sys.path.insert(0, str(KBB)); sys.path.insert(0, str(KBB / "scripts"))
    import spotcheck as sc
    from kbb.release import ReleaseSearch
    from kbb.rerank import Reranker
    release = json.load(open(active))["release"]
    engine = ReleaseSearch(KBB / "data/kbb/serving/releases" / release)
    cases = json.load(open(KBB / "eval/spotcheck.json"))

    # One model load shared by every configuration.
    shared = Reranker(engine.cfg.retrieval.reranker, device="cpu")
    if not shared.warm():
        json.dump({"error": "reranker unavailable; run L0 first", "reason": shared._load_error}, open(args.out, "w"), indent=2)
        sys.exit(1)
    score_fn = shared._score
    engine.search("warmup question about fees", 6)

    results, report = {}, {"release": release, "configs": {}}
    for name, top, budget in CONFIGS:
        if top is None:
            engine.reranker = None
        else:
            engine.reranker = Reranker(engine.cfg.retrieval.reranker, budget_s=budget,
                                       max_chars=engine.cfg.retrieval.rerank_max_chars, loader=lambda: score_fn)
            engine.cfg.retrieval.rerank_top = top
            engine.reranker.rerank("warmup", [("a", "fee"), ("b", "hostel")])
        latencies, statuses, rerank_ms = [], {}, []

        def search(q, k):
            t = time.monotonic()
            hits = engine.search(q, k)
            latencies.append((time.monotonic() - t) * 1000)
            if engine.reranker is not None:
                last = engine.reranker.last
                statuses[last["status"]] = statuses.get(last["status"], 0) + 1
                if last["status"] == "ok":
                    rerank_ms.append(last["ms"])
                engine.reranker.last = {"status": "not_called"}   # exact/policy paths skip reranking
            return hits

        rows = sc.run_engine(cases, search)
        results[name] = rows
        s = sc.summarize(rows)
        report["configs"][name] = {"rerank_top": top, "budget_s": budget, "passed": s["passed"], "scored": s["scored"],
                                   "ordering": s["ordering"], "by_language": s["by_language"],
                                   "search_ms_p50": pct(latencies, .5), "search_ms_p95": pct(latencies, .95),
                                   "rerank_ms_p50": pct(rerank_ms, .5), "rerank_ms_p95": pct(rerank_ms, .95),
                                   "rerank_status": statuses}
        # Let any abandoned job finish so the next configuration starts clean.
        if engine.reranker is not None and engine.reranker._inflight is not None:
            try:
                engine.reranker._inflight.result(timeout=120)
            except Exception:
                pass
        print(name, json.dumps(report["configs"][name]["ordering"]), flush=True)

    base = {r["id"]: r for r in results["off"]}
    for name in results:
        if name == "off":
            continue
        regress = [r["id"] for r in results[name] if base[r["id"]]["status"] == "pass" and r["status"] != "pass"]
        gained = [r["id"] for r in results[name] if base[r["id"]]["status"] != "pass" and r["status"] == "pass"]
        report["configs"][name]["regressions"] = regress
        report["configs"][name]["newly_passing"] = gained

    off = report["configs"]["off"]
    def ok(name):
        c = report["configs"][name]
        calls = sum(c["rerank_status"].values()) - c["rerank_status"].get("not_called", 0)
        slow = c["rerank_status"].get("timeout", 0) + c["rerank_status"].get("busy", 0)
        hindi, hindi_off = c["by_language"].get("hindi", {}).get("mrr"), off["by_language"].get("hindi", {}).get("mrr")
        return (not c["regressions"] and c["ordering"]["mrr"] > off["ordering"]["mrr"]
                and (hindi is None or hindi_off is None or hindi >= hindi_off)
                and (c["rerank_ms_p95"] or 0) <= 1500 and slow <= 0.05 * max(1, calls))
    passing = [n for n in ("top10", "top20", "top30") if ok(n)]
    report["recommended"] = max(passing, key=lambda n: report["configs"][n]["ordering"]["mrr"]) if passing else None
    report["passed"] = bool(passing)
    json.dump(report, open(args.out, "w"), indent=2, ensure_ascii=False)
    json.dump(results, open(out_dir / "rows.json", "w"), indent=1, ensure_ascii=False)
    (out_dir / "report.md").write_text(sc.compare(results), encoding="utf-8")
    print(json.dumps({"recommended": report["recommended"], "passed": report["passed"]}))


if __name__ == "__main__":
    main()
```

### My check before finishing

Per the AGENTS long-test rule I unpacked the scripts into `idea/FutureWork/report04_artifacts/`, syntax-checked them (`python -m py_compile`, `bash -n`), and ran `bash run_all_long_tests.sh --check`. The checks write `check.json`, not `summary.json`, so they cannot cause the resumable runner to skip your real run. The check confirmed the cache is incomplete (1 `.incomplete` blob, no weights), the active release and case file exist, and the new harness functions import. I did not run `L0` or `L1` or start them in the background. When you have the two `summary.json` files, give them to me and I will replace the pending rows above with measured values.
