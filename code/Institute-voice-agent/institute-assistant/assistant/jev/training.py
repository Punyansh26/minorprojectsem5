"""Bounded local teacher labeling and reproducible Open Jev training."""
from dataclasses import asdict
import json
from pathlib import Path
import random
import time

from .common import (BPETokenizer, LABELS, UPSTREAM, VERSION, digest, json_hash,
                     questions, read_json, write_json)
from .data import synthetic_rows


def prepare(root, limit=2000):
    root = Path(root)
    if (root / "data.json").exists():
        return read_json(root / "data.json")
    rows = synthetic_rows(limit=limit)
    write_json(root / "data.json", rows)
    write_json(root / "pilot.json", {"started_at": time.time(), "budget_seconds": 14400,
                                   "seed": 42, "max_examples": limit})
    print(json.dumps({"prepared": len(rows), "splits": {s: sum(r["split"] == s for r in rows)
          for s in ("train", "calibration", "test")}}), flush=True)
    return rows


def remaining(root):
    pilot = read_json(Path(root) / "pilot.json")
    return max(0, pilot["budget_seconds"] - (time.time() - pilot["started_at"]))


def label(root, settings):
    """Use the application's proven one-question router as the local teacher.

    Query differences determine rewrite-needed. Unsupported language examples
    retain their independently authored language label because the existing
    router's public response schema intentionally exposes only three languages.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from assistant.llm import invoke_json, RoutingDecision, model_identity
    from assistant.nodes import ROUTING_PROMPT
    root = Path(root)
    rows = read_json(root / "data.json")
    path = root / "teacher.json"
    labels = read_json(path) if path.exists() else {}
    bases = {r["id"].rsplit("-", 1)[0]: r for r in rows
             if r["id"].endswith("-0") and r["split"] != "test"}
    errors = 0
    started = time.perf_counter()
    for key, row in bases.items():
        if key in labels:
            continue
        if remaining(root) < 1800 + settings.OLLAMA_TIMEOUT_SECONDS:
            break
        try:
            result = invoke_json(RoutingDecision, ROUTING_PROMPT, {
                "message": row["message"], "history": [], "pending_action": {},
                "previous_language": "english", "today": datetime.now(ZoneInfo(settings.TIMEZONE)).date().isoformat(),
                "last_resolved_query": "", "timezone": settings.TIMEZONE}, provider="ollama")
            language = "unsupported" if row["gold"]["language"] == "unsupported" else result.language
            labels[key] = {"intent": result.intent, "category": result.category, "language": language,
                           "rewrite": language != "english" or (result.intent == "knowledge" and result.query.strip() != row["message"].strip())}
            write_json(path, labels)
            errors = 0
        except Exception as error:
            errors += 1
            print(json.dumps({"teacher_error": type(error).__name__}), flush=True)
            if errors >= 3:
                break
        if len(labels) % 10 == 0 or len(labels) == len(bases):
            print(json.dumps({"teacher_bases": len(labels), "total_bases": len(bases),
                              "elapsed_s": round(time.perf_counter() - started)}), flush=True)
    audit = {}
    for name in ("intent", "category", "language", "rewrite"):
        evaluated = [(row, labels[key]) for key, row in bases.items() if key in labels]
        audit[name] = sum(row["gold"][name] == value[name] for row, value in evaluated) / max(1, len(evaluated))
    write_json(root / "teacher_manifest.json", {"identity": model_identity(provider="ollama"),
               "method": "existing RoutingDecision call; one message per request; authored unsupported-language annotation",
               "prompt_sha256": json_hash(ROUTING_PROMPT), "labels_sha256": digest(path) if path.exists() else None,
               "bases": len(labels), "expected_bases": len(bases), "complete": set(bases) <= set(labels),
               "authored_agreement": audit, "target_smoothing": .05,
               "uncertainty": "label smoothing, not measured teacher probabilities"})
    return labels


def train(root, device="cpu"):
    import torch
    from tokenizers import Tokenizer, models, pre_tokenizers, trainers, decoders
    from .vendor.model import Jev, JevConfig, RLCDLoss
    root = Path(root)
    if remaining(root) <= 0:
        raise ValueError("Pilot time budget exhausted")
    random.seed(42)
    torch.manual_seed(42)
    torch.set_num_threads(4)  # This CLI is a separate process from speech/Ollama.
    rows = read_json(root / "data.json")
    teacher = read_json(root / "teacher.json")
    # Mirror the deterministic language override used by classify_intent_node.
    from assistant.dialogue import language_hint
    for row in rows:
        key = row["id"].rsplit("-", 1)[0]
        if row["id"].endswith("-0") and key in teacher:
            language = "unsupported" if row["gold"]["language"] == "unsupported" else (language_hint(row["message"]) or teacher[key]["language"])
            teacher[key]["language"] = language
            teacher[key]["rewrite"] = teacher[key]["rewrite"] or language != "english"
    write_json(root / "teacher.json", teacher)
    provenance = read_json(root / "teacher_manifest.json")
    provenance["labels_sha256"] = digest(root / "teacher.json")
    provenance["language_override"] = "same language_hint as runtime; authored unsupported-language annotation"
    bases = [r for r in rows if r["id"].endswith("-0") and r["id"].rsplit("-", 1)[0] in teacher]
    provenance["authored_agreement_after_language_override"] = {
        name: sum(r["gold"][name] == teacher[r["id"].rsplit("-", 1)[0]][name] for r in bases) / max(1, len(bases))
        for name in ("intent", "category", "language", "rewrite")}
    write_json(root / "teacher_manifest.json", provenance)
    training = [r for r in rows if r["split"] == "train" and r["id"].rsplit("-", 1)[0] in teacher]
    validation = [r for r in rows if r["split"] == "calibration"]
    if len(training) < 64 or not validation:
        raise ValueError("Insufficient labeled training/calibration data")
    token_path = root / "tokenizer.json"
    if not token_path.exists():
        tok = Tokenizer(models.BPE(unk_token="[UNK]"))
        tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
        tok.decoder = decoders.ByteLevel()
        trainer = trainers.BpeTrainer(vocab_size=8192, min_frequency=2,
                    special_tokens=["[PAD]", "[UNK]"], initial_alphabet=pre_tokenizers.ByteLevel.alphabet())
        tok.train_from_iterator((r["message"] for r in training), trainer)
        tok.save(str(token_path))
    tokenizer = BPETokenizer(token_path)
    cfg = JevConfig(vocab_size=8192, d_model=128, n_heads=4, d_ff=512,
                    n_state_layers=3, n_readout_layers=4, max_state_len=512)
    model = Jev(cfg, tokenizer).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)
    loss_fn = RLCDLoss()
    qs = questions()
    best, stale, first_epoch = float("inf"), 0, 0
    history = []
    fingerprint = json_hash({"data": digest(root / "data.json"), "teacher": digest(root / "teacher.json"),
                             "tokenizer": digest(token_path), "config": asdict(cfg)})
    resume_path = root / "resume.pt"
    if resume_path.exists():
        resume = torch.load(resume_path, map_location=device, weights_only=True)
        if resume["fingerprint"] != fingerprint:
            raise ValueError("Training inputs changed since saved progress")
        model.load_state_dict(resume["model"])
        optimizer.load_state_dict(resume["optimizer"])
        first_epoch, best, stale, history = resume["epoch"] + 1, resume["best"], resume["stale"], resume["history"]
        torch.set_rng_state(resume["rng"].cpu())
    for epoch in range(first_epoch, 30):
        if remaining(root) <= 0 or stale >= 5:
            break
        training.sort(key=lambda row: row["id"])
        random.Random(42 + epoch).shuffle(training)
        model.train()
        losses = []
        for offset in range(0, len(training), 16):
            if remaining(root) <= 0:
                break
            batch = training[offset:offset + 16]
            targets = []
            for index, name in enumerate(("intent", "category", "language", "rewrite")):
                target = torch.full((len(batch), len(LABELS[index])), .05 / (len(LABELS[index]) - 1), device=device)
                for j, row in enumerate(batch):
                    label_value = teacher[row["id"].rsplit("-", 1)[0]][name]
                    target[j, LABELS[index].index(label_value)] = .95
                targets.append(target)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model, [r["message"] for r in batch], qs, targets)
            if not torch.isfinite(loss):
                raise ValueError("Non-finite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(loss.item())
        if remaining(root) <= 0:
            break
        model.eval()
        validation_loss = 0
        with torch.inference_mode():
            for offset in range(0, len(validation), 16):
                batch = validation[offset:offset + 16]
                outputs = model.logits([r["message"] for r in batch], qs)
                for i, name in enumerate(("intent", "category", "language", "rewrite")):
                    ids = torch.tensor([LABELS[i].index(r["gold"][name]) for r in batch], device=device)
                    validation_loss -= outputs[i][0].gather(1, ids[:, None]).log().sum().item()
        validation_loss /= len(validation) * 4
        if validation_loss < best:
            best, stale = validation_loss, 0
            tmp = root / "model.tmp.pt"
            torch.save(model.state_dict(), tmp)
            tmp.replace(root / "model.pt")
        else:
            stale += 1
        entry = {"epoch": epoch + 1, "loss": sum(losses) / max(len(losses), 1), "validation_loss": validation_loss,
                 "remaining_s": round(remaining(root))}
        history.append(entry)
        torch.save({"fingerprint": fingerprint, "model": model.state_dict(), "optimizer": optimizer.state_dict(),
                    "epoch": epoch, "best": best, "stale": stale, "history": history, "rng": torch.get_rng_state()}, resume_path)
        write_json(root / "training.json", history)
        print(json.dumps(entry), flush=True)
    if not (root / "model.pt").exists():
        raise ValueError("No trained checkpoint produced within budget")
    manifest = {"version": VERSION, "upstream": UPSTREAM, "config": asdict(cfg), "labels": LABELS,
                "model_sha256": digest(root / "model.pt"), "tokenizer_sha256": digest(token_path),
                "data_sha256": digest(root / "data.json"), "teacher_sha256": digest(root / "teacher.json"),
                "training_examples": len(training), "epochs": len(history), "seed": 42,
                "thresholds": {"probability": 1.0, "confidence": 1.0, "rewrite": 0.0},
                "split_hashes": {s: json_hash([r for r in rows if r["split"] == s]) for s in ("train", "calibration", "test")}}
    write_json(root / "manifest.json", manifest)
    return manifest
