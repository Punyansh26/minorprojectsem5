#!/usr/bin/env python3
"""Run the spot-check questions against any retrieval engine and compare engines side by side.

An engine is anything with ``search(question, k) -> list[hit]`` where a hit has ``text``,
``source_file``, ``page_number`` (``-1`` for pageless sources) and ``block_id``.  Scoring is
deliberately mechanical so results are reproducible:

``answerable``     pass = every ``required_terms`` string (and one of ``required_any``) appears in the
                   retrieved text AND, when the case names a source, a hit comes from that file/page
``no_result``      pass = the engine returned nothing (exact-lookup misses must not be guessed)
``answer_review``  no retrieval pass/fail – listed for a human to read the generated answer
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def norm(s: str) -> str:
    return " ".join((s or "").casefold().split())


def source_matches(hit: Any, expected: dict) -> bool:
    name = norm(str(getattr(hit, "source_file", "")))
    want = norm(expected["file"])
    if want not in name and name not in want and Path(name).stem not in want and want not in Path(name).stem:
        return False
    page = expected.get("page")
    if page in (None, -1):
        return True
    return int(getattr(hit, "page_number", -1)) == int(page)


def score_case(case: dict, hits: list) -> dict[str, Any]:
    """Score one case against already-retrieved hits (pure function; unit tested)."""
    expect = case["expect"]
    text = norm("\n".join(h.text for h in hits))
    row = {"id": case["id"], "topic": case["topic"], "language": case["language"], "origin": case["origin"],
           "expect": expect, "hits": len(hits)}
    if expect == "answer_review":
        row.update(status="review", terms_ok=None, source_ok=None)
        return row
    if expect == "no_result":
        row.update(status="pass" if not hits else "fail", terms_ok=None, source_ok=None)
        return row
    terms_ok = all(norm(t) in text for t in case.get("required_terms", []))
    any_terms = case.get("required_any")
    if any_terms:
        terms_ok = terms_ok and any(norm(t) in text for t in any_terms)
    sources = case.get("expected_sources", [])
    source_ok = True if not sources else any(source_matches(h, s) for h in hits for s in sources)
    row.update(terms_ok=terms_ok, source_ok=source_ok, status="pass" if terms_ok and source_ok else "fail")
    if row["status"] == "fail":
        row["got"] = [{"file": getattr(h, "source_file", ""), "page": getattr(h, "page_number", None)} for h in hits[:3]]
    return row


def run_engine(cases: list[dict], search: Callable[[str, int], list], k: int = 6) -> list[dict]:
    rows = []
    for case in cases:
        try:
            hits = search(case["question"], k)
        except Exception as error:  # an engine crash is a failed case, never a skipped one
            rows.append({"id": case["id"], "topic": case["topic"], "language": case["language"],
                         "origin": case["origin"], "expect": case["expect"], "status": "error",
                         "error": f"{type(error).__name__}: {error}"})
            continue
        rows.append(score_case(case, hits))
    return rows


def summarize(rows: list[dict]) -> dict[str, Any]:
    scored = [r for r in rows if r["status"] in {"pass", "fail", "error"}]
    by_topic: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in scored:
        by_topic[r["topic"]][1] += 1
        by_topic[r["topic"]][0] += r["status"] == "pass"
    passed = sum(r["status"] == "pass" for r in scored)
    return {"scored": len(scored), "passed": passed, "pass_rate": round(passed / max(1, len(scored)), 4),
            "review_cases": sum(r["status"] == "review" for r in rows),
            "by_topic": {k: {"passed": v[0], "total": v[1]} for k, v in sorted(by_topic.items())}}


def compare(results: dict[str, list[dict]]) -> str:
    """Markdown side-by-side report; regressions are cases the first engine passed and another failed."""
    names = list(results)
    lines = ["# Spot-check report", "", "| engine | scored | passed | pass rate | needs answer review |", "| --- | ---: | ---: | ---: | ---: |"]
    summaries = {n: summarize(r) for n, r in results.items()}
    for n in names:
        s = summaries[n]
        lines.append(f"| {n} | {s['scored']} | {s['passed']} | {s['pass_rate']:.1%} | {s['review_cases']} |")
    topics = sorted({t for s in summaries.values() for t in s["by_topic"]})
    lines += ["", "## By topic (passed/total)", "", "| topic | " + " | ".join(names) + " |", "| --- | " + " | ".join("---:" for _ in names) + " |"]
    for t in topics:
        lines.append(f"| {t} | " + " | ".join(
            f"{summaries[n]['by_topic'].get(t, {}).get('passed', 0)}/{summaries[n]['by_topic'].get(t, {}).get('total', 0)}" for n in names) + " |")
    if len(names) > 1:
        base = {r["id"]: r for r in results[names[0]]}
        for other in names[1:]:
            regress = [r["id"] for r in results[other] if base.get(r["id"], {}).get("status") == "pass" and r["status"] != "pass"]
            gained = [r["id"] for r in results[other] if base.get(r["id"], {}).get("status") != "pass" and r["status"] == "pass"]
            lines += ["", f"## {other} vs {names[0]}", f"- regressions ({len(regress)}): {', '.join(regress) or 'none'}",
                      f"- newly passing ({len(gained)}): {', '.join(gained[:40]) or 'none'}"]
    for n in names:
        fails = [r for r in results[n] if r["status"] in {"fail", "error"}]
        if fails:
            lines += ["", f"## Failing cases – {n}"]
            for r in fails[:60]:
                detail = r.get("error") or f"terms_ok={r.get('terms_ok')} source_ok={r.get('source_ok')} got={r.get('got')}"
                lines.append(f"- `{r['id']}` ({r['topic']}, {r['language']}): {detail}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- engines
class _Hit:
    def __init__(self, text, source_file, page_number, block_id=""):
        self.text, self.source_file, self.page_number, self.block_id = text, source_file, page_number, block_id


def legacy_engine() -> Callable[[str, int], list]:
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    legacy = ROOT.parent / "Institute-voice-agent" / "institute-assistant"
    sys.path.insert(0, str(legacy))
    os.environ["KB_STATE_DIR"] = str(legacy / "kb_state")
    from assistant.config import settings
    from assistant.kb.common import active_release
    from assistant.kb.search import SearchEngine
    root, manifest = active_release(Path(settings.KB_STATE_DIR))
    engine = SearchEngine(root, manifest)
    return lambda q, k: engine.search(q, k)


def release_engine(release: Path) -> Callable[[str, int], list]:
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    from kbb.release import ReleaseSearch
    engine = ReleaseSearch(release)
    return lambda q, k: engine.search(q, k)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engine", action="append", required=True,
                        help="legacy | release:<dir>   (repeat to compare; first is the reference)")
    parser.add_argument("--cases", type=Path, default=ROOT / "eval" / "spotcheck.json")
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "reports")
    parser.add_argument("-k", type=int, default=6)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    results = {}
    for spec in args.engine:
        if spec == "legacy":
            search = legacy_engine()
        elif spec.startswith("release:"):
            search = release_engine(Path(spec.split(":", 1)[1]))
        else:
            parser.error(f"unknown engine {spec}")
        results[spec] = run_engine(cases, search, args.k)
        print(spec, summarize(results[spec])["pass_rate"], flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    report = compare(results)
    (args.out / "spotcheck_report.md").write_text(report, encoding="utf-8")
    (args.out / "spotcheck_rows.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(report.split("## By topic")[0])
    print(f"report: {args.out / 'spotcheck_report.md'}")


if __name__ == "__main__":
    main()
