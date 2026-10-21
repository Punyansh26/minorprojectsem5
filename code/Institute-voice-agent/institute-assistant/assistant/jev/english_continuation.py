"""Fork a completed development run to continue optimization without erasing evidence."""
from pathlib import Path
import json
import shutil
from tempfile import TemporaryDirectory

from .common import digest, json_hash, read_json, write_json
from .english_policy import PROFILE
from .english_training import (atomic_save, checked_manifest, training_inputs,
                               validate_base_assets)
from .english_recovery import legacy_checkpoint_matches


def extend(source, destination, epochs=40, patience=5):
    """Copy verified resume state into a fresh run, changing only stopping limits."""
    import torch
    from safetensors.torch import load_file
    source, destination = Path(source).resolve(), Path(destination).expanduser().resolve()
    if destination.exists() or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Continuation needs a new, separate artifact directory")
    if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
        raise ValueError("Epoch limit must be a positive integer")
    if isinstance(patience, bool) or not isinstance(patience, int) or patience < 1:
        raise ValueError("Patience must be a positive integer")
    profile = read_json(source / "profile.json")
    if profile["profile"] != PROFILE:
        raise ValueError("Only English recovery runs can be continued")
    validate_base_assets(source)
    manifest = checked_manifest(source, read_json(source / "manifest.json"))
    summary = read_json(source / "training_summary.json")
    if summary["artifact_id"] != json_hash(manifest):
        raise ValueError("Source summary does not match the artifact")
    configs = [summary["candidates"][name]["training"]["config"] for name in ("frozen", "finetuned")]
    if configs[0] != configs[1] or configs[0] != profile["config"]:
        raise ValueError("Source candidate configurations do not match")
    old_config = configs[0]
    if epochs <= old_config["epochs"] or patience < old_config["patience"]:
        raise ValueError("Continuation must increase epochs and retain or increase patience")
    config = {**old_config, "epochs": epochs, "patience": patience}
    checkpoints = {}
    for name in ("frozen", "finetuned"):
        candidate_manifest = checked_manifest(source, read_json(source / f"candidates/{name}/manifest.json"))
        inputs = training_inputs(source, old_config, name)
        training = summary["candidates"][name]["training"]
        if candidate_manifest["training_fingerprint"] != training["fingerprint"]:
            raise ValueError("Source candidate report does not match its manifest")
        checkpoint = torch.load(source / f"candidates/{name}/resume.pt", map_location="cpu", weights_only=True)
        if checkpoint["fingerprint"] != json_hash(inputs) and not legacy_checkpoint_matches(inputs, checkpoint["fingerprint"]):
            raise ValueError("Source training inputs changed; continuation refused")
        if checkpoint["epoch"] != training["epochs"] or checkpoint["history"] != read_json(source / f"candidates/{name}/training.json"):
            raise ValueError("Source resume state does not match completed training")
        if checkpoint["best"] != training["best_validation_loss"]:
            raise ValueError("Source best-checkpoint loss differs")
        best = torch.load(source / f"candidates/{name}/best.pt", map_location="cpu", weights_only=True)
        # The exported candidate is the best epoch, whereas resume.pt holds the
        # last completed epoch. Authenticate best.pt against the bound export.
        exported_encoder = load_file(str(source / candidate_manifest["encoder_dir"] / "model.safetensors"))
        exported_heads = torch.load(source / candidate_manifest["heads_file"], map_location="cpu", weights_only=True)
        exported = {**{"encoder." + key: value for key, value in exported_encoder.items()},
                    **{"heads." + key: value for key, value in exported_heads.items()}}
        if set(best) != set(exported) or any(not torch.equal(best[key], value) for key, value in exported.items()):
            raise ValueError("Source best checkpoint does not match exported weights")
        checkpoints[name] = {"epoch": checkpoint["epoch"],
                             "resume_sha256": digest(source / f"candidates/{name}/resume.pt"),
                             "best_sha256": digest(source / f"candidates/{name}/best.pt")}
        del checkpoint, best, exported, exported_encoder, exported_heads
    destination.parent.mkdir(parents=True, exist_ok=True)
    record = {"source_directory": str(source), "source_artifact_id": summary["artifact_id"],
              "source_summary_sha256": digest(source / "training_summary.json"),
              "old_config": old_config, "config": config, "checkpoints": checkpoints,
              "changes": ["maximum epochs", "early-stopping patience"],
              "calibration_policy_changed": False, "data_changed": False, "final_test_consumed": False}
    # Build privately and publish once complete. Copy bytes rather than hardlinks:
    # saving future epochs must never modify the completed source run.
    with TemporaryDirectory(prefix=".english-continuation-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "run"
        stage.mkdir()
        for filename in ("data.json", "label_review.json", "base_assets.json"):
            shutil.copy2(source / filename, stage / filename)
        shutil.copytree(source / "base_encoder", stage / "base_encoder", ignore=shutil.ignore_patterns(".cache"))
        write_json(stage / "profile.json", {**profile, "config": config})
        for name, identity in checkpoints.items():
            parent = stage / "candidates" / name
            parent.mkdir(parents=True)
            checkpoint = torch.load(source / f"candidates/{name}/resume.pt", map_location="cpu", weights_only=True)
            if (digest(source / f"candidates/{name}/resume.pt") != identity["resume_sha256"]
                    or digest(source / f"candidates/{name}/best.pt") != identity["best_sha256"]):
                raise ValueError("Source checkpoints changed during continuation preparation")
            checkpoint["fingerprint"] = json_hash(training_inputs(stage, config, name))
            atomic_save(checkpoint, parent / "resume.pt")
            shutil.copy2(source / f"candidates/{name}/best.pt", parent / "best.pt")
            write_json(parent / "training.json", checkpoint["history"])
            del checkpoint
        write_json(stage / "continuation.json", record)
        if destination.exists():
            raise ValueError("Continuation destination already exists")
        stage.rename(destination)
    print(json.dumps({"prepared_continuation": str(destination), "config": config,
                      "completed_epochs": {name: value["epoch"] for name, value in checkpoints.items()},
                      "training_started": False, "activated": False}, indent=2), flush=True)
    return record
