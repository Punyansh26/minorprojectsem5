#!/usr/bin/env python3
"""
run_all.py  --  One-file Colab (A100 / Tier T2) orchestrator for the Minor voice stack.

WHY THIS FILE EXISTS
--------------------
`colab run file.sh` and `colab exec -f file.sh` hand the file to the Colab *Python*
kernel, which tries to parse bash (`set -uo pipefail`, ...) as Python and dies with
`SyntaxError`. This wrapper is pure Python, so the kernel accepts it, and it drives
the real bash/CLI steps via subprocess inside ONE persistent session -- so the
background `ollama serve` started in stage 1 stays alive for stages 2/3/4
(a plain `colab run` would tear the VM down after each script and kill the server).

HOW TO RUN IT (from your laptop terminal)
-----------------------------------------
    # one-time: make sure you have a GPU session called 'minor'
    colab new -s minor --gpu A100        # (skip if it already exists)

    # (optional) load your keys into the session as env vars first -- see ENV KEYS below
    # then run everything headless:
    colab exec -s minor -f '/run/media/rtx/Files/Study/Semester 5/Minor/RTX/run_all.py'

ENV KEYS (optional)
-------------------
This script reads keys from, in priority order:
  1. environment variables already set in the kernel,
  2. a `.env`-style file whose path is in COLAB_ENV_FILE, or `/content/.env` if present.
Recognised keys (all optional):
  GH_TOKEN         GitHub PAT for a private clone (public clone used if absent)
  GROQ_API_KEY     enables the cloud-reasoning latency comparison (stage 4b)
  REPO_BRANCH      git branch to clone (default: main)
  MODEL_TAG        Ollama model tag (default: qwen3.5:9b)
  STAGES           comma list to limit stages, e.g. "1,2,3" (default: all)

Because `colab exec` can't set remote env vars directly, the easiest path is:
  - put your keys in a local file, then upload it:
        colab upload '/run/media/rtx/Files/Study/Semester 5/Minor/RTX/colab.env' /content/.env
  - this script auto-detects /content/.env.

All outputs land in /content/colab_out/ . Download them with:
    colab download /content/colab_out/benchmark_decode_summary.json ./
    colab download /content/colab_out/demo2_latency_summary.json ./
"""

import json
import os
import shlex
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------- #
# Config / constants
# --------------------------------------------------------------------------- #
WORK = Path("/content/minor")
OUT = Path("/content/colab_out")
REPO_USER = "Punyansh26"
REPO = "minorprojectsem5"
SCRIPTS_REL = "idea/FutureWork/colab_scripts"
OLLAMA_URL = "http://127.0.0.1:11434"


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def say(msg):
    print(f"\n{'=' * 70}\n=== {msg}\n{'=' * 70}", flush=True)


def sh(cmd, check=True, env=None, cwd=None, quiet=False):
    """Run a shell command, streaming output. Returns the CompletedProcess."""
    if not quiet:
        print(f"$ {cmd}", flush=True)
    proc = subprocess.run(
        cmd, shell=True, text=True, env=env, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if proc.stdout:
        print(proc.stdout, end="", flush=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {cmd}")
    return proc


def load_env_file():
    """Merge a .env-style file into os.environ (does not overwrite existing vars)."""
    candidates = []
    if os.getenv("COLAB_ENV_FILE"):
        candidates.append(Path(os.environ["COLAB_ENV_FILE"]))
    candidates += [Path("/content/.env"), Path("/content/colab.env")]
    for path in candidates:
        if path.is_file():
            print(f"[env] loading keys from {path}")
            for raw in path.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                # strip an optional leading 'export '
                if key.startswith("export "):
                    key = key[len("export "):].strip()
                if key and key not in os.environ:
                    os.environ[key] = val
            return path
    print("[env] no .env file found (that's fine; all keys are optional)")
    return None


def ollama_up():
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/version", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Stages
# --------------------------------------------------------------------------- #
def stage0_env():
    say("STAGE 0  Environment + keys")
    load_env_file()
    OUT.mkdir(parents=True, exist_ok=True)
    sh("nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv || "
       "echo 'WARNING: no GPU visible -- set the session to A100.'", check=False)
    print(f"[env] MODEL_TAG   = {os.getenv('MODEL_TAG', 'qwen3.5:9b')}")
    print(f"[env] REPO_BRANCH = {os.getenv('REPO_BRANCH', 'main')}")
    print(f"[env] GH_TOKEN    = {'set' if os.getenv('GH_TOKEN') else 'absent (public clone)'}")
    print(f"[env] GROQ_API_KEY= {'set' if os.getenv('GROQ_API_KEY') else 'absent (ollama only)'}")


def stage1_bootstrap():
    """Clone repo, install deps, install+start GPU Ollama, pull model.

    We delegate to the repo's own 01_bootstrap.sh (single source of truth) but
    run it correctly: as bash, not as a Python cell.
    """
    say("STAGE 1  Bootstrap (clone + deps + Ollama + model)")
    model = os.getenv("MODEL_TAG", "qwen3.5:9b")

    # zstd is needed by the Ollama installer; Colab images often lack it.
    sh("command -v zstd >/dev/null 2>&1 || (apt-get -qq update && apt-get -qq install -y zstd) "
       "|| echo 'WARNING: could not install zstd'", check=False)

    # First-pass clone so the repo (and its 01_bootstrap.sh) exists locally.
    if not (WORK / ".git").is_dir():
        branch = os.getenv("REPO_BRANCH", "main")
        token = os.getenv("GH_TOKEN", "")
        if token:
            url = f"https://{token}@github.com/{REPO_USER}/{REPO}.git"
            sh(f"git clone --branch {shlex.quote(branch)} {shlex.quote(url)} {shlex.quote(str(WORK))}")
            # scrub the token out of the stored remote
            sh(f"git -C {shlex.quote(str(WORK))} remote set-url origin "
               f"https://github.com/{REPO_USER}/{REPO}.git", check=False)
        else:
            url = f"https://github.com/{REPO_USER}/{REPO}.git"
            sh(f"git clone --branch {shlex.quote(branch)} {shlex.quote(url)} {shlex.quote(str(WORK))}")
    else:
        sh(f"git -C {shlex.quote(str(WORK))} pull --ff-only || echo 'pull skipped'", check=False)

    boot = WORK / SCRIPTS_REL / "01_bootstrap.sh"
    if not boot.is_file():
        raise RuntimeError(f"bootstrap script missing at {boot} -- wrong branch?")

    # Forward GH_TOKEN so the script can reuse the repo; pass model as arg 1.
    env = dict(os.environ)
    sh(f"bash {shlex.quote(str(boot))} {shlex.quote(model)}", env=env)

    if not ollama_up():
        raise RuntimeError("Ollama did not come up after bootstrap; see /content/colab_out/ollama.log")
    print("[stage1] Ollama is up.")


def stage2_serve():
    say("STAGE 2  Serving config (keep-alive + .env.colab)")
    model = os.getenv("MODEL_TAG", "qwen3.5:9b")
    serve = WORK / SCRIPTS_REL / "02_serve_config.sh"
    env = dict(os.environ)
    sh(f"bash {shlex.quote(str(serve))} {shlex.quote(model)}", env=env)


def stage3_benchmark():
    say("STAGE 3  Decode benchmark (tok/s on A100)")
    model = os.getenv("MODEL_TAG", "qwen3.5:9b")
    bench = WORK / SCRIPTS_REL / "03_benchmark_decode.py"
    env = dict(os.environ, COLAB_OUT=str(OUT), OLLAMA_BASE_URL=OLLAMA_URL)
    sh(f"{shlex.quote(sys.executable)} {shlex.quote(str(bench))} "
       f"--model {shlex.quote(model)} --repeats 5", env=env)
    _print_json(OUT / "benchmark_decode_summary.json")


def stage4_latency():
    say("STAGE 4  End-to-end demo2 latency")
    model = os.getenv("MODEL_TAG", "qwen3.5:9b")

    # Preflight: the known blocker is a missing/empty sibling agent project.
    graph = WORK / "code/Institute-voice-agent/institute-assistant/assistant/graph.py"
    bridge = WORK / "code/demo2/agent_bridge.py"
    if not bridge.is_file():
        print("[stage4] SKIP: code/demo2/agent_bridge.py not present in this clone.")
        return
    if not graph.is_file():
        print("[stage4] The Institute agent appears missing/empty. Trying submodule init...")
        sh(f"git -C {shlex.quote(str(WORK))} submodule update --init --recursive "
           "|| echo 'no submodules / init failed'", check=False)
    if not graph.is_file():
        print("[stage4] SKIP: Institute agent still missing "
              f"({graph} not found). The public clone likely doesn't ship it.")
        print("[stage4] Stage 3 decode numbers are the headline result and are complete.")
        return

    lat = WORK / SCRIPTS_REL / "04_demo2_latency.py"
    agent_dir = WORK / "code/Institute-voice-agent/institute-assistant"
    envfile = OUT / ".env.colab"
    base_env = dict(os.environ, COLAB_OUT=str(OUT))
    if envfile.is_file():
        for raw in envfile.read_text().splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                base_env[k.strip()] = v.strip()

    # The agent routing layer needs a LOCAL TOKENIZER file (OLLAMA_TOKENIZER_PATH),
    # downloaded by setup_local.py. Without it every turn fails fast with
    # LocalModelError("Local tokenizer is missing...") before Ollama is ever called.
    setup_local = agent_dir / "setup_local.py"
    if setup_local.is_file():
        print("[stage4] Ensuring local tokenizer (setup_local.py)...")
        # tokenizers/httpx are imports setup_local needs; install if absent.
        sh(f"{shlex.quote(sys.executable)} -c 'import tokenizers, httpx' 2>/dev/null "
           f"|| pip -q install tokenizers httpx", check=False)
        rc = sh(f"{shlex.quote(sys.executable)} {shlex.quote(str(setup_local))}",
                env=base_env, cwd=str(agent_dir), check=False).returncode
        if rc != 0:
            print("[stage4] setup_local.py did not fully succeed (see output above).")
            print("[stage4] If it failed on the tokenizer download, the model family "
                  "may not map to a HuggingFace repo in setup_local.py's TOKENIZERS. "
                  "You can set OLLAMA_TOKENIZER_PATH to a compatible tokenizer.json and re-run STAGES=4.")

    # 4a: local Ollama
    sh(f"{shlex.quote(sys.executable)} {shlex.quote(str(lat))} --turns 2 --warmup --provider ollama",
       env=base_env, check=False)
    _print_json(OUT / "demo2_latency_summary.json")

    # If no turn answered, run the purpose-built diagnostic to surface the REAL
    # llm_error message (04 only reports status, hiding the actionable cause).
    if _no_turn_answered(OUT / "demo2_latency_summary.json"):
        diag = WORK / SCRIPTS_REL / "diag_llm_error.py"
        if diag.is_file():
            say("STAGE 4 DIAGNOSTIC  (surfacing the hidden LocalModelError)")
            sh(f"{shlex.quote(sys.executable)} {shlex.quote(str(diag))} --provider ollama",
               env=base_env, cwd=str(WORK / 'code/demo2'), check=False)
            # Also tail the ollama server log: the real HTTP error often lands there.
            print("\n[stage4] last 25 lines of ollama.log:")
            sh("tail -n 25 /content/colab_out/ollama.log 2>/dev/null || true", check=False)

    # 4b: optional cloud comparison if a Groq key is present
    if os.getenv("GROQ_API_KEY"):
        print("[stage4] GROQ_API_KEY present -- running cloud-reasoning comparison.")
        sh(f"{shlex.quote(sys.executable)} {shlex.quote(str(lat))} --turns 2 --warmup --provider groq",
           env=base_env, check=False)


def _no_turn_answered(path):
    try:
        data = json.loads(path.read_text())
        return (data.get("answered", 0) or 0) == 0
    except Exception:
        return False


def _print_json(path):
    if path.is_file():
        print(f"\n----- {path} -----")
        try:
            print(json.dumps(json.loads(path.read_text()), indent=2, ensure_ascii=False))
        except Exception:
            print(path.read_text())
    else:
        print(f"[warn] expected output not found: {path}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
STAGE_FUNCS = {
    "1": stage1_bootstrap,
    "2": stage2_serve,
    "3": stage3_benchmark,
    "4": stage4_latency,
}


def main():
    t_start = time.time()
    stage0_env()  # always runs

    wanted = os.getenv("STAGES", "1,2,3,4")
    stages = [s.strip() for s in wanted.split(",") if s.strip()]
    print(f"\n[plan] running stages: {', '.join(stages)}")

    for s in stages:
        fn = STAGE_FUNCS.get(s)
        if not fn:
            print(f"[warn] unknown stage '{s}', skipping")
            continue
        try:
            fn()
        except Exception as e:
            say(f"STAGE {s} FAILED: {e}")
            print("Stopping. Fix the error above and re-run "
                  "(set STAGES to resume, e.g. STAGES=3,4).")
            sys.exit(1)

    say(f"ALL DONE in {round(time.time() - t_start, 1)}s")
    print("Outputs in /content/colab_out/ :")
    sh("ls -la /content/colab_out/ 2>/dev/null || true", check=False)
    print("\n(If launched via colab_go.sh, these are now downloaded into your RTX folder.)")


if __name__ == "__main__":
    main()
