#!/usr/bin/env python3
"""L0 - Stage 0: build the verified-triple store from Demo2's own data (CPU, no model).

Mines code/demo2/data/conversations.sqlite (real turns) plus the public evaluation
pool evaluation/upgrade-20260930/cases.json for VERIFIED, privacy-filtered, de-duplicated
triples (chapter 09 section 3), then splits them into family-disjoint train/cal/test
(section 3.5) and reports the pipeline-health numbers the chapter asks for:
accepted-triple count, family disjointness, and the fraction of candidate turns rejected
by the verified-only gate.

This is the only chapter-09 long test that is Demo2-local and needs no GPU/download; it
is "long" only because it depends on whatever conversation volume has accumulated and is
the gate for every later student. Scratch stays out of code/demo2/data. Resumable: writes
summary.json and exits 0 on pass (>=1 accepted triple and a disjoint split).
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Repo root: idea/FutureWork/report09_artifacts -> up 3 -> Minor
ROOT = HERE.parents[2]
DEMO2 = ROOT / "code/demo2"
sys.path.insert(0, str(DEMO2))


def _cases_as_turns(cases_path: Path):
    """Turn the public cases.json into candidate turns (no PII, institute questions).

    Only entries that already carry a grounded answer + quote are usable; the file is a
    QA spec, so most entries are treated as questions whose evidence is unknown and will
    simply fail the verified gate. Shaped defensively against schema drift.
    """
    if not cases_path.is_file():
        return []
    try:
        data = json.loads(cases_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    cases = data if isinstance(data, list) else data.get("cases", [])
    turns = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        answer = case.get("answer") or case.get("expected_answer") or ""
        quote = case.get("quote") or ""
        evidence = case.get("evidence") or case.get("source_text") or quote
        if not (answer and quote and evidence):
            continue
        turns.append({
            "question": case.get("question", ""),
            "answer_text": answer,
            "response_status": "answered",
            "sources": [{"category": case.get("category", "general"), "quote": quote}],
            "retrieved_chunks": [{"text": evidence}],
            "language": case.get("language", "english"),
            "intent": "knowledge",
            "detected_category": case.get("category", "general"),
        })
    return turns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "L0_triple_store" / "summary.json")
    parser.add_argument("--check", action="store_true", help="fast validation only")
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    from distillation import mine_verified_triples, split_by_family, is_verified_turn

    if args.check:
        # Trivial, fast: run the pipeline on one synthetic verified turn only.
        turn = {
            "question": "who is the dean of academics", "answer_text": "Prof Srinivasa K G.",
            "response_status": "answered",
            "sources": [{"category": "faculty", "quote": "Dean(Academics"}],
            "retrieved_chunks": [{"text": "... Professor and Dean(Academics | DSAI ..."}],
            "language": "english", "intent": "knowledge", "detected_category": "faculty",
        }
        triples = mine_verified_triples(None, extra_turns=[turn])
        args.out.write_text(json.dumps({"test": "L0", "mode": "check",
            "accepted": len(triples), "pass": len(triples) == 1}, indent=2))
        print(json.dumps({"mode": "check", "accepted": len(triples)}))
        return 0 if triples else 1

    conv_db = DEMO2 / "data/conversations.sqlite"
    cases = DEMO2 / "evaluation/upgrade-20260930/cases.json"
    extra = _cases_as_turns(cases)

    triples = mine_verified_triples(conv_db if conv_db.is_file() else None, extra_turns=extra)
    split = split_by_family(triples) if triples else None

    summary = {
        "test": "L0",
        "conversations_db": str(conv_db),
        "conversations_present": conv_db.is_file(),
        "extra_candidate_turns": len(extra),
        "accepted_triples": len(triples),
        "languages": sorted({t.language for t in triples}),
        "categories": sorted({t.category for t in triples}),
        "split": split.summary() if split else None,
        "pass": bool(triples) and (split.is_disjoint() if split else False),
    }
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({k: summary[k] for k in ("accepted_triples", "split", "pass")},
                     ensure_ascii=False))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
