"""English recovery regressions exercise the same policy and artifacts as runtime."""
import pytest

from assistant.jev.common import accepted, preflight


def confident(intent="knowledge", **changes):
    value = {"intent": intent, "category": "admissions", "language": "english",
             "intent_probability": .999, "category_probability": .999,
             "english_probability": .999, "rewrite_probability": .001}
    return {**value, **changes}


def thresholds():
    return {"policy": "english-v2", "supported": True, "intent": .95,
            "category": .95, "english": .99, "rewrite": .05}


def test_confirmation_corpus_keeps_relatives_and_excludes_existing_data():
    from assistant.jev.english_audit import confirmation_rows, check_overlap
    from assistant.jev.english_data import development_rows
    rows = confirmation_rows()
    check_overlap(rows, development_rows())
    assert all(r["split"] == "calibration_confirmation" for r in rows)
    assert len({r["family"] for r in rows}) < len(rows)
    assert any(r["gold"]["language"] == "unsupported" for r in rows)
    with pytest.raises(ValueError, match="overlaps"):
        check_overlap(rows, rows[:1])


def test_confirmation_freezes_existing_sweep_and_preserves_strict_ties():
    from assistant.jev.english_audit import select_proposal
    strict = {"thresholds": thresholds(), "accepted": 23, "precision": 1., "critical_failures": 0}
    loose = {**strict, "thresholds": {**thresholds(), "category": .8}}
    chosen = select_proposal({"risk_coverage": [strict, loose,
        {**loose, "accepted": 40, "precision": .97}, {**loose, "accepted": 50, "critical_failures": 1}]})
    assert chosen == strict
    with pytest.raises(ValueError, match="No error-qualified"):
        select_proposal({"risk_coverage": [{**strict, "accepted": 0}]})


def test_confirmation_counts_wrong_category_and_critical_acceptance():
    from assistant.jev.english_audit import assess_confirmation
    rows = [{"id": "admission", "family": "a", "message": "What is the IIIT-NR application charge?",
             "gold": {"intent": "knowledge", "category": "admissions", "language": "english", "rewrite": False},
             "critical": False},
            {"id": "mixed", "family": "a", "message": "What is the IIIT-NR application charge, and write a song?",
             "gold": {"intent": "knowledge", "category": "admissions", "language": "english", "rewrite": True},
             "critical": True}]
    metrics, details = assess_confirmation(rows, [confident(category="academics"), confident()], thresholds())
    assert metrics["accepted"] == 2 and metrics["accepted_families"] == 1
    assert metrics["correct"] == 0 and metrics["critical_failures"] == 1
    assert metrics["accepted_error_ids"] == ["admission", "mixed"]
    assert details[1]["critical_failure"]
    assert not metrics["development_confirmation_passed"]


def test_confirmation_and_export_preserve_source_and_cannot_activate(tiny_prepared, monkeypatch):
    from assistant.jev import english_audit, english_model, english_training, english_freeze, evaluation
    from assistant.jev.common import digest, read_json, write_json
    english_training.train(tiny_prepared, "cpu", config={**english_training.DEFAULT_CONFIG, "epochs": 1, "cpu_threads": 1})
    source_files = {str(p.relative_to(tiny_prepared)): digest(p) for p in tiny_prepared.rglob("*") if p.is_file()}
    proposal = {"thresholds": thresholds(), "accepted": 23, "precision": 1., "critical_failures": 0}
    monkeypatch.setattr(english_audit, "select_proposal", lambda calibration: proposal)
    rows = english_audit.confirmation_rows()
    # Isolate export/evidence behavior from tiny randomly initialized fixture accuracy.
    fake_predictions = [confident(r["gold"]["intent"], category=r["gold"]["category"],
        language=r["gold"]["language"], rewrite_probability=float(r["gold"]["rewrite"])) for r in rows]
    monkeypatch.setattr(english_model, "predictions", lambda *args: fake_predictions)
    audit_dir = tiny_prepared.parent / (tiny_prepared.name + "-audit")
    result = english_audit.audit(tiny_prepared, audit_dir)
    assert result["development_confirmation_passed"] and not result["passed"]
    assert english_audit.audit(tiny_prepared, audit_dir) == result
    output = tiny_prepared.parent / (tiny_prepared.name + "-calibrated")
    summary = english_freeze.freeze(tiny_prepared, audit_dir, output)
    assert summary["artifact_id"] != summary["source_artifact_id"]
    derived = english_training.checked_manifest(output, read_json(output / "manifest.json"))
    assert derived["thresholds"]["supported"]
    assert read_json(output / "profile.json")["stage"] == "calibrated"
    assert read_json(output / derived["additional_calibration_file"]) == rows
    assert not (output / "activation.json").exists()
    with pytest.raises(ValueError, match="fresh reviewed holdout"):
        evaluation.activate(output)
    from assistant.jev.english_normalization import normalize_artifact, normalization_spec, check_normalization
    normalized = output.with_name(output.name + "-normalized")
    normalized_summary = normalize_artifact(output, normalized)
    normalized_manifest = read_json(normalized / "manifest.json")
    assert normalized_summary["artifact_id"] != summary["artifact_id"]
    assert normalized_manifest["input_normalization"] == normalization_spec()
    assert all(digest(normalized / name) == checksum for name, checksum in derived["files"].items())
    assert not (normalized / "activation.json").exists()
    with pytest.raises(ValueError, match="normalization binding"):
        check_normalization({**normalized_manifest, "input_normalization": {"policy": "unknown"}})
    assert source_files == {str(p.relative_to(tiny_prepared)): digest(p) for p in tiny_prepared.rglob("*") if p.is_file()}
    # Rehashing edited verdicts is insufficient: export recomputes from predictions.
    saved = read_json(audit_dir / "predictions.json")
    saved[0]["accepted"] = not saved[0]["accepted"]
    write_json(audit_dir / "predictions.json", saved)
    write_json(audit_dir / "report.json", {**result, "predictions_sha256": digest(audit_dir / "predictions.json")})
    with pytest.raises(ValueError, match="decisions"):
        english_freeze.freeze(tiny_prepared, audit_dir, output.with_name(output.name + "-bad"))
    assert not output.with_name(output.name + "-bad").exists()


def test_normalization_preserves_query_and_makes_encoder_aliases_equivalent(tiny_prepared):
    import torch
    from assistant.jev.english_model import EnglishRouter
    from assistant.jev.english_normalization import normalize_message, normalization_spec, load_inference_router
    base = EnglishRouter(tiny_prepared / "base_encoder")
    torch.save(base.heads.state_dict(), tiny_prepared / "heads.pt")
    manifest = {"encoder_dir": "base_encoder", "heads_file": "heads.pt",
                "input_normalization": normalization_spec()}
    model = load_inference_router(tiny_prepared, manifest)
    original = "What is the application charge at IIIT Naya Raipur?"
    canonical = "What is the application charge at IIIT-NR?"
    assert normalize_message(original) == canonical
    assert normalize_message("What is the charge at IIIT Hyderabad?") == "What is the charge at IIIT Hyderabad?"
    with torch.inference_mode():
        outputs = model([original, canonical])
    assert all(torch.equal(values[0], values[1]) for values in outputs.values())
    assert model.token_lengths([original, canonical])[0] == model.token_lengths([original, canonical])[1]
    assert accepted(original, confident(), thresholds()).query == original


def reviewed_holdout_fixture(manifest, checksum):
    """A test-only attestation exercises validation without certifying real model data."""
    from datetime import date
    from assistant.jev.common import json_hash
    return {"artifact_id": json_hash(manifest), "dataset_sha256": checksum,
            "reviewer": "Unit test reviewer", "reviewed_at": date.today().isoformat(),
            "notes": "Synthetic fixture only, not a real review.", "independent_human_review": True,
            "labels_checked": True, "family_disjointness_checked": True,
            "public_or_synthetic": True, "not_used_for_development": True}


def holdout_rows_fixture():
    from assistant.jev.english_audit import confirmation_rows
    return [{**r, "split": "test", "critical": r["critical"] or r["gold"]["rewrite"]}
            for r in confirmation_rows()]


def test_holdout_requires_bound_human_review_and_rejects_calibration_reuse():
    from assistant.jev.english_holdout import validate_holdout
    rows, manifest = holdout_rows_fixture(), {"fixture": True}
    review = reviewed_holdout_fixture(manifest, "fixture-sha")
    validate_holdout(rows, review, "fixture-sha", manifest, [])
    for change in ({"independent_human_review": False}, {"reviewer": "Codex"},
                   {"dataset_sha256": "changed"}, {"family_disjointness_checked": False}):
        with pytest.raises(ValueError, match="human review"):
            validate_holdout(rows, {**review, **change}, "fixture-sha", manifest, [])
    with pytest.raises(ValueError, match="overlaps"):
        validate_holdout(rows, review, "fixture-sha", manifest, rows[:1])
    with pytest.raises(ValueError, match="must cover"):
        validate_holdout(rows[:5], review, "fixture-sha", manifest, [])


def test_final_holdout_saves_evidence_and_reuse_cannot_pass(tiny_prepared, monkeypatch):
    import shutil
    from assistant.jev import english_training, english_model, english_holdout
    from assistant.jev.common import read_json, write_json, digest
    english_training.train(tiny_prepared, "cpu", config={**english_training.DEFAULT_CONFIG, "epochs": 1, "cpu_threads": 1})
    manifest = read_json(tiny_prepared / "manifest.json")
    # The toy fixture needs a supported policy; no production artifact is modified.
    manifest["thresholds"] = thresholds()
    cal_path = tiny_prepared / manifest["calibration_file"]
    write_json(cal_path, {**read_json(cal_path), "thresholds": thresholds()})
    manifest["files"][manifest["calibration_file"]] = digest(cal_path)
    write_json(tiny_prepared / "manifest.json", manifest)
    rows = holdout_rows_fixture()
    data_path, review_path = tiny_prepared.parent / "holdout.json", tiny_prepared.parent / "review.json"
    write_json(data_path, rows)
    write_json(review_path, reviewed_holdout_fixture(manifest, digest(data_path)))
    monkeypatch.setattr(english_model, "predictions", lambda *args: [confident(
        r["gold"]["intent"], category=r["gold"]["category"], language=r["gold"]["language"],
        rewrite_probability=float(r["gold"]["rewrite"])) for r in rows])
    result = english_holdout.evaluate_holdout(tiny_prepared, data_path, review_path)
    assert result["passed"] and result["fresh_test"] and result["accepted"] >= 100
    assert not (tiny_prepared / "activation.json").exists()
    for name, checksum in result["files"].items():
        assert digest(tiny_prepared / name) == checksum
    with pytest.raises(ValueError, match="already exists"):
        english_holdout.evaluate_holdout(tiny_prepared, data_path, review_path)
    assert len(read_json(tiny_prepared.parent / "english_holdout_exposures.json")) == 1
    second = tiny_prepared.parent / (tiny_prepared.name + "-second")
    shutil.copytree(tiny_prepared, second, ignore=shutil.ignore_patterns("evaluation.json", "final_holdout_*.json"))
    repeated = english_holdout.evaluate_holdout(second, data_path, review_path)
    assert not repeated["fresh_test"] and not repeated["passed"]
    assert repeated["test_exposures"] == 2


def test_optional_paraphrasing_does_not_require_rewrite():
    from assistant.jev.english_data import rewrite_required
    assert not rewrite_required("What is the IIIT-NR application charge?")
    assert rewrite_required("What is the IIIT-NR application charge?", mixed=True)
    assert rewrite_required("What is the application charge?")
    assert rewrite_required("What about that at IIIT-NR?", reference=True)


@pytest.mark.parametrize("text", ["IIIT-NR ki fees kya hai?", "IIIT-NR की फीस?",
                                   "Bonjour, quels sont les frais?", "IIIT-NR fees batao"])
def test_non_english_is_deferred_even_with_confident_predictions(text):
    assert accepted(text, confident(), thresholds()) is None


def test_unknown_latin_language_requires_positive_model_gate():
    assert accepted("IIIT-NR toelating informatie", confident(english_probability=.3), thresholds()) is None


def test_only_relevant_heads_gate_non_knowledge():
    assert accepted("Good to meet you", confident("smalltalk", category_probability=.1), thresholds())
    assert accepted("What is the IIIT-NR application charge?", confident(category_probability=.1), thresholds()) is None


def test_unsupported_calibration_always_defers():
    assert accepted("What is the IIIT-NR application charge?", confident(), {**thresholds(), "supported": False}) is None


@pytest.mark.parametrize("key", ["intent_probability", "category_probability", "english_probability", "rewrite_probability"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 1.1])
def test_invalid_probabilities_defer(key, value):
    assert accepted("What is the IIIT-NR application charge?", confident(**{key: value}), thresholds()) is None


def test_english_gate_does_not_reject_unicode_punctuation():
    assert preflight("What’s the tuition at IIIT-NR?") is None
    assert accepted("What’s the tuition at IIIT-NR?", confident(), thresholds())


def test_dataset_families_and_operational_targets():
    from assistant.jev.english_data import development_rows, validate_rows, dataset_summary
    from assistant.jev.common import live_case_overlaps
    rows = development_rows()
    validate_rows(rows)
    assert dataset_summary(rows)["languages"] == {"english": 400, "unsupported": 60}
    assert not live_case_overlaps(rows)
    assert all(r["split"] != "test" for r in rows)
    assert all(r["gold"]["rewrite"] for r in rows if r["kind"] == "mixed")
    assert not dataset_summary(rows)["independent_human_review"]
    families = {}
    for row in rows:
        families.setdefault(row["family"], []).append(row)
    for members in families.values():
        assert len({r["split"] for r in members}) == 1
        if any(r["kind"] == "mixed" for r in members):
            assert any(r["kind"] == "clean" for r in members)


@pytest.fixture
def tiny_prepared(tmp_path, request):
    """Real tiny local transformer exercises training/serialization without a download."""
    from transformers import BertConfig, BertModel, BertTokenizerFast
    from assistant.jev.common import write_json, json_hash, digest
    from assistant.jev.english_data import development_rows
    from assistant.jev.english_training import file_hashes
    if getattr(request, "param", False):
        tmp_path = tmp_path / ".cache" / "institute-assistant" / "english-v2"
        tmp_path.mkdir(parents=True)
    base = tmp_path / "base_encoder"
    base.mkdir()
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "what", "is", "the", "at", "iiit", "nr", "?", "-", "hello"]
    (base / "vocab.txt").write_text("\n".join(vocab) + "\n")
    BertTokenizerFast(vocab_file=str(base / "vocab.txt")).save_pretrained(base)
    BertModel(BertConfig(vocab_size=len(vocab), hidden_size=24, num_hidden_layers=1,
                        num_attention_heads=2, intermediate_size=32, max_position_embeddings=512)).save_pretrained(base)
    rows = development_rows()
    write_json(tmp_path / "data.json", rows)
    write_json(tmp_path / "profile.json", {"profile": "english-v2", "data_hash": json_hash(rows)})
    write_json(tmp_path / "label_review.json", {"data_sha256": digest(tmp_path / "data.json")})
    write_json(tmp_path / "base_assets.json", file_hashes(tmp_path, base))
    return tmp_path


def test_masked_labels_and_frozen_encoder(tiny_prepared):
    import torch
    from assistant.jev.english_model import EnglishRouter, targets, masked_loss
    from assistant.jev.english_data import development_rows
    model = EnglishRouter(tiny_prepared / "base_encoder", frozen=True).train()
    assert model.training and not model.encoder.training
    negative = next(r for r in development_rows() if r["kind"] == "reject")
    values, masks = targets([negative], "cpu")
    assert not masks["intent"].any() and not masks["category"].any() and not masks["rewrite"].any()
    assert masks["english"].all()
    loss = masked_loss(model([negative["message"]]), [negative])
    loss.backward()
    assert all(p.grad is None for p in model.encoder.parameters())
    assert model.heads["english"].weight.grad is not None
    assert model.heads["intent"].weight.grad is None


@pytest.mark.parametrize("tiny_prepared", [False, True], indirect=True, ids=["plain-directory", "cache-directory"])
def test_full_training_artifact_roundtrip_and_no_activation(tiny_prepared):
    from assistant.jev.english_training import train, DEFAULT_CONFIG
    from assistant.jev import runtime, evaluation
    from assistant.jev.common import read_json, write_json, json_hash
    config = {**DEFAULT_CONFIG, "epochs": 1, "cpu_threads": 1}
    result = train(tiny_prepared, "cpu", config=config)
    assert set(result["candidates"]) == {"frozen", "finetuned"}
    assert not result["activated"] and not result["fresh_test"]
    assert not (tiny_prepared / "test_exposures.json").exists()
    assert not (tiny_prepared / "evaluation.json").exists()
    signature = runtime.artifact_signature(tiny_prepared)
    manifest = runtime.checked_manifest(str(tiny_prepared), signature)
    prediction = runtime._worker_predict(str(tiny_prepared), signature, 1, "What is the IIIT-NR fee?")
    assert 0 <= prediction["english_probability"] <= 1
    assert runtime._worker_predict(str(tiny_prepared), signature, 1, "what " * 300) is None
    with pytest.raises(ValueError, match="development-only"):
        evaluation.activate(tiny_prepared)
    with pytest.raises(ValueError, match="Saved progress"):
        train(tiny_prepared, "cpu", config=config)
    again = train(tiny_prepared, "cpu", resume=True, config=config)
    assert again["selected_candidate"] == result["selected_candidate"]
    assert again["candidates"] == result["candidates"]
    # An encoder or tokenizer change invalidates the worker's cached validation.
    tokenizer_config = tiny_prepared / manifest["encoder_dir"] / "tokenizer_config.json"
    tokenizer_config.write_text(tokenizer_config.read_text() + "\n")
    with pytest.raises(ValueError, match="checksum"):
        runtime.checked_manifest(str(tiny_prepared), runtime.artifact_signature(tiny_prepared))


def test_hashes_include_cache_root_but_exclude_download_metadata(tmp_path):
    from assistant.jev.english_training import file_hashes
    from assistant.jev.common import digest
    root = tmp_path / ".cache" / "router"
    encoder = root / "encoder"
    metadata = encoder / ".cache" / "huggingface"
    metadata.mkdir(parents=True)
    weights = encoder / "model.safetensors"
    weights.write_bytes(b"model asset")
    (metadata / "download.lock").write_text("temporary metadata")
    assert file_hashes(root, encoder) == {"encoder/model.safetensors": digest(weights)}


def test_legacy_cache_repair_preserves_completed_checkpoint(tiny_prepared, monkeypatch):
    import torch
    from assistant.jev import english_training as training, english_recovery as recovery
    from assistant.jev.common import read_json, write_json, json_hash, digest
    from assistant.jev.english_policy import MODEL_ID, MODEL_REVISION
    config = {**training.DEFAULT_CONFIG, "epochs": 1, "cpu_threads": 1}
    torch.set_num_threads(1)
    rows = read_json(tiny_prepared / "data.json")
    training.train_candidate(tiny_prepared, rows, config, "cpu", "frozen", False, 600)
    original_base = read_json(tiny_prepared / "base_assets.json")
    # Stand in for authenticated upstream bytes, without network access in tests.
    monkeypatch.setattr(recovery, "PINNED_ASSET_SHA256",
                        {name.removeprefix("base_encoder/"): value for name, value in original_base.items()})
    profile = read_json(tiny_prepared / "profile.json")
    write_json(tiny_prepared / "profile.json", {**profile, "model_id": MODEL_ID, "model_revision": MODEL_REVISION})
    inputs = training.training_inputs(tiny_prepared, config, "frozen")
    checkpoint = tiny_prepared / "candidates/frozen/resume.pt"
    saved = torch.load(checkpoint, weights_only=True)
    saved["fingerprint"] = json_hash({**inputs, "base": {}, "recipe": recovery.LEGACY_RECIPE})
    training.atomic_save(saved, checkpoint)
    checkpoint_hash = digest(checkpoint)
    write_json(tiny_prepared / "base_assets.json", {})
    training.validate_base_assets(tiny_prepared)
    assert read_json(tiny_prepared / "base_assets.before-cache-fix.json") == {}
    assert read_json(tiny_prepared / "base_assets.json") == original_base
    model, report = training.train_candidate(tiny_prepared, rows, config, "cpu", "frozen", True, 600)
    assert report["epochs"] == 1 and digest(checkpoint) == checkpoint_hash
    best = torch.load(tiny_prepared / "candidates/frozen/best.pt", weights_only=True)
    assert all(torch.equal(value, model.state_dict()[name]) for name, value in best.items())
    with pytest.raises(ValueError, match="inputs changed"):
        training.train_candidate(tiny_prepared, rows, {**config, "head_lr": .02}, "cpu", "frozen", True, 600)


def test_empty_base_index_does_not_bless_unknown_assets(tiny_prepared):
    from assistant.jev import english_training as training
    from assistant.jev.common import read_json, write_json
    from assistant.jev.english_policy import MODEL_ID, MODEL_REVISION
    profile = read_json(tiny_prepared / "profile.json")
    write_json(tiny_prepared / "profile.json", {**profile, "model_id": MODEL_ID, "model_revision": MODEL_REVISION})
    write_json(tiny_prepared / "base_assets.json", {})
    with pytest.raises(ValueError, match="pinned pretrained snapshot"):
        training.validate_base_assets(tiny_prepared)
    assert read_json(tiny_prepared / "base_assets.json") == {}


def test_continuation_preserves_source_and_matches_uninterrupted_training(tiny_prepared):
    import shutil
    import torch
    from assistant.jev import english_training as training
    from assistant.jev.english_continuation import extend
    from assistant.jev.common import read_json, write_json, digest
    config = {**training.DEFAULT_CONFIG, "epochs": 1, "patience": 3, "cpu_threads": 1}
    profile = read_json(tiny_prepared / "profile.json")
    write_json(tiny_prepared / "profile.json", {**profile, "config": config})
    training.train(tiny_prepared, "cpu", config=config)
    source_hashes = training.file_hashes(tiny_prepared, tiny_prepared)
    destination = tiny_prepared.with_name(tiny_prepared.name + "-extended")
    record = extend(tiny_prepared, destination, epochs=2, patience=3)
    assert record["config"] == {**config, "epochs": 2}
    assert training.file_hashes(tiny_prepared, tiny_prepared) == source_hashes
    assert not any((destination / name).exists() for name in ("manifest.json", "activation.json", "training_summary.json", "evaluation.json"))
    assert digest(destination / "data.json") == digest(tiny_prepared / "data.json")
    assert (destination / "base_encoder/model.safetensors").stat().st_ino != (tiny_prepared / "base_encoder/model.safetensors").stat().st_ino
    for name in ("frozen", "finetuned"):
        old = torch.load(tiny_prepared / f"candidates/{name}/resume.pt", weights_only=True)
        new = torch.load(destination / f"candidates/{name}/resume.pt", weights_only=True)
        assert old["epoch"] == new["epoch"] == 1
        assert old["history"] == new["history"]
        assert old["fingerprint"] != new["fingerprint"]
        assert all(torch.equal(value, new["model"][key]) for key, value in old["model"].items())
        assert torch.equal(old["rng"], new["rng"])
    completed = training.train(destination, "cpu", resume=True, config=record["config"])
    assert all(r["training"]["epochs"] == 2 for r in completed["candidates"].values())
    uninterrupted = tiny_prepared.with_name(tiny_prepared.name + "-uninterrupted")
    uninterrupted.mkdir()
    for name in ("base_encoder", "data.json", "label_review.json", "base_assets.json"):
        src = tiny_prepared / name
        shutil.copytree(src, uninterrupted / name) if src.is_dir() else shutil.copy2(src, uninterrupted / name)
    training.train_candidate(uninterrupted, read_json(tiny_prepared / "data.json"), record["config"], "cpu", "finetuned", False, 600)
    expected = torch.load(uninterrupted / "candidates/finetuned/resume.pt", weights_only=True)["model"]
    actual = torch.load(destination / "candidates/finetuned/resume.pt", weights_only=True)["model"]
    assert all(torch.equal(value, actual[key]) for key, value in expected.items())
    assert training.file_hashes(tiny_prepared, tiny_prepared) == source_hashes
    with pytest.raises(ValueError, match="new, separate"):
        extend(tiny_prepared, destination, epochs=2, patience=3)
    with pytest.raises(ValueError, match="increase epochs"):
        extend(tiny_prepared, destination.with_name("invalid-limit"), epochs=1, patience=3)
    # Corruption of the checkpoint that would seed continuation cannot be hidden
    # by otherwise valid published encoder/head checksums.
    best_path = tiny_prepared / "candidates/frozen/best.pt"
    best = torch.load(best_path, weights_only=True)
    key = next(iter(best))
    best[key] = best[key] + 1
    torch.save(best, best_path)
    with pytest.raises(ValueError, match="best checkpoint"):
        extend(tiny_prepared, destination.with_name("corrupt-source"), epochs=2, patience=3)


def test_cli_training_honors_prepared_continuation_config(tiny_prepared, monkeypatch):
    import sys
    from unittest.mock import Mock
    import jev_pipeline
    from assistant.jev import english_training as training
    from assistant.jev.common import read_json, write_json
    config = {**training.DEFAULT_CONFIG, "epochs": 40, "patience": 5}
    write_json(tiny_prepared / "profile.json", {**read_json(tiny_prepared / "profile.json"), "config": config})
    runner = Mock()
    monkeypatch.setattr(training, "train", runner)
    monkeypatch.setattr(sys, "argv", ["jev_pipeline.py", "--artifacts", str(tiny_prepared), "train", "--device", "cuda", "--resume"])
    jev_pipeline.main()
    runner.assert_called_once_with(tiny_prepared, "cuda", True, 7200, config=config)


def test_resume_restores_exact_training_state(tiny_prepared, monkeypatch):
    import shutil
    import torch
    from assistant.jev import english_training as training
    from assistant.jev.common import read_json
    rows = read_json(tiny_prepared / "data.json")
    config = {**training.DEFAULT_CONFIG, "epochs": 2, "patience": 3, "cpu_threads": 1}
    torch.set_num_threads(1)
    full = tiny_prepared / "uninterrupted"
    full.mkdir()
    for name in ("base_encoder", "data.json", "label_review.json", "base_assets.json"):
        source = tiny_prepared / name
        shutil.copytree(source, full / name) if source.is_dir() else shutil.copy2(source, full / name)
    training.train_candidate(full, rows, config, "cpu", "finetuned", False, 600)
    save = training.atomic_save
    def interrupt_after_checkpoint(value, path):
        save(value, path)
        if path.name == "resume.pt":
            raise KeyboardInterrupt()
    monkeypatch.setattr(training, "atomic_save", interrupt_after_checkpoint)
    with pytest.raises(KeyboardInterrupt):
        training.train_candidate(tiny_prepared, rows, config, "cpu", "finetuned", False, 600)
    monkeypatch.setattr(training, "atomic_save", save)
    training.train_candidate(tiny_prepared, rows, config, "cpu", "finetuned", True, 600)
    def checkpoint(root):
        return torch.load(root / "candidates/finetuned/resume.pt", weights_only=True)
    resumed, continuous = checkpoint(tiny_prepared), checkpoint(full)
    assert resumed["epoch"] == continuous["epoch"] == 2
    assert all(torch.equal(value, continuous["model"][name]) for name, value in resumed["model"].items())
    with pytest.raises(ValueError, match="inputs changed"):
        training.train_candidate(tiny_prepared, rows, {**config, "head_lr": .02}, "cpu", "finetuned", True, 600)


def test_non_english_never_invokes_classifier(monkeypatch):
    from dataclasses import replace
    from unittest.mock import Mock
    from assistant.config import settings
    from assistant.jev import runtime
    predict = Mock()
    monkeypatch.setattr(runtime, "predict", predict)
    metrics = {}
    assert runtime.try_route("IIIT-NR ki fees kya hai?", [], {}, replace(settings, JEV_ROUTING_MODE="shadow"), metrics) is None
    assert metrics["router_fallback"] == "non_english" and metrics["classifier_calls"] == 0
    predict.assert_not_called()


def test_english_graph_fast_path_preserves_review(monkeypatch):
    from dataclasses import replace
    from unittest.mock import Mock
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from assistant import nodes
    from assistant.graph import build_graph
    from assistant.llm import GroundedAnswer, Evidence
    from assistant.retrieval import RetrievedChunk
    from assistant.jev import runtime
    manifest = {"backend": "minilm-english-v2", "thresholds": thresholds()}
    monkeypatch.setattr(runtime, "artifact_signature", lambda _: ())
    monkeypatch.setattr(runtime, "checked_manifest", lambda *args: manifest)
    monkeypatch.setattr(runtime, "activation_valid", lambda *args: True)
    monkeypatch.setattr(runtime, "predict", lambda *args: (confident(), None))
    monkeypatch.setattr(nodes, "settings", replace(nodes.settings, JEV_ROUTING_MODE="enabled"))
    # Reuse the integration fixture's retrieval contract, including exact citations.
    chunk = RetrievedChunk("Admission requires verified documents.", "public.txt", "admissions", 1, 0.)
    monkeypatch.setattr(nodes, "retrieve", lambda *args, **kwargs: [chunk])
    answer = GroundedAnswer(status="answered", answer="Admission requires verified documents.", evidence=[Evidence(source_id=1, quote="Admission requires verified documents.")])
    model = Mock(return_value=answer)
    monkeypatch.setattr(nodes, "invoke_json", model)
    result = build_graph(MemorySaver()).invoke({"messages": [HumanMessage(content="What are the admission documents at IIIT-NR?")]}, {"configurable": {"thread_id": "english-fast"}})
    assert result["rag_metrics"]["router_path"] == "open_jev"
    assert model.call_count == 2
    assert result["sources"] and result["response_status"] == "answered"
