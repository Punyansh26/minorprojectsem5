"""Emit the chapter 12 §6 report block and apply the §9 regression gates.

The protocol chapter requires every experiment to produce one markdown block with a pinned
manifest and a SHIP / HOLD / REJECT verdict, and §11 requires the emitter to **refuse to emit
a verdict if residency drifted or any side-effect patch was bypassed**. This module is the
single place those rules live.

  * `EvidenceLabel`  — the three labels from 00_INDEX; a gate may rest only on `MEASURED`.
  * `Metric`         — one reported row (name, baseline/candidate p50/p95, Δ+CI, gate verdict).
  * `GateResult`     — pass/fail of a named §9 gate with the rule that decided it.
  * evaluate_* helpers — translate `stats.py` outputs into gate verdicts
    (latency p50/p95, status McNemar, claim Wilson, cache false-hit, VRAM).
  * `render_report_block(...)` — the §6 markdown; raises `ResidencyDriftError` or
    `SideEffectError` so a drifted / side-effecting run can never be presented as a result.

Pure Python; imports `stats` only. No model, network or GPU.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence

import stats


class EvidenceLabel(str, Enum):
    """00_INDEX labels. A gate decision may rest only on MEASURED values."""
    MEASURED = "[Measured-here]"
    REPORTED = "[Reported]"
    ESTIMATED = "[Estimated]"


class ResidencyDriftError(RuntimeError):
    """Raised when ollama residency changed across the run (§7.1): the run is not comparable."""


class SideEffectError(RuntimeError):
    """Raised when a side-effect patch was bypassed (§7.7): a write happened during eval."""


# default §9 thresholds, kept here next to the gate logic
P95_RATIO_MAX = 1.05           # performance_passed
CLAIM_UPPER_MAX = 0.01         # G-claim: unsupported-claim 95 % upper ≤ 1 %
RECALL_MIN = 0.90              # G-recall
VRAM_MAX_T0_MIB = 8188         # G-vram on T0
STATUS_ALPHA = 0.05            # G-status: McNemar worsening p ≥ 0.05


@dataclass
class Metric:
    """One row of the §6 metric table."""
    name: str
    baseline: str = ""
    candidate: str = ""
    delta_p50: str = ""
    delta_p95: str = ""
    gate: str = ""
    evidence: EvidenceLabel = EvidenceLabel.MEASURED

    def row(self) -> str:
        return (f"| {self.name} | {self.baseline} | {self.candidate} | "
                f"{self.delta_p50} | {self.delta_p95} | {self.gate} |")


@dataclass
class GateResult:
    """Pass/fail of one named §9 gate, with the rule and evidence label that decided it."""
    gate: str
    passed: Optional[bool]       # None = not applicable / insufficient data
    detail: str
    evidence: EvidenceLabel = EvidenceLabel.MEASURED


# --------------------------------------------------------------------------- gate helpers


def evaluate_latency_p50(ci: dict, *, non_latency_change: bool = False) -> GateResult:
    """G-latency-p50: Δ p50 95 % CI entirely ≤ 0 (improvement), or unchanged for a
    non-latency change (CI must straddle / include 0, i.e. no regression)."""
    lo, hi, point = ci["ci_low"], ci["ci_high"], ci["point"]
    detail = f"Δp50 point={point:.4g}s, 95% CI [{lo:.4g}, {hi:.4g}]"
    if non_latency_change:
        passed = not ci["regression"]     # must not get slower
        return GateResult("G-latency-p50", passed, detail + " (non-latency change: no regression)")
    return GateResult("G-latency-p50", ci["improvement"], detail)


def evaluate_latency_p95(ratio: dict) -> GateResult:
    """G-latency-p95: p95_ratio candidate/baseline ≤ 1.05 (CI upper bound)."""
    hi = ratio["ratio_high"]
    passed = hi <= P95_RATIO_MAX
    return GateResult("G-latency-p95", passed,
                      f"p95 ratio point={ratio['point']:.4f}, CI upper={hi:.4f} (limit {P95_RATIO_MAX})")


def evaluate_status(mcnemar_result: dict, *, alpha: float = STATUS_ALPHA) -> GateResult:
    """G-status: answer-status accuracy not significantly worse.

    Worse only if the candidate lost on balance (b > c) AND that change is significant.
    A tie or a gain always passes.
    """
    b, c, p = mcnemar_result["b"], mcnemar_result["c"], mcnemar_result["p_value"]
    worse = c < b
    significant = p < alpha
    passed = not (worse and significant)
    direction = "candidate worse" if worse else ("candidate better" if c > b else "tie")
    return GateResult("G-status", passed,
                      f"b={b} c={c} p={p:.4g} ({direction}); fails only if worse and p<{alpha}")


def evaluate_claim(wilson: dict, *, limit: float = CLAIM_UPPER_MAX) -> GateResult:
    """G-claim: unsupported-claim 95 % Wilson upper bound ≤ limit (needs ≥300 clean cases)."""
    hi = wilson["high"]
    enough = wilson["n"] >= stats.samples_for_upper_bound(limit)
    passed = hi <= limit and enough
    note = "" if enough else f" (INSUFFICIENT: need ≥{stats.samples_for_upper_bound(limit)} clean cases, have {wilson['n']})"
    return GateResult("G-claim", passed,
                      f"unsupported-claim rate p̂={wilson['point']:.4f}, 95% upper={hi:.4f} (limit {limit}){note}")


def evaluate_cache_false_hit(wilson: dict) -> GateResult:
    """G-cache: cache false-hit rate = 0 (release-bound keys). Any observed false hit fails."""
    passed = wilson["successes"] == 0
    return GateResult("G-cache", passed,
                      f"false-hits={wilson['successes']}/{wilson['n']}, 95% upper={wilson['high']:.4f} (must be 0)")


def evaluate_vram(peak_mib: float, *, limit: float = VRAM_MAX_T0_MIB) -> GateResult:
    """G-vram: VRAM peak ≤ 8188 MiB on T0 with desktop resident."""
    passed = peak_mib <= limit
    return GateResult("G-vram", passed, f"peak={peak_mib:.0f} MiB (limit {limit} MiB on T0)")


def evaluate_recall(recall_at_6: float, *, minimum: float = RECALL_MIN) -> GateResult:
    """G-recall: retrieval recall@6 ≥ 0.90."""
    passed = recall_at_6 >= minimum
    return GateResult("G-recall", passed, f"recall@6={recall_at_6:.4f} (min {minimum})")


# --------------------------------------------------------------------------- verdict + render


def overall_verdict(gates: Sequence[GateResult]) -> tuple[str, str]:
    """SHIP / HOLD / REJECT from the applicable gates (§8 flow).

    REJECT if any applicable gate fails; HOLD if a required gate is inapplicable/unknown
    (None) and none failed; SHIP only if every applicable gate passed.
    """
    failed = [g for g in gates if g.passed is False]
    unknown = [g for g in gates if g.passed is None]
    if failed:
        return "REJECT", "failed: " + ", ".join(g.gate for g in failed)
    if unknown:
        return "HOLD", "insufficient evidence: " + ", ".join(g.gate for g in unknown)
    return "SHIP", "all applicable gates passed"


@dataclass
class Residency:
    """ollama /api/ps snapshot used for the §7.1 pin. `stable` is the run-wide check."""
    size_vram: Optional[int] = None
    total: Optional[int] = None
    context_length: Optional[int] = None
    digest: Optional[str] = None
    stable: bool = True

    def summary(self) -> str:
        if self.size_vram is None:
            return "residency: not captured"
        return (f"size_vram={self.size_vram}/{self.total}, context={self.context_length}, "
                f"digest={(self.digest or '')[:12]} (unchanged across run: {'yes' if self.stable else 'no'})")


@dataclass
class ReportBlock:
    """Everything the §6 template needs. `render()` enforces the §7 refusals."""
    experiment_id: str
    chapter: str
    change_under_test: str
    baseline_ref: str
    tier: str = "T0"
    warm: str = "warm"
    trials: int = 3
    order: str = "alternating"
    dataset: str = ""
    normalisation: str = ""
    residency: Residency = field(default_factory=Residency)
    side_effects_written: int = 0
    human_review: str = "no"
    metrics: list[Metric] = field(default_factory=list)
    gates: list[GateResult] = field(default_factory=list)

    def render(self) -> str:
        """Emit the §6 markdown block. Refuses (raises) on residency drift or a side effect."""
        if not self.residency.stable:
            raise ResidencyDriftError(
                f"{self.experiment_id}: ollama residency drifted during the run (§7.1); "
                "the run is not comparable and no verdict may be emitted.")
        if self.side_effects_written != 0:
            raise SideEffectError(
                f"{self.experiment_id}: {self.side_effects_written} side effect(s) written during eval "
                "(§7.7); create_ticket/create_reminder must be patched to raise.")
        verdict, reason = overall_verdict(self.gates)
        header = [
            f"### Experiment: {self.experiment_id}  ({self.chapter}, one change: {self.change_under_test})",
            f"- Change under test: {self.change_under_test} vs baseline {self.baseline_ref}",
            f"- Tier: {self.tier}    Warm/Cold: {self.warm}    Trials: >={self.trials}    Order: {self.order}",
            f"- Residency (ollama ps): {self.residency.summary()}",
            f"- Dataset: {self.dataset}    Normalisation: {self.normalisation or '—'}",
            "",
            "| Metric | Baseline (p50 / p95) | Candidate (p50 / p95) | Δ p50 [95% CI] | Δ p95 [95% CI] | Gate |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        rows = [m.row() for m in self.metrics]
        gate_lines = ["", "Gate results:"]
        for g in self.gates:
            mark = {True: "PASS", False: "FAIL", None: "N/A"}[g.passed]
            gate_lines.append(f"- {g.gate}: {mark} — {g.detail}")
        footer = [
            "",
            f"- Verdict: {verdict}    Reason: {reason}",
            f"- Human review done: {self.human_review}    Side-effects written: {self.side_effects_written}",
        ]
        return "\n".join(header + rows + gate_lines + footer) + "\n"
