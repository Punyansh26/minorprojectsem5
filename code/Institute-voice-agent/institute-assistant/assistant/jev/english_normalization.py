"""Versioned institute-name normalization for inference, preserving the RAG query."""
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from .common import INSTITUTE, digest, json_hash, read_json, write_json


def normalize_message(message):
    """Map only known names of this institute to the spelling used during training."""
    return INSTITUTE.sub("IIIT-NR", message)


def normalization_spec():
    """Bind the exact preprocessing implementation and alias pattern to an artifact."""
    return {"policy": "institute-alias-v1", "code_sha256": digest(__file__),
            "common_sha256": digest(Path(__file__).with_name("common.py"))}


def check_normalization(manifest):
    """Old artifacts keep their original inputs; incompatible new policies fail closed."""
    value = manifest.get("input_normalization")
    if value is not None and value != normalization_spec():
        raise ValueError("English input normalization binding mismatch")


def load_inference_router(root, manifest):
    """Normalize encoder inputs only; callers retain original text for policy and RAG."""
    from torch import nn
    from .english_model import load_router
    check_normalization(manifest)
    model = load_router(root, manifest)
    if not manifest.get("input_normalization"):
        return model

    class NormalizedRouter(nn.Module):
        def __init__(self, encoder):
            super().__init__()
            self.router = encoder

        def token_lengths(self, messages):
            return self.router.token_lengths([normalize_message(m) for m in messages])

        def forward(self, messages):
            return self.router([normalize_message(m) for m in messages])

    return NormalizedRouter(model).eval()


def normalize_artifact(root, output):
    """Export unchanged weights with explicit preprocessing and no inherited activation."""
    from .english_training import checked_manifest
    root, output = Path(root).expanduser().resolve(), Path(output).expanduser().resolve()
    if output.exists() or output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("Use a new, separate normalization artifact directory")
    manifest = checked_manifest(root, read_json(root / "manifest.json"))
    profile = read_json(root / "profile.json")
    if (profile.get("stage") != "calibrated" or not manifest["thresholds"]["supported"]
            or manifest.get("input_normalization")):
        raise ValueError("Require a calibrated artifact without an existing normalization policy")
    exposed = read_json(root / "data.json")
    if manifest.get("additional_calibration_file"):
        exposed += read_json(root / manifest["additional_calibration_file"])
    if any(normalize_message(r["message"]) != r["message"] for r in exposed):
        raise ValueError("Normalization changes prior training/calibration inputs; a new calibration experiment is required")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".english-normalize-", dir=output.parent) as temporary:
        staged = Path(temporary) / "artifact"
        staged.mkdir()
        for name, checksum in manifest["files"].items():
            target = staged / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, target)
            if digest(target) != checksum:
                raise ValueError("Source changed during normalization export")
        write_json(staged / "normalization_source_manifest.json", manifest)
        derived = {**manifest, "input_normalization": normalization_spec(),
                   "normalization_source_artifact_id": json_hash(manifest),
                   "files": {**manifest["files"], "normalization_source_manifest.json": digest(staged / "normalization_source_manifest.json")}}
        checked_manifest(staged, derived)
        check_normalization(derived)
        write_json(staged / "manifest.json", derived)
        write_json(staged / "profile.json", {**profile, "stage": "calibrated"})
        summary = read_json(root / "calibration_summary.json")
        summary = {**summary, "artifact_id": json_hash(derived),
                   "normalization_source_artifact_id": json_hash(manifest),
                   "input_normalization": derived["input_normalization"],
                   "normalization_note": "Known institute aliases map to IIIT-NR for the encoder only. All prior training/calibration messages are byte-identical after normalization; original RAG queries are preserved.",
                   "fresh_test": False, "gold_reviewed": False, "passed": False, "activated": False}
        write_json(staged / "calibration_summary.json", summary)
        staged.rename(output)
    print(json.dumps({"prepared": str(output), "artifact_id": summary["artifact_id"],
                      "input_normalization": summary["input_normalization"], "activated": False}, indent=2), flush=True)
    return summary
