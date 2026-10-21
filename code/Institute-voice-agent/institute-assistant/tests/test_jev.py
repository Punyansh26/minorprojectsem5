"""Local routing policy, artifact integrity, isolation and graph regression checks."""
from concurrent.futures import Future
from dataclasses import replace
from threading import Semaphore
from unittest.mock import Mock

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
import pytest

from assistant import nodes
from assistant.config import settings
from assistant.graph import build_graph
from assistant.jev import runtime
from assistant.jev.common import (BPETokenizer, LABELS, UPSTREAM, VERSION, accepted,
                                  digest, json_hash, preflight, write_json)
from assistant.jev.data import synthetic_rows
from assistant.jev.evaluation import assess, benchmark_passed, quality_passed
from assistant.llm import RoutingDecision, GroundedAnswer, Evidence
from assistant.retrieval import RetrievedChunk

THRESHOLDS = {"probability": .95, "confidence": .8, "rewrite": .05}
QUESTION = "What are the admission documents at IIIT Naya Raipur?"


def prediction(intent="knowledge", **updates):
    result = {"intent": intent, "category": "admissions", "language": "english", "rewrite_probability": .01}
    for name in ("intent", "category", "language"):
        result.update({name + "_probability": .99, name + "_confidence": .9})
    return {**result, **updates}


@pytest.mark.parametrize("message,kwargs,reason", [
    ("", {}, "input_size"), ("x" * 2001, {}, "input_size"),
    (QUESTION, {"history": [{"role": "user", "text": "hello"}]}, "conversation_history"),
    (QUESTION, {"pending": {"kind": "reminder"}}, "pending_action"),
    ("Remind me about IIIT fees", {}, "action_language"),
    ("IIIT की याद दिलाओ", {}, "action_language"),
])
def test_preflight(message, kwargs, reason):
    assert preflight(message, **kwargs) == reason


def test_only_standalone_named_english_knowledge_can_skip_rewrite():
    decision = accepted(QUESTION, prediction(), THRESHOLDS)
    assert decision.query == QUESTION
    assert accepted("What about that?", prediction(rewrite_probability=.99), THRESHOLDS) is None
    assert accepted("What are the fees?", prediction(), THRESHOLDS) is None
    assert accepted("IIIT Naya Raipur ki fees kya hai?", prediction(language="hinglish"), THRESHOLDS) is None
    assert accepted("IIIT Naya Raipur की फीस?", prediction(), THRESHOLDS) is None
    assert accepted(QUESTION + " And write a game.", prediction(rewrite_probability=.8), THRESHOLDS) is None


@pytest.mark.parametrize("intent", ["handoff", "reminder", "cancel"])
def test_classifier_cannot_authorize_actions(intent):
    assert accepted(QUESTION, prediction(intent=intent), THRESHOLDS) is None


@pytest.mark.parametrize("updates", [{"intent_probability": .5}, {"language_confidence": .2},
    {"category_probability": float("nan")}, {"intent_confidence": float("inf")}, {"intent_confidence": 1.1}])
def test_uncertainty_and_invalid_numbers_abstain(updates):
    assert accepted(QUESTION, prediction(**updates), THRESHOLDS) is None


def test_families_and_translations_never_cross_splits():
    rows = synthetic_rows()
    assert 1000 <= len(rows) <= 2000
    groups = {}
    for row in rows:
        groups.setdefault(row["family"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in groups.values())
    assert len({r["id"] for r in rows}) == len(rows)
    assert all(any(r["split"] == split and r["gold"]["language"] == language for r in rows)
               for split in ("train", "calibration", "test") for language in LABELS[2])


def test_low_coverage_high_precision_is_not_sufficient():
    report = {"accepted": 99, "precision": 1., "critical_failures": 0, "gold_reviewed": True, "family_overlap": False, "fresh_test": True}
    assert not quality_passed(report)
    report["accepted"] = 100
    assert quality_passed(report)
    report["critical_failures"] = 1
    assert not quality_passed(report)
    assert not benchmark_passed({"pairs": 24, "coverage": 1, "median_improvement": .5,
                                 "p95_ratio": .8, "new_behavior_failures": 0})


@pytest.fixture
def fake_artifact(monkeypatch):
    manifest = {"thresholds": THRESHOLDS}
    monkeypatch.setattr(runtime, "artifact_signature", lambda _: ())
    monkeypatch.setattr(runtime, "checked_manifest", lambda *args: manifest)
    monkeypatch.setattr(runtime, "activation_valid", lambda *args: True)
    classify = Mock(return_value=(prediction(), None))
    monkeypatch.setattr(runtime, "predict", classify)
    return classify


@pytest.mark.parametrize("mode,accepts", [("off", False), ("shadow", False), ("enabled", True)])
def test_modes(mode, accepts, fake_artifact):
    metrics = {}
    decision = runtime.try_route(QUESTION, [], {}, replace(settings, JEV_ROUTING_MODE=mode), metrics)
    assert (decision is not None) == accepts
    assert metrics["classifier_calls"] == (0 if mode == "off" else 1)
    assert ("classifier" in metrics.get("stage_ms", {})) == (mode != "off")


def test_enabled_requires_certificate(monkeypatch, fake_artifact):
    monkeypatch.setattr(runtime, "activation_valid", lambda *args: False)
    metrics = {}
    assert runtime.try_route(QUESTION, [], {}, replace(settings, JEV_ROUTING_MODE="enabled"), metrics) is None
    assert metrics["router_fallback"] == "not_activated"
    fake_artifact.assert_not_called()


def test_missing_artifacts_fall_back_without_sensitive_logging(tmp_path):
    metrics = {}
    assert runtime.try_route(QUESTION, [], {}, replace(settings, JEV_ROUTING_MODE="enabled", JEV_ARTIFACT_DIR=str(tmp_path)), metrics) is None
    assert metrics["router_fallback"] == "artifact_missing"
    assert QUESTION not in str(metrics)


def test_worker_queue_is_bounded_and_timeout_does_not_release_capacity_early(monkeypatch):
    semaphore = Semaphore(1)
    future = Future()
    pool = Mock()
    pool.submit.return_value = future
    monkeypatch.setattr(runtime, "_POOL", pool)
    monkeypatch.setattr(runtime, "_CAPACITY", semaphore)
    assert runtime.predict("unused", (), 1, .001, QUESTION) == (None, "timeout")
    assert runtime.predict("unused", (), 1, .001, QUESTION) == (None, "busy")
    future.set_result(prediction())
    assert runtime.predict("unused", (), 1, .01, QUESTION)[0] == prediction()


def test_graph_skip_routing_preserves_generation_review_citations_and_followup(monkeypatch, fake_artifact):
    monkeypatch.setattr(nodes, "settings", replace(nodes.settings, JEV_ROUTING_MODE="enabled"))
    source = RetrievedChunk("Bring your Class 12 marksheet.", "admissions/reporting.txt", "admissions", 2, .2)
    answer = GroundedAnswer(status="answered", answer="Bring your Class 12 marksheet.",
                            evidence=[Evidence(source_id=1, quote=source.text)])
    model = Mock(side_effect=[answer, answer, RoutingDecision(intent="knowledge", query="IIIT Naya Raipur CG admission documents"), answer, answer])
    monkeypatch.setattr(nodes, "invoke_json", model)
    monkeypatch.setattr(nodes, "retrieve", Mock(return_value=[source]))
    ticket = Mock(side_effect=AssertionError("No ticket expected"))
    monkeypatch.setattr(nodes, "create_ticket", ticket)
    graph = build_graph(MemorySaver())
    config = {"configurable": {"thread_id": "jev-test", "llm_provider": "groq"}}
    result = graph.invoke({"messages": [HumanMessage(content=QUESTION)]}, config)
    assert result["response_status"] == "answered" and result["sources"]
    assert result["rag_metrics"]["model_calls"] == 2
    assert result["rag_metrics"]["provider"] == "groq"
    assert all(call.args[0] is GroundedAnswer for call in model.call_args_list)
    result = graph.invoke({"messages": [HumanMessage(content="And for CG?")]}, config)
    assert result["rag_metrics"]["router_fallback"] == "conversation_history"
    assert result["search_query"] == "IIIT Naya Raipur CG admission documents"
    assert fake_artifact.call_count == 1
    ticket.assert_not_called()


def test_shadow_keeps_selected_llm_and_compares_intents(monkeypatch, fake_artifact):
    monkeypatch.setattr(nodes, "settings", replace(nodes.settings, JEV_ROUTING_MODE="shadow"))
    model = Mock(return_value=RoutingDecision(intent="out_of_scope"))
    monkeypatch.setattr(nodes, "invoke_json", model)
    graph = build_graph(MemorySaver())
    result = graph.invoke({"messages": [HumanMessage(content=QUESTION)]}, {"configurable": {"thread_id": "shadow"}})
    assert result["response_status"] == "out_of_scope"
    assert result["rag_metrics"]["router_shadow_agrees"] is False
    assert model.call_count == 1


def test_real_artifact_roundtrip_tokenizer_and_checksum(tmp_path):
    import torch
    from tokenizers import Tokenizer, models, pre_tokenizers, trainers
    from dataclasses import asdict
    from assistant.jev.vendor.model import Jev, JevConfig
    tokenizer = Tokenizer(models.BPE(unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.train_from_iterator([QUESTION, "हिंदी प्रश्न"], trainers.BpeTrainer(vocab_size=300,
        special_tokens=["[PAD]", "[UNK]"], initial_alphabet=pre_tokenizers.ByteLevel.alphabet()))
    tokenizer.save(str(tmp_path / "tokenizer.json"))
    bpe = BPETokenizer(tmp_path / "tokenizer.json")
    assert 1 not in bpe.encode("अनदेखा शब्द 🦉", 512)
    cfg = JevConfig(vocab_size=8192, d_model=16, n_heads=2, d_ff=32, n_state_layers=1, n_readout_layers=1, max_state_len=512)
    torch.save(Jev(cfg, bpe).state_dict(), tmp_path / "model.pt")
    manifest = {"version": VERSION, "upstream": UPSTREAM, "labels": LABELS, "training_examples": 64, "epochs": 1,
                "config": asdict(cfg), "thresholds": THRESHOLDS,
                "model_sha256": digest(tmp_path / "model.pt"), "tokenizer_sha256": digest(tmp_path / "tokenizer.json")}
    write_json(tmp_path / "manifest.json", manifest)
    checked = runtime.checked_manifest(str(tmp_path), runtime.artifact_signature(tmp_path))
    assert checked["config"]["d_model"] == 16
    result = runtime._worker_predict(str(tmp_path), runtime.artifact_signature(tmp_path), 1, QUESTION)
    assert result["intent"] in LABELS[0]
    assert runtime._worker_predict(str(tmp_path), runtime.artifact_signature(tmp_path), 1, "x " * 1000) is None
    with (tmp_path / "model.pt").open("ab") as stream:
        stream.write(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        runtime.checked_manifest(str(tmp_path), runtime.artifact_signature(tmp_path))


def test_unsupported_language_never_becomes_a_routing_decision():
    assert accepted(QUESTION, prediction(language="unsupported"), THRESHOLDS) is None


def test_mixed_topic_error_blocks_quality_gate():
    row = {"message": QUESTION + " And tell me whale facts.", "gold": {
        "intent": "knowledge", "category": "admissions", "language": "english", "rewrite": True}, "critical": True}
    result = assess([row], [prediction()], THRESHOLDS)
    assert result["critical_failures"] == 1 and result["precision"] == 0


def test_activation_binds_exact_artifact_and_reports(tmp_path):
    manifest = {"test": "identity"}
    identity = json_hash(manifest)
    quality = {"artifact_id": identity, "accepted": 100, "precision": .99, "critical_failures": 0,
               "gold_reviewed": True, "family_overlap": False, "fresh_test": True}
    benchmark = {"artifact_id": identity, "pairs": 24, "coverage": .5, "median_improvement": .2,
                 "p95_ratio": .9, "new_behavior_failures": 0, "source_review_passed": True, "live_suite_complete": True}
    write_json(tmp_path / "evaluation.json", quality)
    write_json(tmp_path / "benchmark.json", benchmark)
    write_json(tmp_path / "activation.json", {"artifact_id": identity,
               "evaluation_sha256": digest(tmp_path / "evaluation.json"),
               "benchmark_sha256": digest(tmp_path / "benchmark.json")})
    assert runtime.activation_valid(tmp_path, manifest)
    assert not runtime.activation_valid(tmp_path, {"test": "different thresholds"})
    benchmark["new_behavior_failures"] = 1
    write_json(tmp_path / "benchmark.json", benchmark)
    assert not runtime.activation_valid(tmp_path, manifest)


def test_bad_tokenizer_padding_is_rejected(tmp_path):
    from tokenizers import Tokenizer, models
    tokenizer = Tokenizer(models.WordLevel({"[UNK]": 0, "[PAD]": 1}, unk_token="[UNK]"))
    tokenizer.save(str(tmp_path / "tokenizer.json"))
    with pytest.raises(ValueError, match="padding mismatch"):
        BPETokenizer(tmp_path / "tokenizer.json")


def test_failed_classifier_uses_existing_router(monkeypatch, fake_artifact):
    fake_artifact.return_value = (None, "inference_error")
    monkeypatch.setattr(nodes, "settings", replace(nodes.settings, JEV_ROUTING_MODE="enabled"))
    model = Mock(return_value=RoutingDecision(intent="clarification"))
    monkeypatch.setattr(nodes, "invoke_json", model)
    result = build_graph(MemorySaver()).invoke({"messages": [HumanMessage(content=QUESTION)]},
                                              {"configurable": {"thread_id": "failure", "llm_provider": "groq"}})
    assert result["response_status"] == "clarification"
    assert result["rag_metrics"]["router_fallback"] == "inference_error"
    assert result["rag_metrics"]["provider"] == "groq"
    assert model.call_count == 1


def test_quick_benchmark_cannot_activate_even_with_good_timings():
    report = {"pairs": 24, "coverage": .8, "median_improvement": .3, "p95_ratio": .8,
              "new_behavior_failures": 0, "source_review_passed": True, "live_suite_complete": False}
    assert not benchmark_passed(report)
    report["live_suite_complete"] = True
    assert benchmark_passed(report)


def test_dead_worker_is_recreated_on_next_request(monkeypatch):
    from concurrent.futures.process import BrokenProcessPool
    old_pool = Mock()
    old_pool.submit.side_effect = BrokenProcessPool("worker exited")
    monkeypatch.setattr(runtime, "_POOL", old_pool)
    monkeypatch.setattr(runtime, "_CAPACITY", Semaphore(1))
    assert runtime.predict("unused", (), 1, .01, QUESTION) == (None, "inference_error")
    assert runtime._POOL is None
    old_pool.shutdown.assert_called_once_with(wait=False, cancel_futures=True)


def test_teacher_uses_existing_router_and_never_labels_test_split(tmp_path, monkeypatch):
    import time
    from assistant import llm
    from assistant.jev.training import label
    rows = [{"id": "train-0-0", "family": "train", "split": "train", "message": QUESTION,
             "gold": {"intent": "knowledge", "category": "admissions", "language": "english", "rewrite": False}},
            {"id": "heldout-0-0", "family": "heldout", "split": "test", "message": "Held-out public question",
             "gold": {"intent": "knowledge", "category": "general", "language": "english", "rewrite": False}}]
    write_json(tmp_path / "data.json", rows)
    write_json(tmp_path / "pilot.json", {"started_at": time.time(), "budget_seconds": 14400})
    invoke = Mock(return_value=RoutingDecision(intent="knowledge", category="admissions", query=QUESTION))
    monkeypatch.setattr(llm, "invoke_json", invoke)
    result = label(tmp_path, settings)
    assert set(result) == {"train-0"}
    assert result["train-0"]["rewrite"] is False
    assert invoke.call_count == 1
    assert invoke.call_args.kwargs == {"provider": "ollama"}
    assert invoke.call_args.args[2]["message"] == QUESTION
    # Saved labels resume without another model request.
    label(tmp_path, settings)
    assert invoke.call_count == 1


def test_reused_test_set_cannot_certify_a_model():
    report = {"accepted": 200, "precision": .995, "critical_failures": 0,
              "gold_reviewed": True, "family_overlap": False, "fresh_test": False}
    assert not quality_passed(report)


def test_preparation_reserves_existing_live_evaluation_families():
    from assistant.jev.common import live_case_overlaps, normalized_message
    rows = synthetic_rows()
    assert not live_case_overlaps(rows)
    assert not any("how much is it" in normalized_message(r["message"]) for r in rows)


def test_latency_summary_counts_followup_turns_individually():
    from assistant.jev.evaluation import summarize_pairs
    def result(seconds, accepted=False):
        return {"turns": [{"seconds": value, "metrics": {"model_calls": 2,
                "router_path": "open_jev" if accepted else "llm"}} for value in seconds], "behavior_passed": True}
    pairs = [{"modes": {"off": result([10]), "enabled": result([9], True)}},
             {"modes": {"off": result([20, 30]), "enabled": result([18, 27])}}]
    report = summarize_pairs(pairs)
    assert report["pairs"] == 2 and report["turn_pairs"] == 3
    assert report["baseline_p50_seconds"] == 20
    assert report["candidate_p50_seconds"] == 18
    assert report["coverage"] == pytest.approx(1 / 3)
    assert report["new_behavior_failures"] == 0
