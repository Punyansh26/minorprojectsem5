# Local Open Jev routing

**Current speed work:** follow the [English v3 latency guide](ENGLISH_ROUTER_SPEED.md).
It extends the [English-only v2 router](ENGLISH_ROUTER_RECOVERY.md) with bounded
query preparation and repeated end-to-end timing. All JEV shortcuts are
English-only; Hindi/Hinglish use the existing LLM router. The rest of this document
preserves the historical `pilot-v1` architecture and commands.

Open Jev is an optional, locally trained intent classifier for Demo 2 and the text
CLI. It can replace one routing LLM call; it does not generate answers, speed up
vector search, or replace grounding review. The default remains `off`.

The vendored [research implementation](https://github.com/kyegomez/open-jev) is
pinned to `93843ef288f3d35fd91263377c40b6f917d77da0`. It is not TypeSafe's production
model and supplies no trained weights. Neither TypeSafe nor openjev.sh is called.
Its original hash tokenizer is replaced through the upstream tokenizer interface
with a local byte-level BPE tokenizer. Upstream code and its Apache license are
preserved unchanged under `assistant/jev/vendor`.

## Behavior

Existing deterministic greetings, thanks, and action confirmations run first.
Conversation history, pending actions, action language, and oversized inputs use
the existing router. Only confident English smalltalk, out-of-scope, clarification, and
standalone English knowledge questions explicitly naming IIIT-NR may skip it.
Knowledge questions requiring translation, reference resolution, or removal of an
unrelated request retain the existing LLM rewrite. All answer generation,
retrieval scope, exact quotations, grounding review, and provider selection remain
in place. This first version does not choose between answer models.

The classifier uses one CPU worker process with one pending request. Thread
settings are isolated from speech and embedding libraries. Busy, timed-out,
missing, corrupt, incompatible, uncertain, or unactivated models fall back to the
existing selected LLM provider. A timed-out request retains worker capacity until
it actually finishes, preventing an unbounded queue. A slow cold load can
therefore cause an initial fallback. Runtime never downloads assets or uses
freshly initialized weights for routing.

## Run the bounded pilot

From `institute-assistant`, use the existing `minor` environment. PyTorch and
`tokenizers` are already shared with the speech/model stack; no package upgrades
or new environment are required on the configured machine.

```bash
conda activate minor
python jev_pipeline.py prepare
python jev_pipeline.py label
python jev_pipeline.py train
python jev_pipeline.py evaluate
python jev_pipeline.py benchmark
python jev_pipeline.py activate
```

The global `--artifacts /absolute/path` option precedes the command. Defaults live
under `~/.cache/institute-assistant/open-jev/pilot-v1`, outside Git. `prepare`
creates a four-hour deadline for data generation/labeling and training together;
rerunning it does not reset that deadline. Labels and epoch checkpoints are
resumable within the same budget. A separate directory explicitly starts another
pilot. Evaluation and live benchmarking are reported separately from that compute
budget. `train --device cuda` is available when GPU memory is deliberately freed;
the pilot defaults to CPU to coexist with Ollama on the 8 GB GPU.

The synthetic corpus includes English, Hindi and Hinglish public helpdesk
utterances, ambiguous references, action requests, and mixed-topic requests.
Entire topic families—including translations and template variants—are assigned
to one split before training. Existing live evaluation questions and their entire
synthetic families are reserved before labeling. Benchmarking excludes any
training/calibration overlaps found in older artifact datasets. Ollama labels the training/calibration family bases;
semantically equivalent template variants inherit those labels. Labeling uses the
existing one-question RoutingDecision call. Valid saved labels survive retries.
Unsupported-language examples use an authored language annotation because the
existing router only exposes three languages. The model trains
on training labels only. Test labels are independently authored in `data.py`, not
copied from the teacher. No user conversations or student databases are used, and
these utterances are never indexed as institute facts.

Targets use 0.05 label smoothing. These synthetic distributions are **not**
measured ensemble uncertainty. The confidence head and thresholds require local
validation. This small, template-based pilot cannot establish general language
understanding or TypeSafe-equivalent quality.

Training uses width 128, four heads, three state layers, four readout layers,
512 input tokens, an 8,192-token vocabulary limit, AdamW at 0.0003, batch size 16,
and at most 30 epochs with five-epoch validation patience. Tokenizer vocabulary
may be smaller than its limit on this corpus. Validation uses authored calibration
labels. Thresholds are chosen only on calibration data; the test split is never
used to select them. Repeated experiments on the test set are marked development results and cannot
activate a model; they require a new independently reviewed final test set. Keep
`test_exposures.json` with the experiment record rather than resetting it.

## Evaluation and activation

The pipeline saves model, tokenizer, dataset/split hashes, training history,
teacher provenance, calibration thresholds, predictions, and evaluation results.
Runtime uses `torch.load(weights_only=True)` and checks artifact compatibility
and checksums. Keep artifact directories under the application's control.

Activation requires all of:

- At least 100 accepted held-out examples, 98% accepted precision, reviewed gold on a first-exposure test set,
  no family leakage, and zero critical action/mixed-topic errors.
- The complete existing live behavior suite, with at least 12 paired cases, isolated baseline/candidate caches and
  memory-only conversations; action writes are blocked.
- At least 15% coverage, 10% median total-latency improvement, at most 5% p95
  regression, and no new behavior failures.
- Inspection of generated answers against original cited sources. Record the
  source review in `benchmark.json` by setting `source_review_passed` to true
  and replacing `source_review` with the reviewer/date and findings. Re-run
  `activate` afterward. Automated citation matching is not factual review.

Latency summaries count individual turns, including separate follow-up turns.

`benchmark --quick` runs a diagnostic subset when the quality gate already fails;
it cannot satisfy activation. A full benchmark is required for promotion.

`benchmark_pairs.json` contains only the fixed public evaluation prompts' results
and evidence. Inspect baseline failures separately; a pre-existing knowledge-base
gap must not be repaired by inventing facts. Quality or latency failure leaves
activation unavailable even when source review succeeds.

After successful activation, configure **both** application entrypoints as needed:

```dotenv
JEV_ROUTING_MODE=enabled
JEV_ARTIFACT_DIR=/absolute/path/to/evaluated/artifacts
JEV_CPU_THREADS=2
JEV_TIMEOUT_SECONDS=10
```

`shadow` runs the classifier but always uses the existing router, recording intent
agreement. It adds latency. `off` is the immediate rollback; restart the app after
changing settings. Calibration or retraining changes the artifact identity and
invalidates older activation records. An enabled setting alone cannot bypass the
evaluation gates. Keep previous artifact directories to restore a known version.

## Metrics and verification

`rag_metrics` adds `classifier_calls`, `router_path`, `router_mode`,
`router_version`, `router_fallback`, and classifier stage milliseconds. Shadow
mode additionally records predicted intent and agreement. Existing `model_calls`
still counts LLM calls; generation, review and speech keep their existing provider
boundary. Deterministic replies report zero classifier calls. Metrics contain no
student message text or provider exception bodies.

Run `python -m pytest -q` in the helpdesk and Demo 2 directories. Tests use fake
providers and isolated storage, including artifact corruption, missing
activation, queue saturation, multilingual rewriting, follow-ups, and preservation
of grounding review after an accepted route. See `OPEN_JEV_VALIDATION.md` for this
pilot's actual outcome; a passing test suite is not model quality evidence.
