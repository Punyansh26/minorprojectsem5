"""Measure user-visible latency with isolated caches and balanced execution order."""
from collections import Counter
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch
from uuid import uuid4
import json
import statistics

from .common import digest, json_hash, live_case_overlaps, read_json, write_json


def diagnostics(pairs):
    """Separate real call elimination from generator noise and cache effects."""
    modes = {mode: [t for p in pairs for t in p["modes"][mode]["turns"]] for mode in ("off", "enabled")}
    candidate = modes["enabled"]
    total = len(candidate)
    def counts(key):
        return dict(Counter(t["metrics"].get(key) or "none" for t in candidate))
    calls = {mode: sum("routing_model" in t["metrics"].get("stage_ms", {}) for t in turns)
             for mode, turns in modes.items()}
    saved = [(a["seconds"] - b["seconds"]) for a, b in zip(modes["off"], candidate, strict=True)]
    return {"routing_llm_calls": calls, "routing_calls_saved": calls["off"] - calls["enabled"],
            "median_paired_seconds_saved": statistics.median(saved),
            "classifier_coverage": sum(t["metrics"].get("router_path") == "open_jev" for t in candidate) / total,
            "deterministic_followup_coverage": sum(t["metrics"].get("router_path") == "deterministic_followup" for t in candidate) / total,
            "fallback_reasons": counts("router_fallback"), "query_strategies": counts("query_strategy"),
            "cache_outcomes": {mode: {kind: dict(Counter(t["metrics"].get(kind, "bypass") for t in turns))
                                      for kind in ("retrieval_cache", "draft_cache")} for mode, turns in modes.items()},
            "by_language": {language: {"turns": len(group),
                "local_routes": sum(t["metrics"].get("router_path") in {"open_jev", "deterministic_followup"} for t in group)}
                for language in sorted({t.get("language", "unknown") for t in candidate})
                if (group := [t for t in candidate if t.get("language", "unknown") == language])},
            "stage_total_seconds": {mode: {stage: round(sum(t["metrics"].get("stage_ms", {}).get(stage, 0)
                    for t in turns) / 1000, 3) for stage in ("routing", "classifier", "generation_model", "review_model")}
                    for mode, turns in modes.items()}}


def environment(configured):
    """Record only model/KB identity and residency, never prompts or provider bodies."""
    import httpx
    from assistant.kb.common import active_release
    from assistant.llm import model_identity
    release = active_release(Path(configured.KB_STATE_DIR))
    kb = {"root": str(release[0]), "manifest": release[1]} if release else None
    residency = None
    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            response = client.get(configured.OLLAMA_BASE_URL.rstrip("/") + "/api/ps")
            response.raise_for_status()
            model = next(m for m in response.json()["models"] if m.get("name") == configured.OLLAMA_MODEL)
            residency = {key: model.get(key) for key in ("digest", "size", "size_vram", "context_length")}
    except (httpx.HTTPError, ValueError, KeyError, StopIteration):
        pass
    return {"provider": model_identity(provider="ollama"), "kb_release": json_hash(kb), "residency": residency}


def cache_path(temporary, trial, name, mode):
    """Only a case's own repeat phase shares its cache."""
    return str(Path(temporary) / f"{trial}-{name}-{mode}.sqlite")


def mode_order(trial, case_index, repeat):
    """Reverse order across both cache phases and successive complete trials."""
    return ("off", "enabled") if (trial + case_index + repeat) % 2 == 0 else ("enabled", "off")


def benchmark(root, quick=False, trials=3):
    """Save every trial and require stable, fully paired measurements for promotion."""
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from assistant import nodes
    from assistant.graph import build_graph
    from assistant.jev import runtime
    from .evaluation import benchmark_passed, summarize_pairs
    from evaluate_helpdesk import CASES, context_checks
    if isinstance(trials, bool) or not isinstance(trials, int) or not 1 <= trials <= 10:
        raise ValueError("Use between one and ten benchmark trials")
    root = Path(root)
    manifest = runtime.checked_manifest(str(root), runtime.artifact_signature(root))
    selected = {"english_admissions", "hindi_admissions", "hinglish_admissions", "off_topic", "prompt_injection",
                "ambiguous", "unknown", "verified_cutoff", "followup", "no_smtp_promise", "loan_conditions", "cache_exact"}
    exposed = read_json(root / "data.json")
    if manifest.get("additional_calibration_file"):
        exposed += read_json(root / manifest["additional_calibration_file"])
    overlaps = live_case_overlaps(exposed)
    cases = [case for case in CASES if (not quick or case[0] in selected) and case[0] not in overlaps]
    if not cases:
        raise ValueError("No unexposed benchmark cases")
    run = root / "benchmarks" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    run.mkdir(parents=True)
    # Retain the original pre-v2 benchmark before replacing convenience pointers.
    if (root / "benchmark.json").exists():
        import shutil
        previous = run / "previous"
        previous.mkdir()
        for name in ("benchmark.json", "benchmark_pairs.json"):
            if (root / name).exists():
                shutil.copy2(root / name, previous / name)
    pairs, trial_reports = [], []
    write_json(run / "plan.json", {"artifact_id": json_hash(manifest), "trials": trials, "quick": quick,
               "cases": [c[0] for c in cases], "order": "alternate by trial, case and cache phase"})
    try:
        with TemporaryDirectory(prefix="jev-benchmark-") as temporary, ExitStack() as stack:
            stack.enter_context(patch.object(nodes, "create_ticket", side_effect=AssertionError("Action writes blocked")))
            stack.enter_context(patch.object(nodes, "create_reminder", side_effect=AssertionError("Action writes blocked")))
            stack.enter_context(patch.object(runtime, "activation_valid", return_value=True))
            baseline_settings = nodes.settings
            prediction, failure = runtime.predict(str(root), runtime.artifact_signature(root), 2, 60,
                    "What are the BTech admission requirements at IIIT Naya Raipur?")
            if prediction is None:
                raise ValueError("Classifier warmup failed: " + str(failure))
            warm = replace(baseline_settings, JEV_ROUTING_MODE="off", RAG_CACHE_DB_PATH=str(Path(temporary) / "warm.sqlite"))
            with patch.object(nodes, "settings", warm):
                build_graph(MemorySaver()).invoke({"messages": [HumanMessage(content=
                    "How is admission to B.Tech at IIIT Naya Raipur decided in 2026?")]},
                    {"configurable": {"thread_id": "warm", "llm_provider": "ollama"}})
            initial = environment(baseline_settings)
            if initial["residency"] is None:
                raise ValueError("Ollama residency unavailable after warmup; cannot certify a controlled benchmark")
            write_json(run / "environment.json", initial)
            for trial in range(trials):
                trial_pairs = []
                for ci, (name, messages, expected) in enumerate(cases):
                    for repeat in range(2):
                        pair = {"trial": trial + 1, "case": name, "cache": "miss" if repeat == 0 else "repeat",
                                "order": mode_order(trial, ci, repeat), "modes": {}}
                        for mode in pair["order"]:
                            configured = replace(baseline_settings, JEV_ROUTING_MODE=mode, JEV_ARTIFACT_DIR=str(root),
                                RAG_CACHE_DB_PATH=cache_path(temporary, trial, name, mode))
                            with patch.object(nodes, "settings", configured):
                                graph, session, turns = build_graph(MemorySaver()), str(uuid4()), []
                                for message in messages:
                                    before = environment(configured)
                                    if before != initial:
                                        raise ValueError("Model, KB release or residency changed during benchmark")
                                    started = perf_counter()
                                    output = graph.invoke({"messages": [HumanMessage(content=message)], "student_category": "general"},
                                        {"configurable": {"thread_id": session, "llm_provider": "ollama"}})
                                    seconds = perf_counter() - started
                                    if environment(configured) != initial:
                                        raise ValueError("Model, KB release or residency changed during benchmark")
                                    turns.append({"seconds": seconds, "status": output.get("response_status"),
                                        "language": output.get("language"), "answer": output.get("answer_text"),
                                        "sources": output.get("sources"), "query": output.get("search_query"),
                                        "metrics": output.get("rag_metrics", {}),
                                        "actions": bool(output.get("ticket_id") or output.get("reminder_id"))})
                            pair["modes"][mode] = {"turns": turns, "seconds": sum(t["seconds"] for t in turns),
                                "behavior_passed": turns[-1]["status"] in expected and context_checks(name, turns)
                                                   and not any(t["actions"] for t in turns)}
                        trial_pairs.append(pair)
                        pairs.append(pair)
                        write_json(run / "benchmark_pairs.json", pairs)
                        print(json.dumps({"trial": trial + 1, "benchmark_case": name, "cache": pair["cache"],
                            "seconds": {m: round(v["seconds"], 3) for m, v in pair["modes"].items()}}), flush=True)
                trial_report = {**summarize_pairs(trial_pairs), **diagnostics(trial_pairs)}
                trial_reports.append(trial_report)
                write_json(run / f"trial-{trial+1}.json", trial_report)
    except BaseException as error:
        write_json(run / "interruption.json", {"completed_pairs": len(pairs), "error_type": type(error).__name__,
                   "live_suite_complete": False, "passed": False})
        raise
    report = {**summarize_pairs(pairs), **diagnostics(pairs), "benchmark_version": 2,
              "trials": trial_reports, "environment_stable": True, "environment": initial,
              "artifact_id": json_hash(manifest), "live_suite_complete": not quick and not overlaps,
              "excluded_training_overlap_cases": sorted(overlaps), "source_review_passed": False,
              "source_review": "Inspect all trial answers against original cited sources before activation.",
              "pairs_sha256": digest(run / "benchmark_pairs.json"), "provider": initial["provider"],
              "run_directory": str(run)}
    report["passed"] = benchmark_passed(report)
    write_json(run / "benchmark.json", report)
    write_json(root / "benchmark_pairs.json", pairs)
    write_json(root / "benchmark.json", report)
    print(json.dumps(report, indent=2), flush=True)
    return report
