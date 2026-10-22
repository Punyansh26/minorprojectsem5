#!/usr/bin/env python3
"""
vm_run.py -- runs ON the Colab VM (sent there by `launch.py` via `colab exec`).

Pure Python on purpose: `colab exec` hands the file to the Colab *Python* kernel, so bash scripts
cannot be used. Everything is idempotent -- re-running only redoes what changed:

  1. unpack /content/code_bundle.zip  -> /content/minor_run
  2. link the TTS voice checkpoints   (/content/tts_models, uploaded once by launch.py)
  3. Python 3.11 venv (uv) with the same stack as the local `minor` conda env
  4. Ollama (GPU) + model, tokenizer for the agent
  5. Demo 2 FastAPI backend   -> 127.0.0.1:API_PORT
  6. Node + Next.js app build -> 127.0.0.1:WEB_PORT   (proxies /api/py/* to the backend)
  7. Cloudflare quick tunnel  -> public HTTPS URL (HTTPS is required for browser microphone access)

Result URL: printed at the end and saved to /content/colab_out/public_url.txt
Stop everything: python3 run_colab/launch.py --stop
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path("/content/minor_run")
APP = ROOT / "app/voiceagent"
DEMO2 = ROOT / "code/demo2"
AGENT = ROOT / "code/Institute-voice-agent/institute-assistant"
TTS_DIR = ROOT / "code/TTS/chattisgarhi-tts-models"
TTS_CACHE = Path("/content/tts_models")
TTS_PARTS = Path("/content/tts_parts")
BUNDLE = Path("/content/code_bundle.zip")
VENV = Path("/content/venv311")
PY = VENV / "bin/python"
LOGS = Path("/content/colab_out")
OLLAMA_URL = "http://127.0.0.1:11434"
VOICES = ("Female", "Male")

# Mirrors the local, test-verified `minor` conda env (Python 3.11, numpy 1.26, TTS 0.22, transformers 4.46).
CONSTRAINTS = ["numpy==1.26.4", "transformers==4.46.1", "torch==2.5.1", "torchaudio==2.5.1", "tokenizers<0.21"]
PKG_TORCH = ["torch==2.5.1", "torchaudio==2.5.1"]
PKG_TTS = ["TTS==0.22.0", "transformers==4.46.1", "numpy==1.26.4"]
PKG_DEMO2 = ["fastapi==0.115.6", "uvicorn[standard]==0.34.0", "python-multipart", "edge-tts==7.2.8",
             "soundfile>=0.12", "scipy>=1.11", "python-dotenv>=1.0", "faster-whisper==1.2.1", "silero-vad==6.2.1"]
DEPS_VERSION = hashlib.sha256(json.dumps([CONSTRAINTS, PKG_TORCH, PKG_TTS, PKG_DEMO2]).encode()).hexdigest()[:16]


# --------------------------------------------------------------------------------------------- helpers
def say(msg):
    print(f"\n{'=' * 72}\n=== {msg}\n{'=' * 72}", flush=True)


def sh(cmd, env=None, cwd=None, check=True):
    """Run a shell command and stream its output as it is produced."""
    print(f"$ {cmd}", flush=True)
    proc = subprocess.Popen(cmd, shell=True, cwd=cwd, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    tail = []
    for line in proc.stdout:
        print(line, end="", flush=True)
        tail.append(line)
        tail = tail[-30:]
    rc = proc.wait()
    if check and rc != 0:
        raise RuntimeError(f"command failed ({rc}): {cmd}")
    return rc


def bg(cmd, logfile, env=None, cwd=None):
    """Start a long-lived process detached from this kernel call."""
    LOGS.mkdir(parents=True, exist_ok=True)
    log = open(logfile, "ab")
    return subprocess.Popen(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, start_new_session=True)


def http_ok(url, timeout=3):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (colab-demo2)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


def wait_for(url, seconds, label):
    end = time.time() + seconds
    while time.time() < end:
        if http_ok(url):
            return True
        time.sleep(2)
    print(f"[warn] {label} did not become ready within {seconds}s", flush=True)
    return False


def tail_log(path, n=40):
    try:
        lines = Path(path).read_text(errors="replace").splitlines()[-n:]
        print(f"----- last {len(lines)} lines of {path} -----")
        print("\n".join(lines))
    except OSError:
        print(f"[warn] no log at {path}")


def read_cfg():
    """Settings from /content/.env (uploaded colab.env). File values beat the kernel's env."""
    cfg = {}
    path = Path("/content/.env")
    if path.is_file():
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    return lambda key, default="": cfg.get(key) or os.environ.get(key) or default


def pkill(pattern):
    subprocess.run(["pkill", "-f", pattern], check=False)


def stop_services(include_tunnel=True):
    for pat in ("uvicorn api_server:app", "next start", "next dev", "next-server"):
        pkill(pat)
    if include_tunnel:
        pkill("cloudflared tunnel")
    time.sleep(1)


# ------------------------------------------------------------------------------------------- stages
def stage_unpack():
    say("1. Unpack code bundle")
    if not BUNDLE.is_file():
        raise RuntimeError(f"{BUNDLE} missing -- run this via launch.py (it uploads the bundle first)")
    ROOT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BUNDLE) as zf:
        zf.extractall(ROOT)
    for need in (DEMO2 / "api_server.py", APP / "package.json", AGENT / "assistant/graph.py"):
        if not need.is_file():
            raise RuntimeError(f"bundle is incomplete, missing {need}")
    print(f"unpacked to {ROOT}")


def stage_tts():
    say("2. TTS voice checkpoints")
    parts = sorted(TTS_PARTS.glob("tts.zip.part*"))
    if parts and not all((TTS_CACHE / v / "best_model.pth").is_file() for v in VOICES):
        zpath = Path("/content/tts_models.zip")
        with open(zpath, "wb") as out:
            for p in parts:
                with open(p, "rb") as src:
                    shutil.copyfileobj(src, out, 16 * 1024 * 1024)
        TTS_CACHE.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(TTS_CACHE)
        zpath.unlink()
        for p in parts:
            p.unlink()
        print("assembled checkpoints from uploaded parts")
    linked = 0
    for v in VOICES:
        src = TTS_CACHE / v / "best_model.pth"
        dst = TTS_DIR / v / "best_model.pth"
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.is_symlink() or dst.exists():
                dst.unlink()
            dst.symlink_to(src)
            linked += 1
    if linked == len(VOICES):
        print("both voices linked")
    else:
        print("[warn] TTS checkpoints not found -> spoken answers will fail; text answers still work. "
              "Re-run launch.py without --no-tts.")


def stage_python():
    say("3. Python 3.11 environment (uv)")
    mark = VENV / ".deps_ok"
    if PY.is_file() and mark.is_file() and mark.read_text() == DEPS_VERSION:
        print("venv up to date")
    else:
        sh(f"{sys.executable} -m pip -q install uv")
        uv = f"{sys.executable} -m uv"
        sh(f"{uv} venv --python 3.11 --clear {VENV}")
        cons = Path("/content/constraints.txt")
        cons.write_text("\n".join(CONSTRAINTS) + "\n")
        pip = f"{uv} pip install --python {PY} -c {cons}"
        quote = lambda items: " ".join(f"'{i}'" for i in items)
        sh(f"{pip} {quote(PKG_TORCH)}")
        sh(f"{pip} {quote(PKG_TTS)}")
        sh(f"{pip} {quote(PKG_DEMO2)}")
        req = AGENT / "requirements.txt"
        if req.is_file():
            sh(f"{pip} -r {req}")
        mark.write_text(DEPS_VERSION)
    sh(f"{PY} -c \"import torch,fastapi,uvicorn,multipart,TTS,transformers,faster_whisper,chromadb,"
       f"langgraph,sentence_transformers,soundfile,edge_tts; "
       f"print('torch', torch.__version__, 'cuda', torch.cuda.is_available())\"", env=clean_env())


def clean_env(extra=None):
    """Environment for child processes: the kernel's own Python vars must not leak into the venv."""
    env = dict(os.environ)
    for k in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "NODE_ENV"):
        env.pop(k, None)
    env["PATH"] = f"{VENV / 'bin'}:{env.get('PATH', '')}"
    env["PYTHONUNBUFFERED"] = "1"
    env.update(extra or {})
    return env


def backend_env(get):
    # CTranslate2 (faster-whisper) needs cuBLAS/cuDNN 12; torch's pip wheels ship them inside site-packages.
    libs = sorted(str(p) for p in VENV.glob("lib/python3.11/site-packages/nvidia/*/lib"))
    ld = ":".join(libs + [os.environ.get("LD_LIBRARY_PATH", "")]).strip(":")
    env = clean_env({
        "LLM_PROVIDER": "ollama",
        "OLLAMA_BASE_URL": OLLAMA_URL,
        "OLLAMA_MODEL": get("MODEL_TAG", "qwen3.5:9b"),
        "OLLAMA_NUM_CTX": get("OLLAMA_NUM_CTX", "16384"),
        "OLLAMA_KEEP_ALIVE": "-1",
        "DEMO2_CODE_ROOT": str(ROOT / "code"),
        "DEMO2_STT_DEVICE": get("DEMO2_STT_DEVICE", "auto"),
        "DEMO2_TTS_DEVICE": get("DEMO2_TTS_DEVICE", "cpu"),
        "DEMO2_WHISPER_MODEL": get("DEMO2_WHISPER_MODEL", "small"),
        "DEMO2_SPEECH_THREADS": "8",
        "JEV_ROUTING_MODE": "off",
        "USE_TF": "0", "USE_FLAX": "0", "USE_JAX": "0", "USE_TORCH": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "LD_LIBRARY_PATH": ld,
    })
    if get("GROQ_API_KEY"):
        env["GROQ_API_KEY"] = get("GROQ_API_KEY")
    return env


def stage_ollama(get):
    say("4. Ollama (GPU) + model")
    model = get("MODEL_TAG", "qwen3.5:9b")
    if not shutil.which("ollama"):
        sh("command -v zstd >/dev/null 2>&1 || (apt-get -qq update && apt-get -qq install -y zstd)", check=False)
        sh("curl -fsSL https://ollama.com/install.sh | sh")
    if not http_ok(f"{OLLAMA_URL}/api/version"):
        env = dict(os.environ, OLLAMA_HOST="127.0.0.1:11434", OLLAMA_KEEP_ALIVE="-1")
        bg(["ollama", "serve"], LOGS / "ollama.log", env=env)
        if not wait_for(f"{OLLAMA_URL}/api/version", 60, "ollama"):
            tail_log(LOGS / "ollama.log")
            raise RuntimeError("ollama did not start")
    listed = subprocess.run(["ollama", "list"], text=True, capture_output=True).stdout
    if model not in listed:
        sh(f"ollama pull {model}")
    # Load the model onto the GPU now, with the same context the agent will request (avoids a reload on turn 1).
    body = json.dumps({"model": model, "prompt": "ok", "stream": False, "keep_alive": -1,
                       "options": {"num_predict": 1, "num_ctx": int(get("OLLAMA_NUM_CTX", "16384"))}}).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=300).read()
    except Exception as exc:
        print(f"[warn] model warm-up failed: {exc}")
    sh("ollama ps", check=False)

    env = backend_env(get)
    # The agent needs a local tokenizer file for its prompt budgeting.
    sh(f"{PY} setup_local.py", env=env, cwd=AGENT, check=False)
    # Pre-fetch the Whisper model so the first microphone question is not delayed by a download.
    sh(f"{PY} -c \"from faster_whisper import download_model; "
       f"print(download_model('{get('DEMO2_WHISPER_MODEL', 'small')}'))\"", env=env, check=False)


def stage_backend(get):
    say("5. Demo 2 FastAPI backend")
    port = get("API_PORT", "8020")
    pkill("uvicorn api_server:app")
    time.sleep(1)
    (DEMO2 / "data").mkdir(exist_ok=True)
    bg([str(PY), "-m", "uvicorn", "api_server:app", "--host", "127.0.0.1", "--port", port],
       LOGS / "backend.log", env=backend_env(get), cwd=DEMO2)
    if not wait_for(f"http://127.0.0.1:{port}/api/health", 240, "backend"):
        tail_log(LOGS / "backend.log", 80)
        raise RuntimeError("Demo 2 backend did not come up")
    print(f"backend healthy on :{port}")


def node_version_ok():
    if not shutil.which("node"):
        return False
    out = subprocess.run(["node", "--version"], text=True, capture_output=True).stdout.strip()
    m = re.match(r"v(\d+)\.(\d+)", out)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (20, 9)


def stage_web(get):
    say("6. Next.js web app")
    if not node_version_ok():
        print("installing Node.js 22")
        sh("curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y -qq nodejs")
    sh("node --version && npm --version")
    web, api = get("WEB_PORT", "3001"), get("API_PORT", "8020")
    env = backend_env(get)
    env.update({"DEMO2_API_URL": f"http://127.0.0.1:{api}", "DEMO2_DIR": str(DEMO2), "DEMO2_PYTHON": str(PY),
                "NEXT_TELEMETRY_DISABLED": "1", "HOSTNAME": "127.0.0.1", "PORT": web})
    if not (APP / "node_modules/.bin/next").is_file():
        sh("npm ci --no-audit --no-fund", cwd=APP, env=env)
    shutil.rmtree(APP / ".next", ignore_errors=True)
    built = sh("npm run build", cwd=APP, env=env, check=False) == 0
    mode = "start" if built else "dev"
    if not built:
        print("[warn] production build failed -> falling back to `next dev` (slower first page loads)")
    bg([str(APP / "node_modules/.bin/next"), mode, "-H", "127.0.0.1", "-p", web],
       LOGS / "web.log", env=env, cwd=APP)
    if not wait_for(f"http://127.0.0.1:{web}/api/py/health", 180, "web app"):
        tail_log(LOGS / "web.log", 60)
        raise RuntimeError("web app did not come up")
    print(f"web app ready on :{web} ({mode})")


def stage_tunnel(get):
    say("7. Public HTTPS tunnel (Cloudflare quick tunnel)")
    web = get("WEB_PORT", "3001")
    url_file = LOGS / "public_url.txt"
    pkill("cloudflared tunnel")
    time.sleep(1)
    if not shutil.which("cloudflared"):
        sh("curl -fsSL -o /usr/local/bin/cloudflared "
           "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 "
           "&& chmod +x /usr/local/bin/cloudflared")
    logfile = LOGS / "cloudflared.log"
    logfile.write_bytes(b"")
    bg(["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{web}", "--no-autoupdate"], logfile)
    url = None
    for _ in range(60):
        m = re.search(r"https://[-a-z0-9]+\.trycloudflare\.com", logfile.read_text(errors="replace"))
        if m:
            url = m.group(0)
            break
        time.sleep(1)
    if not url:
        tail_log(logfile)
        raise RuntimeError("could not obtain a tunnel URL")
    ok = wait_for(f"{url}/api/py/health", 90, "public tunnel")
    url_file.write_text(url + "\n")
    return url, ok


# ----------------------------------------------------------------------------------------------- main
def main():
    action = os.environ.pop("ACTION", "run")
    LOGS.mkdir(parents=True, exist_ok=True)
    if action == "stop":
        stop_services()
        print("services stopped (Ollama left running; stop the Colab session to release the GPU)")
        return
    t0 = time.time()
    get = read_cfg()
    say("0. GPU")
    sh("nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv "
       "|| echo 'WARNING: no GPU visible'", check=False)
    try:
        stop_services(include_tunnel=False)   # free ports before the code on disk changes
        stage_unpack()
        stage_tts()
        stage_python()
        stage_ollama(get)
        stage_backend(get)
        stage_web(get)
        url, ok = stage_tunnel(get)
    except Exception as exc:
        say(f"FAILED: {exc}")
        print(f"Logs are in {LOGS}/ (backend.log, web.log, ollama.log, cloudflared.log).")
        sys.exit(1)

    say(f"READY in {time.time() - t0:.0f}s")
    print(f"\n   OPEN:  {url}\n")
    if not ok:
        print("(The tunnel answered no health check yet -- DNS can take up to a minute; just retry the URL.)")
    print("Notes:")
    print(" - The URL is public and has NO login. Anyone who has it can use the helpdesk and your GPU.")
    print(" - First question is slower (embedding model + graph load); Chhattisgarhi (MMS-1B) downloads ~4 GB on first use.")
    print(" - The URL changes whenever the tunnel restarts. Stop with: python3 run_colab/launch.py --stop")


if __name__ == "__main__":
    main()
