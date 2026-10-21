# English-only router recovery

The `english-v2` profile replaces the failed from-scratch classifier with a
pretrained MiniLM encoder and supervised heads. It reuses JEV's bounded CPU
worker, fallback, metrics and activation boundary. This is a MiniLM classifier,
not a trained release of the original Open Jev architecture. The historical
`pilot-v1` artifacts remain separate.

The forty-epoch run is complete. Its fixed policy passed an additional development
check: 87/88 accepted routes correct on 147 public synthetic scenarios. See the
[extended-run report](ENGLISH_ROUTER_EXTENDED_RUN.md). This does not establish final
quality or deployed RAG improvement; routing remains off pending evaluation.

## Run training

Use the existing `minor` environment. Required dependencies are already installed
on this machine; shared speech/model packages need no upgrades.

```bash
conda activate minor
cd "/run/media/rtx/Files/Study/Semester 5/Minor/code/Institute-voice-agent/institute-assistant"

python jev_pipeline.py \
  --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v2" \
  prepare --profile english-v2

python jev_pipeline.py \
  --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v2" \
  train --device cuda --resume
```

Preparation is already complete on this machine. Repeating it validates and
reuses the prepared data and model. Downloads occur only during preparation;
training and runtime load local assets. Keep `JEV_ROUTING_MODE=off`.

Training runs a frozen-encoder baseline followed by a fine-tuned candidate, each
starting from the same pretrained weights and using identical splits. Defaults:
seed 42, batch size 16, at most ten epochs, two-epoch early stopping, AdamW,
encoder learning rate `2e-5`, head learning rate `1e-3`, weight decay `0.01`.
Progress is printed once per epoch.

`--max-seconds 7200` gives each candidate one hour of training, checked between
epochs. Preparation and calibration are outside that budget. Completed epochs
retain their consumed time across resumes. If exhausted, explicitly increase
the budget, for example `--max-seconds 14400`. An interrupted epoch is replayed
from the last completed epoch. Checkpoints retain weights, optimizer, RNG state
and input fingerprints. Changed training inputs require a new artifact directory.
A completed `--resume` reuses finished epochs and regenerates reports.

If the original run stopped with `Incomplete English artifact binding`, rerun
the same resume command after the cache-path fix. The original file scan excluded
all assets under `~/.cache`. Preparation/training now repairs an empty base index
only when every pretrained file matches the pinned upstream checksums, retaining
the empty index as `base_assets.before-cache-fix.json`. A narrowly matched legacy
checkpoint can resume with unchanged data, model code and training configuration;
its completed epochs, optimizer and RNG state are preserved. No new preparation
or replacement artifact directory is needed for this specific correction.

The RTX 4060 is the intended training device; `--device cpu` also works. If CUDA
runs out of memory, close GPU-heavy applications and retry. The CLI does not
stop Ollama or alter speech settings automatically. Runtime remains on CPU.

## Return these results

After training, return the contents or workspace path of:

```text
~/.cache/institute-assistant/open-jev/english-v2/training_summary.json
```

Print it with artifact validation using:

```bash
python jev_pipeline.py \
  --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v2" report
```

The summary compares intent/category accuracy, accepted precision, coverage,
critical failures and rejection reasons. Candidate directories contain histories,
calibration curves, encoder/head assets and resume checkpoints. Lowest
uncalibrated validation loss selects the candidate; frozen wins exact ties.
Training never activates a candidate. Without holdout arguments, `evaluate` prints
the development report without consuming a final test. `label` is unavailable;
explicit authored targets replace the old teacher labeling path.

## Task, provenance and calibration

The encoder is `sentence-transformers/all-MiniLM-L6-v2`, revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Its normalized mean-pooled embeddings
feed intent, department, rewrite-needed and English/defer heads. Inputs above
256 tokens fall back without truncation. The RAG embedding model is unchanged.

The corpus contains 400 English scenarios and 60 non-English rejection examples.
Clean/mixed relatives and known unnamed-institute relatives share families.
There are 430 authored families: 258 training, 65 validation, 107 calibration,
containing 276/69/115 rows. These are development scenarios, not statistically
independent real conversations. No prefix/suffix expansion inflates the counts.

Rewrite means required translation, unresolved context, missing institute context
or removal of an unrelated request. Optional paraphrasing is false. Rejection
examples train only English/defer. Category and rewrite losses apply only to
English knowledge rows. `label_review.json` records hashes, the operational rubric
and agent authorship; it explicitly disclaims independent human review.
Existing live prompts are reserved before splitting. No final test is supplied,
and these questions are never indexed as institute facts.

Calibration families are partitioned between temperature fitting and threshold
selection. Reports include NLL, Brier scores and precision/coverage sweeps.
Threshold selection requires 30 accepted families, 10 accepted knowledge
decisions, 98% observed precision and zero critical failures. These are development
checks. If no thresholds qualify, `supported=false` makes every request defer;
raw accuracies and sweeps remain available for diagnosis.

All JEV shortcuts are English-only. Clear non-English signals reject before
inference; the learned English gate also must pass, since Latin script alone
does not establish English. This is evaluated behavior, not guaranteed universal
language detection. Hindi/Hinglish retain LLM routing and rewriting. Actions,
history, pending requests and uncertain predictions retain fallback. Accepted
knowledge questions must name IIIT-NR and need no rewrite. Category confidence
is required only for knowledge decisions.

Checksums bind encoder, tokenizer, heads, calibration and data. Changed,
incompatible, missing or unactivated assets fall back. Generation, provider
selection, citations and grounding review remain mandatory. Text-free rejection
metrics distinguish language, rewrite, confidence and calibration support.

## Next stage

The first real run is complete. See [its diagnosis](ENGLISH_ROUTER_FIRST_RUN.md):
fine-tuning improved intent accuracy, but department confidence and calibration
support still prevent activation. Both candidates reached the ten-epoch ceiling
while validation loss was falling.

To continue a completed run without overwriting its evidence:

```bash
python jev_pipeline.py \
  --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v2" \
  extend --output "$HOME/.cache/institute-assistant/open-jev/english-v2-extended" \
  --epochs 40 --patience 5

python jev_pipeline.py \
  --artifacts "$HOME/.cache/institute-assistant/open-jev/english-v2-extended" \
  train --device cuda --resume
```

`extend` prepares a new directory and performs no training. It validates the
published artifacts, source checkpoints, data and training configuration, then
copies weights, optimizer/RNG state, best checkpoints and completed histories.
Only the maximum epochs and early-stopping patience change. Forty means forty
total epochs, so a ten-epoch checkpoint resumes at epoch eleven. The consumed
training budget is retained. Data, learning rates, acceptance thresholds and
review gates stay the same. Earlier evaluation and activation records are not
copied. `continuation.json` records the source and checkpoint checksums.

The CLI reads the prepared run's configuration, so the resume command uses its
extended limits. Repeating `extend` refuses an existing destination; use the
training resume command once a continuation has been prepared.

After reviewing training results, freeze the candidate and policy, obtain a fresh
independently reviewed holdout, then run the complete paired live benchmark and
inspect answers against cited sources. Existing quality, coverage and latency
promotion gates remain. English artifacts additionally require a final-holdout
report and independent human review; development reports cannot activate them.
The [holdout workflow](ENGLISH_ROUTER_HOLDOUT.md) accepts fresh public data and an
independent human review tied to its checksum and the frozen artifact. It never
tunes thresholds. Development or confirmation rows cannot serve as this holdout.

The intended gain is fewer routing LLM calls on eligible English questions while
preserving grounded answers. A completed training job alone does not prove it.

## Implementation verification — 26 September 2026

- Helpdesk: `python -m pytest -q` — 210 passed, with existing dependency deprecation warnings.
- Demo 2: `python -m pytest -q` — 17 passed.
- Tiny local-transformer tests exercise both training candidates, artifact reload,
  checksum rejection, masked rejection labels and refusal of development activation.
- Interrupted/resumed fine-tuning produces exactly the same saved model tensors
  as uninterrupted training in the deterministic CPU fixture.
- The pinned real encoder loaded on CUDA and completed a forward-only batch of
  16 examples. The model plus heads has 22,719,376 parameters. This check used
  about 101 MiB of allocated CUDA memory; it does not measure training memory.
- All prepared corpus inputs fit the 256-token limit; longest is 35 tokens.

Only test fixtures were trained during initial implementation. The user has
since completed the first production recovery training run; final quality
evaluation and the live RAG benchmark have not run.
