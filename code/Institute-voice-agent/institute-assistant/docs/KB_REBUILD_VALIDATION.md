# Knowledge-base rebuild validation

Generated: 2026-09-22T10:04:28.392497+00:00

Release: `20260922T095421217856Z`

- Vector chunks: 222; structured cutoff records: 611.
- Source entries: 75; failed fetches: 26. Failed sources are not marked fresh.
- Extraction blocks awaiting review: 267.
- Evaluation cases: 117; answerable cases: 93.
- Supporting-evidence recall@6: 0.9892; previous corpus recall@6: 0.1075.
- Exact cutoff tests: 42/42.
- Warm retrieval median/p95: 0.0114 / 0.0138 seconds (excludes LLM and speech).

The benchmark tests retrieval and exact numeric lookup. It does not prove the factual accuracy of every generated answer. The expanded corpus and new extractor/model both contribute to changes from the baseline; this is not an isolated embedding-model comparison.

## Remaining limitations

- The institute website timed out during acquisition; current institute scholarships, spot notices, CG/NTPC cutoffs and several service policies need offline confirmation or a later successful refresh.
- Unsupported/unreadable sources and unreviewed visual interpretations are excluded. There is no automatic inference of precise values from unlabeled graphs.
- Bank-specific live rates and institute eligibility for loan subsidies were not established.
- Historical annual reports and dated statistics remain historical.
- See `kb_state/extraction_report.json`, the source inventory, extraction review queue, and the offline checklist for traceable gaps.

Retrieval cases still failing: loan_repayment_hindi

## Live answer checks

Attempted 7 fixed public questions; 0 met expected answer statuses and 7 returned unavailable.
The recorded 2026-09-22 run hit Groq rate limits. This does not validate factual generation or abstention on the new corpus. See [saved live results](kb_live_evaluation.json). No ticket or reminder writes were permitted.

## Code and integration checks

- Agent offline suite: 69 passed; Demo 2 suite: 13 passed.
- Regression cases cover exact rank dimensions, source-bound financial conditions, failed fetch/build preservation, and activation/rollback.
- Demo 2 shared release smoke: 20260922T095421217856Z (passed: exact rank, missing NTPC, scanned calendar).
- Original index backup: `kb_state/backups/legacy-before-verified-20260922`.
