"""Freeze a development policy before testing additional public scenarios."""
import json
from pathlib import Path

from .common import (CATEGORIES, INTENTS, digest, json_hash, live_case_overlaps,
                     normalized_message, preflight, read_json, write_json)
from .english_policy import route, validate_thresholds

CORPUS = Path(__file__).with_name("english_confirmation.txt")
GATES = {"accepted_families": 30, "accepted_knowledge": 10,
         "precision": .98, "critical_failures": 0}


def confirmation_rows(path=CORPUS):
    """Keep clean/mixed relatives together and label before looking at predictions."""
    rows, seen = [], set()
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = [s.strip() for s in line.split("|", 6)]
        if len(fields) != 7:
            raise ValueError(f"Invalid confirmation row {line_number}")
        family, intent, category, language, rewrite, critical, message = fields
        if (not family or not message or intent not in INTENTS or category not in CATEGORIES
                or language not in {"english", "unsupported"} or rewrite not in {"0", "1"}
                or critical not in {"0", "1"}):
            raise ValueError(f"Invalid confirmation labels on row {line_number}")
        normalized = normalized_message(message)
        if normalized in seen:
            raise ValueError("Duplicate confirmation message")
        seen.add(normalized)
        rows.append({"id": json_hash(["english-confirmation-v1", normalized])[:20],
                     "family": "confirmation-v1-" + family, "message": message,
                     "split": "calibration_confirmation", "critical": critical == "1",
                     "gold": {"intent": intent, "category": category,
                              "language": language, "rewrite": rewrite == "1"}})
    if not rows:
        raise ValueError("Empty confirmation corpus")
    return rows


def check_overlap(rows, exposed):
    """Block declared relatives and exact reuse; semantic independence needs review."""
    messages = {normalized_message(r["message"]) for r in exposed}
    families = {r["family"] for r in exposed}
    if any(normalized_message(r["message"]) in messages or r["family"] in families for r in rows):
        raise ValueError("Confirmation overlaps earlier development data")
    if live_case_overlaps([{**r, "split": "calibration"} for r in rows]):
        raise ValueError("Confirmation overlaps reserved live cases")


def select_proposal(calibration):
    """Pick from the existing sweep only; additional outcomes never tune thresholds."""
    best = None
    for point in calibration["risk_coverage"]:
        validate_thresholds(point["thresholds"])
        if (point["thresholds"]["supported"] and point["precision"] >= GATES["precision"]
                and point["critical_failures"] == 0 and point["accepted"] > 0
                and (best is None or point["accepted"] > best["accepted"])):
            best = point
    if best is None:
        raise ValueError("No error-qualified development threshold to audit")
    return best


def assess_confirmation(rows, predicted, thresholds):
    """Expose accepted errors separately from raw head accuracy and rejected rows."""
    from .english_training import assess
    metrics = assess(rows, predicted, thresholds)
    details = []
    for row, prediction in zip(rows, predicted, strict=True):
        reason = preflight(row["message"])
        decision = None
        if reason is None:
            decision, reason = route(row["message"], prediction, thresholds)
        gold = row["gold"]
        correct = decision is not None and (
            gold["language"] == "english" and decision.intent == gold["intent"]
            and (decision.intent != "knowledge" or
                 (decision.category == gold["category"] and not gold["rewrite"])))
        details.append({"id": row["id"], "family": row["family"], "gold": gold,
                        "prediction": prediction, "accepted": decision is not None,
                        "correct": bool(correct), "rejection_reason": reason,
                        "critical_failure": bool(decision is not None and row["critical"] and not correct)})
    failures = [d["id"] for d in details if d["accepted"] and not d["correct"]]
    passed = (metrics["accepted_families"] >= GATES["accepted_families"]
              and metrics["accepted_knowledge"] >= GATES["accepted_knowledge"]
              and metrics["precision"] >= GATES["precision"]
              and metrics["critical_failures"] == GATES["critical_failures"])
    return {**metrics, "accepted_error_ids": failures, "support_gates": GATES,
            "development_confirmation_passed": passed}, details


def audit(root, output, device="cpu"):
    """Save immutable audit inputs/results without modifying or activating a model."""
    from .english_training import checked_manifest, infer
    from .english_model import load_router, predictions
    import torch
    root, output = Path(root).resolve(), Path(output).expanduser().resolve()
    if output == root or output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("Keep the audit outside the trained artifact directory")
    manifest = checked_manifest(root, read_json(root / "manifest.json"))
    calibration = read_json(root / manifest["calibration_file"])
    proposal = select_proposal(calibration)
    rows = confirmation_rows()
    check_overlap(rows, read_json(root / "data.json"))
    if device not in {"cpu", "cuda"} or (device == "cuda" and not torch.cuda.is_available()):
        raise ValueError("Requested audit device unavailable")
    plan = {"evaluation_kind": "development_confirmation", "source_artifacts": str(root),
            "artifact_id": json_hash(manifest), "thresholds": proposal["thresholds"],
            "temperatures": manifest["temperatures"], "selection_point": proposal,
            "selection_rule": "Most accepted among existing sweep points with precision >= .98 and zero critical errors; retain sweep order for ties",
            "corpus_sha256": digest(CORPUS), "rows_hash": json_hash(rows),
            "support_gates": GATES, "device": device,
            "code_sha256": {name: digest(Path(__file__).with_name(name)) for name in
                            ("english_audit.py", "english_policy.py", "english_model.py", "english_training.py", "common.py")},
            "provenance": {"label_source": "Codex-authored public synthetic development scenarios",
                           "independent_human_review": False,
                           "limitations": "Exact reuse and declared relatives checked; no claim of semantic or statistical independence. Not a final holdout."}}
    if output.exists():
        if (not (output / "plan.json").is_file() or read_json(output / "plan.json") != plan
                or not (output / "rows.json").is_file() or read_json(output / "rows.json") != rows):
            raise ValueError("Audit inputs changed; preserve this directory and use a new output")
        if (output / "report.json").is_file():
            result = read_json(output / "report.json")
            if (result["plan_hash"] != json_hash(plan)
                    or result["predictions_sha256"] != digest(output / "predictions.json")):
                raise ValueError("Audit result binding mismatch")
            print(json.dumps(result, indent=2), flush=True)
            return result
    else:
        output.mkdir(parents=True)
        # Persist labels and policy before any prediction, including on interrupted runs.
        write_json(output / "plan.json", plan)
        write_json(output / "rows.json", rows)
    threads = torch.get_num_threads()
    try:
        torch.set_num_threads(2)
        model = load_router(root, manifest).to(device)
        predicted = predictions(infer(model, rows), plan["temperatures"])
    finally:
        torch.set_num_threads(threads)
    metrics, details = assess_confirmation(rows, predicted, plan["thresholds"])
    write_json(output / "predictions.json", details)
    result = {**metrics, "evaluation_kind": "development_confirmation",
              "artifact_id": plan["artifact_id"], "plan_hash": json_hash(plan),
              "thresholds": plan["thresholds"], "families": len({r["family"] for r in rows}),
              "predictions_sha256": digest(output / "predictions.json"),
              "fresh_test": False, "gold_reviewed": False, "independent_human_review": False,
              "passed": False, "activated": False,
              "next_step": "Review all accepted errors. This audit cannot activate or rewrite a trained artifact."}
    write_json(output / "report.json", result)
    print(json.dumps(result, indent=2), flush=True)
    return result
