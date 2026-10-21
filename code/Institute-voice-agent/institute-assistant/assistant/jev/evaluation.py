"""Calibration, held-out quality, paired live timing, and artifact activation."""
from dataclasses import replace
import json
from pathlib import Path
import statistics
import time

from .common import (LABELS, accepted, digest, json_hash, prediction_rows, preflight,
                     questions, read_json, write_json, live_case_overlaps)


def quality_passed(report):
    return (report.get("accepted", 0) >= 100 and report.get("precision", 0) >= .98
            and report.get("critical_failures", 1) == 0 and report.get("gold_reviewed") is True
            and report.get("family_overlap", True) is False and report.get("fresh_test") is True)


def benchmark_passed(report):
    trials_ok = (report.get("benchmark_version") != 2 or (
        report.get("environment_stable") is True and len(report.get("trials", [])) >= 3
        and all(performance_passed(trial) for trial in report["trials"])))
    return (performance_passed(report) and trials_ok
            and report.get("source_review_passed") is True and report.get("live_suite_complete") is True)


def performance_passed(report):
    """Apply unchanged latency/behavior requirements to each independent trial."""
    return (report.get("pairs", 0) >= 12 and report.get("coverage", 0) >= .15
            and report.get("median_improvement", 0) >= .10
            and report.get("p95_ratio", float("inf")) <= 1.05
            and report.get("new_behavior_failures", 1) == 0)


def correct(row, decision):
    gold = row["gold"]
    return (decision.intent == gold["intent"] and decision.language == gold["language"]
            and (decision.intent != "knowledge" or (decision.category == gold["category"] and not gold["rewrite"])))


def assess(rows, predictions, thresholds):
    accepted_count = correct_count = critical = 0
    by_language = {language: {"total": 0, "accepted": 0, "correct": 0} for language in LABELS[2]}
    for row, prediction in zip(rows, predictions, strict=True):
        lang = by_language[row["gold"]["language"]]
        lang["total"] += 1
        decision = None if preflight(row["message"]) else accepted(row["message"], prediction, thresholds)
        if decision is not None:
            accepted_count += 1
            lang["accepted"] += 1
            ok = correct(row, decision)
            correct_count += ok
            lang["correct"] += ok
            critical += row["critical"] and not ok
    return {"total": len(rows), "accepted": accepted_count, "correct": correct_count,
            "precision": correct_count / accepted_count if accepted_count else 0,
            "coverage": accepted_count / len(rows) if rows else 0,
            "critical_failures": critical, "by_language": by_language}


def infer_rows(model, rows):
    import torch
    outputs = []
    with torch.inference_mode():
        for i in range(0, len(rows), 16):
            batch = rows[i:i + 16]
            # Evaluation must follow runtime's no-silent-truncation rule.
            if any(len(model.tokenizer.tokenizer.encode(r["message"]).ids) > 512 for r in batch):
                raise ValueError("Evaluation input exceeds trained context")
            outputs.extend(prediction_rows(model.logits([r["message"] for r in batch], questions())))
    return outputs


def evaluate(root):
    from .runtime import _worker_model, artifact_signature
    root = Path(root)
    manifest = read_json(root / "manifest.json")
    if manifest.get("backend") in {"minilm-english-v2", "minilm-english-v3"}:
        raise ValueError("English recovery is development-only; use jev_pipeline.py report. A fresh reviewed final holdout is required later.")
    rows = read_json(root / "data.json")
    if digest(root / "data.json") != manifest["data_sha256"]:
        raise ValueError("Dataset changed since training")
    groups = {s: {r["family"] for r in rows if r["split"] == s} for s in ("train", "calibration", "test")}
    overlap = bool(groups["train"] & groups["calibration"] or groups["train"] & groups["test"] or groups["calibration"] & groups["test"])
    if overlap:
        raise ValueError("Family leakage")
    model = _worker_model(str(root), artifact_signature(root), 2)
    calibration = [r for r in rows if r["split"] == "calibration"]
    cal_predictions = infer_rows(model, calibration)
    thresholds = {"probability": 1.0, "confidence": 1.0, "rewrite": 0.0}
    best_count = 0
    # Threshold search touches calibration only. Prefer stricter ties.
    for probability in (.99, .98, .95, .90, .85, .80, .70):
        for confidence in (.9, .8, .7, .6, .5, .4):
            for rewrite in (.05, .10, .15):
                candidate = {"probability": probability, "confidence": confidence, "rewrite": rewrite}
                result = assess(calibration, cal_predictions, candidate)
                if result["precision"] >= .98 and result["critical_failures"] == 0 and result["accepted"] > best_count:
                    best_count, thresholds = result["accepted"], candidate
    manifest["thresholds"] = thresholds
    write_json(root / "manifest.json", manifest)
    test = [r for r in rows if r["split"] == "test"]
    exposure_path = root / "test_exposures.json"
    exposures = (read_json(exposure_path)["count"] if exposure_path.exists() else 0) + 1
    write_json(exposure_path, {"count": exposures})
    test_predictions = infer_rows(model, test)
    report = assess(test, test_predictions, thresholds)
    from .data import synthetic_rows
    # Gold is authored and inspected independently of Ollama. A changed/custom dataset
    # needs its own gold review; never infer review from matching the teacher.
    canonical = {r["id"]: r for r in synthetic_rows()}
    gold_reviewed = all(canonical.get(r["id"]) == r for r in test)
    report.update({"artifact_id": json_hash(manifest), "family_overlap": overlap, "fresh_test": exposures == 1, "test_exposures": exposures,
                   "gold_reviewed": gold_reviewed,
                   "gold_source": "independently authored synthetic seed labels in assistant/jev/data.py",
                   "thresholds": thresholds, "calibration": assess(calibration, cal_predictions, thresholds),
                   "head_accuracy": {name: sum(p[name] == r["gold"][name] for r, p in zip(test, test_predictions)) / len(test)
                                     for name in ("intent", "category", "language")}})
    report["passed"] = quality_passed(report)
    write_json(root / "evaluation.json", report)
    write_json(root / "test_predictions.json", [{"id": r["id"], "gold": r["gold"], "prediction": p} for r, p in zip(test, test_predictions)])
    print(json.dumps(report, indent=2), flush=True)
    return report


def percentile95(values):
    return sorted(values)[max(0, __import__("math").ceil(.95 * len(values)) - 1)]


def summarize_pairs(pairs):
    """Report per-turn latency, retaining dialogue-level behavior expectations."""
    if not pairs or any(len(p["modes"]["off"]["turns"]) != len(p["modes"]["enabled"]["turns"]) for p in pairs):
        raise ValueError("Require complete paired turns")
    turns = {mode: [t for p in pairs for t in p["modes"][mode]["turns"]] for mode in ("off", "enabled")}
    baseline = [t["seconds"] for t in turns["off"]]
    candidate = [t["seconds"] for t in turns["enabled"]]
    return {"pairs": len(pairs), "turn_pairs": len(candidate), "latency_unit": "one helpdesk turn, excluding audio",
            "new_behavior_failures": sum(p["modes"]["off"]["behavior_passed"] and not p["modes"]["enabled"]["behavior_passed"] for p in pairs),
            "coverage": sum(t["metrics"].get("router_path") == "open_jev" for t in turns["enabled"]) / len(candidate),
            "median_improvement": 1 - statistics.median(candidate) / statistics.median(baseline),
            "p95_ratio": percentile95(candidate) / percentile95(baseline),
            "baseline_p50_seconds": statistics.median(baseline), "candidate_p50_seconds": statistics.median(candidate),
            "baseline_p95_seconds": percentile95(baseline), "candidate_p95_seconds": percentile95(candidate),
            "llm_calls": {m: sum(t["metrics"].get("model_calls", 0) for t in ts) for m, ts in turns.items()},
            "classifier_calls": sum(t["metrics"].get("classifier_calls", 0) for t in turns["enabled"]),
            "classifier_ms": [t["metrics"]["stage_ms"]["classifier"] for t in turns["enabled"] if "classifier" in t["metrics"].get("stage_ms", {})],
            "routing_ms": {mode: [t["metrics"].get("stage_ms", {}).get("routing", 0) for t in ts] for mode, ts in turns.items()}}


def benchmark(root, quick=False, trials=3):
    """Use balanced trials while retaining the historical summary interface."""
    from .paired_benchmark import benchmark as run
    return run(root, quick=quick, trials=trials)


def activate(root):
    from .runtime import artifact_signature, checked_manifest
    root = Path(root)
    manifest = checked_manifest(str(root), artifact_signature(root))
    if manifest.get("backend") in {"minilm-english-v2", "minilm-english-v3"}:
        evaluation_path = root / "evaluation.json"
        final = read_json(evaluation_path) if evaluation_path.exists() else {}
        if not (manifest["thresholds"]["supported"] and final.get("evaluation_kind") == "final_holdout"
                and final.get("independent_human_review") is True):
            raise ValueError("English training is development-only; fresh reviewed holdout and live benchmark required before activation")
    evaluation = read_json(root / "evaluation.json")
    benchmark_report = read_json(root / "benchmark.json")
    if manifest.get("backend") == "minilm-english-v3" and benchmark_report.get("benchmark_version") != 2:
        raise ValueError("V3 activation requires three controlled benchmark trials")
    if not (quality_passed(evaluation) and benchmark_passed(benchmark_report)
            and evaluation["artifact_id"] == benchmark_report["artifact_id"] == json_hash(manifest)
            and benchmark_report["pairs_sha256"] == digest(root / "benchmark_pairs.json")):
        raise ValueError("Quality, latency, behavior or source-review gate failed; keep routing off/shadow")
    write_json(root / "activation.json", {"artifact_id": json_hash(manifest),
               "evaluation_sha256": digest(root / "evaluation.json"), "benchmark_sha256": digest(root / "benchmark.json")})
    print("Artifact activated. Set JEV_ROUTING_MODE=enabled and restart the application.", flush=True)
