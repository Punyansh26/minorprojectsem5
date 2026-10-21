# REPORT 11 — End-to-End Speech Models

Task document: [`11_END_TO_END_SPEECH_MODELS.md`](11_END_TO_END_SPEECH_MODELS.md)
Target: **Demo2 only** (`code/demo2/`). Tier of all measurements: **T0** (RTX 4060 Laptop
8 GB, i7-14650HX, 31 GB RAM), but every check in this report is CPU-only, offline, and
hardware-independent (pure-Python string analysis; no model, no network, no GPU).
Environment: `minor` Conda env, `/home/rtx/miniconda3/envs/minor/bin/python` (Python 3.11.15).
Date of measurements: 2026-10-21.

## Summary

Chapter 11's verdict is unambiguous: an end-to-end speech-to-speech (S2S) model must **not**
be the answer back-end on any tier, because speech-native generation bypasses the grounding
contract (verbatim `source_quote` + exact `facts.sqlite` values), and on T0 no S2S model even
fits beside the resident 9B LLM. The only S2S-shaped change the chapter actually endorses —
and its explicitly "recommended first step" (§6.1) — is a small **canned-phrase
acknowledgement talker** that fills the first silence ("एक पल…", "let me check…") while the
verified cascade produces the real answer, under one hard safety invariant (§5, measured by
§9): **the talker must never speak a knowledge-base fact, and its fact-leakage rate must be
0%**. Demo2 already ships that canned-phrase talker (`fillers.py`, built under Task 07) but
had **no mechanical enforcement** of the invariant. This task adds a deterministic, offline,
zero-VRAM **fact-leakage guard** (`filler_guard.py`) that makes the §5 property provable, wires
it into `fillers.py` so a fact-bearing phrase can never be defined or returned, and adds the
chapter §9 **fact-leakage measurement harness** (`measure_fact_leakage.py`). The result turns
the dormant, unverified talker into one whose 0% leakage is enforced at import, at use, in CI,
and by a reusable metric — the smallest coherent change that delivers the chapter's only
T0-supported, grounding-preserving recommendation.

## What was done

- **Created `code/demo2/filler_guard.py`** — a deterministic fact-leakage guard:
  - `find_fact_tokens(phrase)` — lists every fact-bearing token in a talker utterance.
  - `is_fact_free(phrase)` / `assert_fact_free(phrase)` — boolean / raising guard
    (`FactLeakageError`).
  - `leakage_rate(phrases)` — the chapter §9 metric (`total`, `leaked`, `rate`, `pass`,
    `offenders`), pass criterion `rate == 0.0` (any leak fails).
  - The guard's "fact" vocabulary is **bound to what the TTS path actually speaks**
    (`verbalization.py`): the Indian scale/unit words (करोड़/लाख/हजार/सौ, रुपये, प्रतिशत,
    दशमलव, ऋण), month names, the entity `LEXICON` (both English keys and Devanagari
    renderings — IIIT, JoSAA, शुल्क, …), plus decimal digits in any script and the ₹ / %
    symbols.
- **Modified `code/demo2/fillers.py`** — wired the guard in:
  - import `filler_guard`;
  - `_validate_fillers()` runs **at import** over every phrase in `FILLERS` (fails loudly at
    startup if any phrase would leak);
  - `filler_text()` re-asserts the invariant **at use time** (covers `filler_audio()`
    transitively, since it calls `filler_text()`);
  - docstring updated to state the §5/§9 invariant.
- **Created `code/demo2/measure_fact_leakage.py`** — the chapter §9 harness:
  - scores the built-in talker (`fillers.FILLERS`, per-language + overall) and an optional
    `--transcript FILE` (one talker utterance per line, e.g. an audio-logged talker track);
  - writes a machine-readable `summary.json` to a **scratch temp dir by default** (never into
    Demo2's `data/` directories), per the AGENTS long-running-tests rule;
  - exits non-zero on any leak so it can gate CI.
- **Created `code/demo2/tests/test_filler_guard.py`** — 29 offline unit tests for the guard,
  the fact-free fillers, the import-time/use-time guards, and the §9 metric shape.

No files outside `code/demo2/` were modified. No chapter documents were edited. No
dependencies were added. The grounded answer path (`agent_bridge.py::ask` → the cascade graph
→ `evidence.py::source_quote` → `facts.sqlite`) is **untouched**.

## How it was done

**Interpretation of the task into Demo2.** Chapter 11 is primarily a survey with a negative
recommendation (no S2S back-end) and one positive, lowest-risk pilot (§6.1 canned-phrase
talker). Mapping that to Demo2:

- The canned-phrase talker **already exists** as `fillers.py` (Task 07 A4). It is the chapter's
  "recommended first step" verbatim: pre-synthesised neutral acknowledgements, reusing the
  release-bound TTS cache, zero VRAM. Re-implementing it would be scope creep.
- What chapter 11 adds that Task 07 did **not** is the *safety invariant that makes a talker
  admissible*: §5 ("talker must never speak a fact") measured by §9 ("fact-leakage rate = 0%,
  any leak fails"). That invariant had no code. Implementing it is the smallest coherent,
  measurable change this chapter supports on T0.

**Why a deterministic guard (not a model).** The chapter's whole thesis is that grounding must
not depend on a generative model's good behaviour. A fact-leakage *checker* that was itself an
LLM would reintroduce the same trust problem. So the guard is pure, deterministic string
analysis whose vocabulary is literally the verbalizer's own number/unit/entity tables — i.e.
it flags exactly the tokens the TTS stage would pronounce as a value. This makes the 0%
property a *proof over a finite phrase set*, not a statistical hope.

**The one non-obvious design decision — lone number words.** The shipped Hindi filler "एक पल"
("one moment") contains "एक" (= `verbalization._SMALL[1]`, the spoken word for 1). A naïve
"any number word is a fact" rule would reject the project's own shipped, reviewed filler at
import and break `fillers.py`. The grounding risk the chapter cares about is a *grounded KB
value* (a fee, a cutoff rank, a date, a percentage), and every such value the system speaks is
either a digit string or a **multi-word magnitude** ("नब्बे हजार", "तीन दशमलव पाँच"). So the
guard treats a small-number word (0–99) as a fact **only when it forms a magnitude** — adjacent
across whitespace to another number word or to a scale/unit word. Scale/unit words, months,
digits, ₹/%, and entities are *always* facts. This keeps the guard strict on every real KB
value while permitting idiomatic acknowledgements. The choice is documented in code and
asserted by `test_lone_number_word_is_allowed_but_magnitude_is_flagged`.

**Techniques from the chapter — implemented vs. deferred.**

| Chapter item | Status in this pass |
|---|---|
| §6.1 alt. 1 — canned-phrase TTS talker (recommended first step) | **Already present** (`fillers.py`, Task 07); this pass makes it *safe/verified* |
| §5 invariant — talker never speaks a fact | **Implemented** (`filler_guard.py`, wired into `fillers.py`) |
| §9 metric — fact-leakage rate, 0% pass | **Implemented** (`measure_fact_leakage.py` + guard) |
| §6.1 alt. 2 — small streaming TTS talker (Kokoro/Piper) | Deferred (new model/dep; T0 adds no benefit over canned phrases) |
| §6.1 alt. 3 / §6 full-duplex S2S talker + barge-in | **Out of scope (not T0)**: needs a second GPU slot (§8); chapter marks T1/T2 only |
| §4 speech-native RAG (WavRAG/VoxRAG/MoshiRAG) | **Out of scope as back-end** (chapter §4/§5: breaks verbatim quote + exact SQL) |
| §7 turn controller / barge-in wiring into `app.py`, `jobs.py` | Deferred (documentation-only in the chapter; full-duplex is T1/T2) |
| §3 S2S model survey, §8 VRAM tables | Documentation/analysis, nothing to implement in Demo2 |

**Deviation from the chapter.** None of substance. The chapter's §6.1 talker is kept exactly;
this pass only adds the enforcement + measurement the chapter demands but did not provide code
for. The lone-number-word allowance is a refinement of the §5 wording ("a number") toward its
evident intent ("a *grounded KB value*"), chosen specifically so the project's existing
reviewed fillers remain valid; it is conservative in the safe direction for every real value.

## Before vs. After

| Metric | Before | After | Change | Evidence label |
| --- | --- | --- | --- | --- |
| Mechanical enforcement of "talker never speaks a fact" (§5) | None (phrases trusted by convention) | Enforced at import + at use (`FactLeakageError`) | Invariant now provable | [Measured-here] |
| Fact-leakage rate of shipped talker (`fillers.FILLERS`, §9) | Unmeasured | **0.0% (0/6 leaked), PASS** | Now measured = 0% | [Measured-here] |
| A §9 fact-leakage harness exists | No | Yes (`measure_fact_leakage.py`, exits non-zero on any leak) | New capability | [Measured-here] |
| Guard catches injected leaks (e.g. "The fee is ₹90,000.") | n/a | Flagged, tokens `['9','0','₹','fee']`, rate 0.3333, exit 1 | Detector verified | [Measured-here] |
| Grounded answer path (`source_quote` / `facts.sqlite`) | Verified cascade | **Unchanged** (not touched) | No regression by construction | [Measured-here] |
| VRAM added by this change | 0 | 0 (pure-Python string analysis) | None | [Measured-here] |
| Unit tests for the talker safety invariant | 0 | 29 (new file), all passing | +29 | [Measured-here] |

The latency/UX numbers that a *piloted* talker would move (first-silence reduction < 800 ms,
barge-in correctness, Hindi talker MOS) are **not** claimed here: this pass adds the safety
gate, not a wired-in talker. They remain `[Estimated]`/pending and belong to a T1/T2 pilot
(see Next steps and the long-running tests).

## Files changed

```
Created:  code/demo2/filler_guard.py          — deterministic fact-leakage guard (find_fact_tokens / is_fact_free / assert_fact_free / leakage_rate); fact vocabulary bound to verbalization.py (§5/§9)
Modified: code/demo2/fillers.py               — import filler_guard; _validate_fillers() at import; filler_text() re-asserts at use time; docstring states the §5/§9 invariant
Created:  code/demo2/measure_fact_leakage.py  — chapter §9 fact-leakage harness; scores fillers + optional --transcript; writes summary.json to scratch (not demo2/data); non-zero exit on any leak
Created:  code/demo2/tests/test_filler_guard.py — 29 offline unit tests (fact detection, fact-free fillers, import/use guards, §9 metric)
Created:  code/demo2/run_all_long_tests_fw11.sh — long-test runner: runs L1 (fast regression) now, prints L0 (120-turn audio-logged) instructions; scratch under $TMPDIR
Created:  code/demo2/fw11_selfcheck.py          — trivial fast self-check of the guard (shipped fillers 0%, planted leak caught); exit 0/1
```

No files were deleted. No dependency manifests (`requirements.txt`,
`compatibility-constraints.txt`) were changed.

## Issues encountered

- **Shipped Hindi filler "एक पल" collided with the number word "एक".** The first guard version
  flagged every cardinal word, which would have raised `FactLeakageError` at import of
  `fillers.py` and broken the module. **Resolved** by refining the rule: a small-number word
  (0–99) is a fact token only when it forms a magnitude (adjacent to another number/scale
  word); scale/unit words, months, digits, ₹/%, and KB entities remain unconditional facts.
  Verified: `fillers` now imports cleanly and all 6 shipped phrases score 0% leakage. The
  decision is documented in `filler_guard.py` and asserted by a dedicated test.
- **The talker is still not wired into the live turn flow.** `fillers.py` is dormant
  (`workflow.run_turn` / `app.py` never call it), both before and after this change. That is
  **intended** for this pass: chapter 11's T0 recommendation is only to have a *safe* talker
  available; wiring it as a live first-silence cue (and barge-in) is the §6/§7 full-duplex work
  the chapter restricts to T1/T2. Flagged here so it is not mistaken for a completed UX feature.
  No regression results, since nothing previously called the fillers either.

## Dependencies and prerequisites

- **New packages installed into `minor`:** none. `filler_guard.py` and
  `measure_fact_leakage.py` use only the Python standard library plus the existing local
  `verbalization` module.
- **Assumed-complete prior work:** Task 07 A4 (the `fillers.py` canned-phrase talker and the
  release-bound TTS cache) — present and unchanged. The guard reuses `verbalization.py`'s
  number/unit/entity tables, which already exist.
- **Hardware requirements:** none. All code and all checks in this report are CPU-only,
  offline, and independent of the GPU/VRAM budget. This is precisely why the chapter rates the
  canned-phrase talker as the zero-risk T0 option.

## Next steps

- **(T1/T2) Pilot the talker live.** Wire `fillers.filler_audio()` as a first-silence
  acknowledgement cue played on turn start (`app.py` + `jobs.py`), with the fact-leakage guard
  gating the phrase set in CI. Only then measure first-silence reduction (< 800 ms, §9) and
  barge-in correctness (≥ 95%, §9). These require the full-duplex turn controller the chapter
  defers to T1/T2.
- **Extend the §9 harness to audio-logged transcripts.** Run `measure_fact_leakage.py
  --transcript` over the talker track of the 120-turn benchmark (chapter §9) once such a track
  exists; see the long-running test L0 below.
- **Optionally broaden the entity vocabulary.** If future KB releases add entities not in
  `verbalization.LEXICON`, extend the guard's source vocabulary in lock-step (the guard is
  deliberately bound to the verbalizer so the two cannot drift silently).
- **Do not** pursue S2S as an answer back-end or speech-native RAG — chapter §4/§5 rule these
  out while the verbatim-quote + exact-SQL grounding contract stands.

## Test results

All checks were run in the `minor` env with
`/home/rtx/miniconda3/envs/minor/bin/python` (Python 3.11.15), 2026-10-21, on T0.

- Syntax check (all four files):
  ```
  python -m py_compile filler_guard.py fillers.py measure_fact_leakage.py tests/test_filler_guard.py
  # -> py_compile OK
  ```
- New guard test suite:
  ```
  python -m pytest tests/test_filler_guard.py -q
  # -> 29 passed in 0.20s
  ```
- No regression in the existing speech-output suite:
  ```
  python -m pytest tests/test_filler_guard.py tests/test_speech_output.py -q
  # -> 46 passed in 0.21s
  ```
- Import + §9 metric spot-check:
  ```
  python -c "import fillers, filler_guard; \
    print(filler_guard.leakage_rate([p for v in fillers.FILLERS.values() for p in v]))"
  # -> {'total': 6, 'leaked': 0, 'rate': 0.0, 'pass': True, 'offenders': []}
  ```
- Harness behaviour (short check):
  ```
  python measure_fact_leakage.py --out /tmp/fw11_check
  # -> [PASS] fillers.FILLERS: 0/6 leaked, rate=0.0000 ; Overall: PASS ; exit 0
  python measure_fact_leakage.py --transcript /tmp/fw11_talker.txt   # file has "The fee is ₹90,000."
  # -> [FAIL] ...: 1/3 leaked, rate=0.3333, leak tokens ['9','0','₹','fee'] ; exit 1
  ```
  `summary.json` was written under `/tmp` scratch, never into `code/demo2/data/`.

**Long tests not run by me:** the audio-logged 120-turn talker fact-leakage run (needs the
GPU and recorded/synthesised talker audio) is deferred to the user — see the next section
(test `L0`). The fast re-check of the harness/metric on existing data is `L1`.

## Long-running tests (to be run by the user later)

| ID | Question it answers | Approx. run time | Needs | Pass / read-out criterion |
| --- | --- | --- | --- | --- |
| **L0** | Does the talker speak any KB fact over a full 120-turn benchmark with its audio logged? (chapter §9 "audio-logged") | 20–60 min (GPU-bound; depends on how the talker track is produced) | GPU idle; a 120-turn talker **transcript** (one utterance/line) produced from the benchmark; `minor` env | `summary.json` → `pass == true` (fact-leakage `rate == 0.0`). **Any leak fails.** |
| **L1** | Do the guard + §9 harness run green end-to-end on the shipped fillers (and any provided transcript) as a fast regression? | < 1 min | `minor` env only; no GPU, no download | Runner exits 0; `fillers` source `pass == true`. |

### Setup instructions

1. Save the two fenced scripts below into `code/demo2/` (the runner expects to run from
   there). Each script is preceded by a `**File:** \`name\`` line.
2. From `code/demo2/`, in the `minor` env:
   ```bash
   conda activate minor
   bash run_all_long_tests_fw11.sh            # runs L1 immediately (fast); prints L0 instructions
   ```
3. **L1** writes `summary.json` to a scratch dir printed on screen (under the system temp dir,
   never into `code/demo2/data/`).
4. **L0** needs a talker transcript file. Produce one talker utterance per line from the
   120-turn benchmark's logged acknowledgement audio (ASR of the talker track, or the exact
   canned strings the talker played), save it as e.g. `talker_track_120.txt`, then:
   ```bash
   python measure_fact_leakage.py --transcript talker_track_120.txt --out "$TMPDIR/fw11_L0"
   echo "exit=$?"   # 0 = PASS (0% leakage); non-zero = at least one leaked fact
   ```
   The resulting `summary.json` is the artifact to hand back.

After you run these, hand me the `summary.json` files and I will fold the numbers into this
report as an addendum. Until then, L0's fact-leakage rate on the full 120-turn talker track is
**pending**.

**File:** `run_all_long_tests_fw11.sh`
```bash
#!/usr/bin/env bash
# FutureWork 11 long-test runner. Runs the fast regression (L1) now and prints how to run the
# GPU/human-dependent L0. Resumable: each test writes its own summary.json; re-running is safe.
# Scratch state stays under $TMPDIR (never code/demo2/data/). No model is loaded by L1.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
PY="${PYTHON:-python}"   # expects the `minor` env on PATH (conda activate minor)
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/fw11_long.XXXXXX")"
echo "Scratch dir: $SCRATCH"

echo "==> L1: fast fact-leakage regression on shipped fillers"
"$PY" measure_fact_leakage.py --out "$SCRATCH/L1"
L1_STATUS=$?
echo "L1 summary: $SCRATCH/L1/summary.json (exit $L1_STATUS)"

echo
echo "==> L0: audio-logged 120-turn talker fact-leakage (manual input required)"
echo "   1) Produce a talker transcript (one utterance per line) from the 120-turn benchmark"
echo "      talker/acknowledgement audio, e.g. talker_track_120.txt"
echo "   2) Run:"
echo "      $PY measure_fact_leakage.py --transcript talker_track_120.txt --out \"$SCRATCH/L0\""
echo "   3) Pass criterion: summary.json -> pass==true (rate==0.0). Any leak fails."
echo
echo "Done. Hand back: $SCRATCH/L1/summary.json (and $SCRATCH/L0/summary.json once L0 is run)."
```

**File:** `fw11_selfcheck.py`
```python
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
```

### My check of the scripts before finishing

- `bash -n run_all_long_tests_fw11.sh` — syntax OK (verified).
- `python -m py_compile fw11_selfcheck.py` — OK (verified).
- `python fw11_selfcheck.py` (trivial, fast) — prints `shipped fillers: 0/6 leaked,
  rate=0.0000, pass=True`, catches the planted leak, prints `SELF-CHECK: PASS`, exits 0
  (verified).
- `python measure_fact_leakage.py --help` — prints usage, exits 0 (verified).
- The long run itself (**L0**, the 120-turn audio-logged track) was **not** executed — it
  needs the GPU and a human-produced transcript, per the AGENTS long-test rule.
