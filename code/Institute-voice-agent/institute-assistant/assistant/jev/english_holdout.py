"""Evaluate externally reviewed, previously unused public holdout data once."""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from .common import (CATEGORIES, INTENTS, digest, json_hash, normalized_message,
                     read_json, write_json)


def validate_holdout(rows, review, dataset_sha256, manifest, exposed):
    """Require an explicit reviewer attestation and check machine-detectable leakage."""
    if (review.get("artifact_id") != json_hash(manifest)
            or review.get("dataset_sha256") != dataset_sha256
            or not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()
            or review["reviewer"].strip().casefold() in {"codex", "chatgpt", "assistant"}
            or not isinstance(review.get("notes"), str) or not review["notes"].strip()
            or any(review.get(key) is not True for key in (
                "independent_human_review", "labels_checked", "family_disjointness_checked",
                "public_or_synthetic", "not_used_for_development"))):
        raise ValueError("A human review tied to this dataset and frozen artifact is required")
    try:
        if date.fromisoformat(review["reviewed_at"]) > date.today():
            raise ValueError("Future review date")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Use the actual review date in YYYY-MM-DD format") from error
    if not isinstance(rows, list) or not rows:
        raise ValueError("Holdout must be a nonempty JSON array")
    ids, families, messages = set(), set(), set()
    categories, intents, challenges = set(), set(), set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("gold"), dict):
            raise ValueError("Invalid holdout row or gold label")
        gold = row.get("gold", {})
        if manifest.get("backend") == "minilm-english-v3":
            from .english_v3_policy import QUERY_ACTIONS
            if (gold.get("query_action") not in QUERY_ACTIONS or gold.get("rewrite") != (
                    gold.get("intent") == "knowledge" and gold.get("query_action") == "defer")):
                raise ValueError("V3 holdouts require an explicit query_action and consistent rewrite label")
            history = row.get("history", [])
            if (not isinstance(history, list) or any(
                    not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}
                    or any(key in item and not isinstance(item[key], str)
                           for key in ("text", "resolved_query", "response_status"))
                    for item in history)
                    or (row.get("pending") is not None and not isinstance(row["pending"], dict))):
                raise ValueError("Invalid v3 holdout history or pending action")
            if ("expected_query" in row or history and gold.get("intent") == "knowledge") and (
                    gold.get("intent") != "knowledge" or not isinstance(row.get("expected_query"), str)
                    or not row["expected_query"].strip()):
                raise ValueError("Contextual knowledge requires an explicitly reviewed expected_query")
        if (row.get("split") != "test" or any(not isinstance(row.get(k), str) or not row[k].strip()
                for k in ("id", "family", "message"))
                or gold.get("intent") not in INTENTS or gold.get("category") not in CATEGORIES
                or gold.get("language") not in {"english", "unsupported"}
                or not isinstance(gold.get("rewrite"), bool) or not isinstance(row.get("critical"), bool)):
            raise ValueError("Invalid holdout row or gold label")
        message = normalized_message(row["message"])
        if row["id"] in ids or message in messages:
            raise ValueError("Duplicate holdout ID or message")
        ids.add(row["id"])
        families.add(row["family"])
        messages.add(message)
        if gold["language"] == "english":
            intents.add(gold["intent"])
            if gold["intent"] == "knowledge":
                categories.add(gold["category"])
                if gold["rewrite"]:
                    challenges.add("rewrite")
        else:
            challenges.add("language")
        if ((gold["language"] != "english" or gold["rewrite"]
             or gold["intent"] in {"handoff", "reminder", "cancel"}) and not row["critical"]):
            raise ValueError("Language, rewrite and action challenges must be critical")
    if categories != set(CATEGORIES) or intents != set(INTENTS) or challenges != {"rewrite", "language"}:
        raise ValueError("Holdout must cover every intent/category plus non-English and rewrite challenges")
    if (messages & {normalized_message(r["message"]) for r in exposed}
            or families & {r["family"] for r in exposed}):
        raise ValueError("Holdout overlaps training, validation or calibration data")
    from evaluate_helpdesk import CASES
    reserved = {normalized_message(q) for _, turns, _ in CASES for q in turns}
    if messages & reserved:
        raise ValueError("Holdout reuses reserved live benchmark cases")


def register_exposure(root, rows, artifact_id, dataset_sha256):
    """Share exposure history across sibling experiments; never reset it on retraining."""
    ledger = Path(root).parent / "english_holdout_exposures.json"
    lock = ledger.with_suffix(".lock")
    try:
        stream = lock.open("x")
    except FileExistsError as error:
        raise ValueError("Another holdout is recording exposure; retry after it completes") from error
    try:
        with stream:
            previous = read_json(ledger) if ledger.exists() else []
            messages = {json_hash(normalized_message(r["message"])) for r in rows}
            families = {r["family"] for r in rows}
            fresh = not any(messages & set(p["message_hashes"]) or families & set(p["families"]) for p in previous)
            previous.append({"artifact_id": artifact_id, "dataset_sha256": dataset_sha256,
                             "message_hashes": sorted(messages), "families": sorted(families)})
            write_json(ledger, previous)
            return {"fresh_test": fresh, "test_exposures": len(previous), "exposure_ledger": str(ledger)}
    finally:
        lock.unlink()


def evaluate_holdout(root, data_path, review_path, device="cpu"):
    """Score a fixed supported policy without tuning, training or self-certifying review."""
    root = Path(root).expanduser().resolve()
    lock = root / ".holdout-evaluation.lock"
    try:
        stream = lock.open("x")
    except FileExistsError as error:
        raise ValueError("A holdout evaluation is already in progress for this artifact") from error
    try:
        with stream:
            return _evaluate_holdout(root, data_path, review_path, device)
    finally:
        lock.unlink()


def _evaluate_holdout(root, data_path, review_path, device):
    import torch
    from .english_training import checked_manifest, infer, assess
    from .english_model import predictions
    from .english_normalization import load_inference_router
    from .english_audit import assess_confirmation
    from .evaluation import quality_passed
    root, data_path, review_path = (Path(p).expanduser().resolve() for p in (root, data_path, review_path))
    manifest = read_json(root / "manifest.json")
    v3 = manifest.get("backend") == "minilm-english-v3"
    if v3:
        from .english_v3_training import checked_manifest, infer, assess
        from .english_v3_model import predictions, load_router as load_inference_router
        if read_json(root / "profile.json").get("stage") != "calibrated":
            raise ValueError("Freeze v3 into a separate artifact before final evaluation")
    manifest = checked_manifest(root, manifest)
    if not manifest["thresholds"]["supported"]:
        raise ValueError("Calibrate and freeze a supported policy before final evaluation")
    data_bytes = data_path.read_bytes()
    rows, review = json.loads(data_bytes), read_json(review_path)
    dataset_sha256 = sha256(data_bytes).hexdigest()
    exposed = read_json(root / "data.json")
    if manifest.get("additional_calibration_file"):
        exposed += read_json(root / manifest["additional_calibration_file"])
    validate_holdout(rows, review, dataset_sha256, manifest, exposed)
    if device not in {"cpu", "cuda"} or (device == "cuda" and not torch.cuda.is_available()):
        raise ValueError("Requested evaluation device unavailable")
    if (root / "evaluation.json").exists():
        raise ValueError("Evaluation already exists; use report to inspect it. Preserve results and exposure history.")
    threads = torch.get_num_threads()
    try:
        torch.set_num_threads(2)
        model = load_inference_router(root, manifest).to(device)
        if any(n > manifest["max_tokens"] for n in model.token_lengths([r["message"] for r in rows])):
            raise ValueError("Holdout contains oversized inputs; use the separate runtime token-limit regression tests")
        # Labels, review and policy are fixed before prediction. An interrupted inference
        # counts as exposure because some predictions may already have been observed.
        exposure = register_exposure(root, rows, json_hash(manifest), dataset_sha256)
        predicted = predictions(infer(model, rows), manifest["temperatures"])
    finally:
        torch.set_num_threads(threads)
    metrics = assess(rows, predicted, manifest["thresholds"])
    if v3:
        _, details = assess(rows, predicted, manifest["thresholds"], details=True)
    else:
        _, details = assess_confirmation(rows, predicted, manifest["thresholds"])
    write_json(root / "final_holdout_data.json", rows)
    write_json(root / "final_holdout_review.json", review)
    write_json(root / "final_holdout_predictions.json", details)
    report = {**metrics, **exposure, "evaluation_kind": "final_holdout",
              "artifact_id": json_hash(manifest), "thresholds": manifest["thresholds"],
              "gold_reviewed": True, "independent_human_review": True, "family_overlap": False,
              "reviewer": review["reviewer"], "dataset_input_sha256": dataset_sha256,
              "files": {name: digest(root / name) for name in
                        ("final_holdout_data.json", "final_holdout_review.json", "final_holdout_predictions.json")},
              "review_limitations": "Human review is an attestation; code checks exact messages and declared families, not semantic independence."}
    report["passed"] = quality_passed(report)
    write_json(root / "evaluation.json", report)
    print(json.dumps(report, indent=2), flush=True)
    return report
