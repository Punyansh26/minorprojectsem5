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

**End-to-end, 8-question run (commit `025a09a`, `TURNS=8 --warmup`, fresh cache, 07:18 IST) — current headline:**

| # | Question | Status | Wall | Cited |
|---|---|---|---|---|
| 0 | बी टेक में प्रवेश किस आधार पर होता है? | answered | 5.93 s | FAQs p2 |
| 1 | What documents are required for admission? | answered | 8.36 s | JOSAA 2026 p1 (×8, same page repeated) |
| 2 | Is hostel accommodation available for first year students? | answered | 5.86 s | JOSAA 2026 p2 |
| 3 | फीस कितनी है? | insufficient | 3.20 s | — |
| 4 | Which B.Tech branches does the institute offer? | answered | 5.81 s | ECE syllabus p4 |
| 5 | IIIT Naya Raipur kis university se affiliated hai? | answered | 6.47 s | FAQs p1 |
| 6 | What is the application fee for B.Tech admission? | answered | 5.89 s | B TECH_2026 p10 (₹500, non-refundable) |
| 7 | हॉस्टल में कौन-कौन सी सुविधाएं हैं? | answered | 7.87 s | B TECH_2026 p3 |

- **Answered turns: median 5.93 s, max 8.36 s, n=7** (T0: median 18.7 s, p95 29.9 s, n=120) → **≈3.2× faster median** [Measured-here, Colab A100, 2026-10-22]. The run's `p95` field (8.36 s) is nearest-rank = max; with n=7 it is not a real p95.
- Stage medians (answered): routing 1.18 s, retrieval 43 ms, generation 2.23 s, review 2.27 s. Generation + review are ~76 % of the turn → chapter 06 (cheaper verification) is the next latency lever on T2, not serving.
- All 8 turns `retrieval_cache=miss`, `draft_cache=miss`; warm-up 24.2 s (first-turn embedding/graph load), excluded.
- Decode benchmark this run: 84.25 tok/s median.
- Quality notes: `फीस कितनी है?` is under-specified (which programme/year?) — `insufficient` is acceptable, though a clarifying question would be better UX. Turn 1 lists the same citation 8×: citation dedup belongs to the agent (`code/Institute-voice-agent/`, outside Demo2 scope).

**Earlier 2-turn run (commit `286906a`), superseded:**

| Turn | Status | Wall | Routing | Generation | Review | Prompt tokens |
|---|---|---|---|---|---|---|
| What documents are required for admission? | answered, 8 sources | 8.2 s | 1.2 s | 2.8 s | 3.9 s | 4,123 / 4,260 |
| बी टेक में प्रवेश किस आधार पर होता है? | insufficient | 4.0 s | 1.0 s | 1.5 s | 1.5 s | 4,981 / 4,733 |

`load_seconds` ≈ 0.001 on every call (model stays resident).

Notes on that run:
- n = 2 and the warm-up reused QUESTIONS[0] (retrieval-cache hit, 16 ms). Both fixed.
- **Hindi B.Tech question: retrieval finds the right content; the turn is unstable.** Local T0 probes (2026-10-22): raw `retrieve()` puts the B.Tech admission page and `admissions/B TECH_2026.pdf` p1 in the top 3. Three full local turns: 2× answered from `FAQs _ IIIT NAYA RAIPUR.pdf` p2 ("…केवल JEE…"), 1× answered with a correct B.Tech answer (JoSAA/CSAB, CG quota, NTPC quota) but **cited `M.Tech Admission 2026 _ IIIT NAYA RAIPUR.html`**. Likely cause: the site's HTML pages share boilerplate ("Admission into the B. Tech programs can…" also appears in the Training & Placement page), so the same B.Tech text exists under several page titles and the citation lands on whichever chunk wins. That is a knowledge-base dedup issue (`code/knowledgebaseenhanced/`, outside Demo2 scope) — ask before changing it. The 2-turn Colab `insufficient` was the review stage rejecting a draft; in the 8-question run the same question answered from FAQs p2.

### Latency benchmark moved into Demo2 (2026-10-22, uncommitted until pushed)

- **`code/demo2/evaluate_latency.py` is now the single source of truth** (Demo2-only rule in `FutureWork/AGENTS.md`). `idea/FutureWork/colab_scripts/04_demo2_latency.py` is a thin launcher that calls it with `--tier T2 --output /content/colab_out/<file>`; the CLI (`--turns --provider --warmup --out --keep-cache`) is unchanged, so `run_all.py` needs nothing else.
- Unit tests: `code/demo2/tests/test_evaluate_latency.py` (6 offline tests). Documented in `code/demo2/README.md` → "Turn-latency benchmark".
- Warm-up uses `Where is IIIT Naya Raipur located?` (outside the timed set).
- 8 questions (3 Hindi, 4 English, 1 Hinglish); `--turns` defaults to one pass. Repeats (turns > 8) are flagged `repeat=true` and excluded from `wall_s_first_pass` and `wall_s_answered`.
- **Fresh temporary `DEMO2_DATA_DIR` per run, deleted afterwards.** Reason: the RAG cache (TTL 1 h) persists on the Colab VM between `colab_go.sh` runs, so a re-run would report draft-cache hits (~65 ms answer stage, measured locally) as model latency. Also keeps benchmark state out of `code/demo2/data`. `--keep-cache` restores old behaviour.
- Summary: `wall_s_answered` / `wall_s_all` / `wall_s_first_pass` (median, p95 via demo2 `stats.p95`, min, max), `status_counts`, `stage_ms_median_answered`, per-turn `answer_text`, `source_files`, `llm_error`.
- `--out` file name, so the Groq run writes `demo2_latency_groq_summary.json` instead of overwriting the Ollama summary (it did before).
- `run_all.py`: `TURNS` env (default 8); Groq run uses `--out`. `colab_go.sh`: downloads the Groq summary; duplicate CLI-lookup block removed.
- Verified: demo2 suite 195 passed; Colab launcher run locally (T0, `--turns 1 --warmup`) → tier T2 label, `retrieval_cache=miss`, `draft_cache=miss`, temp dir removed.

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

1. **Push the Demo2 move** (Colab clones from GitHub). The 8-question run above used the pre-move `04` (commit `025a09a`); after pushing, `bash colab_go.sh` runs the same benchmark through `code/demo2/evaluate_latency.py`:
   `git add code/demo2/evaluate_latency.py code/demo2/tests/test_evaluate_latency.py code/demo2/README.md idea/FutureWork/colab_scripts/04_demo2_latency.py idea/FutureWork/colab_scripts/README.md RTX/SESSION_SUMMARY.md && git commit -m "[FW-12] move latency benchmark into demo2 (evaluate_latency.py); colab 04 delegates" && git push`
2. **Paired T0 run on the laptop** with the identical question set, so the 3.2× claim compares like with like (the 18.7 s T0 figure came from a different 120-turn set):
   `cd code/demo2 && python evaluate_latency.py --output /tmp/demo2_latency/t0.json --warmup` (~3–4 min on T0; GPU should be otherwise idle).
3. Next latency lever on T2 is chapter 06 (generation + review ≈ 76 % of the turn).
4. Optional: add `GROQ_API_KEY` to `RTX/colab.env` for the cloud-reasoning comparison (writes `demo2_latency_groq_summary.json`). First `git rm --cached RTX/colab.env` — it is tracked, so a filled-in key would be committed.
5. Optional cleanup: `benchmark_decode_summary.json` was committed at the repo root in `7d1e7bb` (a run artifact) — `git rm --cached benchmark_decode_summary.json`.
6. For a trustworthy p95 (n≥30 distinct questions), the question set needs to grow; cycling the 8 only adds cache-hit repeats.
