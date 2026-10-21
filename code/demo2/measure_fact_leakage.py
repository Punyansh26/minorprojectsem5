"""Fact-leakage measurement harness for the acknowledgement talker (FutureWork 11 §9).

Chapter 11 §9 defines the one metric that gates any talker/S2S pilot:

    **Fact-leakage rate** = fraction of talker utterances that contain a number or entity
    from the knowledge base. Pass criterion: **0%** — any single leak fails.

This script computes that metric deterministically and offline (no model, no network, no
GPU) over two sources:

  1. The built-in canned-phrase talker (``fillers.FILLERS``) — the default, and the only
     source that must *always* score 0% because those phrases are what Demo2 actually speaks.
  2. An optional transcript log (``--transcript FILE``): one talker utterance per line, e.g.
     the audio-logged talker track from the 120-turn benchmark (chapter §9 "audio-logged").
     Use this to score a real or recorded talker before trusting it in a pilot.

Output:
  * A human-readable summary to stdout.
  * A machine-readable ``summary.json`` (``--out DIR``), so a report can regenerate its
    tables from the artifact (AGENTS.md benchmark discipline). By default the output goes to
    a scratch directory under the system temp dir, **never** into Demo2's own ``data/``
    directories (AGENTS.md long-running-tests rule).

Exit status is non-zero if any inspected source fails the 0% criterion, so it can gate CI.

Usage (in the `minor` env):
    python measure_fact_leakage.py                      # score built-in fillers only
    python measure_fact_leakage.py --transcript talker_track.txt
    python measure_fact_leakage.py --out /tmp/fw11_leakage
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import fillers
import filler_guard


def _score_fillers() -> dict:
    """Score every phrase the built-in canned-phrase talker can speak, per language."""
    per_language = {}
    all_phrases: list[str] = []
    for language, phrases in fillers.FILLERS.items():
        per_language[language] = filler_guard.leakage_rate(phrases)
        all_phrases.extend(phrases)
    overall = filler_guard.leakage_rate(all_phrases)
    return {"source": "fillers.FILLERS", "overall": overall, "per_language": per_language}


def _score_transcript(path: Path) -> dict:
    """Score an external talker transcript: one utterance per non-empty line."""
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    utterances = [line for line in lines if line]
    result = filler_guard.leakage_rate(utterances)
    return {"source": str(path), "overall": result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--transcript", type=Path, default=None,
                        help="Optional talker transcript: one utterance per line.")
    parser.add_argument("--out", type=Path, default=None,
                        help="Directory for summary.json (default: a scratch temp dir).")
    args = parser.parse_args(argv)

    report = {"metric": "fact_leakage_rate", "pass_criterion": "rate == 0.0 (any leak fails)",
              "sources": []}

    fillers_result = _score_fillers()
    report["sources"].append(fillers_result)

    if args.transcript is not None:
        if not args.transcript.is_file():
            parser.error(f"Transcript not found: {args.transcript}")
        report["sources"].append(_score_transcript(args.transcript))

    report["pass"] = all(src["overall"]["pass"] for src in report["sources"])

    out_dir = args.out or Path(tempfile.mkdtemp(prefix="fw11_leakage_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Human-readable read-out.
    print(f"Fact-leakage rate (FutureWork 11 §9) — pass criterion: 0% (any leak fails)")
    for src in report["sources"]:
        overall = src["overall"]
        status = "PASS" if overall["pass"] else "FAIL"
        print(f"  [{status}] {src['source']}: "
              f"{overall['leaked']}/{overall['total']} leaked, rate={overall['rate']:.4f}")
        for offender in overall["offenders"]:
            print(f"      leak @ index {offender['index']}: {offender['phrase']!r} "
                  f"-> tokens {offender['tokens']}")
    print(f"Overall: {'PASS' if report['pass'] else 'FAIL'}")
    print(f"Wrote {summary_path}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
