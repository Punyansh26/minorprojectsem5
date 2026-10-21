# Phase 0 "Quick Wins" — run-one-by-one scripts

These scripts implement the **run-right-now** part of Phase 0 from `13_ROADMAP_AND_PRIORITISATION.md`: the environment/VRAM/Ollama setup (items **A1** and **A3**). Everything else in Phase 0 (A2, A6, A7, A8) is _code_ that lives in the repo and is covered by the completion reports; those are not shell commands you "run".

> Target machine: **T0** — RTX 4060 Laptop 8 GB, i7-14650HX, 31 GB RAM. Your desktop currently uses ~2.9 GB VRAM, so the 9B model runs ~half on CPU. The goal of A1 is to free that VRAM so the 9B fits fully on the GPU.

## Run order

| Step | Script                      | What it does                                                                                                                                                | Changes system?                      |
| ---- | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| 1    | `01_diagnose.sh`            | Reports GPU/VRAM, Ollama, model sizes, CPU/GPU split. Read-only.                                                                                            | No                                   |
| 2    | `02_ollama_keepalive_A3.sh` | Sets `OLLAMA_KEEP_ALIVE=-1` + bigger context so the model never idle-unloads (kills ~8.3 s cold reloads).                                                   | Yes (Ollama env, reversible)         |
| 3    | `03_free_vram_A1.sh`        | **Guided** — shows you how to move the display to the iGPU / free VRAM. Does NOT auto-change your display; it prints the exact steps and checks the result. | Only if you follow its printed steps |
| 4    | `04_measure_gpu_fit.sh`     | Loads the 9B and reports whether it is 100% on GPU and the decode tok/s. This is long-ish (loads a model) — run when the GPU is idle.                       | No (just loads/unloads a model)      |

## How to run

```bash
conda activate minor
cd "idea/FutureWork/phase0_scripts"
bash 01_diagnose.sh          # look at the output first
bash 02_ollama_keepalive_A3.sh
bash 03_free_vram_A1.sh      # follow its printed steps, then re-run 01
bash 04_measure_gpu_fit.sh   # run only when GPU is idle
```

Outputs are written to `./out/` in this folder (kept out of demo2 data dirs).

## Safety notes

- None of these delete data or touch `code/demo2/`.
- `03_free_vram_A1.sh` is intentionally **advisory**: changing which GPU drives your display is hardware/OS specific and can log you out, so the script tells you what to do and verifies the outcome rather than doing it silently.
- To undo A3, run `02_ollama_keepalive_A3.sh --revert`.
