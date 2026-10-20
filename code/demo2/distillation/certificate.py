"""§10 acceptance gates mirroring the JEV certificate (Demo2-local, CPU-only, no model).

Chapter 09 §10: promote any student only with a certificate like
``assistant/jev/runtime.py::activation_valid`` — it requires ``activation.json``,
``evaluation.json`` and ``benchmark.json`` present, their artifact hashes matching a
single artifact identity, ``evaluation_kind == "final_holdout"``,
``independent_human_review == true``, and the quality + benchmark checks passing.

This module re-implements that discipline *Demo2-locally* so a Demo2 student
(whenever one is trained by the deferred long tests) can be gated by Demo2 code
without importing or modifying the frozen Institute agent. It adds the concrete §10
threshold table:

| Gate                       | Threshold                              | Applies to                   |
| Accepted precision         | >= 98% on a fresh family-disjoint test | router, verifier             |
| Critical errors            | 0 (action/mixed-topic/scope)           | router                       |
| Coverage                   | >= 15%                                  | router                       |
| Median latency improvement | >= 10%                                 | any latency-claiming student |
| p95 regression             | <= 5%                                  | any (JEV v3 failed: +5.6%)   |
| New behaviour failures     | 0                                      | any                          |
| Human source review        | passed (recorded reviewer+date)        | drafter, verifier            |

A student that improves p50 but regresses p95 (02 §5) fails, exactly as JEV v3 did.
Pure stdlib (hashlib/json) so it runs anywhere.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# --------------------------------------------------------------------------- #
# Artifact identity (mirrors common.json_hash / runtime.digest)
# --------------------------------------------------------------------------- #

def _canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_hash(obj) -> str:
    """SHA-256 of the canonical JSON of an object (the JEV manifest identity)."""
    return hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    """SHA-256 of a file's bytes (the JEV report digest)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def artifact_signature(manifest: dict) -> str:
    """The artifact identity a certificate must agree on, from its manifest.

    Binds the checksummed weights/tokenizer and the calibrated thresholds, so any
    recalibration changes the identity and invalidates older activation records
    (``OPEN_JEV.md``: "changes the artifact identity and invalidates older activation
    records").
    """
    return json_hash(manifest)


# --------------------------------------------------------------------------- #
# §10 gate thresholds
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class AcceptanceGate:
    """One row of the §10 threshold table, as a checkable predicate."""

    name: str
    description: str
    check: Callable[[dict], bool]
    applies_to: tuple[str, ...]


def _get(metrics: dict, key: str, default: float = 0.0) -> float:
    value = metrics.get(key, default)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


DEFAULT_GATES: tuple[AcceptanceGate, ...] = (
    AcceptanceGate(
        "accepted_precision", "Accepted precision >= 98% on a fresh family-disjoint holdout",
        lambda m: _get(m, "accepted_precision") >= 0.98,
        ("router", "verifier"),
    ),
    AcceptanceGate(
        "critical_errors", "Zero critical action/mixed-topic/scope errors",
        lambda m: _get(m, "critical_errors") == 0,
        ("router",),
    ),
    AcceptanceGate(
        "coverage", "Coverage >= 15%",
        lambda m: _get(m, "coverage") >= 0.15,
        ("router",),
    ),
    AcceptanceGate(
        "median_latency_improvement", "Median latency improvement >= 10%",
        lambda m: _get(m, "median_latency_improvement") >= 0.10,
        ("router", "verifier", "drafter"),
    ),
    AcceptanceGate(
        "p95_regression", "p95 regression <= 5% (JEV v3 failed at +5.6%)",
        lambda m: _get(m, "p95_regression") <= 0.05,
        ("router", "verifier", "drafter"),
    ),
    AcceptanceGate(
        "new_behaviour_failures", "Zero new behaviour failures",
        lambda m: _get(m, "new_behaviour_failures") == 0,
        ("router", "verifier", "drafter"),
    ),
    AcceptanceGate(
        "human_source_review", "Human source review passed (reviewer + date recorded)",
        lambda m: bool(m.get("human_source_review_passed"))
        and bool(m.get("human_reviewer")) and bool(m.get("human_review_date")),
        ("drafter", "verifier"),
    ),
)


def _applicable(gate: AcceptanceGate, student_kind: str) -> bool:
    return student_kind in gate.applies_to


# --------------------------------------------------------------------------- #
# Certificate evaluation
# --------------------------------------------------------------------------- #

@dataclass
class CertificateResult:
    passed: bool
    student_kind: str
    artifact_id: str
    gate_results: dict[str, bool] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "student_kind": self.student_kind,
            "artifact_id": self.artifact_id,
            "gate_results": self.gate_results,
            "failures": self.failures,
        }


def evaluate_certificate(
    manifest: dict,
    evaluation: dict,
    benchmark: dict,
    *,
    student_kind: str,
    gates: tuple[AcceptanceGate, ...] = DEFAULT_GATES,
) -> CertificateResult:
    """Apply the §10 gates to a student's reports and return a pass/fail with reasons.

    ``manifest`` is the artifact manifest (identity source); ``evaluation`` holds the
    quality metrics (``accepted_precision``, ``coverage``, ``critical_errors``,
    ``evaluation_kind``, ``independent_human_review``, human-review fields); ``benchmark``
    holds the latency metrics (``median_latency_improvement``, ``p95_regression``,
    ``new_behaviour_failures``). Only the gates whose ``applies_to`` contains
    ``student_kind`` are enforced.

    Beyond the threshold table, this enforces the JEV structural requirements:
    ``evaluation_kind == "final_holdout"`` and ``independent_human_review is True``.
    """
    artifact_id = artifact_signature(manifest)
    metrics = {**evaluation, **benchmark}
    result = CertificateResult(True, student_kind, artifact_id)

    # Structural requirements (JEV activation_valid), always enforced.
    if evaluation.get("evaluation_kind") != "final_holdout":
        result.failures.append("evaluation_kind != final_holdout")
    if evaluation.get("independent_human_review") is not True:
        result.failures.append("independent_human_review != true")
    # Identity binding: reports must name the same artifact.
    for report_name, report in (("evaluation", evaluation), ("benchmark", benchmark)):
        if report.get("artifact_id") not in (None, artifact_id):
            result.failures.append(f"{report_name}.artifact_id mismatch")

    for gate in gates:
        if not _applicable(gate, student_kind):
            continue
        ok = bool(gate.check(metrics))
        result.gate_results[gate.name] = ok
        if not ok:
            result.failures.append(f"gate failed: {gate.name} ({gate.description})")

    result.passed = not result.failures
    return result


def activation_valid(artifact_dir: str | Path, *, student_kind: str) -> bool:
    """Demo2-local mirror of ``jev/runtime.py::activation_valid`` over a certificate dir.

    Requires ``manifest.json``, ``activation.json``, ``evaluation.json`` and
    ``benchmark.json`` in ``artifact_dir``; checks the activation record binds the
    exact artifact identity and the SHA-256 of each report, then runs
    :func:`evaluate_certificate`. Returns False on any missing/malformed file rather
    than raising, so a caller can gate silently.
    """
    root = Path(artifact_dir)
    required = ("manifest.json", "activation.json", "evaluation.json", "benchmark.json")
    if not all((root / name).is_file() for name in required):
        return False
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        activation = json.loads((root / "activation.json").read_text())
        evaluation = json.loads((root / "evaluation.json").read_text())
        benchmark = json.loads((root / "benchmark.json").read_text())
    except (ValueError, OSError):
        return False

    identity = artifact_signature(manifest)
    if activation.get("artifact_id") != identity:
        return False
    if activation.get("evaluation_sha256") != file_sha256(root / "evaluation.json"):
        return False
    if activation.get("benchmark_sha256") != file_sha256(root / "benchmark.json"):
        return False

    return evaluate_certificate(
        manifest, evaluation, benchmark, student_kind=student_kind
    ).passed
