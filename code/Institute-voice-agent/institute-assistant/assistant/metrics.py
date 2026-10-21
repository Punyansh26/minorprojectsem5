"""Measure RAG work without recording questions, profiles or provider bodies."""
from copy import deepcopy
from functools import wraps
from time import perf_counter


def measure_node(stage: str, reset: bool = False):
    """Return metrics explicitly in graph updates, avoiding in-place checkpoint mutation."""
    def decorate(function):
        @wraps(function)
        def measured(state):
            from assistant.operations import check
            check(stage)
            state = {**state, "rag_metrics": (
                {"retrieval_cache": "bypass", "draft_cache": "bypass", "history_pairs": 0,
                 "model_calls": 0, "classifier_calls": 0, "router_path": "deterministic", "stage_ms": {}, "calls": []} if reset else deepcopy(state.get("rag_metrics", {})))}
            metrics = state["rag_metrics"]
            metrics.setdefault("stage_ms", {})
            started = perf_counter()
            result = function(state)
            metrics["stage_ms"][stage] = round((perf_counter() - started) * 1000, 3)
            return {**result, "rag_metrics": metrics}
        return measured
    return decorate


def call_model(state, invoke, schema, prompt, payload, stage):
    """Count logical model calls including failures; provider retries remain separately bounded.

    Also surface the cost-model terms for this call (prompt/output token counts
    and prefill/decode rates, cost model 02 §2) into ``rag_metrics['calls']`` so
    they can be split from benchmark traffic without new instrumentation. The
    numeric allowlist comes from ``operations.record_attempt``; no prompt,
    question or provider body is stored.
    """
    from assistant.operations import check, last_measurement, clear_measurement
    from assistant.cost_model import call_record
    check(stage)
    metrics = state["rag_metrics"]
    metrics["model_calls"] = metrics.get("model_calls", 0) + 1
    # Clear the slot so a failure or a provider that reports nothing cannot
    # mis-attribute the previous call's token counts to this stage.
    clear_measurement()
    started = perf_counter()
    try:
        return invoke(schema, prompt, payload)
    finally:
        metrics["stage_ms"][stage] = round((perf_counter() - started) * 1000, 3)
        measurement = last_measurement()
        if measurement:
            record = call_record(stage, measurement)
            if len(record) > 1:  # more than just the stage name
                metrics.setdefault("calls", []).append(record)
