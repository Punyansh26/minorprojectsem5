#!/usr/bin/env python3
"""Trivial, fast self-check for the FutureWork 11 fact-leakage guard (safe to run anytime).

Loads no model, hits no network, uses no GPU. Confirms the guard detects a planted leak and
passes the shipped fillers. Exits 0 on success, 1 on failure. This is the "trivial function"
check required before trusting the long runner; it does NOT execute the long L0 run.
"""
import sys

import fillers
import filler_guard


def main() -> int:
    ok = True

    # Shipped fillers must be fact-free (chapter §9: rate 0%).
    shipped = [p for phrases in fillers.FILLERS.values() for p in phrases]
    result = filler_guard.leakage_rate(shipped)
    print(f"shipped fillers: {result['leaked']}/{result['total']} leaked, "
          f"rate={result['rate']:.4f}, pass={result['pass']}")
    ok = ok and result["pass"]

    # A planted leak must be caught (detector sanity).
    planted = "शुल्क ₹90,000 है।"
    tokens = filler_guard.find_fact_tokens(planted)
    print(f"planted leak {planted!r} -> tokens {tokens}")
    ok = ok and bool(tokens)

    print("SELF-CHECK:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
