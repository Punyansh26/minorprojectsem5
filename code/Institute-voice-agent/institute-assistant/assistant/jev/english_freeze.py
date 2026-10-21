"""Publish audited calibration in a new directory while preserving training runs."""
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from .common import digest, json_hash, read_json, write_json


def checked_audit(root, audit_dir, manifest):
    """Recompute the decision checks and verify their frozen inputs before export."""
    from .english_audit import (GATES, assess_confirmation, check_overlap, select_proposal)
    audit_dir = Path(audit_dir)
    plan = read_json(audit_dir / "plan.json")
    rows = read_json(audit_dir / "rows.json")
    report = read_json(audit_dir / "report.json")
    details = read_json(audit_dir / "predictions.json")
    if (plan["artifact_id"] != json_hash(manifest) or plan["rows_hash"] != json_hash(rows)
            or report["plan_hash"] != json_hash(plan)
            or report["artifact_id"] != plan["artifact_id"]
            or report["predictions_sha256"] != digest(audit_dir / "predictions.json")
            or plan["temperatures"] != manifest["temperatures"] or plan["support_gates"] != GATES):
        raise ValueError("Audit does not match the frozen artifact and data")
    for name in ("english_audit.py", "english_policy.py", "english_model.py", "english_training.py", "common.py"):
        if plan["code_sha256"].get(name) != digest(Path(__file__).with_name(name)):
            raise ValueError("Audit code changed; preserve the old audit and run a new one")
    original_path = audit_dir / "source_calibration.json"
    if not original_path.exists():
        original_path = Path(root) / manifest["calibration_file"]
    if digest(original_path) != manifest["files"][manifest["calibration_file"]]:
        raise ValueError("Original calibration binding mismatch")
    original = read_json(original_path)
    proposal = select_proposal(original)
    if plan["selection_point"] != proposal or plan["thresholds"] != proposal["thresholds"]:
        raise ValueError("Audit policy was not frozen from the original calibration sweep")
    check_overlap(rows, read_json(Path(root) / "data.json"))
    metrics, expected = assess_confirmation(rows, [d["prediction"] for d in details], plan["thresholds"])
    if details != expected or any(report.get(k) != v for k, v in metrics.items()):
        raise ValueError("Audit decisions do not match saved predictions")
    if not metrics["development_confirmation_passed"]:
        raise ValueError("Development confirmation failed; keep the unsupported artifact")
    return plan, rows, report


def freeze(root, audit_dir, output):
    """Copy only bound assets and evidence, never an activation or resume checkpoint."""
    from .english_training import checked_manifest
    root, audit_dir, output = (Path(p).expanduser().resolve() for p in (root, audit_dir, output))
    if output.exists():
        raise ValueError("Destination already exists; preserve it and choose a new directory")
    if any(output.is_relative_to(p) or p.is_relative_to(output) for p in (root, audit_dir)):
        raise ValueError("Use a separate calibrated artifact directory")
    manifest = checked_manifest(root, read_json(root / "manifest.json"))
    if manifest.get("additional_calibration_file"):
        raise ValueError("This artifact is already calibrated by confirmation")
    plan, rows, report = checked_audit(root, audit_dir, manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".english-freeze-", dir=output.parent) as temporary:
        staged = Path(temporary) / "artifact"
        staged.mkdir()
        for name in manifest["files"]:
            target = staged / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, target)
        evidence = staged / "confirmation"
        evidence.mkdir()
        for name in ("plan.json", "rows.json", "report.json", "predictions.json"):
            shutil.copy2(audit_dir / name, evidence / name)
        shutil.copy2(root / "manifest.json", evidence / "source_manifest.json")
        shutil.copy2(root / manifest["calibration_file"], evidence / "source_calibration.json")
        write_json(staged / manifest["calibration_file"], {
            "temperatures": plan["temperatures"], "thresholds": plan["thresholds"],
            "source_artifact_id": plan["artifact_id"], "confirmation_report": "confirmation/report.json",
            "note": "Policy frozen before additional development predictions; final holdout and live review still required."})
        files = {name: digest(staged / name) for name in manifest["files"]}
        files.update({str(p.relative_to(staged)): digest(p) for p in evidence.iterdir()})
        derived = {**manifest, "files": files, "thresholds": plan["thresholds"],
                   "source_artifact_id": plan["artifact_id"],
                   "additional_calibration_file": "confirmation/rows.json"}
        checked_manifest(staged, derived)
        # Verify the copied source was stable throughout export, including weights.
        for name, checksum in manifest["files"].items():
            if name != manifest["calibration_file"] and digest(staged / name) != checksum:
                raise ValueError("Source changed during calibrated artifact export")
        if read_json(evidence / "source_manifest.json") != manifest:
            raise ValueError("Source manifest changed during export")
        checked_audit(staged, evidence, manifest)
        write_json(staged / "manifest.json", derived)
        profile = read_json(root / "profile.json")
        write_json(staged / "profile.json", {**profile, "stage": "calibrated",
                                             "source_artifact_id": plan["artifact_id"]})
        summary = {"profile": "english-v2", "stage": "calibrated", "candidate": manifest["candidate"],
                   "artifact_id": json_hash(derived), "source_artifact_id": plan["artifact_id"],
                   "thresholds": plan["thresholds"], "development_confirmation": report,
                   "fresh_test": False, "gold_reviewed": False, "passed": False, "activated": False,
                   "next_step": "Run paired live RAG benchmark; obtain a fresh independently reviewed final holdout before activation."}
        write_json(staged / "calibration_summary.json", summary)
        staged.rename(output)
    print(json.dumps({"prepared": str(output), **summary}, indent=2), flush=True)
    return summary
