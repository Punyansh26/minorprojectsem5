#!/usr/bin/env python3
"""L3 — tool-agent task runner with pass^k reliability (chapter 12 §2.5).

τ²-bench / VoiceAgentBench-style [R1206/R1204]: runs scripted caller goals against the Demo2
agent k independent times each, scoring answer-status correctness as the task-success proxy and
pass^k (solved in ALL k trials — reliability, not luck once). Side effects are hard-blocked:
nodes.create_ticket / create_reminder are patched to raise, and any write fails the run
(§2.5 no-side-effect safety, §7.7). Caches are isolated per case (release-bound).

Long because: loads the 9B agent and makes k×N model calls on the GPU. Run with Ollama resident
and nothing else on the GPU. The user runs it; the agent runs --check.

Task set JSON (user-provided or reuse evaluation/upgrade-20260930/cases.json):
  [{"id": "...", "question": "...", "expected": "answerable|insufficient|no_cutoff"}]
"""
import argparse
import json
import os
import sys
from pathlib import Path

DEMO2 = Path(__file__).resolve().parents[3] / "code" / "demo2"
sys.path.insert(0, str(DEMO2))

import stats  # noqa: E402

_CORRECT = {"answerable": {"answered"}, "insufficient": {"insufficient"},
            "no_cutoff": {"insufficient", "out_of_scope"}}


def run(cases_path: Path, out: Path, k: int):
    scratch = out.parent / "caches"
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ.update(LLM_PROVIDER="ollama", JEV_ROUTING_MODE="off",
                      HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                      CHECKPOINT_DB_PATH=str(scratch / "unused.sqlite"),
                      RAG_CACHE_DB_PATH=str(scratch / "cache.sqlite"),
                      TICKETS_DB_PATH=str(scratch / "blocked.sqlite"))
    import settings as cfg  # noqa: E402
    cfg.configure_agent()
    sys.path.insert(0, str(cfg.AGENT_ROOT))
    from unittest.mock import patch
    from dataclasses import replace
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from assistant import nodes
    from assistant.graph import build_graph

    cases = json.loads(cases_path.read_text())
    rows = []
    side_effects = 0
    with patch.object(nodes, "create_ticket", side_effect=AssertionError("blocked")), \
            patch.object(nodes, "create_reminder", side_effect=AssertionError("blocked")):
        for case in cases:
            trials = []
            for trial in range(k):
                cache = scratch / f"{case['id']}-{trial}.sqlite"
                with patch.object(nodes, "settings", replace(nodes.settings, RAG_CACHE_DB_PATH=str(cache))):
                    try:
                        result = build_graph(MemorySaver()).invoke(
                            {"messages": [HumanMessage(content=case["question"])],
                             "student_id": "l3-eval", "student_category": "general"},
                            {"configurable": {"thread_id": f"{case['id']}-{trial}", "llm_provider": "ollama"}})
                        status = result.get("response_status")
                    except AssertionError:
                        side_effects += 1
                        status = "SIDE_EFFECT"
                    except Exception as error:
                        status = f"error:{type(error).__name__}"
                trials.append(status in _CORRECT.get(case.get("expected", ""), set()))
            rows.append({"id": case["id"], "trials": trials,
                         "pass1": trials[0], "passk": all(trials)})
    n = len(rows)
    summary = {
        "test": "L3_tool_tasks", "k": k, "n": n, "side_effects_written": side_effects,
        "pass1_rate": sum(r["pass1"] for r in rows) / n if n else None,
        "passk_rate": sum(r["passk"] for r in rows) / n if n else None,
        "pass1_wilson": stats.wilson_interval(sum(r["pass1"] for r in rows), max(1, n)),
        "gate_no_side_effects": side_effects == 0,
        "rows": rows,
    }
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({x: y for x, y in summary.items() if x != "rows"}, indent=2, ensure_ascii=False))
    # release the model when done
    os.system("ollama stop qwen3.5:9b >/dev/null 2>&1 || true")


def check(out: Path):
    assert "answered" in _CORRECT["answerable"]
    assert "out_of_scope" in _CORRECT["no_cutoff"]
    assert stats.wilson_interval(3, 3)["point"] == 1.0
    out.write_text(json.dumps({"test": "L3_tool_tasks", "check": "ok"}, indent=2))
    print("L3 --check ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cases", type=Path, help="task set (e.g. evaluation/upgrade-20260930/cases.json)")
    ap.add_argument("--k", type=int, default=3, help="independent trials per task for pass^k")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.check:
        return check(args.out)
    if not args.cases:
        ap.error("--cases is required for a full run")
    run(args.cases, args.out, args.k)


if __name__ == "__main__":
    main()
