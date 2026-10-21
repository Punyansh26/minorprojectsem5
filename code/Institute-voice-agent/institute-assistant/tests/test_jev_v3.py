"""Exercise v3's real query boundary and ensure speed never skips grounding."""
from dataclasses import replace
from unittest.mock import Mock

import pytest

from assistant.jev.english_v3_policy import (
    DEFAULT_THRESHOLDS, LocalRoute, exact_followup, route, scoped_query)

THRESHOLDS = {**DEFAULT_THRESHOLDS, "supported": True, "intent": .9, "category": .9,
              "query_action": .9}
QUESTION = "Are visiting students allowed to use the library at IIIT-NR?"
RANK = "What are the opening and closing ranks for 2025 JoSAA round 3 ECE SC All India Gender-Neutral at IIIT-NR?"


def prediction(**updates):
    return {"intent": "knowledge", "category": "general", "language": "english",
            "intent_probability": .999, "category_probability": .999,
            "english_probability": .999, "query_action": "copy", "query_action_probability": .999, **updates}


def test_copy_preserves_every_character_and_category_can_abstain():
    result, reason = route(QUESTION, prediction(category_probability=.45), THRESHOLDS)
    assert reason is None and result.decision.query == QUESTION
    assert result.retrieval_preference is None


def test_scope_only_adds_institute_without_inventing_dimensions():
    question = "Which documents prove income for a tuition concession?"
    result, reason = route(question, prediction(query_action="scope_institute"), THRESHOLDS)
    assert reason is None and result.decision.query == scoped_query(question)
    assert "2026" not in result.decision.query


def test_public_scheme_keeps_its_general_scope():
    question = "Does PM Vidyalaxmi require a guarantor?"
    result, _ = route(question, prediction(), THRESHOLDS)
    assert result.decision.query == question
    assert route(question, prediction(query_action="scope_institute"), THRESHOLDS)[0] is None


@pytest.mark.parametrize("message,changes", [
    ("What does that cost at IIIT-NR?", {}),
    ("What are the hostel charges at IIT Madras?", {"query_action": "scope_institute"}),
    ("Compare IIIT-NR and IIIT Hyderabad fees", {}),
    ("IIIT-NR mein hostel kaise milta hai?", {}),
    ("IIIT-NR में हॉस्टल कैसे मिलेगा?", {}),
    ("Remind me about the IIIT-NR payment tomorrow", {}),
    (QUESTION + " and write a poem", {"query_action": "defer"}),
    ("Why does seawater taste salty?", {"query_action": "scope_institute"}),
])
def test_unsafe_preparation_defers(message, changes):
    assert route(message, prediction(**changes), THRESHOLDS)[0] is None


@pytest.mark.parametrize("key", ["intent_probability", "category_probability", "english_probability", "query_action_probability"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, 2, True])
def test_invalid_probabilities_never_authorize_routes(key, bad):
    assert route(QUESTION, prediction(**{key: bad}), THRESHOLDS)[0] is None


def test_history_requires_explicit_standalone_question():
    history = [{"role": "assistant", "resolved_query": RANK}]
    assert route(QUESTION, prediction(), THRESHOLDS, history)[0]
    assert not route("What are the charges?", prediction(query_action="scope_institute"), THRESHOLDS, history)[0]
    assert not route("How much is that?", prediction(intent="clarification"), THRESHOLDS, history)[0]
    assert not route(QUESTION, prediction(), THRESHOLDS, history, {"kind": "handoff"})[0]


def test_exact_followup_preserves_scope_and_rejects_ambiguous_or_non_english():
    from assistant.kb.structured import rank_filters
    history = [{"role": "assistant", "resolved_query": RANK}]
    local = exact_followup("And for ST?", history)
    before = rank_filters(RANK)
    assert rank_filters(local.decision.query) == {**before, "seat_category": "ST"}
    second = exact_followup("And round 4?", [{"role": "assistant", "resolved_query": local.decision.query}])
    assert rank_filters(second.decision.query) == {**before, "seat_category": "ST", "round": "4"}
    for message in ("Aur ST ke liye?", "और एसटी के लिए?", "And for ST at another college?", "And for that one?"):
        assert exact_followup(message, history) is None
    assert exact_followup("And for ST?", [{"role": "assistant", "resolved_query": "SC rank?"}]) is None
    assert exact_followup("And for ST?", history, {"kind": "handoff"}) is None


def test_dataset_groups_named_unnamed_and_mixed_relatives():
    from assistant.jev.english_v3_data import development_rows, validate_rows
    rows = development_rows()
    validate_rows(rows)
    tuition = [r for r in rows if r["family"] == "v3-ad_tuition"]
    assert len(tuition) >= 3 and len({r["split"] for r in tuition}) == 1
    assert {r["gold"]["query_action"] for r in tuition} == {"copy", "scope_institute", "defer"}


def test_assessment_scores_query_strategy_and_reports_category_abstention():
    from assistant.jev.english_v3_training import assess
    row = {"id": "one", "family": "one", "message": QUESTION, "critical": False,
           "gold": {"intent": "knowledge", "category": "hostel", "language": "english",
                    "query_action": "copy", "rewrite": False}}
    report = assess([row], [prediction(category_probability=.1)], THRESHOLDS)
    assert report["precision"] == 1 and report["category_abstained"] == 1
    assert report["knowledge_category_accuracy"] == 0
    assert assess([row], [prediction()], THRESHOLDS)["precision"] == 0
    unsafe = {**row, "critical": True, "gold": {**row["gold"], "query_action": "defer", "rewrite": True}}
    assert assess([unsafe], [prediction(category_probability=.1)], THRESHOLDS)["critical_failures"] == 1


def test_graph_local_route_uses_neutral_retrieval_and_still_reviews(monkeypatch):
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver
    from assistant import nodes
    from assistant.graph import build_graph
    from assistant.llm import GroundedAnswer, Evidence
    from assistant.retrieval import RetrievedChunk
    local, _ = route(QUESTION, prediction(category_probability=.4), THRESHOLDS)
    monkeypatch.setattr(nodes, "try_route", lambda *args: local)
    retrieve = Mock(return_value=[RetrievedChunk("Visiting students may use the reading room.", "library.pdf", "general", 1, .1)])
    monkeypatch.setattr(nodes, "retrieve", retrieve)
    answer = GroundedAnswer(status="answered", answer="Visiting students may use the reading room.",
                            evidence=[Evidence(source_id=1, quote="Visiting students may use the reading room.")])
    invoke = Mock(return_value=answer)
    monkeypatch.setattr(nodes, "invoke_json", invoke)
    result = build_graph(MemorySaver()).invoke({"messages": [HumanMessage(content=QUESTION)]},
                                             {"configurable": {"thread_id": "v3"}})
    assert result["response_status"] == "answered" and result["sources"]
    assert invoke.call_count == 2 and result["rag_metrics"]["model_calls"] == 2
    assert retrieve.call_args.kwargs["preferred_category"] is None


def test_runtime_exact_followup_requires_activation_and_preserves_shadow(monkeypatch):
    from assistant.jev import runtime
    from assistant.config import settings
    monkeypatch.setattr(runtime, "artifact_signature", lambda *_: ())
    monkeypatch.setattr(runtime, "checked_manifest", lambda *_: {"backend": "minilm-english-v3", "thresholds": THRESHOLDS})
    monkeypatch.setattr(runtime, "activation_valid", lambda *_: False)
    infer = Mock(side_effect=AssertionError("Exact followup must not call a model"))
    monkeypatch.setattr(runtime, "predict", infer)
    history = [{"role": "assistant", "resolved_query": RANK}]
    config = replace(settings, JEV_ROUTING_MODE="enabled")
    metrics = {}
    assert runtime.try_route("And for ST?", history, None, config, metrics) is None
    assert metrics["router_fallback"] == "not_activated"
    monkeypatch.setattr(runtime, "activation_valid", lambda *_: True)
    assert isinstance(runtime.try_route("And for ST?", history, None, config, metrics), LocalRoute)
    assert metrics["router_path"] == "deterministic_followup" and metrics["classifier_calls"] == 0
    assert runtime.try_route("And for ST?", history, None, replace(config, JEV_ROUTING_MODE="shadow"), metrics) is None
    assert metrics["router_path"] == "shadow"
    infer.assert_not_called()


def test_benchmark_caches_are_isolated_and_order_is_balanced(tmp_path):
    from assistant.jev.paired_benchmark import cache_path, mode_order
    assert len({cache_path(tmp_path, trial, case, mode)
                for trial in range(3) for case in ("a", "b") for mode in ("off", "enabled")}) == 12
    assert mode_order(0, 0, 0) == tuple(reversed(mode_order(0, 0, 1)))
    assert mode_order(0, 0, 0) == tuple(reversed(mode_order(1, 0, 0)))


def test_each_benchmark_trial_must_pass_without_counting_deterministic_as_classifier():
    from assistant.jev.evaluation import benchmark_passed
    from assistant.jev.paired_benchmark import diagnostics
    trial = {"pairs": 50, "coverage": .5, "median_improvement": .2, "p95_ratio": .9, "new_behavior_failures": 0}
    report = {**trial, "benchmark_version": 2, "environment_stable": True,
              "live_suite_complete": True, "source_review_passed": True, "trials": [trial] * 3}
    assert benchmark_passed(report)
    assert not benchmark_passed({**report, "trials": [trial]})
    assert not benchmark_passed({**report, "trials": [trial, trial, {**trial, "median_improvement": .01}]})
    assert not benchmark_passed({**report, "environment_stable": False})
    result = diagnostics([{"modes": {
        "off": {"turns": [{"seconds": 10, "language": "english", "metrics": {"stage_ms": {"routing_model": 6}}}]},
        "enabled": {"turns": [{"seconds": 4, "language": "english", "metrics": {
            "router_path": "deterministic_followup", "stage_ms": {}}}]}}}])
    assert result["classifier_coverage"] == 0
    assert result["deterministic_followup_coverage"] == 1 and result["routing_calls_saved"] == 1


def test_reporting_retrieval_prefers_qualified_requirements_over_annexures():
    from assistant.kb.search import requirements_priority
    question = "What documents are needed for admission reporting?"
    requirements = {"text": "Documents to be submitted at the time of admission:\nCG State Quota | NTPC Quota\nPwD certificate, if applicable",
                    "verification_status": "approved"}
    assert requirements_priority(question, requirements)
    assert not requirements_priority(question, {"text": "Annexures: Download certificates", "verification_status": "approved"})
    assert not requirements_priority(question, {**requirements, "verification_status": "needs_review"})
    assert not requirements_priority("What are the fees?", requirements)


def test_v3_holdout_validates_reviewed_query_context_before_exposure():
    from datetime import date
    from assistant.jev.common import json_hash
    from assistant.jev.english_holdout import validate_holdout
    from assistant.jev.english_v3_data import development_rows
    # Test-only schema fixtures; these are never written as a real holdout/review.
    rows = [{**row, "split": "test"} for row in development_rows()]
    manifest = {"backend": "minilm-english-v3", "fixture": True}
    review = {"artifact_id": json_hash(manifest), "dataset_sha256": "fixture",
              "reviewer": "Unit test reviewer", "reviewed_at": date.today().isoformat(),
              "notes": "Schema fixture only, not a real human review.",
              **{key: True for key in ("independent_human_review", "labels_checked",
                 "family_disjointness_checked", "public_or_synthetic", "not_used_for_development")}}
    validate_holdout(rows, review, "fixture", manifest, [])
    index = next(i for i, row in enumerate(rows) if row["gold"]["intent"] == "knowledge")
    original = rows[index]
    invalid = [
        ({"gold": {**original["gold"], "query_action": "guess"}}, "query_action"),
        ({"gold": {**original["gold"], "rewrite": not original["gold"]["rewrite"]}}, "query_action"),
        ({"history": "previous turn"}, "history"),
        ({"history": [{"role": "assistant", "resolved_query": 123}]}, "history"),
        ({"pending": "handoff"}, "pending"),
        ({"history": [{"role": "assistant", "resolved_query": RANK}]}, "expected_query"),
        ({"expected_query": ""}, "expected_query"),
    ]
    for changes, message in invalid:
        rows[index] = {**original, **changes}
        with pytest.raises(ValueError, match=message):
            validate_holdout(rows, review, "fixture", manifest, [])
    rows[index] = {**original, "history": [{"role": "assistant", "resolved_query": RANK}],
                   "expected_query": RANK}
    validate_holdout(rows, review, "fixture", manifest, [])
    with pytest.raises(ValueError, match="human review"):
        validate_holdout(rows, {**review, "independent_human_review": False}, "fixture", manifest, [])


def test_calibration_can_recover_coverage_without_accepting_critical_errors():
    from assistant.jev.english_v3_training import select_thresholds, assess
    safe = {"message": QUESTION, "critical": False,
            "gold": {"intent": "knowledge", "category": "general", "language": "english",
                     "query_action": "copy", "rewrite": False}}
    rows = [{**safe, "id": str(i), "family": str(i)} for i in range(35)]
    predicted = [prediction(query_action_probability=.86)] * len(rows)
    rows.append({**safe, "id": "mixed", "family": "mixed", "critical": True,
                 "message": QUESTION + " Also write a poem about whales.",
                 "gold": {**safe["gold"], "query_action": "defer", "rewrite": True}})
    predicted.append(prediction(query_action_probability=.84))
    selected, risk = select_thresholds(rows, predicted)
    assert selected["supported"] and selected["query_action"] == .85
    assert assess(rows, predicted, selected)["precision"] == 1
    assert any(point["critical_failures"] > 0 for point in risk)


def test_v3_training_roundtrip_and_policy_checksum(tmp_path):
    import torch
    from transformers import BertConfig, BertModel, BertTokenizerFast
    from assistant.jev.common import write_json, digest, json_hash, read_json
    from assistant.jev import english_v3_training as training
    from assistant.jev.english_v3_data import development_rows
    from assistant.jev.english_v3_model import load_router, targets
    base = tmp_path / "base_encoder"
    base.mkdir()
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "what", "is", "iiit", "nr", "?", "-"]
    (base / "vocab.txt").write_text("\n".join(vocab) + "\n")
    BertTokenizerFast(vocab_file=str(base / "vocab.txt")).save_pretrained(base)
    BertModel(BertConfig(vocab_size=len(vocab), hidden_size=16, num_hidden_layers=1,
                        num_attention_heads=2, intermediate_size=24, max_position_embeddings=512)).save_pretrained(base)
    all_rows = development_rows()
    rows = [r for split in ("train", "validation", "calibration") for r in [x for x in all_rows if x["split"] == split][:64]]
    write_json(tmp_path / "data.json", rows)
    write_json(tmp_path / "profile.json", {"profile": "english-v3", "data_hash": json_hash(rows)})
    write_json(tmp_path / "label_review.json", {"data_sha256": digest(tmp_path / "data.json")})
    write_json(tmp_path / "base_assets.json", training.file_hashes(tmp_path, base))
    original_threads = torch.get_num_threads()
    try:
        result = training.train(tmp_path, "cpu", config={**training.DEFAULT_CONFIG, "epochs": 1, "cpu_threads": 1})
        manifest = read_json(tmp_path / "manifest.json")
        training.checked_manifest(tmp_path, manifest)
        model = load_router(tmp_path, manifest)
        assert set(model([QUESTION])) == {"intent", "category", "query_action", "english"}
        reject = {"gold": {"intent": "out_of_scope", "category": "general", "language": "english", "query_action": "defer"}}
        _, masks = targets([reject], "cpu")
        assert masks["query_action"].all() and not masks["category"].any()
        assert not result["activated"]
        broken = {**manifest, "policy_files": {}}
        with pytest.raises(ValueError, match="policy implementation"):
            training.checked_manifest(tmp_path, broken)
        with pytest.raises(ValueError, match="No supported calibration"):
            training.freeze(tmp_path, tmp_path.parent / "frozen")
    finally:
        torch.set_num_threads(original_threads)
