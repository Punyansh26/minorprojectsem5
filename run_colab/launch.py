#!/usr/bin/env python3
"""
launch.py -- run on your LAPTOP. Zips this project, uploads it to a Colab GPU session
and starts Demo 2 (FastAPI backend) + the Next.js web app there, behind a public HTTPS URL.

    python3 run_colab/launch.py            # build zip, upload, start everything
    python3 run_colab/launch.py --stop     # stop backend / web app / tunnel on the VM
    python3 run_colab/launch.py --no-tts   # skip the ~2 GB TTS voice upload (text answers only)
    python3 run_colab/launch.py --rebuild-tts   # force re-upload of the TTS voices

What gets uploaded
  code_bundle.zip   source of app/voiceagent + code/{demo2,Institute-voice-agent,knowledgebaseenhanced,
                    STT,TTS configs} (small; re-uploaded every run, so your latest local edits are used)
  tts_models parts  the two Chhattisgarhi VITS checkpoints (~2 GB). Uploaded ONCE per Colab VM in
                    200 MB parts; later runs detect them on the VM and skip.
Never uploaded: any .env (API keys), .git, node_modules, .next, caches, demo2/data (8 GB of old runs),
                laya-service, the agri demo, idea/, RTX/.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent                       # .../Minor
DIST = HERE / "dist"
SESSION = os.environ.get("COLAB_SESSION", "minor")
GPU = os.environ.get("COLAB_GPU", "A100")
PART_BYTES = 200 * 1024 * 1024
UPLOAD_TIMEOUT = 1800

# --- what goes in the code bundle ------------------------------------------------------------
INCLUDE_ROOTS = [
    "app/voiceagent",
    "code/demo2",
    "code/Institute-voice-agent",
    "code/knowledgebaseenhanced",
    "code/STT",
    "code/TTS",                              # configs/scripts only; weights are handled separately
]
EXCLUDE_DIR_NAMES = {".git", "node_modules", ".next", "__pycache__", ".pytest_cache", ".venv", "venv",
                     ".mypy_cache", ".ruff_cache"}
EXCLUDE_PREFIXES = [                         # project-relative posix paths
    "code/demo2/data",                       # 8 GB of old evaluation runs + live sqlite state
    "code/Institute-voice-agent/institute-assistant/kb_state",   # legacy KB; demo2 uses the kbb release
    "code/Institute-voice-agent/voice-orchestrator",
]
EXCLUDE_SUFFIXES = (".pyc", ".pth", ".wav", ".log", ".pid", ".ipynb")
EXCLUDE_FILE_NAMES = {".env"}                # secrets stay on the laptop; VM gets /content/.env instead
TTS_REL = "code/TTS/chattisgarhi-tts-models"
VOICES = ("Female", "Male")


def log(msg):
    print(f"[launch] {msg}", flush=True)


def find_colab():
    exe = shutil.which("colab")
    if exe:
        return exe
    for d in (Path.home() / "miniconda3/bin", Path.home() / "anaconda3/bin", Path.home() / ".local/bin"):
        if (d / "colab").exists():
            return str(d / "colab")
    sys.exit("[launch] colab CLI not found (install: uv tool install google-colab-cli)")


COLAB = find_colab()


def colab(*args, check=True, capture=False, timeout=None):
    cmd = [COLAB, *args]
    if capture:
        return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    rc = subprocess.run(cmd, timeout=timeout).returncode
    if check and rc != 0:
        sys.exit(f"[launch] command failed ({rc}): {' '.join(cmd)}")
    return rc


def ensure_session():
    r = colab("status", "-s", SESSION, capture=True, check=False)
    if SESSION in (r.stdout or "") and "Hardware:" in (r.stdout or ""):
        log(f"session '{SESSION}' exists")
        return
    log(f"creating session '{SESSION}' ({GPU})")
    colab("new", "-s", SESSION, "--gpu", GPU)


def skip(rel: Path, is_dir=False):
    posix = rel.as_posix()
    if any(part in EXCLUDE_DIR_NAMES for part in rel.parts):
        return True
    if any(posix == p or posix.startswith(p + "/") for p in EXCLUDE_PREFIXES):
        return True
    if not is_dir and (rel.name in EXCLUDE_FILE_NAMES or rel.name.endswith(EXCLUDE_SUFFIXES)):
        return True
    return False


def build_code_zip() -> Path:
    DIST.mkdir(exist_ok=True)
    out = DIST / "code_bundle.zip"
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root in INCLUDE_ROOTS:
            base = PROJECT / root
            if not base.exists():
                log(f"WARNING: {root} not found, skipped")
                continue
            for dirpath, dirnames, filenames in os.walk(base):
                rel_dir = Path(dirpath).relative_to(PROJECT)
                dirnames[:] = [d for d in dirnames if not skip(rel_dir / d, is_dir=True)]
                for name in filenames:
                    rel = rel_dir / name
                    if skip(rel):
                        continue
                    path = PROJECT / rel
                    if path.is_symlink() or not path.is_file():
                        continue
                    zf.write(path, rel.as_posix())
                    count += 1
    log(f"code_bundle.zip: {count} files, {out.stat().st_size / 1e6:.1f} MB")
    return out


def tts_on_vm() -> bool:
    probe = (
        "from pathlib import Path\n"
        "ok = all(Path('/content/tts_models/%s/best_model.pth' % v).is_file() for v in ('Female','Male'))\n"
        "print('TTS_ON_VM=' + ('yes' if ok else 'no'))\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(probe)
        name = f.name
    try:
        r = colab("exec", "-s", SESSION, "-f", name, "--timeout", "120", capture=True, check=False)
    finally:
        os.unlink(name)
    return "TTS_ON_VM=yes" in ((r.stdout or "") + (r.stderr or ""))


def upload_tts():
    sources = []
    for v in VOICES:
        ckpt = PROJECT / TTS_REL / v / "best_model.pth"
        if not ckpt.is_file() or ckpt.stat().st_size < 1_000_000:
            log(f"WARNING: {ckpt} missing or a Git-LFS pointer; TTS voices will not work")
            return False
        sources.append((v, ckpt))
    zpath = DIST / "tts_models.zip"
    log("packing TTS checkpoints (stored, no compression)...")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as zf:
        for v, ckpt in sources:
            zf.write(ckpt, f"{v}/best_model.pth")
    total = zpath.stat().st_size
    parts = -(-total // PART_BYTES)
    log(f"uploading {total / 1e9:.2f} GB in {parts} parts of 200 MB (one-time per VM)")
    part_dir = DIST / "tts_parts"
    shutil.rmtree(part_dir, ignore_errors=True)
    part_dir.mkdir()
    with open(zpath, "rb") as src:
        for i in range(parts):
            part = part_dir / f"tts.zip.part{i:03d}"
            part.write_bytes(src.read(PART_BYTES))
            for attempt in (1, 2, 3):
                rc = colab("upload", "-s", SESSION, str(part), f"/content/tts_parts/{part.name}",
                           check=False, timeout=UPLOAD_TIMEOUT)
                if rc == 0:
                    break
                log(f"  part {i + 1}/{parts} failed (attempt {attempt}/3)")
            else:
                sys.exit(f"[launch] could not upload {part.name}")
            part.unlink()
            log(f"  part {i + 1}/{parts} done")
    shutil.rmtree(part_dir, ignore_errors=True)
    zpath.unlink()
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop", action="store_true", help="stop the services on the VM and exit")
    ap.add_argument("--no-tts", action="store_true", help="do not upload TTS voice checkpoints")
    ap.add_argument("--rebuild-tts", action="store_true", help="re-upload TTS even if present on the VM")
    ap.add_argument("--timeout", type=int, default=3300, help="seconds allowed for the VM setup run")
    args = ap.parse_args()

    ensure_session()
    vm_script = HERE / "vm_run.py"

    if args.stop:
        colab("exec", "-s", SESSION, "-f", str(vm_script), "--timeout", "300", "--env", "ACTION=stop")
        return

    code_zip = build_code_zip()

    env_file = HERE / "colab.env"
    if env_file.is_file():
        colab("upload", "-s", SESSION, str(env_file), "/content/.env", check=False)

    if not args.no_tts:
        if args.rebuild_tts or not tts_on_vm():
            upload_tts()
        else:
            log("TTS checkpoints already on the VM -> skipping upload")

    log("uploading code bundle")
    colab("upload", "-s", SESSION, str(code_zip), "/content/code_bundle.zip", timeout=UPLOAD_TIMEOUT)

    log("starting Demo 2 + web app on the VM (first run on a fresh VM takes ~10-15 min)")
    rc = colab("exec", "-s", SESSION, "-f", str(vm_script), "--timeout", str(args.timeout),
               "--env", "ACTION=run", check=False)

    url_file = HERE / "public_url.txt"
    colab("download", "-s", SESSION, "/content/colab_out/public_url.txt", str(url_file), check=False)
    if url_file.is_file():
        log(f"OPEN THIS URL: {url_file.read_text().strip()}")
    else:
        log("no public URL was produced; check the output above and /content/colab_out/*.log on the VM")
    sys.exit(rc)


if __name__ == "__main__":
    main()
