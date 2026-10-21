#!/usr/bin/env python3
"""L2 — claim-level unsupported-claim audit (chapter 12 §2.3, §4.4).

Implements the RAGChecker *method* (claim extraction + entailment against cited sources)
[R1200] with a LOCAL checker [R26/R1222 LettuceDetect / R25 MiniCheck], never a cloud default.
For each clean, grounded case it decomposes the answer into atomic claims, marks each as
entailed/not by the cited source quotes, and reports the unsupported-claim rate with a Wilson
95 % interval. Gate G-claim: 95 % upper ≤ 1 %, which needs ≥300 clean cases (rule of three).
Also exports a human-review spreadsheet (CSV) for the parallel ≥300-case manual audit.

Long because: needs a local checker model (download) + GPU and ≥300 clean cases. The user runs
it; the agent runs --check.

Clean-case set JSON (user-provided): the recorded answers + their cited source quotes:
  [{"id": "...", "answer": "...", "sources": [{"quote": "..."}]}]
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

DEMO2 = Path(__file__).resolve().parents[3] / "code" / "demo2"
sys.path.insert(0, str(DEMO2))

import stats  # noqa: E402
import report_block as rb  # noqa: E402


def _atomic_claims(answer: str):
    """Naive sentence/clause split; the checker decides entailment, not this splitter."""
    parts = re.split(r"(?<=[।.?!])\s+", answer.strip())
    return [p.strip() for p in parts if len(p.strip()) > 3]


def _load_checker():
    """LettuceDetect first (span-level, small), then MiniCheck; raise if neither is present."""
    try:
        from lettucedetect.models.inference import HallucinationDetector  # type: ignore
        detector = HallucinationDetector(method="transformer",
                                         model_path="KRLabsOrg/lettucedect-base-modernbert-en-v1")
        def entailed(context, claim):
            spans = detector.predict(context=[context], question="", answer=claim,
                                     output_format="spans")
            return len(spans) == 0  # no hallucinated span ⇒ supported
        return entailed, "lettucedetect"
    except Exception:
        from minicheck.minicheck import MiniCheck  # type: ignore
        scorer = MiniCheck(model_name="flan-t5-large")
        def entailed(context, claim):
            label, _, _, _ = scorer.score(docs=[context], claims=[claim])
            return bool(label[0])
        return entailed, "minicheck"


def run(cases_path: Path, out: Path):
    entailed, checker = _load_checker()
    cases = json.loads(cases_path.read_text())
    unsupported = 0
    total_claims = 0
    review_rows = []
    for case in cases:
        context = "\n".join(s.get("quote", "") for s in case.get("sources", []))
        for claim in _atomic_claims(case.get("answer", "")):
            total_claims += 1
            ok = entailed(context, claim)
            if not ok:
                unsupported += 1
            review_rows.append({"id": case["id"], "claim": claim,
                                "supported": ok, "context": context[:500]})
    wilson = stats.wilson_interval(unsupported, max(1, total_claims))
    gate = rb.evaluate_claim(wilson)
    summary = {"test": "L2_claim_audit", "checker": checker,
               "n_cases": len(cases), "n_claims": total_claims,
               "unsupported": unsupported, "unsupported_wilson": wilson,
               "gate_G_claim_pass": gate.passed, "gate_detail": gate.detail}
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    with (out.parent / "human_review.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "claim", "supported", "context"])
        writer.writeheader()
        writer.writerows(review_rows)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def check(out: Path):
    assert _atomic_claims("Fee is 1000. It is non-refundable.") == ["Fee is 1000.", "It is non-refundable."]
    # a <1 % claim needs >=300 clean cases: 0/50 must NOT pass, 0/2000 must pass
    assert rb.evaluate_claim(stats.wilson_interval(0, 50)).passed is False
    assert rb.evaluate_claim(stats.wilson_interval(0, 2000)).passed is True
    out.write_text(json.dumps({"test": "L2_claim_audit", "check": "ok"}, indent=2))
    print("L2 --check ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cases", type=Path, help="clean grounded QA set (>=300 for the <1% gate)")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.check:
        return check(args.out)
    if not args.cases:
        ap.error("--cases is required for a full run")
    run(args.cases, args.out)


if __name__ == "__main__":
    main()
