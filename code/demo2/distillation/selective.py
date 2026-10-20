"""§2.3 temperature scaling and selective escalation (Demo2-local, CPU-only, no model).

A selective student answers a turn itself only when confident, and otherwise *defers*
to the 9B. Chapter 09 §2.3 gives the three pieces this module implements, with no
numpy/torch dependency (pure Python, so it runs on the CPU-only tier and in unit
tests):

* **Temperature scaling** [R911]: calibrate a classifier's confidence with one scalar
  ``T`` fit on held-out data, dividing logits before softmax,
  ``p_hat = softmax(z / T)``.
* **Selective threshold**: the student abstains unless ``max_c p_hat_c >= theta``,
  with ``theta`` chosen on calibration data to hold **accepted precision >= target**
  (JEV's rule is 0.98) at the largest coverage.
* **Expected cost**: ``E[t] = cov * t_student + (1 - cov) * (t_student + t_9B)`` — so
  **coverage**, not peak accuracy, drives the saving. This is why JEV's 36% coverage
  barely moved the median.

These functions are the maths a router/verifier/drafter calibration step (§4/§6)
would call; they are implemented and tested here so Stage 0 ships the selective rule
even though the students themselves are deferred to long GPU tests.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


# --------------------------------------------------------------------------- #
# Temperature scaling (§2.3, [R911])
# --------------------------------------------------------------------------- #

def temperature_scale(logits: Sequence[float], temperature: float) -> list[float]:
    """Return ``softmax(logits / temperature)`` as a probability list.

    Numerically stable (subtracts the max). ``temperature > 0`` required; T == 1 is the
    uncalibrated softmax, T > 1 softens (less confident), T < 1 sharpens.
    """
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    scaled = [z / temperature for z in logits]
    peak = max(scaled)
    exps = [math.exp(s - peak) for s in scaled]
    total = sum(exps)
    return [e / total for e in exps]


def _nll(logits_list: Sequence[Sequence[float]], labels: Sequence[int], temperature: float) -> float:
    """Mean negative log-likelihood of ``labels`` under temperature-scaled logits."""
    total = 0.0
    for logits, label in zip(logits_list, labels):
        probs = temperature_scale(logits, temperature)
        total += -math.log(max(probs[label], 1e-12))
    return total / max(len(labels), 1)


def fit_temperature(
    logits_list: Sequence[Sequence[float]],
    labels: Sequence[int],
    *,
    lo: float = 0.05,
    hi: float = 10.0,
    iterations: int = 60,
) -> float:
    """Fit the single temperature that minimises NLL on held-out (logits, label) pairs.

    Ternary search over a convex-enough 1-D objective; returns T in [lo, hi]. This is
    the calibration step §2.3 names; it needs only the model's held-out logits, no
    training.
    """
    if not logits_list:
        return 1.0
    for _ in range(iterations):
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        if _nll(logits_list, labels, m1) < _nll(logits_list, labels, m2):
            hi = m2
        else:
            lo = m1
    return round((lo + hi) / 2.0, 4)


# --------------------------------------------------------------------------- #
# Selective threshold + coverage (§2.3)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ThresholdFit:
    """The calibrated accept threshold and the operating point it buys."""

    threshold: float
    coverage: float
    accepted_precision: float
    accepted: int
    correct: int
    n: int


def _confidences(logits_list: Sequence[Sequence[float]], temperature: float):
    for logits in logits_list:
        probs = temperature_scale(logits, temperature)
        best = max(range(len(probs)), key=lambda i: probs[i])
        yield best, probs[best]


def threshold_for_precision(
    logits_list: Sequence[Sequence[float]],
    labels: Sequence[int],
    *,
    target_precision: float = 0.98,
    temperature: float = 1.0,
) -> ThresholdFit:
    """Largest-coverage accept threshold holding accepted precision >= target.

    Sweeps candidate thresholds (the distinct observed confidences) from low to high;
    for each, "accept" the turns whose top-class confidence >= threshold and measure
    the precision of those accepts. Returns the *lowest* threshold (hence highest
    coverage) whose accepted precision meets the target. If no threshold reaches the
    target, returns a threshold above 1.0 → zero coverage (abstain on everything),
    which is the safe degenerate: never answer rather than answer below precision.
    """
    if not 0.0 < target_precision <= 1.0:
        raise ValueError("target_precision must be in (0, 1]")
    preds = list(_confidences(logits_list, temperature))
    n = len(preds)
    if n == 0:
        return ThresholdFit(1.0 + 1e-9, 0.0, 1.0, 0, 0, 0)

    candidates = sorted({conf for _, conf in preds})
    best: ThresholdFit | None = None
    for threshold in candidates:
        accepted = [(pred, lab) for (pred, conf), lab in zip(preds, labels) if conf >= threshold]
        if not accepted:
            continue
        correct = sum(pred == lab for pred, lab in accepted)
        precision = correct / len(accepted)
        if precision >= target_precision:
            fit = ThresholdFit(
                threshold=round(threshold, 6),
                coverage=round(len(accepted) / n, 6),
                accepted_precision=round(precision, 6),
                accepted=len(accepted),
                correct=correct,
                n=n,
            )
            # Lowest qualifying threshold = highest coverage; candidates ascend, so the
            # first qualifying one is the answer.
            best = fit
            break
    if best is None:
        return ThresholdFit(round(candidates[-1] + 1e-9, 6), 0.0, 1.0, 0, 0, n)
    return best


def coverage_at_threshold(
    logits_list: Sequence[Sequence[float]],
    *,
    threshold: float,
    temperature: float = 1.0,
) -> float:
    """Fraction of turns the student would answer (top confidence >= threshold)."""
    preds = list(_confidences(logits_list, temperature))
    if not preds:
        return 0.0
    return round(sum(conf >= threshold for _, conf in preds) / len(preds), 6)


# --------------------------------------------------------------------------- #
# Expected cost / saving (§2.3 E[t])
# --------------------------------------------------------------------------- #

def expected_turn_time(coverage: float, t_student: float, t_9b: float) -> float:
    """``E[t] = cov * t_student + (1 - cov) * (t_student + t_9B)`` (§2.3).

    The student always runs; on deferred turns the 9B runs *after* it, so the deferred
    arm pays ``t_student + t_9B``. Equivalent to ``t_student + (1 - cov) * t_9B``.
    """
    if not 0.0 <= coverage <= 1.0:
        raise ValueError("coverage must be in [0, 1]")
    if t_student < 0 or t_9b < 0:
        raise ValueError("times must be non-negative")
    return coverage * t_student + (1.0 - coverage) * (t_student + t_9b)


def selective_saving(coverage: float, t_student: float, t_9b: float) -> dict:
    """Seconds and fraction saved versus always calling the 9B for this stage.

    Baseline is the always-9B cost ``t_9B`` (the stage the student replaces). Returns
    absolute and relative saving plus the expected time, so a caller can report the
    §11 per-stage saving table honestly — the saving scales with coverage.
    """
    expected = expected_turn_time(coverage, t_student, t_9b)
    saved = t_9b - expected
    return {
        "coverage": round(coverage, 6),
        "expected_time": round(expected, 6),
        "baseline_9b_time": round(t_9b, 6),
        "saved_seconds": round(saved, 6),
        "saved_fraction": round(saved / t_9b, 6) if t_9b > 0 else 0.0,
    }
