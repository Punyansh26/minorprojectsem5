"""Turn two existing `evaluate_upgrade.py` result sets into a chapter 12 §6 report block.

This is the *analysis* half of the protocol: it never runs the model. It reads the baseline
and candidate `results.json` already produced by `evaluate_upgrade.py`, pairs the per-turn
`seconds` by case `id` (the §4.1 paired design), and computes the §4 statistics via `stats.py`:

  * paired-bootstrap CI on Δ p50 and the p95 ratio (latency gates),
  * McNemar on answer-status correctness (status gate),
  * Wilson on the cache false-hit rate (cache gate),

then emits the §6 markdown block through `report_block.py` — which refuses a verdict if
residency drifted or a side effect was written.

Because it only reads files, running it on the real 120-turn baseline/candidate data is a
valid [Measured-here] short check: the numbers are measured properties of those recorded runs,
not of a fresh model invocation.

Usage::

    python eval_report.py --baseline data/upgrade-20260930/baseline/results.json \\
                          --candidate data/upgrade-20260930/candidate/results.json \\
                          --cases evaluation/upgrade-20260930/cases.json \\
                          [--json summary.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import report_block as rb
import stats

# expected-family → the response_status values that count as correct for that family.
# answerable must be answered; insufficient must say insufficient; no_cutoff must abstain
# (insufficient or out_of_scope) and must never fabricate an answer.
_CORRECT_STATUS = {
    "answerable": {"answered"},
    "insufficient": {"insufficient"},
    "no_cutoff": {"insufficient", "out_of_scope"},
}
_ABSTAIN_FAMILIES = {"insufficient", "no_cutoff"}


def _load_rows(path: Path) -> dict[str, dict]:
    rows = json.loads(Path(path).read_text())
    return {row["id"]: row for row in rows}


def _expected_by_id(cases_path: Optional[Path]) -> dict[str, str]:
    if not cases_path:
        return {}
    return {case["id"]: case.get("expected") for case in json.loads(Path(cases_path).read_text())}


def _status_correct(row: dict, expected_family: Optional[str]) -> Optional[bool]:
    """True/False if the recorded status matches the expected family; None if unknown."""
    expected_family = expected_family or row.get("expected")
    if expected_family not in _CORRECT_STATUS:
        return None
    return row.get("response_status") in _CORRECT_STATUS[expected_family]


def _seconds(row: dict) -> Optional[float]:
    value = row.get("seconds")
    return float(value) if isinstance(value, (int, float)) else None


def _false_hit(row: dict) -> bool:
    """A cache false-hit is a 'hit' served against a status other than a grounded answer.

    Release-bound keys should make this impossible; we count any retrieval/draft cache 'hit'
    on a row whose status is not 'answered' as the observable proxy for a stale hit.
    """
    metrics = row.get("rag_metrics") or {}
    hit = metrics.get("retrieval_cache") == "hit" or metrics.get("draft_cache") == "hit"
    return bool(hit) and row.get("response_status") != "answered"


def analyze(baseline_path: Path, candidate_path: Path, cases_path: Optional[Path] = None,
            *, seed: int = 0, resamples: int = 10000) -> dict:
    """Compute the §4 statistics over the paired result sets; returns a structured summary."""
    baseline = _load_rows(baseline_path)
    candidate = _load_rows(candidate_path)
    expected = _expected_by_id(cases_path)

    shared = [cid for cid in baseline if cid in candidate]
    pairs: list[tuple[float, float]] = []
    base_correct: list[bool] = []
    cand_correct: list[bool] = []
    base_abstain_ok: list[bool] = []
    cand_abstain_ok: list[bool] = []
    base_false_hits = cand_false_hits = 0

    for cid in shared:
        b_row, c_row = baseline[cid], candidate[cid]
        b_sec, c_sec = _seconds(b_row), _seconds(c_row)
        if b_sec is not None and c_sec is not None:
            pairs.append((b_sec, c_sec))
        fam = expected.get(cid) or b_row.get("expected")
        bc, cc = _status_correct(b_row, fam), _status_correct(c_row, fam)
        if bc is not None and cc is not None:
            base_correct.append(bc)
            cand_correct.append(cc)
            if fam in _ABSTAIN_FAMILIES:
                base_abstain_ok.append(bc)
                cand_abstain_ok.append(cc)
        base_false_hits += _false_hit(b_row)
        cand_false_hits += _false_hit(c_row)

    summary: dict = {
        "n_shared": len(shared),
        "n_latency_pairs": len(pairs),
        "n_status_pairs": len(base_correct),
    }
    if pairs:
        summary["latency_p50_ci"] = stats.paired_bootstrap_ci(pairs, "median", resamples=resamples, seed=seed)
        summary["latency_p95_ratio"] = stats.p95_ratio_ci(pairs, resamples=resamples, seed=seed)
        summary["baseline_p50"] = stats.median([b for b, _ in pairs])
        summary["candidate_p50"] = stats.median([c for _, c in pairs])
        summary["baseline_p95"] = stats.p95([b for b, _ in pairs])
        summary["candidate_p95"] = stats.p95([c for _, c in pairs])
    if base_correct:
        summary["status_mcnemar"] = stats.mcnemar_from_labels(base_correct, cand_correct)
        summary["baseline_status_acc"] = sum(base_correct) / len(base_correct)
        summary["candidate_status_acc"] = sum(cand_correct) / len(cand_correct)
    if base_abstain_ok:
        summary["baseline_abstain_recall"] = sum(base_abstain_ok) / len(base_abstain_ok)
        summary["candidate_abstain_recall"] = sum(cand_abstain_ok) / len(cand_abstain_ok)
    summary["candidate_false_hit_wilson"] = stats.wilson_interval(cand_false_hits, max(1, len(shared)))
    summary["baseline_false_hits"] = base_false_hits
    summary["candidate_false_hits"] = cand_false_hits
    return summary


def build_block(summary: dict, *, experiment_id: str, baseline_ref: str,
                dataset: str, residency: Optional[rb.Residency] = None,
                side_effects_written: int = 0) -> rb.ReportBlock:
    """Translate an `analyze` summary into a renderable §6 ReportBlock with its gates."""
    metrics: list[rb.Metric] = []
    gates: list[rb.GateResult] = []

    if "latency_p50_ci" in summary:
        ci = summary["latency_p50_ci"]
        ratio = summary["latency_p95_ratio"]
        metrics.append(rb.Metric(
            "Perceived turn latency (s)",
            f"{summary['baseline_p50']:.2f} / {summary['baseline_p95']:.2f}",
            f"{summary['candidate_p50']:.2f} / {summary['candidate_p95']:.2f}",
            f"{ci['point']:.2f} [{ci['ci_low']:.2f}, {ci['ci_high']:.2f}]",
            f"ratio {ratio['point']:.3f} [≤{ratio['ratio_high']:.3f}]",
            "p95_ratio<=1.05",
        ))
        gates.append(rb.evaluate_latency_p50(ci))
        gates.append(rb.evaluate_latency_p95(ratio))

    if "status_mcnemar" in summary:
        mc = summary["status_mcnemar"]
        metrics.append(rb.Metric(
            "Answer-status accuracy (%)",
            f"{summary['baseline_status_acc'] * 100:.1f}",
            f"{summary['candidate_status_acc'] * 100:.1f}",
            f"McNemar p={mc['p_value']:.3g}", "—", "not worse",
        ))
        gates.append(rb.evaluate_status(mc))

    if "candidate_abstain_recall" in summary:
        passed = summary["candidate_abstain_recall"] >= summary["baseline_abstain_recall"]
        metrics.append(rb.Metric(
            "Abstention recall (%)",
            f"{summary['baseline_abstain_recall'] * 100:.1f}",
            f"{summary['candidate_abstain_recall'] * 100:.1f}",
            "", "—", ">=baseline",
        ))
        gates.append(rb.GateResult("G-abstain", passed,
                                   f"candidate abstention recall {summary['candidate_abstain_recall']:.3f} "
                                   f"vs baseline {summary['baseline_abstain_recall']:.3f}"))

    false_hit = summary["candidate_false_hit_wilson"]
    metrics.append(rb.Metric(
        "Cache false-hit rate (%)", f"{summary['baseline_false_hits']}",
        f"{false_hit['successes']}", f"Wilson 95% up {false_hit['high']:.4f}", "—", "==0",
    ))
    gates.append(rb.evaluate_cache_false_hit(false_hit))

    return rb.ReportBlock(
        experiment_id=experiment_id,
        chapter="ch12 analysis",
        change_under_test="candidate vs baseline (recorded runs)",
        baseline_ref=baseline_ref,
        dataset=dataset,
        normalisation="status-family mapping; seconds paired by case id",
        residency=residency or rb.Residency(),
        side_effects_written=side_effects_written,
        metrics=metrics,
        gates=gates,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=None)
    parser.add_argument("--experiment-id", default="analysis-recorded")
    parser.add_argument("--baseline-ref", default="recorded baseline run")
    parser.add_argument("--dataset", default="120-turn recorded set")
    parser.add_argument("--resamples", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--json", type=Path, default=None, help="also write the raw summary json")
    args = parser.parse_args()

    summary = analyze(args.baseline, args.candidate, args.cases,
                      seed=args.seed, resamples=args.resamples)
    block = build_block(summary, experiment_id=args.experiment_id,
                        baseline_ref=args.baseline_ref,
                        dataset=f"{args.dataset} (n={summary['n_shared']})")
    print(block.render())
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2, default=lambda o: o))
        print(f"\n[wrote {args.json}]")


if __name__ == "__main__":
    main()
