"""Single decision rule for every evaluation gate (chapter 12 §4).

Pure-Python implementation of the four statistics the protocol chapter names as the
one-change-at-a-time acceptance test. No heavy dependency: `random` and `math` only,
so the module imports with zero model/network/GPU cost and can gate CI.

  * `paired_bootstrap_ci`  — §4.2, CI on Δ of a paired latency statistic (median / p95),
    resampling **over pairs** so the within-case correlation the paired design created is
    preserved [R1215, R1220].
  * `mcnemar`              — §4.3, exact binomial (small discordant counts) and
    continuity-corrected χ² for paired binary outcomes [R1216].
  * `wilson_interval`      — §4.4, Wilson score 95% interval for a proportion [R1217].
  * `rule_of_three`        — §4.4, 3/n upper bound for 0 observed events; the sample size
    needed to support a "<rate" claim [R1218].

Every function is deterministic given its `seed`, returns plain dicts/floats, and documents
which gate it feeds. Thresholds (p95_ratio ≤ 1.05, claim upper ≤ 1 %) live with the gate
logic in `report_block.py`, not here: this module only produces the estimates.
"""
from __future__ import annotations

import math
import random
from typing import Callable, Sequence


# --------------------------------------------------------------------------- statistics


def median(values: Sequence[float]) -> float:
    """Plain median; defined for the latency distributions the paired design compares."""
    ordered = sorted(values)
    size = len(ordered)
    if size == 0:
        raise ValueError("median of empty sequence")
    mid = size // 2
    if size % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile (numpy 'linear' / type-7), q in [0, 100].

    Matches ``numpy.percentile(values, q)`` so a report that quotes p95 here reads the
    same as one computed with NumPy, without importing it.
    """
    if not 0.0 <= q <= 100.0:
        raise ValueError("q must be in [0, 100]")
    ordered = sorted(values)
    size = len(ordered)
    if size == 0:
        raise ValueError("percentile of empty sequence")
    if size == 1:
        return float(ordered[0])
    rank = (q / 100.0) * (size - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(ordered[int(rank)])
    fraction = rank - low
    return float(ordered[low] * (1.0 - fraction) + ordered[high] * fraction)


def p95(values: Sequence[float]) -> float:
    """Shorthand the latency gate reads (p95_ratio ≤ 1.05)."""
    return percentile(values, 95.0)


_STATISTICS: dict[str, Callable[[Sequence[float]], float]] = {
    "median": median,
    "p50": median,
    "p95": p95,
    "mean": lambda xs: sum(xs) / len(xs),
}


def _resolve_stat(stat: str | Callable[[Sequence[float]], float]) -> Callable[[Sequence[float]], float]:
    if callable(stat):
        return stat
    try:
        return _STATISTICS[stat]
    except KeyError:
        raise ValueError(f"unknown statistic {stat!r}; use one of {sorted(_STATISTICS)} or a callable") from None


def paired_bootstrap_ci(
    pairs: Sequence[tuple[float, float]],
    stat: str | Callable[[Sequence[float]], float] = "median",
    *,
    resamples: int = 10000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict:
    """§4.2 paired-bootstrap CI on Δ = stat(candidate) − stat(baseline).

    `pairs` is ``[(baseline_i, candidate_i), …]`` — the same case measured under both
    systems. Resampling draws **whole pairs** with replacement (not individual turns), so
    the within-case correlation survives [R1215, R1220]. For latency, lower is better: a
    change "improves" only when the whole CI is below 0.

    Returns the point estimate, the CI bounds, and `improvement`/`regression` booleans so
    the latency gate can read a single verdict. Deterministic for a fixed `seed`.
    """
    if not pairs:
        raise ValueError("paired_bootstrap_ci needs at least one pair")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    if resamples < 1:
        raise ValueError("resamples must be >= 1")
    func = _resolve_stat(stat)
    baseline = [b for b, _ in pairs]
    candidate = [c for _, c in pairs]
    point = func(candidate) - func(baseline)

    rng = random.Random(seed)
    size = len(pairs)
    diffs: list[float] = []
    for _ in range(resamples):
        idx = [rng.randrange(size) for _ in range(size)]
        b_star = [baseline[i] for i in idx]
        c_star = [candidate[i] for i in idx]
        diffs.append(func(c_star) - func(b_star))

    tail = (1.0 - confidence) / 2.0
    lo = percentile(diffs, tail * 100.0)
    hi = percentile(diffs, (1.0 - tail) * 100.0)
    return {
        "statistic": stat if isinstance(stat, str) else getattr(stat, "__name__", "callable"),
        "n_pairs": size,
        "point": point,
        "ci_low": lo,
        "ci_high": hi,
        "confidence": confidence,
        "resamples": resamples,
        "seed": seed,
        # whole CI below 0 ⇒ candidate faster; whole CI above 0 ⇒ candidate slower
        "improvement": hi < 0.0,
        "regression": lo > 0.0,
    }


def p95_ratio_ci(
    pairs: Sequence[tuple[float, float]],
    *,
    resamples: int = 10000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict:
    """p95 ratio candidate/baseline with a bootstrap CI, mirroring `performance_passed`.

    The JEV lesson (§4.2): a change ships only if p95 does not regress beyond 5 %. This
    returns the point ratio and the CI upper bound so the gate can test
    ``ratio_high <= 1.05``.
    """
    if not pairs:
        raise ValueError("p95_ratio_ci needs at least one pair")
    baseline = [b for b, _ in pairs]
    candidate = [c for _, c in pairs]
    base_p95 = p95(baseline)
    if base_p95 <= 0:
        raise ValueError("baseline p95 must be positive to form a ratio")
    point = p95(candidate) / base_p95

    rng = random.Random(seed)
    size = len(pairs)
    ratios: list[float] = []
    for _ in range(resamples):
        idx = [rng.randrange(size) for _ in range(size)]
        b_p95 = p95([baseline[i] for i in idx])
        c_p95 = p95([candidate[i] for i in idx])
        if b_p95 > 0:
            ratios.append(c_p95 / b_p95)
    tail = (1.0 - confidence) / 2.0
    return {
        "n_pairs": size,
        "point": point,
        "ratio_low": percentile(ratios, tail * 100.0),
        "ratio_high": percentile(ratios, (1.0 - tail) * 100.0),
        "confidence": confidence,
        "resamples": resamples,
        "seed": seed,
    }


def mcnemar(b: int, c: int, *, exact_threshold: int = 25) -> dict:
    """§4.3 McNemar's test for paired binary outcomes.

    `b` = #(baseline correct, candidate wrong); `c` = #(baseline wrong, candidate correct).
    Only the discordant cells carry information [R1216]. Uses the exact two-sided binomial
    test when ``b + c <= exact_threshold`` (small counts), else the continuity-corrected
    χ² approximation. Returns the p-value plus a `candidate_better` sign so the status/
    abstention gate can test "not significantly worse".
    """
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be non-negative")
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "n_discordant": 0, "method": "none", "p_value": 1.0,
                "statistic": 0.0, "candidate_better": None}

    if n <= exact_threshold:
        k = min(b, c)
        # two-sided exact binomial around p = 0.5
        tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n)
        p_value = min(1.0, 2.0 * tail)
        method = "exact_binomial"
        statistic = float(k)
    else:
        statistic = (abs(b - c) - 1) ** 2 / n
        p_value = _chi2_sf_df1(statistic)
        method = "chi2_continuity"
    return {"b": b, "c": c, "n_discordant": n, "method": method,
            "statistic": statistic, "p_value": p_value,
            "candidate_better": None if b == c else (c > b)}


def mcnemar_from_labels(
    baseline_correct: Sequence[bool], candidate_correct: Sequence[bool], **kwargs
) -> dict:
    """Build the discordant counts from per-case correctness vectors, then run `mcnemar`."""
    if len(baseline_correct) != len(candidate_correct):
        raise ValueError("label vectors must be the same length (paired on the same cases)")
    b = sum(1 for base, cand in zip(baseline_correct, candidate_correct) if base and not cand)
    c = sum(1 for base, cand in zip(baseline_correct, candidate_correct) if cand and not base)
    result = mcnemar(b, c, **kwargs)
    result["n_cases"] = len(baseline_correct)
    return result


def _chi2_sf_df1(x: float) -> float:
    """Survival function of χ² with 1 df = erfc(sqrt(x/2)); exact, no SciPy."""
    if x <= 0:
        return 1.0
    return math.erfc(math.sqrt(x / 2.0))


def wilson_interval(successes: int, n: int, *, confidence: float = 0.95) -> dict:
    """§4.4 Wilson score interval for a proportion [R1217].

    Reports the interval, never p̂ alone, for every rate gate (unsupported-claim rate,
    false-cut rate, cache false-hit rate, number-reading error rate). Returns `point`,
    `low`, `high` and `z`; the gate reads `high` (e.g. unsupported-claim `high <= 0.01`).
    """
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= successes <= n:
        raise ValueError("successes must be in [0, n]")
    z = _z_for_confidence(confidence)
    p_hat = successes / n
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    return {"successes": successes, "n": n, "point": p_hat,
            "low": max(0.0, center - half), "high": min(1.0, center + half),
            "confidence": confidence, "z": z}


def _z_for_confidence(confidence: float) -> float:
    """Two-sided normal quantile via the inverse error function (no SciPy)."""
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    if abs(confidence - 0.95) < 1e-12:
        return 1.959963984540054  # exact common case, avoids erfinv drift
    return math.sqrt(2.0) * _erfinv(confidence)


def _erfinv(x: float) -> float:
    """Inverse error function (Winitzki rational approximation + one Newton step)."""
    if not -1.0 < x < 1.0:
        raise ValueError("erfinv domain is (-1, 1)")
    if x == 0.0:
        return 0.0
    a = 0.147
    ln = math.log(1 - x * x)
    term = 2.0 / (math.pi * a) + ln / 2.0
    guess = math.copysign(math.sqrt(math.sqrt(term * term - ln / a) - term), x)
    # one Newton refinement against erf
    guess -= (math.erf(guess) - x) / (2.0 / math.sqrt(math.pi) * math.exp(-guess * guess))
    return guess


def rule_of_three(n: int, *, confidence: float = 0.95) -> dict:
    """§4.4 rule of three: with 0 observed events in `n` trials, 95 % upper ≈ 3/n [R1218].

    Also returns `n_required` — the number of clean cases needed to support a given upper
    bound (3/target). This is the quantitative replacement for "0 % hallucination": a
    "<1 %" claim needs ≥ 300 clean, grounded cases.
    """
    if n <= 0:
        raise ValueError("n must be positive")
    # for 95 % the constant is ~3; general: -ln(1-conf)
    constant = -math.log(1.0 - confidence)
    return {"n": n, "upper_bound": constant / n, "confidence": confidence, "constant": constant}


def samples_for_upper_bound(target_rate: float, *, confidence: float = 0.95) -> int:
    """Smallest `n` so that 0 observed events gives an upper bound ≤ `target_rate` [R1218]."""
    if not 0.0 < target_rate < 1.0:
        raise ValueError("target_rate must be in (0, 1)")
    constant = -math.log(1.0 - confidence)
    return math.ceil(constant / target_rate)
