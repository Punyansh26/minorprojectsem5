"""Verify the cost-model equations (02) and that per-call token metrics reach rag_metrics.

No network, model download or provider call: the invoke function is a stub and the
provider measurement is injected through operations.record_attempt's allowlist.
"""
import json
import math

import pytest

from assistant import cost_model as cm
from assistant import operations
from assistant.metrics import call_model, measure_node


# --- §1 perceived latency and streaming overlap ---------------------------

def test_perceived_latency_sums_terms_and_ignores_unset():
    assert cm.perceived_latency(t_eou=0.3, t_llm_ttft=0.566, t_tts_ttfb=0.2) == pytest.approx(1.066)
    # Streaming time to first output is the sum of first-chunk latencies (02 §1.1).
    assert cm.streaming_first_output([0.3, 0.1, 0.2]) == pytest.approx(0.6)


# --- §2 one LLM call and the decode-bound threshold -----------------------

def test_llm_call_seconds_matches_worked_terms():
    # 920-token cold prompt, 10 output tokens, baseline rates, cold load 8.3 s.
    t = cm.llm_call_seconds(920, 10, r_prefill=cm.R_PREFILL_TOK_S, r_decode=cm.R_DECODE_TOK_S,
                            t_load=cm.COLD_LOAD_SECONDS)
    assert t == pytest.approx(8.3 + 920 / 820 + 10 / 17.7, rel=1e-6)
    # Prefix reuse removes reused prompt tokens from the prefill term.
    reused = cm.llm_call_seconds(920, 10, n_reused=900)
    fresh = cm.llm_call_seconds(920, 10)
    assert reused < fresh


def test_decode_bound_threshold_reproduces_chapter_example():
    # 02 §2: N_out > N_prompt * 17.7/820 ~= 0.022 N_prompt; a 3000-token prompt is
    # decode-bound above ~65 output tokens.
    assert cm.decode_bound_output_threshold(3000) == pytest.approx(3000 * 17.7 / 820, rel=1e-6)
    assert 64 < cm.decode_bound_output_threshold(3000) < 66
    assert cm.is_decode_bound(3000, 100)
    assert not cm.is_decode_bound(3000, 50)


@pytest.mark.parametrize("bad", [(-1, 10), (10, -1)])
def test_llm_call_rejects_negative_counts(bad):
    with pytest.raises(ValueError):
        cm.llm_call_seconds(*bad)


# --- §2.1 memory-bound decode ---------------------------------------------

def test_decode_rate_fully_on_gpu_doubles_the_offloaded_case():
    b_gpu, b_cpu = cm.split_weights_gb(0.45)
    assert b_cpu == pytest.approx(5.6 * 0.45)
    offloaded = cm.decode_tokens_per_second(b_gpu, b_cpu)
    on_gpu = cm.decode_tokens_per_second(cm.WEIGHTS_GB_Q4, 0.0)
    # Chapter: ~17 tok/s offloaded, ~32 tok/s fully on GPU — roughly a doubling.
    assert 15 < offloaded < 20
    assert 28 < on_gpu < 36
    assert on_gpu > offloaded * 1.5


def test_decode_rate_requires_weights_somewhere():
    with pytest.raises(ValueError):
        cm.decode_tokens_per_second(0.0, 0.0)


def test_split_weights_fraction_bounds():
    with pytest.raises(ValueError):
        cm.split_weights_gb(1.5)


# --- §3 memory ------------------------------------------------------------

def test_kv_cache_reproduces_256_mib_at_8192():
    assert cm.kv_cache_mib(8192) == pytest.approx(256.0, rel=1e-6)
    # q8_0 (1 byte) halves it.
    assert cm.kv_cache_mib(8192, bytes_per_elem=1) == pytest.approx(128.0, rel=1e-6)


def test_vram_fits_boundary():
    assert cm.vram_fits(4412, 256, 48, 485, 2737, 8188)
    assert not cm.vram_fits(6300, 256, 48, 485, 2737, 8188)


# --- §4 Amdahl ------------------------------------------------------------

def test_amdahl_removing_routing_matches_chapter():
    # Remove the routing call (p=0.20, s=inf): 18.7 s -> ~14.9 s (02 §4).
    assert cm.amdahl_new_turn(18.7, 0.20, float("inf")) == pytest.approx(14.96, abs=0.1)
    # Model fully on GPU (~2x decode on ~95% of the turn): ~9.8 s.
    assert cm.amdahl_new_turn(18.7, 0.95, 2) == pytest.approx(9.8, abs=0.3)


def test_amdahl_rejects_bad_fraction():
    with pytest.raises(ValueError):
        cm.amdahl_speedup(1.2, 2)


# --- §5 tails -------------------------------------------------------------

def test_tail_probability_three_calls():
    # 02 §5: three calls each 5% slow -> ~14% chance at least one is slow.
    assert cm.tail_probability(0.05, 3) == pytest.approx(1 - 0.95 ** 3, rel=1e-9)
    assert cm.tail_probability(0.05, 3) == pytest.approx(0.142625, abs=1e-6)


# --- §6 energy and cost ---------------------------------------------------

def test_energy_and_cost_per_turn():
    energy = cm.energy_joules(115, 15.7)  # the old $0.60/month assumption's terms
    assert energy == pytest.approx(115 * 15.7)
    cost = cm.cost_per_turn(energy, price_per_kwh=8.0)
    assert cost == pytest.approx((energy / 3.6e6) * 8.0, rel=1e-9)
    # Hardware amortisation adds a per-turn share.
    amortised = cm.cost_per_turn(energy, 8.0, hardware_cost=100000, turns_over_lifetime=1_000_000)
    assert amortised > cost


# --- splitting a real call into cost-model terms --------------------------

def test_split_call_rates_from_ollama_fields():
    fields = {"provider": "ollama", "prompt_eval_count": 920, "prompt_eval_duration": 1_122_000_000,
              "eval_count": 127, "eval_duration": 7_175_000_000, "load_duration": 8_300_000_000,
              "total_duration": 16_600_000_000}
    rates = cm.split_call_rates(fields)
    assert rates.prompt_tokens == 920 and rates.output_tokens == 127
    assert rates.prefill_tok_s == pytest.approx(920 / 1.122, abs=0.5)
    assert rates.decode_tok_s == pytest.approx(127 / 7.175, abs=0.1)
    assert rates.load_seconds == pytest.approx(8.3, abs=0.01)
    assert rates.cold is True


def test_split_call_rates_warm_and_missing_fields():
    warm = cm.split_call_rates({"eval_count": 100, "eval_duration": 5_000_000_000, "load_duration": 0})
    assert warm.cold is False
    assert warm.decode_tok_s == pytest.approx(20.0, rel=1e-6)
    # Nothing numeric -> no derived rates, no crash.
    empty = cm.split_call_rates({})
    assert empty.decode_tok_s is None and empty.prompt_tokens is None
    assert cm.split_call_rates(None).output_tokens is None


def test_call_record_is_json_safe_and_carries_no_content():
    fields = {"prompt_eval_count": 10, "eval_count": 5, "eval_duration": 1_000_000_000,
              "response": "SECRET BODY", "message": {"content": "private"}}
    record = cm.call_record("generation_model", fields)
    serialized = json.dumps(record)
    assert "SECRET" not in serialized and "private" not in serialized
    assert record["stage"] == "generation_model"
    assert record["output_tokens"] == 5
    assert record["decode_tok_s"] == pytest.approx(5.0, rel=1e-6)


# --- metrics wiring: per-call token counts reach rag_metrics --------------

def _fresh_state():
    # Reproduce the measure_node reset so rag_metrics has the expected shape.
    @measure_node("routing", reset=True)
    def node(state):
        return {}
    return node({})


def test_measure_node_reset_includes_calls_list():
    state = _fresh_state()
    assert state["rag_metrics"]["calls"] == []
    assert state["rag_metrics"]["stage_ms"]  # routing timed


def test_call_model_records_token_metrics_per_stage(monkeypatch):
    state = {"rag_metrics": {"model_calls": 0, "stage_ms": {}, "calls": []}}

    def fake_invoke(schema, prompt, payload):
        # A real provider adapter calls record_attempt in its finally block.
        operations.record_attempt("ollama", 0.0, {
            "prompt_eval_count": 300, "prompt_eval_duration": 400_000_000,
            "eval_count": 120, "eval_duration": 6_000_000_000, "load_duration": 0})
        return "answer"

    result = call_model(state, fake_invoke, object, "PROMPT", {"q": "x"}, "generation_model")
    assert result == "answer"
    calls = state["rag_metrics"]["calls"]
    assert len(calls) == 1
    assert calls[0]["stage"] == "generation_model"
    assert calls[0]["output_tokens"] == 120
    assert calls[0]["decode_tok_s"] == pytest.approx(20.0, rel=1e-6)
    assert calls[0]["cold"] is False
    assert state["rag_metrics"]["model_calls"] == 1
    assert "generation_model" in state["rag_metrics"]["stage_ms"]


def test_call_model_does_not_misattribute_previous_measurement(monkeypatch):
    state = {"rag_metrics": {"model_calls": 0, "stage_ms": {}, "calls": []}}

    def reporting_invoke(schema, prompt, payload):
        operations.record_attempt("ollama", 0.0, {"eval_count": 10, "eval_duration": 1_000_000_000})
        return "a"

    def silent_invoke(schema, prompt, payload):
        return "b"  # provider reported nothing this time

    call_model(state, reporting_invoke, object, "P", {}, "routing_model")
    call_model(state, silent_invoke, object, "P", {}, "generation_model")
    stages = [c["stage"] for c in state["rag_metrics"]["calls"]]
    # The silent call must not inherit the routing call's token counts.
    assert stages == ["routing_model"]


def test_call_model_on_failure_records_nothing_but_counts_the_call():
    state = {"rag_metrics": {"model_calls": 0, "stage_ms": {}, "calls": []}}

    def failing_invoke(schema, prompt, payload):
        operations.clear_measurement()
        raise RuntimeError("provider down")

    with pytest.raises(RuntimeError):
        call_model(state, failing_invoke, object, "P", {}, "review_model")
    assert state["rag_metrics"]["model_calls"] == 1
    assert state["rag_metrics"]["calls"] == []
    assert "review_model" in state["rag_metrics"]["stage_ms"]


def test_record_attempt_publishes_without_an_operation_and_hides_content():
    operations.clear_measurement()
    operations.record_attempt("ollama", 0.0, {"prompt_eval_count": 7, "response": "SECRET"})
    measurement = operations.last_measurement()
    assert measurement["prompt_eval_count"] == 7
    assert "SECRET" not in json.dumps(measurement)
