"""Demo2-local Stage-0 for FutureWork chapter 09 (distillation and fine-tuning).

This package implements the only parts of chapter 09 that belong to Demo2 and can
run CPU-only without training a model: the verified-triple data pipeline (§3), the
selective-escalation cost/coverage maths (§2.3), and the JEV-style acceptance
certificate (§10). These are "Stage 0: build verified triple store" in the §11
roadmap — the prerequisite every student (router/verifier/drafter) depends on.

The GPU-trained students themselves (§4 multilingual router, §5 LoRA drafter,
§6 encoder verifier) live in the frozen Institute agent (`assistant/jev`,
`assistant/nodes`) and need long GPU training runs, so they are out of scope for a
Demo2-local change and are provided as long-test scripts instead.

Nothing here imports torch, transformers, or any model; it reads only Demo2's own
release-bound stores and applies deterministic filters, so it is safe to run on the
CPU-only tier.
"""
from .triples import (
    Triple,
    mine_verified_triples,
    privacy_filter,
    is_verified_turn,
    deduplicate,
    redact_pii,
)
from .families import family_key, assign_families, split_by_family, FamilySplit
from .selective import (
    temperature_scale,
    fit_temperature,
    threshold_for_precision,
    coverage_at_threshold,
    expected_turn_time,
    selective_saving,
)
from .certificate import (
    AcceptanceGate,
    DEFAULT_GATES,
    evaluate_certificate,
    artifact_signature,
    activation_valid,
)

__all__ = [
    "Triple",
    "mine_verified_triples",
    "privacy_filter",
    "is_verified_turn",
    "deduplicate",
    "redact_pii",
    "family_key",
    "assign_families",
    "split_by_family",
    "FamilySplit",
    "temperature_scale",
    "fit_temperature",
    "threshold_for_precision",
    "coverage_at_threshold",
    "expected_turn_time",
    "selective_saving",
    "AcceptanceGate",
    "DEFAULT_GATES",
    "evaluate_certificate",
    "artifact_signature",
    "activation_valid",
]
