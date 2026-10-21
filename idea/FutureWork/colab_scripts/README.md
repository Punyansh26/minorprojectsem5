# Colab (A100 / A80 — Tier T2) scripts

These replace the local-laptop (T0) `phase0_scripts/`. On a Colab A100/A80 the
whole "free the VRAM" idea (**A1**) is irrelevant — the 9B model (~6.6 GB) fits
with tens of GB to spare. What carries over is **A3** (keep the model resident),
and the real T2 wins are a GPU-backed server and, optionally, vLLM/SGLang.

## Tier reminder

| Your runtime | Tier | Notes |
|---|---|---|
| A100 40/80 GB (Pro+/PAYG) | **T2** | Everything fits; full-GPU decode; batching/prefix-cache via vLLM is the real win |
| L4 / T4 16 GB (free/Pro) | **T1** | 9B still fits; slower than A100 |

Colab is **ephemeral**: no systemd, nothing persists between sessions, your repo
isn't there. Script `01` rebuilds everything from scratch each session.

## Secrets (do NOT hardcode your token)

Your GitHub token must **not** be pasted into a notebook. Store it in the Colab
🔑 **Secrets** panel as `GH_TOKEN`, then in the first cell:

```python
import os
from google.colab import userdata
os.environ["GH_TOKEN"] = userdata.get("GH_TOKEN")   # private repo only; skip if public
```

> The token currently embedded in your local git remote is leaked — rotate it on
> GitHub (Settings → Developer settings → Personal access tokens) before using Colab.

## Run order (notebook cells)

Upload this `colab_scripts/` folder to `/content/` (or clone it), then:

```python
# Cell 1 — secrets (see above)
import os
from google.colab import userdata
os.environ["GH_TOKEN"] = userdata.get("GH_TOKEN")
```

```bash
# Cell 2 — bootstrap: clone + deps + GPU Ollama + pull model
!bash colab_scripts/01_bootstrap.sh qwen3.5:9b
```

```bash
# Cell 3 — T2 serving config (writes /content/colab_out/.env.colab)
!bash colab_scripts/02_serve_config.sh qwen3.5:9b
```

```bash
# Cell 4 — decode-speed benchmark (replaces T0 "L0"); writes summary.json
!python colab_scripts/03_benchmark_decode.py --model qwen3.5:9b --repeats 5
```

```bash
# Cell 5 — headless demo2 turn-latency over a few grounded questions
!set -a && source /content/colab_out/.env.colab && set +a && \
  python colab_scripts/04_demo2_latency.py --turns 2 --provider ollama --warmup
```

```python
# Cell 6 — read the results
import json, pathlib
for f in ["benchmark_decode_summary.json", "demo2_latency_summary.json"]:
    p = pathlib.Path("/content/colab_out")/f
    if p.exists(): print(f, "\n", json.dumps(json.loads(p.read_text()), indent=2)[:1500], "\n")
```

## Scripts

| # | File | Purpose | Changes system? |
|---|---|---|---|
| 1 | `01_bootstrap.sh` | Clone repo (token from env), install deps, install+start GPU Ollama, pull model | Yes (installs into the Colab VM) |
| 2 | `02_serve_config.sh` | A3 keep-alive, confirm full-GPU residency, write `.env.colab`; vLLM note | Yes (Ollama env + writes .env.colab) |
| 3 | `03_benchmark_decode.py` | Measure decode/prefill tok/s on the A100; `benchmark_decode_summary.json` | No |
| 4 | `04_demo2_latency.py` | Run the real grounded agent headless; `demo2_latency_summary.json` | No |

All outputs go to `/content/colab_out/`.

## What's deliberately NOT here

- **A1 (free VRAM / iGPU display):** meaningless on a dedicated A100.
- **vLLM/SGLang serving (roadmap D1/C1):** noted in `02_serve_config.sh`. It's a
  separate task, needs HF weights (not the GGUF), and should follow the
  Demo2-only workflow in `../AGENTS.md`. Ask if you want that built next.

## Honest caveats

- Only syntax-checked locally (`bash -n`, `py_compile`). They are written for the
  Colab filesystem (`/content/...`) and can't be fully executed on the laptop.
- `04_demo2_latency.py` assumes the knowledge base ships in the repo clone. If the
  KB/Chroma index isn't present on the chosen branch, the agent may return
  `unavailable`; check `demo2_latency_summary.json` status and the branch.
- Speech (STT/TTS) deps are heavy; `01` installs the core set. If a speech smoke
  check is needed, say so and I'll add a `05_speech_smoke.py`.
