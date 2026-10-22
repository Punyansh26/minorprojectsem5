"""Offline tests for evaluate_latency.py: no model, network, GPU or agent import."""
import pytest

import evaluate_latency as el
import stats


def _row(i, wall, status="answered", *, repeat=False, error=None, stage_ms=None, model="qwen3.5:9b"):
    return {"i": i, "repeat": repeat, "question": f"q{i}", "status": status, "wall_s": wall, "error": error,
            "rag_metrics": {"model": model, "stage_ms": stage_ms or {}}}


def test_warmup_question_is_outside_the_timed_set():
    # A shared question would give a timed turn the warm-up's retrieval/draft cache hit.
    assert el.WARMUP_QUESTION not in el.QUESTIONS
    assert len(set(el.QUESTIONS)) == len(el.QUESTIONS)


def test_summarize_wall_uses_demo2_stats_and_handles_empty():
    xs = [4.0, 8.2, 6.1, 12.5]
    s = el.summarize_wall(xs)
    assert s == {"n": 4, "median": round(stats.median(xs), 3), "p95": round(stats.p95(xs), 3),
                 "min": 4.0, "max": 12.5}
    assert el.summarize_wall([]) == {"n": 0, "median": None, "p95": None, "min": None, "max": None}


def test_source_names_formats_pages_and_skips_unknown_page():
    sources = [{"source_file": "admissions/B TECH_2026.pdf", "page_number": 1},
               {"source_file": "general/page.html", "page_number": -1}, "raw"]
    assert el.source_names(sources) == ["admissions/B TECH_2026.pdf p1", "general/page.html", "raw"]
    assert el.source_names(None) == []


def test_build_summary_separates_answered_repeats_and_errors():
    rows = [
        _row(0, 8.0, stage_ms={"routing": 1000.0, "answer": 7000.0}),
        _row(1, 4.0, "insufficient", stage_ms={"routing": 900.0}),
        _row(2, 10.0, stage_ms={"routing": 1200.0, "answer": 8000.0}),
        _row(3, 2.0, repeat=True, stage_ms={"routing": 50.0, "answer": 60.0}),
        _row(4, 0.1, "error", error="RuntimeError: boom"),
    ]
    s = el.build_summary(rows, provider="ollama", tier="T2", warmup=None, data_dir="x")
    assert s["tier"] == "T2" and s["model"] == "qwen3.5:9b"
    assert s["turns"] == 5 and s["answered"] == 3
    assert s["status_counts"] == {"answered": 3, "insufficient": 1, "error": 1}
    assert s["wall_s_all"]["n"] == 4                 # errored turn excluded from timing
    assert s["wall_s_first_pass"]["n"] == 3          # repeat (cache-hit) turn excluded
    assert s["wall_s_answered"]["n"] == 2            # answered, first pass only
    assert s["wall_s_answered"]["median"] == 9.0
    assert s["stage_ms_median_answered"] == {"answer": 7500.0, "routing": 1100.0}
    assert s["wall_s_median"] == s["wall_s_all"]["median"]


def test_run_turn_records_answer_and_never_raises():
    def ask(question, session_id, profile, *, provider):
        assert session_id and provider == "ollama"
        return {"response_status": "answered", "language": "hindi", "answer_text": "x" * 500, "llm_error": "",
                "sources": [{"source_file": "f.pdf", "page_number": 2}], "rag_metrics": {"model": "m"}}

    row = el.run_turn(ask, "q", {}, "ollama")
    assert row["status"] == "answered" and row["sources"] == 1 and row["source_files"] == ["f.pdf p2"]
    assert len(row["answer_text"]) == 400 and row["llm_error"] is None and row["error"] is None

    def broken(*_, **__):
        raise RuntimeError("down")

    failed = el.run_turn(broken, "q", {}, "ollama")
    assert failed["status"] == "error" and failed["error"] == "RuntimeError: down"
    assert failed["wall_s"] >= 0


def test_turns_must_be_positive():
    with pytest.raises(SystemExit):
        el.main(["--output", "unused.json", "--turns", "0"])
