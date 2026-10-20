"""Short, CPU-only tests for the Demo2 distillation Stage-0 (FutureWork chapter 09).

No model, no training, no network — these exercise the verified-triple pipeline (§3),
the selective-escalation maths (§2.3) and the JEV-style certificate (§10) only. A tiny
real LangGraph checkpoint store is built on disk for the miner so the full
decode→filter→gate→dedup path is covered without the Institute agent running.
"""
import json
import math
import sqlite3
import sys
from pathlib import Path

import pytest

from distillation import (
    Triple,
    mine_verified_triples,
    privacy_filter,
    is_verified_turn,
    deduplicate,
    redact_pii,
    family_key,
    split_by_family,
    temperature_scale,
    fit_temperature,
    threshold_for_precision,
    coverage_at_threshold,
    expected_turn_time,
    selective_saving,
    DEFAULT_GATES,
    evaluate_certificate,
    artifact_signature,
    activation_valid,
)
from distillation.certificate import json_hash, file_sha256


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

EVIDENCE = (
    "Matched source row: [Srinivasa K G](srinivasa_k_g.md) | Professor (DSAI) and "
    "Dean(Academics | DSAI | Ph.D (Bangalore University)"
)


def answered_turn(question="Who is the dean of academics at IIIT NR",
                  answer="The Dean of Academics at IIIT Naya Raipur is Professor Srinivasa K G.",
                  quote="Professor (DSAI) and Dean(Academics", category="faculty",
                  language="english", intent="knowledge"):
    return {
        "question": question,
        "answer_text": answer,
        "response_status": "answered",
        "sources": [{"source_file": "Faculty/*.html", "category": category, "quote": quote}],
        "retrieved_chunks": [{"text": EVIDENCE}],
        "language": language,
        "intent": intent,
        "detected_category": category,
    }


# --------------------------------------------------------------------------- #
# §3 verified-only gate
# --------------------------------------------------------------------------- #

def test_answered_grounded_turn_is_verified():
    assert is_verified_turn(answered_turn()) is True


def test_unanswered_turn_is_rejected():
    turn = answered_turn()
    turn["response_status"] = "out_of_scope"
    assert is_verified_turn(turn) is False


def test_answered_without_sources_is_rejected():
    turn = answered_turn()
    turn["sources"] = []
    assert is_verified_turn(turn) is False


def test_ungrounded_quote_is_rejected():
    # A quote the retrieved chunk does not contain = teacher hallucination; must fail.
    turn = answered_turn(quote="Dean of Academics is Professor Nobody From Nowhere")
    assert is_verified_turn(turn) is False


def test_grounding_is_casefold_and_whitespace_insensitive():
    # Mirrors evidence.py::source_quote normalization (casefold + collapse whitespace).
    turn = answered_turn(quote="professor (dsai)   and   dean(academics")
    assert is_verified_turn(turn) is True


# --------------------------------------------------------------------------- #
# §3.3 privacy filter
# --------------------------------------------------------------------------- #

def test_redact_pii_masks_email_phone_and_id():
    text = "I am 2023BTECH00123, mail me at ravi.kumar@iiitnr.edu.in or call +91 98765 43210"
    out = redact_pii(text)
    assert "@" not in out and "[email]" in out
    assert "[phone]" in out
    assert "[id]" in out
    assert "98765" not in out


def test_redact_pii_leaves_clean_text_unchanged():
    text = "What is the B.Tech admission process?"
    assert redact_pii(text) == text


def test_privacy_filter_drops_identity_fields_and_redacts():
    turn = answered_turn(question="my id is 2023BTECH00999 who is the dean")
    turn.update(student_id="s-1", student_email="x@y.com", session_id="sess", thread_id="th")
    clean = privacy_filter(turn)
    for private in ("student_id", "student_email", "session_id", "thread_id"):
        assert private not in clean
    assert "2023BTECH00999" not in clean["question"]
    assert "[id]" in clean["question"]


# --------------------------------------------------------------------------- #
# §3 dedup
# --------------------------------------------------------------------------- #

def test_deduplicate_collapses_near_duplicates():
    a = Triple("Who is the dean of academics?", "Prof Srinivasa K G.", ("q",), ("e",))
    b = Triple("who is the Dean of Academics", "prof srinivasa k g", ("q",), ("e",))
    c = Triple("What is the fee for B.Tech?", "The fee is 1,81,000.", ("q2",), ("e2",))
    out = deduplicate([a, b, c])
    assert len(out) == 2


# --------------------------------------------------------------------------- #
# §3.5 family-based split
# --------------------------------------------------------------------------- #

def test_translations_and_templates_share_a_family():
    en = Triple("Who is the dean of academics?", "A", ("q",), ("e",), category="faculty")
    hinglish = Triple("academics ka dean kaun hai", "A", ("q",), ("e",), category="faculty")
    assert family_key(en) == family_key(hinglish)


def test_different_topics_are_different_families():
    dean = Triple("Who is the dean of academics?", "A", ("q",), ("e",), category="faculty")
    fee = Triple("What is the B.Tech fee?", "B", ("q",), ("e",), category="fees")
    assert family_key(dean) != family_key(fee)


def test_split_is_family_disjoint_and_deterministic():
    triples = []
    for i in range(40):
        # Each topic appears twice (a clean + a template variant) in the same family.
        base = f"question about topic number {i}"
        triples.append(Triple(base, f"answer {i}", ("q",), ("e",), category=f"cat{i}"))
        triples.append(Triple(base + " please", f"answer {i}", ("q",), ("e",), category=f"cat{i}"))
    split = split_by_family(triples)
    assert split.is_disjoint()
    # Deterministic: same input + seed => identical assignment.
    again = split_by_family(triples)
    assert split.families == again.families
    # Every family's two variants landed together (no variant straddles a boundary).
    summary = split.summary()
    assert summary["train"] + summary["cal"] + summary["test"] == 80


def test_split_rejects_bad_ratios():
    with pytest.raises(ValueError):
        split_by_family([], ratios=(0.5, 0.3, 0.3))


# --------------------------------------------------------------------------- #
# §2.3 selective escalation maths
# --------------------------------------------------------------------------- #

def test_temperature_scale_is_a_distribution():
    probs = temperature_scale([2.0, 1.0, 0.1], 1.0)
    assert math.isclose(sum(probs), 1.0, abs_tol=1e-9)
    assert probs[0] > probs[1] > probs[2]


def test_higher_temperature_softens_confidence():
    sharp = max(temperature_scale([4.0, 0.0], 0.5))
    soft = max(temperature_scale([4.0, 0.0], 4.0))
    assert sharp > soft


def test_fit_temperature_recovers_calibration_direction():
    # Over-confident logits (true label often not the arg-max-by-margin) => T > 1.
    logits = [[3.0, 0.0], [3.0, 0.0], [3.0, 0.0], [3.0, 0.0]]
    labels = [0, 0, 1, 1]  # half wrong at high confidence => should soften
    t = fit_temperature(logits, labels)
    assert t > 1.0


def test_threshold_for_precision_holds_target():
    # Three confident-correct, one confident-wrong, one low-confidence-correct.
    logits = [[5, 0], [5, 0], [5, 0], [5, 0], [0.2, 0]]
    labels = [0, 0, 0, 1, 0]  # the 4th is wrong though highly confident
    fit = threshold_for_precision(logits, labels, target_precision=0.98)
    # Cannot reach 98% while accepting the confident-wrong one, so coverage must drop;
    # accepted precision (when anything is accepted) must meet the target or coverage 0.
    assert fit.accepted_precision >= 0.98 or fit.coverage == 0.0


def test_threshold_degenerates_to_zero_coverage_when_unreachable():
    logits = [[1, 0], [1, 0]]
    labels = [0, 1]  # 50% accuracy at identical confidence => 98% impossible
    fit = threshold_for_precision(logits, labels, target_precision=0.98)
    assert fit.coverage == 0.0


def test_expected_turn_time_matches_formula():
    # cov*t_s + (1-cov)*(t_s + t_9b)
    assert math.isclose(expected_turn_time(0.0, 0.1, 7.4), 7.5)
    assert math.isclose(expected_turn_time(1.0, 0.1, 7.4), 0.1)
    assert math.isclose(expected_turn_time(0.5, 0.1, 7.4), 0.5 * 0.1 + 0.5 * 7.5)


def test_selective_saving_scales_with_coverage():
    low = selective_saving(0.2, 0.1, 7.4)
    high = selective_saving(0.9, 0.1, 7.4)
    assert high["saved_seconds"] > low["saved_seconds"]
    assert 0.0 <= low["saved_fraction"] <= 1.0


# --------------------------------------------------------------------------- #
# §10 certificate
# --------------------------------------------------------------------------- #

def _passing_reports():
    manifest = {"backend": "demo2-router-v1", "thresholds": {"confidence": 0.9},
                "training_examples": 500, "epochs": 3}
    aid = artifact_signature(manifest)
    evaluation = {
        "artifact_id": aid, "evaluation_kind": "final_holdout",
        "independent_human_review": True, "accepted_precision": 0.985, "coverage": 0.30,
        "critical_errors": 0, "human_source_review_passed": True,
        "human_reviewer": "reviewer-1", "human_review_date": "2026-10-21",
    }
    benchmark = {
        "artifact_id": aid, "median_latency_improvement": 0.22, "p95_regression": 0.01,
        "new_behaviour_failures": 0,
    }
    return manifest, evaluation, benchmark


def test_certificate_passes_for_good_router():
    manifest, evaluation, benchmark = _passing_reports()
    result = evaluate_certificate(manifest, evaluation, benchmark, student_kind="router")
    assert result.passed, result.failures


def test_certificate_fails_on_p95_regression_like_jev_v3():
    manifest, evaluation, benchmark = _passing_reports()
    benchmark["p95_regression"] = 0.056  # the exact JEV v3 failure
    result = evaluate_certificate(manifest, evaluation, benchmark, student_kind="router")
    assert not result.passed
    assert any("p95_regression" in f for f in result.failures)


def test_certificate_fails_without_human_review_for_drafter():
    manifest, evaluation, benchmark = _passing_reports()
    evaluation["human_source_review_passed"] = False
    result = evaluate_certificate(manifest, evaluation, benchmark, student_kind="drafter")
    assert not result.passed
    assert any("human_source_review" in f for f in result.failures)


def test_certificate_requires_final_holdout_and_independent_review():
    manifest, evaluation, benchmark = _passing_reports()
    evaluation["evaluation_kind"] = "dev"
    evaluation["independent_human_review"] = False
    result = evaluate_certificate(manifest, evaluation, benchmark, student_kind="router")
    assert not result.passed
    assert any("final_holdout" in f for f in result.failures)
    assert any("independent_human_review" in f for f in result.failures)


def test_certificate_fails_on_low_coverage_router():
    manifest, evaluation, benchmark = _passing_reports()
    evaluation["coverage"] = 0.10  # below the 15% floor
    result = evaluate_certificate(manifest, evaluation, benchmark, student_kind="router")
    assert not result.passed
    assert any("coverage" in f for f in result.failures)


def test_activation_valid_binds_report_hashes(tmp_path):
    manifest, evaluation, benchmark = _passing_reports()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "evaluation.json").write_text(json.dumps(evaluation))
    (tmp_path / "benchmark.json").write_text(json.dumps(benchmark))
    activation = {
        "artifact_id": artifact_signature(manifest),
        "evaluation_sha256": file_sha256(tmp_path / "evaluation.json"),
        "benchmark_sha256": file_sha256(tmp_path / "benchmark.json"),
    }
    (tmp_path / "activation.json").write_text(json.dumps(activation))
    assert activation_valid(tmp_path, student_kind="router") is True

    # Tamper with the evaluation after signing => hash mismatch => invalid.
    evaluation["accepted_precision"] = 0.5
    (tmp_path / "evaluation.json").write_text(json.dumps(evaluation))
    assert activation_valid(tmp_path, student_kind="router") is False


def test_activation_invalid_when_files_missing(tmp_path):
    assert activation_valid(tmp_path, student_kind="router") is False


# --------------------------------------------------------------------------- #
# §3 end-to-end miner over a real LangGraph checkpoint store
# --------------------------------------------------------------------------- #

def _write_checkpoint_store(path: Path, states: list[dict]):
    """Persist states as LangGraph checkpoints the miner can decode."""
    serde = pytest.importorskip("langgraph.checkpoint.serde.jsonplus").JsonPlusSerializer()
    from langchain_core.messages import HumanMessage, AIMessage
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE checkpoints (thread_id TEXT NOT NULL, checkpoint_ns TEXT NOT NULL DEFAULT '',
        checkpoint_id TEXT NOT NULL, parent_checkpoint_id TEXT, type TEXT, checkpoint BLOB, metadata BLOB,
        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id))""")
    for i, st in enumerate(states):
        messages = [HumanMessage(content=st["question"]),
                    AIMessage(content=st["answer_text"],
                              additional_kwargs={"response_status": st["response_status"]})]
        channel_values = {k: v for k, v in st.items()}
        channel_values["messages"] = messages
        typ, blob = serde.dumps_typed({"channel_values": channel_values})
        conn.execute("INSERT INTO checkpoints VALUES (?,?,?,?,?,?,?)",
                     (f"t{i}", "", f"c{i:020d}", None, typ, blob, None))
    conn.commit()
    conn.close()


def test_miner_keeps_only_verified_and_redacts(tmp_path):
    db = tmp_path / "conversations.sqlite"
    good = answered_turn()
    hallucinated = answered_turn(question="who runs the hostel",
                                 quote="The hostel is run by a ghost",  # not in evidence
                                 category="hostel")
    pii = answered_turn(question="my roll 2023BTECH00777 — who is the dean")
    _write_checkpoint_store(db, [good, hallucinated, pii])

    triples = mine_verified_triples(db)
    # hallucinated turn dropped; good + pii kept (different questions => 2 families).
    assert len(triples) == 2
    joined = " ".join(t.question for t in triples)
    assert "2023BTECH00777" not in joined  # privacy filter ran
    # Every surviving triple is grounded.
    for t in triples:
        assert t.answer and t.quotes


def test_miner_accepts_extra_turns_without_db():
    triples = mine_verified_triples(None, extra_turns=[answered_turn(), answered_turn(
        question="what is the fee", answer="The fee is 1,81,000.",
        quote="Professor (DSAI) and Dean(Academics", category="fees")])
    assert len(triples) == 2
