"""Run a resumable public workload against an explicitly selected source/KB snapshot."""
import argparse
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


def main():
    """Keep live measurements reproducible without reading or writing user conversations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-root", type=Path, required=True)
    parser.add_argument("--kb-state", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    os.environ.update(KB_STATE_DIR=str(args.kb_state.resolve()), LLM_PROVIDER="ollama",
                      JEV_ROUTING_MODE="off", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                      CHECKPOINT_DB_PATH=str(args.output.parent / "unused.sqlite"),
                      RAG_CACHE_DB_PATH=str(args.output.parent / "cache.sqlite"),
                      TICKETS_DB_PATH=str(args.output.parent / "blocked.sqlite"))
    sys.path.insert(0, str(args.agent_root.resolve()))
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from assistant import nodes
    from assistant.graph import build_graph
    cases = json.loads(args.cases.read_text())
    results = json.loads(args.output.read_text()) if args.resume and args.output.exists() else []
    done = {r["id"] for r in results}
    with patch.object(nodes, "create_ticket", side_effect=AssertionError("Actions blocked")), \
            patch.object(nodes, "create_reminder", side_effect=AssertionError("Actions blocked")):
        # Recorded separately; cold initialization is not hidden in the warm distribution.
        if not results:
            started = time.monotonic()
            warm = build_graph(MemorySaver()).invoke({"messages": [HumanMessage(content=
                "How is admission to B.Tech at IIIT Naya Raipur decided in 2026?")]},
                {"configurable": {"thread_id": "warmup", "llm_provider": "ollama"}})
            (args.output.parent / (args.output.stem + "-warmup.json")).write_text(json.dumps({
                "seconds": time.monotonic() - started, "status": warm.get("response_status"),
                "metrics": warm.get("rag_metrics")}, indent=2))
        for index, case in enumerate(cases):
            if case["id"] in done:
                continue
            with patch.object(nodes, "settings", replace(nodes.settings,
                    RAG_CACHE_DB_PATH=str(args.output.parent / "caches" / (case["id"] + ".sqlite")))):
                started = time.monotonic()
                try:
                    result = build_graph(MemorySaver()).invoke({"messages": [HumanMessage(content=case["question"])],
                        "student_id": "public-evaluation", "student_category": "general"},
                        {"configurable": {"thread_id": case["id"], "llm_provider": "ollama"}})
                    row = {"id": case["id"], "language_expected": case["language"],
                           "question": case["question"], "expected": case["expected"],
                           **{key: result.get(key) for key in ("answer_text", "response_status", "sources",
                              "language", "search_query", "rag_metrics", "llm_error")}}
                except Exception as error:
                    row = {"id": case["id"], "language_expected": case["language"],
                           "response_status": "error", "error_code": type(error).__name__}
                row["seconds"] = round(time.monotonic() - started, 4)
                results.append(row)
                temporary = args.output.with_suffix(".pending")
                temporary.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
                temporary.replace(args.output)
                print(f"{index + 1}/{len(cases)} {case['id']} {row['response_status']} {row['seconds']}s", flush=True)


if __name__ == "__main__":
    main()
