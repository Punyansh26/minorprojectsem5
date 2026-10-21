"""Versioned English v3 training with bounded query preparation and measured abstention."""
from collections import Counter
from itertools import product
from pathlib import Path
import json
import math
import random
import time

from .common import digest, json_hash, read_json, write_json, preflight
from .english_v3_data import development_rows, validate_rows, dataset_summary, CORPUS_PATH
from .english_v3_policy import (BACKEND, PROFILE, MODEL_ID, MODEL_REVISION, MAX_TOKENS,
                             HEADS, DEFAULT_THRESHOLDS, route, validate_thresholds, QUERY_ACTIONS)

DEFAULT_CONFIG = {"seed": 42, "batch_size": 16, "epochs": 40, "patience": 5,
                  "encoder_lr": 2e-5, "head_lr": 1e-3, "weight_decay": .01,
                  "cpu_threads": 4}
ASSET_NAMES = ("config.json", "model.safetensors", "tokenizer.json",
               "tokenizer_config.json", "special_tokens_map.json", "vocab.txt")
THRESHOLD_GRID = {"intent": (.99, .95, .90, .80),
                  "category": (1., .995, .99, .95, .90),
                  "english": (.99, .95),
                  "query_action": (.99, .95, .90, .85, .80, .75, .70, .60, .50)}


def file_hashes(root, directory):
    """Bind every encoder/tokenizer asset, including tokenizer configuration."""
    root, directory = Path(root), Path(directory)
    return {str(p.relative_to(root)): digest(p) for p in sorted(directory.rglob("*"))
            if p.is_file() and ".cache" not in p.relative_to(directory).parts}


def validate_base_assets(root):
    """Validate the base snapshot, repairing only the known empty-index defect."""
    root = Path(root)
    actual = file_hashes(root, root / "base_encoder")
    recorded = read_json(root / "base_assets.json")
    if recorded == {}:
        from .english_recovery import repair_empty_base_index
        repair_empty_base_index(root, actual)
    elif actual != recorded:
        raise ValueError("Prepared encoder assets changed")


def training_inputs(root, config, name):
    """Bind resume state to the exact data, model assets and training recipe."""
    root = Path(root)
    return {"data": digest(root / "data.json"), "review": digest(root / "label_review.json"),
            "base": read_json(root / "base_assets.json"), "config": config, "name": name,
            "recipe": {file: digest(Path(__file__).parent / file) for file in
                       ("english_v3_training.py", "english_v3_model.py", "english_v3_policy.py", "english_v3_data.py", "english_model.py", "english_policy.py", "english_normalization.py", "common.py", "../history.py", "../kb/structured.py")}}


def prepare(root):
    """Download a pinned base once and materialize reviewed development targets."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    profile_path = root / "profile.json"
    rows = development_rows()
    validate_rows(rows)
    profile = {"profile": PROFILE, "backend": BACKEND, "model_id": MODEL_ID,
               "model_revision": MODEL_REVISION, "corpus_sha256": digest(CORPUS_PATH),
               "data_hash": json_hash(rows), "config": DEFAULT_CONFIG}
    if profile_path.exists() and read_json(profile_path) != profile:
        raise ValueError("Preparation inputs changed; choose a new artifact directory")
    if not profile_path.exists() and any(root.iterdir()):
        raise ValueError("Use an empty artifact directory for the English profile")
    write_json(profile_path, profile)
    if (root / "data.json").exists() and read_json(root / "data.json") != rows:
        raise ValueError("Prepared data changed; choose a new artifact directory")
    write_json(root / "data.json", rows)
    review = {**dataset_summary(rows), "corpus_sha256": digest(CORPUS_PATH),
              "data_sha256": digest(root / "data.json"),
              "rubric": {"knowledge": "Public institute information, including unknown facts; category is a preference.",
                         "query_action": "copy: self-contained named institute or public scheme; scope_institute: append institute only; defer: reference, translation or mixed request.",
                         "actions": "Explicit requests only; never authorized by the classifier.",
                         "rejection": "Non-English examples supervise only English/defer, never task heads."}}
    write_json(root / "label_review.json", review)
    base = root / "base_encoder"
    assets_path = root / "base_assets.json"
    if assets_path.exists():
        validate_base_assets(root)
    else:
        from .english_recovery import PINNED_ASSET_SHA256
        import shutil
        cached = Path.home() / ".cache/institute-assistant/open-jev/english-v2/base_encoder"
        if all((cached / name).is_file() and digest(cached / name) == PINNED_ASSET_SHA256[name]
               for name in ASSET_NAMES):
            base.mkdir(parents=True, exist_ok=True)
            for name in ASSET_NAMES:
                shutil.copy2(cached / name, base / name)
        else:
            from huggingface_hub import snapshot_download
            snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_dir=base,
                              allow_patterns=list(ASSET_NAMES))
        if not all((base / name).is_file() for name in ASSET_NAMES):
            raise ValueError("Incomplete pretrained snapshot; rerun prepare")
        write_json(assets_path, file_hashes(root, base))
    print(json.dumps({"prepared": str(root), **dataset_summary(rows)}, indent=2), flush=True)
    return profile


def atomic_save(value, path):
    """A process interruption must leave the last completed checkpoint intact."""
    import torch
    path = Path(path)
    temporary = path.with_suffix(".tmp.pt")
    torch.save(value, temporary)
    temporary.replace(path)


def infer(model, rows, batch_size=16):
    """Collect raw logits so calibration never needs additional model training."""
    import torch
    model.eval()
    batches = {name: [] for name in HEADS}
    with torch.inference_mode():
        for offset in range(0, len(rows), batch_size):
            values = model([r["message"] for r in rows[offset:offset + batch_size]])
            for name in HEADS:
                batches[name].append(values[name].cpu())
    return {name: torch.cat(values) for name, values in batches.items()}


def _validation_loss(model, rows, batch_size):
    from .english_v3_model import masked_loss
    return float(masked_loss(infer(model, rows, batch_size), rows))


def train_candidate(root, rows, config, device, name, resume, budget_seconds):
    """Resume completed epochs with optimizer/RNG state and immutable training inputs."""
    import torch
    from .english_v3_model import QueryRouter, masked_loss
    root = Path(root)
    candidate = root / "candidates" / name
    candidate.mkdir(parents=True, exist_ok=True)
    checkpoint = candidate / "resume.pt"
    inputs = training_inputs(root, config, name)
    fingerprint = json_hash(inputs)
    if checkpoint.exists() and not resume:
        raise ValueError("Saved progress exists; use --resume or a new artifact directory")
    random.seed(config["seed"])
    torch.manual_seed(config["seed"])
    if device == "cuda":
        torch.cuda.manual_seed_all(config["seed"])
    frozen = name == "frozen"
    model = QueryRouter(root / "base_encoder", frozen=frozen).to(device)
    groups = [{"params": model.heads.parameters(), "lr": config["head_lr"]}]
    if not frozen:
        groups.append({"params": model.encoder.parameters(), "lr": config["encoder_lr"]})
    optimizer = torch.optim.AdamW(groups, weight_decay=config["weight_decay"])
    training = [r for r in rows if r["split"] == "train"]
    validation = [r for r in rows if r["split"] == "validation"]
    first_epoch, best, stale, history, consumed = 0, float("inf"), 0, [], 0.
    if checkpoint.exists():
        saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if saved["fingerprint"] != fingerprint:
            raise ValueError("Training inputs changed since saved progress")
        model.load_state_dict(saved["model"], strict=True)
        optimizer.load_state_dict(saved["optimizer"])
        # Optimizer state follows parameter device after load_state_dict.
        first_epoch, best, stale, history = saved["epoch"], saved["best"], saved["stale"], saved["history"]
        consumed = saved["consumed_seconds"]
        torch.set_rng_state(saved["rng"])
        if device == "cuda" and saved["cuda_rng"]:
            torch.cuda.set_rng_state_all(saved["cuda_rng"])
        random.setstate(saved["python_rng"])
    started = time.monotonic()
    for epoch in range(first_epoch, config["epochs"]):
        if stale >= config["patience"]:
            break
        if consumed + time.monotonic() - started >= budget_seconds:
            raise ValueError("Candidate budget exhausted; progress saved. Increase --max-seconds and resume.")
        ordered = sorted(training, key=lambda row: row["id"])
        random.Random(config["seed"] + epoch).shuffle(ordered)
        model.train()
        losses = []
        for offset in range(0, len(ordered), config["batch_size"]):
            batch = ordered[offset:offset + config["batch_size"]]
            optimizer.zero_grad(set_to_none=True)
            loss = masked_loss(model([r["message"] for r in batch]), batch)
            if not torch.isfinite(loss):
                raise ValueError("Non-finite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
            losses.append(float(loss.detach()))
        validation_loss = _validation_loss(model, validation, config["batch_size"])
        if validation_loss < best:
            best, stale = validation_loss, 0
            atomic_save(model.state_dict(), candidate / "best.pt")
        else:
            stale += 1
        elapsed = consumed + time.monotonic() - started
        entry = {"epoch": epoch + 1, "loss": sum(losses) / len(losses),
                 "validation_loss": validation_loss, "consumed_seconds": round(elapsed, 3)}
        history.append(entry)
        atomic_save({"fingerprint": fingerprint, "model": model.state_dict(), "optimizer": optimizer.state_dict(),
                     "epoch": epoch + 1, "best": best, "stale": stale, "history": history,
                     "consumed_seconds": elapsed, "rng": torch.get_rng_state(),
                     "cuda_rng": torch.cuda.get_rng_state_all() if device == "cuda" else [],
                     "python_rng": random.getstate()}, checkpoint)
        write_json(candidate / "training.json", history)
        print(json.dumps({"candidate": name, **entry}), flush=True)
    model.load_state_dict(torch.load(candidate / "best.pt", map_location=device, weights_only=True), strict=True)
    model.eval()
    model.encoder.save_pretrained(candidate / "encoder", safe_serialization=True)
    model.tokenizer.save_pretrained(candidate / "encoder")
    atomic_save(model.heads.state_dict(), candidate / "heads.pt")
    return model, {"best_validation_loss": best, "epochs": len(history), "fingerprint": fingerprint,
                   "config": config, "device": device}


def policy_hashes():
    """Bind every implementation that may alter a v3 routing decision."""
    return {name: digest(Path(__file__).parent / name) for name in (
        "english_v3_policy.py", "english_v3_model.py", "english_model.py",
        "english_policy.py", "english_normalization.py", "common.py",
        "../history.py", "../kb/structured.py")}


def assess(rows, predicted, thresholds, *, details=False):
    """Score actual query behavior; an abstained department is not a correct prediction."""
    from .english_v3_policy import exact_followup, scoped_query
    accepted = correct = critical = knowledge = classifier_accepted = category_abstained = 0
    families, reasons, strategies = set(), Counter(), Counter()
    category_total = category_correct = intent_total = intent_correct = 0
    records = []
    for row, prediction in zip(rows, predicted, strict=True):
        gold = row["gold"]
        if gold["language"] == "english":
            intent_total += 1
            intent_correct += prediction["intent"] == gold["intent"]
            if gold["intent"] == "knowledge":
                category_total += 1
                category_correct += prediction["category"] == gold["category"]
        history, pending = row.get("history", []), row.get("pending")
        local = exact_followup(row["message"], history, pending) if thresholds["supported"] else None
        reason = None
        if local is None:
            local, reason = route(row["message"], prediction, thresholds, history, pending)
        ok = None
        if local is None:
            reasons[reason] += 1
        else:
            accepted += 1
            classifier_accepted += local.query_strategy != "exact_rank_followup"
            strategies[local.query_strategy] += 1
            families.add(row["family"])
            decision = local.decision
            knowledge += decision.intent == "knowledge"
            ok = gold["language"] == "english" and decision.intent == gold["intent"]
            if decision.intent == "knowledge":
                category_abstained += local.retrieval_preference is None
                expected = row.get("expected_query")
                if expected is None:
                    expected = (row["message"] if gold["query_action"] == "copy" else
                                scoped_query(row["message"]) if gold["query_action"] == "scope_institute" else None)
                ok = ok and decision.query == expected and (
                    local.retrieval_preference is None or local.retrieval_preference == gold["category"])
            correct += bool(ok)
            critical += bool(row["critical"] and not ok)
        if details:
            records.append({"id": row["id"], "gold": gold, "prediction": prediction,
                            "accepted": local is not None, "correct": ok, "rejection": reason,
                            "query_strategy": local.query_strategy if local else None,
                            "query": local.decision.query if local else None,
                            "retrieval_preference": local.retrieval_preference if local else None})
    report = {"total": len(rows), "accepted": accepted, "classifier_accepted": classifier_accepted,
              "accepted_families": len(families), "accepted_knowledge": knowledge, "correct": correct,
              "precision": correct / accepted if accepted else 0, "coverage": accepted / max(len(rows), 1),
              "critical_failures": critical, "intent_accuracy": intent_correct / max(intent_total, 1),
              "knowledge_category_accuracy": category_correct / max(category_total, 1),
              "category_abstained": category_abstained, "query_strategies": dict(strategies),
              "rejection_reasons": dict(reasons)}
    return (report, records) if details else report


def calibrate(model, rows):
    """Separate temperature fitting from threshold selection, both development-only."""
    import torch
    from torch.nn import functional as F
    from .english_v3_model import predictions, targets
    families = sorted({r["family"] for r in rows})
    fitting = set(families[::2])
    fit_rows = [r for r in rows if r["family"] in fitting]
    gate_rows = [r for r in rows if r["family"] not in fitting]
    if not fit_rows or not gate_rows:
        raise ValueError("Insufficient calibration families")
    fit_logits = infer(model, fit_rows)
    values, masks = targets(fit_rows, "cpu")
    temperatures, metrics = {}, {}
    for name in HEADS:
        mask = masks[name]
        if not mask.any():
            temperatures[name] = 1.
            continue
        x, y = fit_logits[name][mask], values[name][mask]
        grid = torch.logspace(-1, 1, 81).tolist()
        temperature = min(grid, key=lambda t: float(F.cross_entropy(x / t, y)))
        temperatures[name] = temperature
        probability = (x / temperature).softmax(-1)
        metrics[name] = {"nll_before": float(F.cross_entropy(x, y)),
                         "nll_after": float(F.cross_entropy(x / temperature, y)),
                         "brier_after": float(((probability - F.one_hot(y, x.shape[1])) ** 2).sum(-1).mean())}
    predicted = predictions(infer(model, gate_rows), temperatures)
    thresholds, risk_coverage = select_thresholds(gate_rows, predicted)
    return {"temperatures": temperatures, "thresholds": thresholds,
            "temperature_metrics": metrics, "temperature_families": sorted(fitting),
            "threshold_families": sorted(set(families) - fitting), "risk_coverage": risk_coverage,
            "threshold_grid": THRESHOLD_GRID,
            "threshold_selection": assess(gate_rows, predicted, thresholds),
            "note": "Selected development precision is not final test quality; no activation is permitted."}


def select_thresholds(rows, predicted):
    """Maximize calibration coverage subject to unchanged precision and critical-error gates."""
    thresholds, best_count, risk_coverage = dict(DEFAULT_THRESHOLDS), 0, []
    # Strict-to-loose iteration breaks ties in favour of stricter thresholds.
    for intent, category, english, query_action in product(*(THRESHOLD_GRID[name] for name in
                                                          ("intent", "category", "english", "query_action"))):
        proposal = {"policy": PROFILE, "supported": True, "intent": intent,
                    "category": category, "english": english, "query_action": query_action}
        report = assess(rows, predicted, proposal)
        risk_coverage.append({"thresholds": proposal, **{k: report[k] for k in
                              ("accepted", "accepted_families", "precision", "coverage", "critical_failures", "accepted_knowledge")}})
        if (report["accepted_families"] >= 30 and report["accepted_knowledge"] >= 10
                and report["precision"] >= .98 and report["critical_failures"] == 0 and report["accepted"] > best_count):
            best_count, thresholds = report["accepted"], proposal
    return thresholds, risk_coverage


def checked_manifest(root, manifest):
    """Validate all new-backend assets, calibration and training provenance."""
    root = Path(root).resolve()
    if (manifest["version"] != 3 or manifest["backend"] != BACKEND
            or manifest["profile"] != PROFILE or manifest["max_tokens"] != MAX_TOKENS
            or manifest["training_examples"] < 64 or manifest["epochs"] < 1
            or manifest["model_id"] != MODEL_ID or manifest["model_revision"] != MODEL_REVISION):
        raise ValueError("Incompatible or untrained English artifact")
    from .common import INTENTS, CATEGORIES
    if manifest["labels"] != {"intent": list(INTENTS), "category": list(CATEGORIES), "query_action": list(QUERY_ACTIONS)}:
        raise ValueError("Incompatible English label order")
    validate_thresholds(manifest["thresholds"])
    if manifest.get("policy_files") != policy_hashes():
        raise ValueError("V3 policy implementation changed; prepare a new experiment")
    if set(manifest["temperatures"]) != set(HEADS) or any(
            isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or not .1 <= t <= 10.00001
            for t in manifest["temperatures"].values()):
        raise ValueError("Invalid calibration temperature")
    assets = manifest["files"]
    required = {manifest["heads_file"], "data.json", "label_review.json", manifest["calibration_file"]}
    required |= {manifest["encoder_dir"] + "/" + name for name in ASSET_NAMES}
    if not required <= set(assets):
        raise ValueError("Incomplete English artifact binding")
    for name, checksum in assets.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or digest(path) != checksum:
            raise ValueError("Artifact checksum mismatch")
    actual_encoder_files = set(file_hashes(root, root / manifest["encoder_dir"]))
    if actual_encoder_files != {name for name in assets if name.startswith(manifest["encoder_dir"] + "/")}:
        raise ValueError("Encoder asset list changed")
    calibration = read_json(root / manifest["calibration_file"])
    if calibration["thresholds"] != manifest["thresholds"] or calibration["temperatures"] != manifest["temperatures"]:
        raise ValueError("Calibration binding mismatch")
    return manifest


def train(root, device="cuda", resume=False, max_seconds=7200, config=None):
    """Train both candidates, publish only a development manifest, and stop."""
    import torch
    from .common import INTENTS, CATEGORIES
    from .english_v3_model import predictions
    root = Path(root)
    config = dict(config or DEFAULT_CONFIG)
    profile = read_json(root / "profile.json")
    if profile["profile"] != PROFILE:
        raise ValueError("Not an English recovery profile")
    if profile.get("stage") == "calibrated" or (root / "evaluation.json").exists():
        raise ValueError("Frozen/evaluated artifacts are immutable; choose a new development run")
    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA unavailable; use --device cpu explicitly")
    if max_seconds <= 0:
        raise ValueError("Training budget must be positive")
    torch.set_num_threads(config["cpu_threads"])
    rows = read_json(root / "data.json")
    validate_rows(rows)
    if json_hash(rows) != profile["data_hash"]:
        raise ValueError("Dataset changed since preparation")
    if read_json(root / "label_review.json")["data_sha256"] != digest(root / "data.json"):
        raise ValueError("Label review does not match data")
    validate_base_assets(root)
    reports, manifests = {}, {}
    for name in ("frozen", "finetuned"):
        print(json.dumps({"stage": "training", "candidate": name, "device": device}), flush=True)
        model, training = train_candidate(root, rows, config, device, name, resume, max_seconds / 2)
        calibration = calibrate(model, [r for r in rows if r["split"] == "calibration"])
        calibration_file = f"candidates/{name}/calibration.json"
        write_json(root / calibration_file, calibration)
        validation = [r for r in rows if r["split"] == "validation"]
        report = {"training": training, "validation": assess(validation, predictions(infer(model, validation), calibration["temperatures"]), calibration["thresholds"]),
                  "calibration": calibration["threshold_selection"]}
        encoder_dir, heads_file = f"candidates/{name}/encoder", f"candidates/{name}/heads.pt"
        files = file_hashes(root, root / encoder_dir)
        files.update({p: digest(root / p) for p in (heads_file, calibration_file, "data.json", "label_review.json")})
        manifest = {"version": 3, "backend": BACKEND, "profile": PROFILE, "candidate": name,
                    "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
                    "encoder_dir": encoder_dir, "heads_file": heads_file, "calibration_file": calibration_file,
                    "files": files, "labels": {"intent": list(INTENTS), "category": list(CATEGORIES), "query_action": list(QUERY_ACTIONS)},
                    "max_tokens": MAX_TOKENS, "epochs": training["epochs"],
                    "training_examples": sum(r["split"] == "train" for r in rows),
                    "training_fingerprint": training["fingerprint"], "data_sha256": digest(root / "data.json"),
                    "thresholds": calibration["thresholds"], "temperatures": calibration["temperatures"],
                    "policy_files": policy_hashes()}
        checked_manifest(root, manifest)
        manifests[name], reports[name] = manifest, report
        write_json(root / f"candidates/{name}/manifest.json", manifest)
        write_json(root / f"candidates/{name}/development.json", report)
        del model
        if device == "cuda":
            torch.cuda.empty_cache()
    selected = min(reports, key=lambda n: reports[n]["training"]["best_validation_loss"])
    write_json(root / "manifest.json", manifests[selected])
    result = {"profile": PROFILE, "selected_candidate": selected,
              "selection_rule": "Lowest uncalibrated validation masked NLL; frozen wins exact ties",
              "artifact_id": json_hash(manifests[selected]), "candidates": reports,
              "dataset": dataset_summary(rows), "fresh_test": False, "gold_reviewed": False,
              "passed": False, "activated": False,
              "next_step": "Return training_summary.json for review. Fresh reviewed holdout and full live RAG benchmark still required."}
    write_json(root / "training_summary.json", result)
    print(json.dumps(result, indent=2), flush=True)
    return result


def report(root):
    """Read bound development evidence without exposing a fresh holdout."""
    root = Path(root)
    manifest = checked_manifest(root, read_json(root / "manifest.json"))
    result = read_json(root / "training_summary.json")
    if result["artifact_id"] != json_hash(manifest):
        raise ValueError("Summary does not match artifact")
    if (root / "evaluation.json").exists():
        final = read_json(root / "evaluation.json")
        if final["artifact_id"] != json_hash(manifest):
            raise ValueError("Final evaluation does not match artifact")
        result = {**result, "final_evaluation": final}
    print(json.dumps(result, indent=2), flush=True)
    return result


def freeze(root, output):
    """Copy supported development calibration without inheriting activation evidence."""
    import shutil
    from tempfile import TemporaryDirectory
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("Choose a new separate frozen artifact directory")
    manifest = checked_manifest(root, read_json(root / "manifest.json"))
    if not manifest["thresholds"]["supported"]:
        raise ValueError("No supported calibration; retain development evidence and improve training")
    summary = read_json(root / "training_summary.json")
    if summary["artifact_id"] != json_hash(manifest):
        raise ValueError("Summary does not match artifact")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".v3-freeze-", dir=output.parent) as temp:
        staged = Path(temp) / "artifact"
        staged.mkdir()
        for name, checksum in manifest["files"].items():
            target = staged / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, target)
            if digest(target) != checksum:
                raise ValueError("Source changed while freezing")
        write_json(staged / "manifest.json", manifest)
        write_json(staged / "profile.json", {**read_json(root / "profile.json"), "stage": "calibrated"})
        write_json(staged / "training_summary.json", summary)
        checked_manifest(staged, manifest)
        staged.rename(output)
    print(json.dumps({"frozen": str(output), "artifact_id": json_hash(manifest), "activated": False}), flush=True)


def recalibrate(root, output):
    """Reuse authenticated weights in a new artifact when only calibration changes."""
    import shutil
    import torch
    from tempfile import TemporaryDirectory
    from .english_v3_model import load_router, predictions
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("Choose a new separate calibration artifact directory")
    manifest = checked_manifest(root, read_json(root / "manifest.json"))
    rows = read_json(root / "data.json")
    validate_rows(rows)
    old_summary = read_json(root / "training_summary.json")
    if old_summary["artifact_id"] != json_hash(manifest):
        raise ValueError("Summary does not match source artifact")
    threads = torch.get_num_threads()
    try:
        torch.set_num_threads(2)
        model = load_router(root, manifest)
        calibration = calibrate(model, [r for r in rows if r["split"] == "calibration"])
        validation = [r for r in rows if r["split"] == "validation"]
        validation_report = assess(validation, predictions(infer(model, validation), calibration["temperatures"]), calibration["thresholds"])
    finally:
        torch.set_num_threads(threads)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".v3-calibrate-", dir=output.parent) as temp:
        staged = Path(temp) / "artifact"
        staged.mkdir()
        for name, checksum in manifest["files"].items():
            target = staged / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, target)
            if digest(target) != checksum:
                raise ValueError("Source changed during calibration")
        write_json(staged / "source_manifest.json", manifest)
        write_json(staged / manifest["calibration_file"], calibration)
        derived = {**manifest, "thresholds": calibration["thresholds"], "temperatures": calibration["temperatures"],
                   "source_artifact_id": json_hash(manifest), "calibration_recipe_sha256": digest(__file__),
                   "files": {**manifest["files"], "source_manifest.json": digest(staged / "source_manifest.json"),
                             manifest["calibration_file"]: digest(staged / manifest["calibration_file"])}}
        name = manifest["candidate"]
        result = {**old_summary, "artifact_id": json_hash(derived), "source_artifact_id": json_hash(manifest),
                  "candidates": {name: {"training": old_summary["candidates"][name]["training"],
                                         "validation": validation_report, "calibration": calibration["threshold_selection"]}},
                  "fresh_test": False, "gold_reviewed": False, "passed": False, "activated": False}
        checked_manifest(staged, derived)
        write_json(staged / "manifest.json", derived)
        write_json(staged / "training_summary.json", result)
        write_json(staged / "profile.json", {**read_json(root / "profile.json"), "stage": "calibrated"})
        staged.rename(output)
    print(json.dumps(result, indent=2), flush=True)
    return result
