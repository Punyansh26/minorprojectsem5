# Open Jev pilot validation — 25 September 2026

**Outcome: integration implemented; the trained pilot is unsuitable for live
routing and remains disabled. No RAG speedup is established.**

The existing Ollama/Groq routing, answers and grounding review remain active.
Enabling `JEV_ROUTING_MODE=enabled` alone cannot promote this checkpoint: its
quality evaluation fails, and no activation certificate has been created.

## Implementation verification

- Shared helpdesk: **179 tests passed**, including 37 Open Jev tests.
- Demo 2: **17 tests passed**.
- Existing Chroma/LangChain Pydantic deprecation warnings remain.

Checks cover conservative eligibility, provider retention, accepted routes still
running generation and grounding review, exact citations, follow-up fallback,
missing/corrupt artifacts, tokenizer compatibility, activation binding, worker
capacity/timeouts/recovery, unsupported languages, and independent dataset splits.
The local teacher test also verifies that test examples never reach the teacher.

## Data and training

The corpus contains **1,776 synthetic utterances**: 1,104 training, 336 calibration,
and 336 test examples. Translations and wording variants remain in the same topic
family and split. There are English, Hindi and Hinglish examples plus explicit
unsupported-language examples. No real conversation or student database was used.
The template-based examples have much less diversity than 1,776 independent
real-world utterances; this pilot cannot establish broad language understanding.

The first attempt used batched teacher calls, whose typed outputs frequently had
wrong semantic labels. Its intent accuracy was 8.0%, and it accepted no test
examples. That attempt is preserved under `attempt-01-batched-teacher` in the
artifact directory. Batched labeling was removed from the implementation.

The corrected workflow uses the existing local `qwen3.5:9b` RoutingDecision call,
one base utterance per request. All 240 training/calibration bases were labeled;
only training examples contribute to gradients. Test labels were independently
authored. Runtime's deterministic language hint is also applied to training
labels, and unsupported-language examples retain an authored language annotation.
Teacher intent agreement with authored base labels was 88.75%; after language
normalization, language agreement was 91.67%. Teacher mistakes remain a limitation.

Training used the existing `minor` environment and CPU, with a local byte-level
BPE tokenizer, width 128, four attention heads, three state layers and four readout
layers. AdamW used learning rate 0.0003 and batches of 16. Early stopping ended the
corrected run at epoch 13; the best validation checkpoint was epoch 8. Weights
occupy approximately 19.4 MB. Both attempts remained inside the original four-hour
generation/training budget, which was not reset between attempts.

## Model quality

The corrected checkpoint was evaluated on 336 examples:

| Measure | Result |
| --- | ---: |
| Raw intent accuracy | 69.35% |
| Raw category accuracy | 56.85% |
| Raw language accuracy | 88.99% |
| Accepted decisions | 14 / 336 (4.17%) |
| Correct accepted decisions | 2 / 14 (14.29%) |
| Critical routing errors | 2 |
| Quality gate | **Failed** |

Calibration selected probability >= 0.8, confidence >= 0.6, and rewrite probability
<= 0.05. Only six calibration examples were accepted, all correct; that small
sample did not generalize to the test families. Typed outputs and high model
confidence did not establish correctness.

The second evaluation reused a test set already exposed by the failed first
attempt, so it is explicitly marked a **development evaluation**. The activation
gate also requires a fresh reviewed test set. Neither the quality failures nor
that requirement was waived.

## Diagnostic latency comparison

A warmed local run compared the existing router with the candidate in isolated
memory-only conversations and separate application caches. Each case was repeated
with a populated cache. Ticket and reminder writes were blocked; audio was excluded.

One existing live question, “How much is it?”, overlapped the original synthetic
training corpus. Its two pairs were excluded from the summary. Raw measurements
are retained for audit. Preparation now excludes existing live questions and their
entire template families before labeling; fresh default preparation produces
1,758 examples. The historical checkpoint and its original 1,776-example dataset
were preserved rather than retrospectively relabeled.

The remaining **22 case pairs covered 24 paired turns** across English, Hindi,
Hinglish, off-topic requests, follow-ups, missing information, cutoff/loan questions,
and disabled reminders. Percentiles below measure individual turns, including both
routing and answer/review work; the two-turn follow-up is not counted as one request.

| Measure | Existing router | Open Jev candidate with fallback |
| --- | ---: | ---: |
| Median turn time | 14.18 s | 14.25 s |
| p95 turn time | 28.94 s | 37.13 s |
| Logical LLM calls | 49 | 49 |
| Turns skipping LLM routing | 0 | 0 |

The classifier ran 20 times, with a median classifier-stage time of **8.51 ms**,
including adapter work and IPC. It fell back on every non-overlapping live example.
There were no new automated behavior failures in this diagnostic subset, but
neither latency nor model quality supported enabling the candidate. Small-sample
LLM timing variation must not be interpreted as a classifier speed guarantee.

This was a diagnostic subset, not the complete promotion suite. Full-suite and
source-review promotion were not performed after the quality failure. The actual
`activate` command path was checked and correctly refused this checkpoint. The
application setting remains `off`, and no activation certificate exists.

## Artifacts and reproduction

Local artifacts are outside Git:

`~/.cache/institute-assistant/open-jev/pilot-v1`

This directory contains the trained checkpoint, BPE tokenizer, dataset and split
hashes, teacher provenance, training history, calibration thresholds, evaluation,
and public synthetic predictions. The model SHA-256 is:

`7e1242d6f38fcc9bd8948ad02d46ef5d0bff68a93b04a28bf6fdfe432bf8dff1`

See [setup, training, metrics and activation requirements](OPEN_JEV.md). Keep
`JEV_ROUTING_MODE=off` for current use. Shadow mode is available for experiments
but adds classifier work while retaining the existing LLM router.
