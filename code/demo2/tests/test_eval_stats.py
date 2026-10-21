"""Offline unit tests for the chapter 12 evaluation infrastructure.

Covers stats.py, report_block.py, metrics_ext.py and eval_report.py. Every test is pure
CPU / no model / no network / no GPU, runs in well under a second, and is deterministic. The
stats tests check against values computed independently (NumPy percentile, the Wilson formula,
the exact binomial, the rule of three). The eval_report test runs against the *real* recorded
120-turn result sets that ship in the repo, so it also guards the measured result in the report.
"""
import json
import math
from pathlib import Path

import pytest

import eval_report
import metrics_ext
import report_block as rb
import stats

try:
    import numpy as _np
except Exception:  # pragma: no cover
    _np = None

DATA = Path(__file__).resolve().parent.parent / "data" / "upgrade-20260930"
EVAL = Path(__file__).resolve().parent.parent / "evaluation" / "upgrade-20260930"


# --------------------------------------------------------------------------- stats.py


def test_median_and_percentile_basic():
    assert stats.median([3, 1, 2]) == 2
    assert stats.median([1, 2, 3, 4]) == 2.5
    assert stats.percentile([1, 2, 3, 4, 5], 50) == 3


@pytest.mark.skipif(_np is None, reason="numpy not available")
@pytest.mark.parametrize("q", [0, 25, 50, 90, 95, 99, 100])
def test_percentile_matches_numpy(q):
    xs = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 10.0, 7.2, 4.4]
    assert stats.percentile(xs, q) == pytest.approx(float(_np.percentile(xs, q)), abs=1e-9)


def test_percentile_domain_errors():
    with pytest.raises(ValueError):
        stats.percentile([1, 2], 101)
    with pytest.raises(ValueError):
        stats.median([])


def test_paired_bootstrap_detects_uniform_improvement():
    # candidate is 2 s faster on every case: Δ median must be −2 with a CI below 0
    pairs = [(10 + i * 0.1, 8 + i * 0.1) for i in range(40)]
    ci = stats.paired_bootstrap_ci(pairs, "median", resamples=2000, seed=0)
    assert ci["point"] == pytest.approx(-2.0, abs=1e-9)
    assert ci["ci_high"] < 0
    assert ci["improvement"] is True
    assert ci["regression"] is False


def test_paired_bootstrap_is_deterministic_for_seed():
    pairs = [(10 + i * 0.3, 9 + (i % 5)) for i in range(30)]
    a = stats.paired_bootstrap_ci(pairs, "p95", resamples=1500, seed=7)
    b = stats.paired_bootstrap_ci(pairs, "p95", resamples=1500, seed=7)
    assert a == b


def test_p95_ratio_ci():
    pairs = [(10 + i * 0.1, 8 + i * 0.1) for i in range(40)]
    ratio = stats.p95_ratio_ci(pairs, resamples=1500, seed=0)
    assert ratio["point"] < 1.0           # candidate faster → ratio below 1
    assert ratio["ratio_high"] < 1.05


def test_mcnemar_exact_small_counts():
    # b=1, c=9: known two-sided exact binomial p ≈ 0.0215
    result = stats.mcnemar(1, 9)
    assert result["method"] == "exact_binomial"
    assert result["p_value"] == pytest.approx(0.021484375, abs=1e-6)
    assert result["candidate_better"] is True


def test_mcnemar_chi2_large_counts():
    result = stats.mcnemar(20, 40)
    assert result["method"] == "chi2_continuity"
    # continuity-corrected χ² = (|20-40|-1)²/60 = 361/60
    assert result["statistic"] == pytest.approx(361 / 60, abs=1e-9)
    assert 0 < result["p_value"] < 0.05


def test_mcnemar_tie_and_zero():
    assert stats.mcnemar(0, 0)["p_value"] == 1.0
    tie = stats.mcnemar(5, 5)
    assert tie["candidate_better"] is None
    assert tie["p_value"] == pytest.approx(1.0, abs=1e-9)


def test_mcnemar_from_labels_counts():
    base = [True, True, False, False, True]
    cand = [True, False, True, True, True]
    # discordant: idx1 base✓ cand✗ (b), idx2+idx3 base✗ cand✓ (c)
    result = stats.mcnemar_from_labels(base, cand)
    assert result["b"] == 1
    assert result["c"] == 2
    assert result["n_cases"] == 5


def test_wilson_interval_known_value():
    w = stats.wilson_interval(5, 100)
    assert w["low"] == pytest.approx(0.0215443, abs=1e-5)
    assert w["high"] == pytest.approx(0.1117492, abs=1e-5)


def test_wilson_zero_successes_is_tight_upper():
    w = stats.wilson_interval(0, 300)
    assert w["point"] == 0.0
    assert w["low"] == pytest.approx(0.0, abs=1e-12)
    assert w["high"] == pytest.approx(0.012643, abs=1e-5)


def test_rule_of_three_and_sample_size():
    rot = stats.rule_of_three(300)
    assert rot["upper_bound"] == pytest.approx(3 / 300, rel=0.02)
    assert stats.samples_for_upper_bound(0.01) == 300


def test_z_for_95_is_exact():
    assert stats._z_for_confidence(0.95) == pytest.approx(1.959963984540054, abs=1e-12)


# --------------------------------------------------------------------------- report_block.py


def _passing_gates():
    pairs = [(10 + i * 0.1, 9 + i * 0.1) for i in range(40)]
    ci = stats.paired_bootstrap_ci(pairs, "median", resamples=800, seed=0)
    ratio = stats.p95_ratio_ci(pairs, resamples=800, seed=0)
    mc = stats.mcnemar_from_labels([True] * 38 + [False, False], [True] * 39 + [False])
    return [rb.evaluate_latency_p50(ci), rb.evaluate_latency_p95(ratio), rb.evaluate_status(mc)]


def test_overall_verdict_ship_hold_reject():
    ship = [rb.GateResult("G-a", True, "")]
    hold = [rb.GateResult("G-a", True, ""), rb.GateResult("G-b", None, "")]
    reject = [rb.GateResult("G-a", False, "")]
    assert rb.overall_verdict(ship)[0] == "SHIP"
    assert rb.overall_verdict(hold)[0] == "HOLD"
    assert rb.overall_verdict(reject)[0] == "REJECT"


def test_render_contains_verdict_and_table():
    block = rb.ReportBlock("E1", "ch05", "text-only GGUF", "commit abc",
                           dataset="n=40", gates=_passing_gates())
    out = block.render()
    assert "### Experiment: E1" in out
    assert "| Metric |" in out
    assert "Verdict:" in out


def test_render_refuses_on_residency_drift():
    block = rb.ReportBlock("E2", "ch05", "x", "y",
                           residency=rb.Residency(stable=False), gates=_passing_gates())
    with pytest.raises(rb.ResidencyDriftError):
        block.render()


def test_render_refuses_on_side_effect():
    block = rb.ReportBlock("E3", "ch05", "x", "y",
                           side_effects_written=1, gates=_passing_gates())
    with pytest.raises(rb.SideEffectError):
        block.render()


def test_claim_gate_needs_300_clean_cases():
    small = rb.evaluate_claim(stats.wilson_interval(0, 50))
    big = rb.evaluate_claim(stats.wilson_interval(0, 2000))
    assert small.passed is False            # too few cases for a <1 % claim
    assert big.passed is True               # 0/2000 → upper well below 1 %


def test_latency_p95_gate_threshold():
    good = rb.evaluate_latency_p95({"point": 1.0, "ratio_high": 1.04})
    bad = rb.evaluate_latency_p95({"point": 1.06, "ratio_high": 1.20})
    assert good.passed is True
    assert bad.passed is False


def test_status_gate_fails_only_when_worse_and_significant():
    worse_sig = rb.evaluate_status(stats.mcnemar(30, 5))      # candidate lost a lot
    worse_ns = rb.evaluate_status(stats.mcnemar(5, 3))        # slightly worse, not sig
    better = rb.evaluate_status(stats.mcnemar(2, 20))
    assert worse_sig.passed is False
    assert worse_ns.passed is True
    assert better.passed is True


def test_vram_gate():
    assert rb.evaluate_vram(8000).passed is True
    assert rb.evaluate_vram(8300).passed is False


# --------------------------------------------------------------------------- metrics_ext.py


def test_residency_stable_logic():
    a = {"available": True, "loaded": 1, "size_vram": 6000, "context_length": 8192, "digest": "abc"}
    assert metrics_ext.residency_stable(a, dict(a)) is True
    assert metrics_ext.residency_stable(a, dict(a, size_vram=5000)) is False
    assert metrics_ext.residency_stable(a, dict(a, digest="xyz")) is False
    assert metrics_ext.residency_stable({"available": False}, a) is False
    assert metrics_ext.residency_stable(a, {"available": True, "loaded": 0}) is False


def test_energy_sampler_integrates_constant_power(monkeypatch):
    clock_values = iter([0.0, 0.0, 1.0, 2.0, 2.0])
    monkeypatch.setattr(metrics_ext, "read_gpu_power_watts", lambda: 100.0)
    monkeypatch.setattr(metrics_ext, "read_rapl_energy_uj", lambda: None)
    sampler = metrics_ext.EnergySampler()
    sampler._clock = lambda: next(clock_values)
    sampler.start()
    sampler.sample()
    reading = sampler.stop()
    # 100 W constant over 2 s = 200 J = 0.05556 Wh
    assert reading["gpu_wh"] == pytest.approx(100.0 * 2.0 / 3600.0, abs=1e-6)
    assert reading["cpu_wh"] is None
    assert reading["gpu_samples"] == 3


def test_energy_sampler_graceful_without_gpu(monkeypatch):
    monkeypatch.setattr(metrics_ext, "read_gpu_power_watts", lambda: None)
    monkeypatch.setattr(metrics_ext, "read_rapl_energy_uj", lambda: None)
    sampler = metrics_ext.EnergySampler()
    sampler.start()
    reading = sampler.stop()
    assert reading["gpu_wh"] is None
    assert reading["total_wh"] is None


def test_read_residency_handles_dead_server(monkeypatch):
    def boom(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(metrics_ext.urllib.request, "urlopen", boom)
    snap = metrics_ext.read_residency(timeout=0.01)
    assert snap["available"] is False


def test_collect_stage_ms_passthrough_and_missing():
    full = metrics_ext.collect_stage_ms(
        {"stage_ms": {"answer": 14000.0}, "model_calls": 3, "router_path": "llm",
         "retrieval_cache": "miss", "draft_cache": "miss", "provider": "ollama", "model": "qwen3.5:9b"})
    assert full["stage_ms"]["answer"] == 14000.0
    assert full["model_calls"] == 3
    empty = metrics_ext.collect_stage_ms(None)
    assert empty["stage_ms"] == {}
    assert empty["model_calls"] is None


def test_snapshot_environment_keys():
    snap = metrics_ext.snapshot_environment()
    assert {"residency", "gpu_vram_used_mib", "gpu_power_watts", "rapl_available",
            "ollama_base_url", "captured_at"} <= set(snap)


# --------------------------------------------------------------------------- eval_report.py


def test_status_correct_mapping():
    assert eval_report._status_correct({"response_status": "answered"}, "answerable") is True
    assert eval_report._status_correct({"response_status": "insufficient"}, "answerable") is False
    assert eval_report._status_correct({"response_status": "out_of_scope"}, "no_cutoff") is True
    assert eval_report._status_correct({"response_status": "answered"}, "no_cutoff") is False
    assert eval_report._status_correct({"response_status": "answered"}, None) is None


def test_false_hit_only_counts_hit_on_non_answered():
    assert eval_report._false_hit(
        {"rag_metrics": {"retrieval_cache": "hit"}, "response_status": "insufficient"}) is True
    assert eval_report._false_hit(
        {"rag_metrics": {"retrieval_cache": "hit"}, "response_status": "answered"}) is False
    assert eval_report._false_hit(
        {"rag_metrics": {"retrieval_cache": "miss"}, "response_status": "insufficient"}) is False


def test_analyze_synthetic_pairs(tmp_path):
    baseline = [{"id": f"c{i}", "seconds": 10.0, "response_status": "answered", "expected": "answerable",
                 "rag_metrics": {"retrieval_cache": "miss"}} for i in range(5)]
    candidate = [{"id": f"c{i}", "seconds": 8.0, "response_status": "answered", "expected": "answerable",
                  "rag_metrics": {"retrieval_cache": "miss"}} for i in range(5)]
    bpath = tmp_path / "b.json"
    cpath = tmp_path / "c.json"
    bpath.write_text(json.dumps(baseline))
    cpath.write_text(json.dumps(candidate))
    summary = eval_report.analyze(bpath, cpath, resamples=500, seed=0)
    assert summary["n_shared"] == 5
    assert summary["latency_p50_ci"]["point"] == pytest.approx(-2.0, abs=1e-9)
    assert summary["candidate_false_hits"] == 0


@pytest.mark.skipif(not (DATA / "baseline" / "results.json").exists(),
                    reason="recorded result set not present")
def test_analyze_real_recorded_runs_reproduces_p95_regression():
    summary = eval_report.analyze(
        DATA / "baseline" / "results.json",
        DATA / "candidate" / "results.json",
        EVAL / "cases.json",
        resamples=1000, seed=0,
    )
    assert summary["n_shared"] == 120
    # p50 improved (CI below 0) but p95 regressed beyond 1.05 — the JEV lesson
    assert summary["latency_p50_ci"]["ci_high"] < 0
    assert summary["latency_p95_ratio"]["point"] > 1.05
    assert summary["candidate_false_hits"] == 0
    # candidate status accuracy not worse
    assert summary["candidate_status_acc"] >= summary["baseline_status_acc"]


@pytest.mark.skipif(not (DATA / "baseline" / "results.json").exists(),
                    reason="recorded result set not present")
def test_build_block_on_real_data_rejects_for_p95():
    summary = eval_report.analyze(
        DATA / "baseline" / "results.json",
        DATA / "candidate" / "results.json",
        EVAL / "cases.json",
        resamples=1000, seed=0,
    )
    block = eval_report.build_block(summary, experiment_id="FW12-test",
                                    baseline_ref="r20260930", dataset="120-turn (n=120)")
    rendered = block.render()
    assert "G-latency-p95: FAIL" in rendered
    assert "Verdict: REJECT" in rendered
