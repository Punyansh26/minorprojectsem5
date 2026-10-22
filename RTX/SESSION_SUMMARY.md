# Session Summary — FutureWork on Google Colab (A100)

_Last updated: 2026-10-22_

## Goal

Run the **Demo2 voice-agent optimization work** from `idea/FutureWork/` on a Google Colab **A100-SXM4-40GB** GPU (Tier **T2**) instead of the local RTX 4060 laptop (Tier **T0**). The point of using Colab is to measure the pipeline on a big, idle GPU the laptop cannot provide.

## Background: what FutureWork is

`idea/FutureWork/` is a research dossier (chapters 01–15 + reports) describing how to make the Demo2 voice agent faster/cheaper/more reliable. `AGENTS.md` there says: work one chapter at a time, change only `code/demo2/`, and the USER runs all long/GPU tests. Chapter 13 (roadmap) ranks the work into phases.

The T0 roadmap's **Phase 0** headline item was **A1 = free the laptop's VRAM** so the 9B model fits fully on GPU. On an A100 that is irrelevant (the model fits trivially), so the Colab work replaces A1 with: bootstrap + GPU serving + decode benchmark + end-to-end latency.

## Tooling: Google Colab CLI (`google-colab-cli`)

We drive Colab from the laptop terminal via the `colab` CLI (installed at `~/miniconda3/bin/colab`). Key facts learned this session:

- **`colab run SCRIPT`** provisions a **fresh ephemeral VM**, runs the file, then **tears the VM down**. It defaults to **no GPU** unless you pass `--gpu A100`. No state persists between invocations.
- **`colab exec -s minor -f SCRIPT`** runs inside the **existing persistent `minor` session** (GPU + background processes preserved). **This is the mode our pipeline needs** — stage 1 starts a background `ollama serve` that must survive into stages 2–4.
- **Both `run` and `exec` send the file to the Colab _Python_ kernel.** There is no bash-script runner. A `.sh` file is parsed as Python and dies (`set -uo pipefail` → `SyntaxError`). This was the original failure that kicked off this session.
- `colab download REMOTE LOCAL` needs a **destination file path**, not a directory (`./` errors with `Is a directory`).
- `colab status -s minor` shows the session; `colab stop -s NAME` releases it; `colab restart-kernel -s NAME` kicks a hung kernel.

## What was built THIS session (laptop-side, in `RTX/`)

Because the CLI runs Python (not bash) and tears down ephemeral VMs, we built a pure-Python orchestrator plus a laptop launcher so the whole job is **one command** and results land back in `RTX/`.

| File (in `RTX/`)          | Role                                                                                                                                      |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `run_all.py`              | **Runs ON the VM.** Pure-Python orchestrator (kernel accepts it). Drives the repo's `01`–`04` scripts via `subprocess` in ONE session. Stages: 1 bootstrap, 2 serve, 3 benchmark, 4 latency. Reads keys from `/content/.env`. Resumable via `STAGES=`. Auto-runs `setup_local.py` and the `diag_llm_error.py` diagnostic. |
| `colab_go.sh`             | **Runs ON the laptop.** One command: ensures A100 `minor` session → uploads `colab.env` as `/content/.env` → `colab exec` the pipeline → downloads results into `RTX/`. Auto-finds the `colab` binary even when not on PATH. |
| `colab.env`               | Key/settings template (all optional): `GH_TOKEN`, `GROQ_API_KEY`, `REPO_BRANCH`, `MODEL_TAG`, `STAGES`. Uploaded to the VM as `/content/.env`. |

The repo-side scripts (`idea/FutureWork/colab_scripts/01_bootstrap.sh`, `02_serve_config.sh`, `03_benchmark_decode.py`, `04_demo2_latency.py`, `diag_llm_error.py`) remain the single source of truth; `run_all.py` just invokes them correctly.

### The one command

```bash
cd "/run/media/rtx/Files/Study/Semester 5/Minor/RTX"
bash colab_go.sh
```

Full console output is saved to `RTX/colab_run_latest.log`; result JSONs download into `RTX/`.

## Results (on the A100, 2026-10-22)

| Step                       | Outcome                                                                              |
| -------------------------- | ------------------------------------------------------------------------------------ |
| Repo clone (`main` branch) | OK — `demo2` found                                                                   |
| Python deps                | OK (benign version-conflict warnings: `langchain-core 0.3.29` vs `langgraph-prebuilt 1.1.1`, numpy, huggingface-hub) |
| Ollama install             | OK after `zstd`; **Ollama 0.40.8**. (Installer warns "Unable to detect NVIDIA GPU" because `lspci`/`lshw` absent, but CUDA binds fine at runtime.) |
| `qwen3.5:9b` pull          | OK. Custom build: `/api/show` capabilities `completion, vision, tools, thinking`; `qwen3.5` renderer/parser |
| `02` serving config        | OK — `ollama ps` = **100% GPU, 32768 context, UNTIL=Forever**                        |
| **`03` decode benchmark**  | **✅ ~84 tok/s median decode** (latest run 83.70–84.29, median 84.1; earlier run 83.98–84.54) |
| **`04` end-to-end latency**| **✅ working** — first answered grounded turn on Colab (see below)                    |

### Headline numbers (confirmed)

**Decode speed: ~17.7 tok/s (T0 laptop, 45/55 CPU-GPU spill) → ~84 tok/s (A100, 100% GPU) ≈ 4.8× faster.** Evidence: `RTX/benchmark_decode_summary.json` [Measured-here, Colab A100, 2026-10-22]. Inside the agent (larger prompts, prefix cache warm) decode is ~108–123 tok/s.

**End-to-end (last run, commit `286906a`, `--turns 2 --warmup`):**

| Turn | Status | Wall | Routing | Generation | Review | Prompt tokens |
|---|---|---|---|---|---|---|
| What documents are required for admission? | **answered, 8 sources** | **8.2 s** | 1.2 s | 2.8 s | 3.9 s | 4,123 / 4,260 |
| बी टेक में प्रवेश किस आधार पर होता है? | insufficient | 4.0 s | 1.0 s | 1.5 s | 1.5 s | 4,981 / 4,733 |

T0 baseline median answered text turn was 18.7 s (p95 29.9 s) → **8.2 s on A100** for the answered turn. `load_seconds` ≈ 0.001 on every call (model stays resident).

Caveats before quoting these as benchmark numbers:
- **n = 2.** Not a median. Superseded by the 8-question run (see TODO 1).
- **Warm-up reused QUESTIONS[0]**, so timed turn 1 got a retrieval-cache hit (16 ms). Fixed in `04` (see below).
- **Hindi "insufficient" is NOT a retrieval miss** (corrected 2026-10-22). Local probe on T0: raw `retrieve()` for "बी टेक में प्रवेश किस आधार पर होता है?" returns the B.Tech admission page and `admissions/B TECH_2026.pdf` p1 in the top 3, and a full local turn **answered** from `FAQs _ IIIT NAYA RAIPUR.pdf` p2 ("…केवल JEE … के परिणामों के आधार पर…", 14.7 s, cache miss). So the Colab rejection happened in generation/review, not retrieval. The old `04` didn't record answer text or which stage refused, so the cause is unknown; the new `04` records `answer_text`, `source_files`, `llm_error` per turn to pin it down.

### `04_demo2_latency.py` changes (2026-10-22, uncommitted until pushed)

- Warm-up uses `Where is IIIT Naya Raipur located?` (outside the timed set).
- 8 questions (3 Hindi, 4 English, 1 Hinglish); `--turns` defaults to one pass. Repeats (turns > 8) are flagged `repeat=true` and excluded from `wall_s_first_pass`.
- **Fresh `DEMO2_DATA_DIR` per run** under `/content/colab_out/`. Reason: the RAG cache (TTL 1 h) persists on the Colab VM between `colab_go.sh` runs, so a re-run would report draft-cache hits (~65 ms answer stage, measured locally) as model latency. `--keep-cache` restores old behaviour.
- Summary adds `wall_s_answered` / `wall_s_all` / `wall_s_first_pass` (median, nearest-rank p95, min, max), `status_counts`, `stage_ms_median_answered`.
- `--out` file name, so the Groq run writes `demo2_latency_groq_summary.json` instead of overwriting the Ollama summary (it did before).
- `run_all.py`: `TURNS` env (default 8); Groq run uses `--out`. `colab_go.sh`: downloads the Groq summary; duplicate CLI-lookup block removed.
- Verified locally (T0, `--turns 1 --warmup`): fresh data dir, `retrieval_cache=miss`, `draft_cache=miss`, Hindi turn answered in 14.7 s.

## Blockers — resolved this session

1. **CLI ran our `.sh` as Python** → fixed by the pure-Python `run_all.py` wrapper that calls bash via `subprocess`.
2. **"Institute agent is missing"** → no longer occurs; the `main` clone contains the agent.
3. **`Local tokenizer is missing`** → `run_all.py` runs `setup_local.py` (tokenizer from HF `Qwen/Qwen3.5-4B`).
4. **Every `/api/chat` returned HTTP 400** (`routing failed (LocalModelError)` at ~12 ms). Real error, surfaced by a raw probe in `diag_llm_error.py`: `{"error": "time: missing unit in duration \"-1\""}`. `.env.colab` sets `OLLAMA_KEEP_ALIVE=-1`; the agent sent it as the JSON *string* `"-1"`, which Ollama parses as a Go duration and rejects. The decode benchmark passed only because `/api/generate` didn't send `keep_alive`. **Fix (`be73f2e`):** `llm._keep_alive_value()` sends numeric values as JSON numbers (`-1`, `0`, `300`), leaves `"5m"`-style strings alone.
   - Earlier misdiagnosis: I first assumed `think:false` was the rejected field and gated it on `/api/show` capabilities (`7d1e7bb`). Harmless and kept, but not the cause.
5. **Answer prompts ~44k tokens ("exceed the local context").** The A7 span menu listed every 1–4 sentence combination (67–249 spans/source) and sent it alongside the full source text. **Fix (`dbf2006`, option A):** one sentence/line per span, the menu replaces (not duplicates) source text, and evidence may set `last_span` to cite a contiguous range that resolves to the exact original substring (≤1500 chars). Real prompts now 3.1–6.2k tokens.
6. **Answers decoded then failed validation (14 evidence items > max 8).** Grammar stripped `maxItems`. **Fix (`dbf2006`):** grammar keeps `evidence.maxItems = 8`.
7. **Colab `git pull` aborted** (`untracked working tree files would be overwritten: code/demo2/agent_memory.sqlite`) → Colab silently stayed on old code for one run. I had accidentally committed that runtime DB in `fb271fc`. **Fix (`c7c4dab`):** untracked + `.gitignore`.
8. **Retrieval `RuntimeError` on Colab only.** `sentence-transformers` → `transformers` imported Colab's preinstalled TensorFlow → JAX → `numpy.dtypes has no attribute StringDType` (JAX needs NumPy 2.x). Laptop has no TensorFlow, so it never reproduced locally. **Fix (`286906a`):** demo2 `configure_agent()` defaults `USE_TF=0 USE_FLAX=0 USE_JAX=0 USE_TORCH=1` before any transformers import; `.env.colab` sets the same.

Diagnostics added along the way (`idea/FutureWork/colab_scripts/diag_llm_error.py`): runs demo2 `configure_agent()` first so settings match the app, prints the retrieval traceback, and raw-probes `/api/chat` variants with the HTTP error body. Lesson: after the second identical 400 with the field hidden, instrument the real error instead of inferring.

Verification: institute-assistant tests 339 passed, demo2 tests 189 passed; locally (RTX, `qwen3.5:9b`) 3/3 sample questions answered with citations.

## Infra notes

- `colab exec` occasionally drops with `RuntimeError: Connection was lost.` / `TimeoutError: Timeout waiting for reply` after the run — transient; results still download.
- To resume: `colab restart-kernel -s minor && bash colab_go.sh` (or `colab stop -s minor ; bash colab_go.sh` if the session is gone). Re-runs take ~1–1.5 min; a fresh VM adds ~6–8 min for the model pull.
- `colab nvidia-smi` is not a CLI command; GPU info is printed in Stage 0.

## Security note (still action required)

The local git remote on the laptop has a **GitHub token in plaintext** in its URL (`gho_...`). **Rotate it** on GitHub and switch the remote to a credential helper or SSH. On Colab, put any token in `RTX/colab.env` as `GH_TOKEN`, never in a script.

## Immediate TODO

1. **Push the `04` change, then re-run** (Colab clones from GitHub, so local edits are invisible to it):
   `git add idea/FutureWork/colab_scripts/04_demo2_latency.py idea/FutureWork/colab_scripts/README.md && git commit -m "[FW-12] colab 04: 8 questions, clean warm-up, fresh cache dir, p95" && git push`
   then `colab restart-kernel -s minor && bash colab_go.sh`. Expect ~3–4 min for stage 4. Read `wall_s_answered.median`/`p95` against T0 18.7 s / 29.9 s.
2. If the Hindi B.Tech question is `insufficient` again, read its `answer_text` and `source_files` in `demo2_latency_summary.json` to see whether generation abstained or review rejected a draft.
3. Optional: add `GROQ_API_KEY` to `RTX/colab.env` for the cloud-reasoning comparison (writes `demo2_latency_groq_summary.json`).
4. Optional cleanup: `benchmark_decode_summary.json` was committed at the repo root in `7d1e7bb` (a run artifact) — `git rm --cached benchmark_decode_summary.json`.
5. For a real T2 benchmark (n≥30, paired with T0), raise `TURNS` or use demo2's `evaluate_*` scripts; 8 turns gives a median, not a trustworthy p95.
