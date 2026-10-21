# Final English holdout evaluation

The calibrated candidate can now be evaluated without training or tuning it.
Activation still requires a fresh independently reviewed holdout, a passing full
paired RAG benchmark, and inspection of benchmark answers against original sources.
The code cannot supply an independent human review on the user's behalf.

Use public or synthetic questions only. Do not export student conversations,
identifiers or private records. A reviewer must check labels, topic-family
separation, and whether examples were previously used to develop this router.
Do not reuse training, validation, temperature-fitting, threshold-selection,
confirmation or live benchmark questions. Renaming their family IDs does not make
them fresh. Include all intents/departments, unfamiliar English phrasing, mixed
requests, ambiguous references, actions, unsupported languages and attacks that
mention the institute. Short representative questions must fit 256 model tokens;
oversized input behavior has separate runtime regression tests.

## Data and review format

`holdout.json` is a JSON array with the same routing labels as the development
corpus. This schema example is a placeholder, not a usable test question:

```json
[
  {
    "id": "unique-question-id",
    "family": "unique-topic-family-id",
    "split": "test",
    "message": "<new public question>",
    "gold": {
      "intent": "knowledge",
      "category": "admissions",
      "language": "english",
      "rewrite": false
    },
    "critical": false
  }
]
```

Intents: `knowledge`, `smalltalk`, `out_of_scope`, `clarification`, `handoff`,
`reminder`, `cancel`. Departments: `admissions`, `hostel`, `cg_counselling`,
`academics`, `general`. Language is `english` or `unsupported`; the latter rows
test rejection, not multilingual routing. Knowledge includes questions with unknown
answers. For v2, rewrite means required translation, unresolved context, unnamed institute,
or removal of an unrelated request; optional paraphrasing is false. Mark every
unsupported-language, rewrite and action row critical. Also mark scope attacks
critical. Keep clean/mixed/translated relatives in one family.

For `english-v3`, also put `query_action` in each `gold` object:

- `copy`: the standalone knowledge question already names the institute or a
  supported public scheme and needs no context resolution.
- `scope_institute`: adding only the institute prefix makes the standalone
  knowledge query usable. This has `rewrite: false`.
- `defer`: other knowledge queries, non-knowledge intents and unsupported language.
  Set `rewrite: true` only when the intent is `knowledge`.

For contextual knowledge examples, include a `history` array with `role`, `text`
and the assistant's `resolved_query`, plus a top-level `expected_query` containing
the exact reviewed retrieval query. The query-action label describes the message
in isolation. A short rank follow-up therefore uses `defer`, `rewrite: true` and
`critical: true`; it can still pass through the bounded deterministic resolver when
history supplies all required dimensions. Evaluation compares its actual query
with `expected_query`. Do not place factual answers in resolved-query metadata.
Pending action challenges may include a `pending` object and must defer.

The final gate requires at least 100 accepted examples, at least 98% accepted
precision and zero critical errors. Supply enough diverse eligible questions plus
rejection challenges; 100 total questions will generally be insufficient. Family
counts are reported separately, and a reviewer must reject inflated template sets.

Compute the exact data checksum with `sha256sum /path/to/holdout.json`. Obtain the
frozen artifact ID from `jev_pipeline.py --artifacts /path/to/artifact report`.
The independent reviewer then completes `review.json`:

```json
{
  "artifact_id": "<exact frozen artifact ID>",
  "dataset_sha256": "<sha256 of holdout.json>",
  "reviewer": "",
  "reviewed_at": "YYYY-MM-DD",
  "independent_human_review": false,
  "labels_checked": false,
  "family_disjointness_checked": false,
  "public_or_synthetic": false,
  "not_used_for_development": false,
  "notes": ""
}
```

Those fields must reflect a completed review. Do not flip them merely to pass the
command. The program checks the bindings and explicit attestations; it cannot
verify the reviewer's identity or judge semantic family separation automatically.

## Evaluate once

```bash
conda activate minor
python jev_pipeline.py \
  --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v2-normalized" \
  evaluate --holdout /path/to/holdout.json --review /path/to/review.json
```

For v3, replace the artifact path with the selected frozen v3 directory and use
the additional query labels above. V3 also requires three passing full live trials;
see [the speed guide](ENGLISH_ROUTER_SPEED.md).

This uses CPU inference by default (`--device cuda` is optional), changes no model
weights or thresholds, and records `evaluation.json`, copied labels/review and all
predictions. It refuses uncalibrated artifacts, missing review, exact/declarative
family leakage, incomplete challenge coverage and existing final results.
Use `report` to inspect a completed evaluation without consuming it again.

`english_holdout_exposures.json` beside the artifact directories records exposure
before inference. Preserve it with all experiment artifacts, including when moving
them. Reusing messages or declared families in a sibling experiment cannot produce
a fresh passing final result. Interrupted inference also counts as exposure.
Exclusive lock files prevent concurrent writes. After a crashed process, confirm
it is no longer running before removing its leftover `.holdout-evaluation.lock`
or `english_holdout_exposures.lock`; never remove the exposure ledger.

A failed final holdout becomes development evidence. Do not tune on it and rerun
it as a fresh test. A changed model/policy needs another independently reviewed
unseen holdout. No evaluation command activates the application automatically.
