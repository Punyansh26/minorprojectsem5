# English v3: faster grounded replies

Success means lower end-to-end response latency while retaining grounding review.
JEV replaces routing calls; it does not generate the factual answer. The earlier
normalized v2 run saved about 5.8 seconds on accepted turns, but accepted only
12/66 turns and improved the overall median by 2.2%.

## Runtime

`english-v3` uses the same pinned MiniLM encoder, with intent, department,
English/defer and query-action heads. It runs on the existing bounded CPU worker.
The query actions are `copy`, `scope_institute` and `defer`. Institute scoping only
prefixes the original message; it never invents programme, year, category or rank
dimensions. A recognizable institute topic is required before adding context.
Relevant named public-scheme questions can be copied without an institute name.

V3 permits a complete named English institute question after history. It also
resolves exact English category/round follow-ups before calling an LLM, provided
the previous resolved rank query contains the required scope. Other contextual
requests, Hindi/Hinglish, pending actions and uncertain decisions use the existing
selected-provider router. Neither local path authorizes an action.

Department uncertainty yields no retrieval preference. `detected_category` remains
available for the existing adapter; the additive `retrieval_preference` state is
used consistently by retrieval and its cache key. Metrics distinguish
`open_jev` from `deterministic_followup`, record query strategy and department
abstention, and count actual routing LLM calls saved. Generation, review and exact
citations remain mandatory on answered turns, including draft-cache hits.

V2's policy, preprocessing and artifacts remain separate. V3 manifests bind the
weights, tokenizer, policy dependencies, calibration and development data.

## Train and inspect

Use the existing `minor` environment from `institute-assistant`:

```bash
python jev_pipeline.py --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v3-new" prepare --profile english-v3
python jev_pipeline.py --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v3-new" train --device cuda --resume
python jev_pipeline.py --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v3-new" report
```

Frozen and fine-tuned candidates share the pinned base and family splits. Defaults
are 40 epochs with five-epoch validation patience. Candidate selection uses
uncalibrated validation loss. Temperatures and thresholds use separate calibration
families. Threshold selection retains 98% accepted precision, zero critical errors,
30 accepted families and 10 accepted knowledge decisions.

The first speed experiment contains 912 rows in 822 declared families, including
70 unsupported-language examples. It combines existing development data with
focused query-preparation examples. Named/unnamed and clean/mixed relatives share
families. This is an initial speed experiment, below the proposed 1,200-family
expansion; it does not establish independent real-traffic quality. The fixed live
questions are excluded. No final gold is generated during preparation.

The query-action head learns to defer non-knowledge English examples as well as
unsafe knowledge requests. The first experiment exposed why this matters: an
unrelated seawater question was mistakenly scoped to the institute. The revised
head and positive topic boundary reject that case.

The calibration grid includes a department threshold of 1.0, meaning effectively
neutral retrieval. This is not a claim of perfect department classification:
reports retain raw department accuracy and abstention counts. The calibrated
first speed candidate selected neutral retrieval, with 74/74 accepted calibration
decisions and 91/91 accepted validation decisions correct.

The first live run exposed excessive query-action abstention. The calibration
search now considers query-action thresholds from 0.99 down to 0.50, keeping the
same precision, critical-error and support requirements. It chooses the strictest
threshold among equal-coverage results. Threshold selection uses calibration
families only; it does not optimize on the live questions. Recalibration selected
0.85 for `english-v3-speed-r3`, accepting 76/76 calibration and 94/94 validation
decisions correctly. Both are development results, not fresh holdout evidence.

`calibrate --output /new/path` reuses authenticated weights and recalibrates only
on development calibration rows in a new immutable artifact. It preserves the
source and does not copy final evaluation, benchmark or activation certificates.
`freeze --output /new/path` exports an already supported development policy without
recalibrating. A changed inference policy requires a new experiment.

## Measure response latency

```bash
python jev_pipeline.py --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v3-speed-r3" benchmark --trials 3
```

Each trial runs the full public suite with separate caches for every case and
mode; only that case's repeat phase reuses its cache. Mode order alternates across
trials and phases. The benchmark warms inference, records model/KB identity and
Ollama residency, and refuses changes during measurement. It blocks action writes.
Run without competing training or inference jobs for meaningful timings.

Results are retained under `benchmarks/<run>/`, including partial/interrupted
runs. The top-level benchmark files point to the latest complete run; previous
files are archived. `--quick` is diagnostic, runs one trial, and cannot activate.
One full trial is also diagnostic; v3 promotion requires at least three full trials.

Every trial must pass the existing coverage, median latency, p95 and behavior
gates. Classifier coverage excludes deterministic follow-ups. Reports separately
show routing-call savings, actual cache outcomes, language and stage totals.
The main verdict remains total response time, excluding audio.

The initial live environment has Qwen3.5 9B partially on CPU. Record the residency
when comparing runs; classifier speed does not eliminate generation/review costs.

### Measured development results, 2026-09-27

The first complete v3 run (`english-v3-speed-calibrated`, run
`20260927T010859Z-2cce87b5`) contains three trials and 198 paired turns:

| Metric | Result |
| --- | --- |
| Classifier coverage | 36.36% |
| Additional deterministic follow-up coverage | 6.06% |
| Routing LLM calls | 192 off; 108 enabled |
| Total LLM calls | 411 off; 324 enabled |
| Median total response | 17.018 s off; 16.318 s enabled |
| Median improvement | 4.11% |
| p95 total response | 43.025 s off; 45.417 s enabled |
| New automated behavior failures | 0 |

This run **failed** the latency gates. Individual trial median gains were 8.74%,
6.31% and 4.13%; the first trial also regressed p95 by 14.61%. Query-action
confidence caused 20 fallback turns per trial. Saved routing calls alone do not
establish the required user-visible improvement.

The separately saved `english-v3-speed-r3` artifact retains those earlier results
and reuses the same trained weights. Its artifact ID is
`a6508746430a1bb72f2ae7e06666a58335f548126b6191bf702da44c8d6fe757`.
Its repeated live benchmark is pending; development precision is not permission
to activate it.

## Evidence and release

The reporting-document defect came from an omitted table on brochure page 10.
Its source-bound review now preserves quota headings, applicability conditions,
the merged All India column and the footnote. The printed rank-card year is 2024
inside a 2026 brochure; it is preserved verbatim, not silently corrected. Full-page
visual evidence is retained beside the initial incomplete crop. The new immutable
KB release passed retrieval evaluation before activation; its predecessor remains
available for rollback. Reporting retrieval prioritizes the requirements section,
and both answer/review prompts preserve certificate applicability and fee periods.

Source inspection of the first complete v3 run still found failures in both
modes despite zero new automated failures. The CG-quota follow-up added incomplete
eligibility conditions: it omitted the Chhattisgarh schooling qualification and
the reserved-category age relaxation on brochure page 8. Fee replies did not
clearly identify the first-semester period from page 11. Reporting-document
replies omitted the quota distinction on page 10, including its All India/JoSAA
column. These findings leave source review failed; prompt instructions and valid
quotes alone did not resolve them. Correct and recheck these answers before
activation. The reviewed source PDF SHA-256 is
`3fdcf2d380898cd2bf3487f3aef0c808b634872470d418d438aa3941399ebbac`.

Before JEV activation, obtain a fresh holdout and independent human attestation
using [the holdout workflow](ENGLISH_ROUTER_HOLDOUT.md). V3 gold additionally needs
`query_action`; `rewrite=true` marks knowledge that needs more than standalone
copying or institute scoping. Fully reviewed history may allow the exact rank
follow-up resolver; other such requests retain LLM rewriting.
For reviewed contextual examples include `history` and the exact `expected_query`.
The evaluator uses the same policy as runtime and retains the shared exposure ledger.

Require at least 100 accepted examples, 98% precision, zero critical failures,
three passing live trials and completed source review. Leave `JEV_ROUTING_MODE`
off until all gates pass. Neither training nor a benchmark activates the app.
After activation, use the chosen artifact with the existing JEV settings; `off`
remains immediate rollback after restarting the application.
