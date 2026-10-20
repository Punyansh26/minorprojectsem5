# AGENTS.md — Future Work Optimization Tasks

## Purpose

This file governs how a coding agent (or human contributor) should approach, execute, and report on the optimization tasks defined in this `FutureWork/` directory. There are approximately 13–15 task documents (chapters 01–13 plus supporting references and an index). Each task will be given **one at a time, in a new conversation**, and must be completed fully before moving on.

## Scope

The tasks in this folder are **future-work optimizations** for the Chhattisgarhi voice-to-voice (S2S) shopping assistant. They aim to make the local voice agent faster, cheaper, and more reliable. The parent [`AGENTS.md`](../AGENTS.md) remains the authoritative source for project identity, safety boundaries, architectural principles, and scope rules. This file supplements it with the workflow for executing these optimization tasks.

## Task inventory

The following documents define the optimization areas. Each will be assigned as a standalone task:

| #   | Document                                                                            | Optimization area                                                                                               |
| --- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| 01  | [Baseline and current architecture](01_BASELINE_AND_CURRENT_ARCHITECTURE.md)        | Establishing the measured baseline: what the system does today, actual latencies, and correcting earlier claims |
| 02  | [Latency, cost model and metrics](02_LATENCY_COST_MODEL_AND_METRICS.md)             | Building a formal cost model with equations to predict where time and memory go                                 |
| 03  | [Speech input and turn-taking](03_SPEECH_INPUT_AND_TURN_TAKING.md)                  | Streaming ASR, VAD integration, semantic end-of-turn detection, barge-in                                        |
| 04  | [Retrieval and knowledge base](04_RETRIEVAL_AND_KNOWLEDGE_BASE.md)                  | Embedding upgrades, cross-lingual reranking, Indic BM25, contextual chunks, prefetch                            |
| 05  | [LLM inference and serving](05_LLM_INFERENCE_AND_SERVING.md)                        | Fitting model in VRAM, stable prefix caching, grammar penalty removal, speculative decoding                     |
| 06  | [Verification and caching](06_VERIFICATION_AND_CACHING.md)                          | Replacing the expensive 9B re-review with a cheap claim checker, draft caching, semantic caching                |
| 07  | [Speech output](07_SPEECH_OUTPUT.md)                                                | Sentence-level TTS streaming, local TTS (Kokoro), pre-synthesised audio, acknowledgement cues                   |
| 08  | [Tool calling and task agents](08_TOOL_CALLING_AND_TASK_AGENTS.md)                  | Deterministic slot filling, tool retrieval, speculative read-only calls, shopping assistant agents              |
| 09  | [Distillation and fine-tuning](09_DISTILLATION_AND_FINE_TUNING.md)                  | Training small student models, extending the learned router to Hindi/Hinglish, LoRA/RAFT                        |
| 10  | [Throughput, concurrency and telephony](10_THROUGHPUT_CONCURRENCY_AND_TELEPHONY.md) | Scaling from one user to many, priority scheduling, SIP telephony                                               |
| 11  | [End-to-end speech models](11_END_TO_END_SPEECH_MODELS.md)                          | Evaluating speech-to-speech models (Moshi-style) and why they're not recommended for the answer path            |
| 12  | [Evaluation and benchmarking](12_EVALUATION_AND_BENCHMARKING.md)                    | Building evaluation infrastructure: speech test sets, claim-level audit, paired statistics, energy logging      |
| 13  | [Roadmap and prioritisation](13_ROADMAP_AND_PRIORITISATION.md)                      | Phased plan ranking all techniques by impact, effort, and risk per hardware tier                                |

Supporting documents:

- [00_INDEX.md](00_INDEX.md) — Executive summary, top-10 recommendations, reading guide, and evidence-label definitions
- [REFERENCES.md](REFERENCES.md) — Ledger of every external source cited across all chapters

## Workflow per task

### 1. Receive the task

The user will specify which task document (e.g., "Task 05: LLM inference and serving") to work on in a **new conversation**. Read the full task document carefully before starting.

### 2. Understand and plan

Before writing any code:

- **Read the task document end-to-end.** Understand every technique, its evidence label (`[Measured-here]`, `[Reported]`, `[Estimated]`), the expected effect, risks, and dependencies.
- **Read the baseline** ([01](01_BASELINE_AND_CURRENT_ARCHITECTURE.md)) and the **cost model** ([02](02_LATENCY_COST_MODEL_AND_METRICS.md)) to know the current numbers.
- **Check the roadmap** ([13](13_ROADMAP_AND_PRIORITISATION.md)) for phase ordering and dependencies — don't implement a Phase 2 technique if its Phase 0/1 dependencies aren't done yet.
- **Identify what already exists** in the codebase. Paths are given in the task documents relative to the repository root (`Minor/`).
- **Plan the implementation** in concrete steps. If the task has multiple techniques, decide which to implement in this pass.

### 3. Implement

- **Make the smallest coherent change** that delivers a measurable optimization.
- **Follow all rules** from the parent [`AGENTS.md`](../AGENTS.md) — especially safety boundaries, grounding requirements, the voice/domain boundary, the `minor` Conda environment, and the zero-budget local path.
- **Preserve existing functionality.** Run relevant tests after each change. If tests don't exist for the area you're modifying, create them.
- **Measure before and after.** Every optimization must have quantified impact. Use the evidence labels from the task document:
  - `[Measured-here]` — you measured it on the project hardware
  - `[Reported]` — cited from a source, not reproduced
  - `[Estimated]` — derived, show the derivation
- **Commit logically.** Each commit should be a self-contained, working state.

### 4. Write the completion report

After completing a task, create a **Markdown report** named according to the pattern:

```
REPORT_<NN>_<SHORT_NAME>.md
```

For example: `REPORT_05_LLM_INFERENCE_AND_SERVING.md`

Place the report **in this `FutureWork/` directory**.

#### Required report sections

Every completion report **must** contain all of the following sections:

---

**`## Summary`**

- One-paragraph description of what was done and why.

**`## What was done`**

- Bullet list of every concrete change: files created, files modified, configurations changed, models added, scripts written.
- Include file paths (relative to repository root `Minor/`).

**`## How it was done`**

- Technical explanation of the approach.
- Which techniques from the task document were implemented and which were deferred (with reason).
- Key design decisions and trade-offs.
- Any deviations from what the task document recommended, and why.

**`## Before vs. After`**

- A clear comparison table or structured format showing the metric(s) that changed.
- Use the format:

| Metric                        | Before | After | Change | Evidence label  |
| ----------------------------- | ------ | ----- | ------ | --------------- |
| e.g., Decode speed (tok/s)    | 17.7   | 32    | +81%   | [Measured-here] |
| e.g., Turn latency median (s) | 18.7   | ~12   | −36%   | [Estimated]     |

- If a metric couldn't be measured (e.g., hardware not available), state that explicitly and provide the estimated/reported value with its label.

**`## Files changed`**

- Complete list of every file that was created, modified, or deleted, with a one-line description of the change.

```
Modified: code/demo2/app.py — switched to streaming LLM calls
Created: code/demo2/claim_checker.py — MiniCheck wrapper for cheap verification
Deleted: code/demo2/old_review.py — replaced by claim_checker
```

**`## Issues encountered`**

- **This section is mandatory even if empty** (write "No issues encountered").
- Document every problem, bug, unexpected behavior, compatibility issue, or limitation found during implementation.
- For each issue, state:
  - What the issue was
  - Whether it was resolved or remains open
  - If resolved, how it was fixed
  - If open, what the workaround is (if any) and what needs to happen to fix it

**`## Dependencies and prerequisites`**

- List any new packages installed into the `minor` environment.
- List any task-document dependencies that were assumed complete (e.g., "Assumes A1 from Phase 0 is already done").
- Note any hardware requirements.

**`## Next steps`**

- What should be done next in this optimization area.
- Any follow-up tasks or Phase 2+ techniques that are now unblocked.

**`## Test results`**

- Summary of tests run and their outcomes.
- Include the command used to run the tests.

---

### 5. Report issues prominently

If during implementation you encounter:

- **Blocking issues** that prevent completing the task → say so explicitly in the report and in the conversation. Don't silently skip the broken part.
- **Regressions** in existing functionality → document them in the Issues section and flag to the user immediately.
- **Safety/grounding concerns** → stop and ask. The parent AGENTS.md safety boundary is non-negotiable.
- **Missing dependencies** from earlier phases → document what's missing and do what you can without it. Note the gap clearly.

## Evidence and measurement standards

Follow the evidence labels defined in [00_INDEX.md](00_INDEX.md):

| Label               | Meaning                                                                                         |
| ------------------- | ----------------------------------------------------------------------------------------------- |
| **[Measured-here]** | Taken from a measurement on the project hardware. State the date, hardware, and conditions.     |
| **[Reported]**      | Stated by a cited source. State the source, model, hardware, and dataset. Not reproduced here.  |
| **[Estimated]**     | Derived by us. Show the derivation. Treat as a planning number to be replaced by a measurement. |

Never present an `[Estimated]` number as `[Measured-here]`. Never claim a `[Reported]` result was reproduced unless it actually was.

## Hardware tiers

Refer to the hardware tiers from [00_INDEX.md](00_INDEX.md):

| Tier         | Machine                                                          |
| ------------ | ---------------------------------------------------------------- |
| **T0**       | Current laptop: RTX 4060 Laptop 8 GB VRAM, i7-14650HX, 31 GB RAM |
| **T1**       | Single 16–24 GB GPU workstation                                  |
| **T2**       | Server with one or more 40–80 GB GPUs                            |
| **CPU-only** | Kiosk / no GPU                                                   |

Always specify which tier your measurements apply to.

## Conventions

- **Conda environment**: All Python work uses the `minor` environment (`conda activate minor`).
- **File paths**: Relative to the repository root (`Minor/`), matching the convention in the task documents.
- **Commits**: Reference the task number in commit messages (e.g., `[FW-05] Free VRAM by switching to text-only GGUF`).
- **No scope creep**: Each task session focuses on its assigned document. Don't implement techniques from other chapters unless they are explicit prerequisites.
- **Preserve grounding**: The verbatim-quote guarantee, release-bound caches, and exact SQL cutoffs must survive every optimization. If an optimization threatens grounding, document the risk and get explicit approval.
- **Parent AGENTS.md rules apply**: Everything in the parent [`AGENTS.md`](../AGENTS.md) — safety, architecture, privacy, evaluation, testing — remains binding. This file only adds the task workflow.

## Template for the user's task assignment

When the user assigns a task, they will typically say something like:

> "Work on Task 05: LLM inference and serving"

or

> "Do the optimizations from chapter 06 (Verification and Caching)"

The agent should then:

1. Read the referenced task document completely.
2. Cross-reference with the baseline, cost model, and roadmap.
3. Check the codebase for current state.
4. Implement.
5. Measure.
6. Write the completion report.
7. Summarize findings to the user with key metrics and any issues.
