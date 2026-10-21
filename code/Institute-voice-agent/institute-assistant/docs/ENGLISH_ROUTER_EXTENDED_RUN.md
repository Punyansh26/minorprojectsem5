# English router: forty-epoch results

The user completed the continuation on 26 September 2026. The fine-tuned candidate
won on uncalibrated validation masked NLL, using the original selection rule.
Further training is not the next experiment: evaluate the frozen policy in RAG.

| Validation metric | Ten epochs | Forty epochs |
| --- | ---: | ---: |
| Intent accuracy, 60 English rows | 91.7% | 93.3% |
| Department accuracy, 33 knowledge rows | 69.7% | 87.9% |
| Fine-tuned masked NLL | 0.5809 | 0.1492 |

The forty-epoch frozen-encoder baseline reached NLL 0.5640 and department accuracy
84.8%. The original training runs remain intact at `english-v2` and
`english-v2-extended` under `~/.cache/institute-assistant/open-jev/`.

## Why the training summary still reports zero accepted

Its best error-qualified threshold point accepted 23/23 calibration-selection
decisions correctly, including 14 knowledge questions. That is below the required
30 distinct accepted families, so the published training artifact correctly retained
`supported=false`. Adding epochs did not enlarge its 56-row threshold-selection set.

The selected exploratory policy requires intent and department probabilities of
at least 0.9, English probability at least 0.99, and rewrite probability at most
0.05. Department/rewrite checks apply only to knowledge. Lowering department
confidence to 0.8 admitted two wrong decisions in a 27-row accepted subset.
The 0.9 policy accepted 34/34 validation rows correctly; that split was already
used for early stopping and is not final test evidence.

## Frozen-policy confirmation

`audit` chooses the largest accepted subset in the saved calibration sweep with
at least 98% observed precision and no critical error; sweep order breaks ties.
It saves that choice, temperatures, code hashes and authored labels **before**
running inference on additional scenarios. It never adjusts thresholds using the
new outcomes. Both success and failure reports are preserved.

The additional corpus contains 147 rows in 132 declared families. Clean/mixed and
unnamed relatives share families. Eight obvious relatives of original scenarios
were removed before inference. Exact development/live-case overlap is checked;
these agent-authored scenarios do not establish statistical or semantic independence.
No model output informed their labels. They are development data, never final gold.

| Confirmation result | Value |
| --- | ---: |
| Accepted / total | 88 / 147 (59.9%) |
| Correct / accepted | 87 / 88 (98.86%) |
| Distinct accepted families | 88 |
| Accepted knowledge decisions | 73 |
| Critical errors | 0 |
| Mixed requests / action requests / unsupported-language samples accepted | 0 / 0 / 0 |

The accepted error was: “Can a candidate who studied mathematics as an additional
subject apply to IIIT-NR?” Gold department is admissions; the model chose academics
at 0.9376 probability. Its intent was correctly knowledge. This remains a mistake
even though department is only a retrieval preference. No label or threshold was
changed to erase it.

These checks satisfy the development support floors. `freeze` therefore exported
a separate calibrated candidate, with unchanged encoder/head weights and bound
confirmation evidence. Its artifact ID is
`4b809ee9f53d1ef6f5d4d4b93ab7451830a04a04ab08ac3f912d11738189d670`.
The source forty-epoch artifact is
`3e95d13988d82efc8ff5979645d55551502bb4f26e657fdad53f19f57c5309cd`.

## Reproduce and inspect

These steps have already been run on this machine. `audit` reuses a completed,
matching report without inference. `freeze` refuses an existing destination.

```bash
conda activate minor
python jev_pipeline.py \
  --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v2-extended" \
  audit --output "$HOME/.cache/institute-assistant/open-jev/english-v2-audit"

python jev_pipeline.py \
  --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v2-extended" \
  freeze --audit "$HOME/.cache/institute-assistant/open-jev/english-v2-audit" \
  --output "$HOME/.cache/institute-assistant/open-jev/english-v2-calibrated"

python jev_pipeline.py \
  --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v2-calibrated" report
```

The calibrated directory cannot resume training. Use the original training
directory for experiments. `confirmation/` preserves the original manifest,
calibration, fixed audit plan, labels and every prediction. All are checksum-bound.
Additional calibration rows are also excluded from live and final evaluations.

The complete paired RAG benchmark uses the calibrated candidate:

```bash
python jev_pipeline.py \
  --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v2-calibrated" benchmark
```

It blocks action writes, isolates caches and never enables the application.
Inspect its answer evidence against the cited documents. Follow the
[final holdout workflow](ENGLISH_ROUTER_HOLDOUT.md) before attempting activation.
Neither the confirmation result nor successful unit tests prove deployed quality.

## First complete live benchmark

The original calibrated candidate completed 50 paired case/phase records, covering
66 paired turns with Ollama `qwen3.5:9b`. There were no new behavior failures, but
the performance gates failed:

| Metric | Observed | Required |
| --- | ---: | ---: |
| Shortcut coverage | 12.12% (8/66 turns) | At least 15% |
| Median end-to-end improvement | 1.52% | At least 10% |
| Candidate / baseline p95 | 1.225 | At most 1.05 |
| Logical LLM calls | 124 vs 131 | Diagnostic |

The baseline median was 15.181 seconds versus 14.951 for the candidate; p95 was
33.633 versus 41.204 seconds. The measured tail regression mainly appeared in
generation/review, not classifier execution. For example, `cache_exact` spent
32.127 seconds in candidate grounding review versus 9.045 seconds in the baseline.
Both paths used the LLM router for that turn. This observation does not establish
why the provider timing differed, and does not waive the failed latency gate.

Both modes passed 49/50 automated case/phase checks. The shared failure was the
repeat `topic_switch` reporting-documents question returning `insufficient`.
Inspection of original brochure pages 7, 8, 10, 11 and 12 found an additional
baseline grounding defect: the uncached answer treats conditional certificate
annexures as generally mandatory reporting documents. Page 12 lists appropriate
formats; page 10 distinguishes quota-specific requirements and applicability.
The classifier deferred these turns in both experiments. Fee amounts match page
11, but the first-semester institution fee also needs clearer period wording.
`source_review.json` records these findings. Source review remains failed and
incomplete; zero *new* automated failures is not proof of factual correctness.

## Institute-name mismatch and correction

The development corpus consistently uses `IIIT-NR`. Several live questions use
the equivalent name `IIIT Naya Raipur`. A counterfactual probe changed only that
name in the fixed English admissions question:

| Head / outcome | Full name | Canonical abbreviation |
| --- | ---: | ---: |
| Knowledge intent probability | 0.9664 | 0.9977 |
| Admissions department probability | 0.7027 | 0.9499 |
| Rewrite probability | 0.0594 | 0.0077 |
| Policy outcome | Defer | Accept |

`normalize` exports a separate candidate with a checksum-bound
`institute-alias-v1` preprocessing policy. Only known aliases of this institute
map to `IIIT-NR` for the classifier encoder. The original message reaches the
acceptance policy, retrieval and generation unchanged. Other institutes are not
renamed. Existing artifacts without that field retain their original behavior.

Export requires every previous training/calibration message to remain byte-for-byte
unchanged under normalization. Otherwise it refuses and requires a new calibration
experiment. Thus this export uses the existing learned weights and fixed
calibration without retraining or relaxing thresholds. A new artifact identity
prevents inheriting old evaluation or activation certificates.

```bash
python jev_pipeline.py \
  --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v2-calibrated" \
  normalize --output "$HOME/.cache/institute-assistant/open-jev/english-v2-normalized"

python jev_pipeline.py \
  --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v2-normalized" benchmark
```

The normalized candidate has already been exported on this machine. Its ID is
`127b055335fdf5756f79f800e695cc15439f8a47027f7555b4c8adda0cf04df3`.
Direct inference through the runtime worker accepts the admissions question and
preserves its original full-name query. Offline verification passes 223 helpdesk
tests and 17 Demo 2 tests. Its live performance must be measured separately;
the failed first benchmark remains attached to the earlier calibrated artifact.

The normalized rerun was interrupted after seven complete case/phase pairs on
27 September because only about 893 MiB of the 8 GiB GPU was free and Ollama had
offloaded most model weights to CPU. No other applications were stopped. The
partial results and environment finding are retained as
`benchmark_pairs.gpu_pressure_partial.json` and `benchmark_interruption.json`.
They cannot satisfy promotion or be compared as a controlled GPU timing result.
The English admissions pair did exercise the new shortcut; a full rerun is still
required after freeing GPU memory. The model and normalization fix need no further
training for that rerun.

That pair returned the same answer and original brochure citation in both modes;
the normalized candidate used two logical LLM calls (generation and grounding
review) versus three for the baseline. Its classifier routing took 9.6 ms. The
single-pair total timings are not treated as a general speedup claim under the
observed GPU pressure.

After freeing GPU memory, unload the currently CPU-offloaded model so Ollama can
place it again, then rerun the complete benchmark:

```bash
ollama stop qwen3.5:9b
python jev_pipeline.py \
  --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v2-normalized" benchmark
```

Keep application routing off. A complete passing benchmark, correction/review of
the observed grounding issue, and independently reviewed final holdout are still
needed before activation.
