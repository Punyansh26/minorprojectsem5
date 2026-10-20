#!/usr/bin/env python3
"""L2 — real MMS `hne` CPU partial/final latency on T0 (replaces the 1850 ms slide).

Loads the stt-service ChhattisgarhiMMSEngine on CPU and times `transcribe` for
each WAV in L2_mms/wavs/, separately for fast=True (partial) and fast=False
(final). This is the number chapter 03 §7/§8 and REPORT_01 §6 flag as unverified.

Run (model downloads on first use; CPU-heavy):
    python l2_mms_latency.py --out L2_mms/summary.json

--check validates torch/transformers import and the WAV folder WITHOUT loading
the 1B model.
"""
import argparse, glob, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STT_ROOT = HERE.parent.parent.parent / "code" / "STT" / "stt-service"
WAV_DIR = HERE / "L2_mms" / "wavs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    if args.check:
        try:
            import torch, transformers  # noqa: F401
            imports_ok = True
        except Exception as e:  # pragma: no cover
            imports_ok = f"{type(e).__name__}: {e}"
        info = {"check": True, "wav_dir": str(WAV_DIR), "wav_dir_exists": WAV_DIR.is_dir(),
                "n_wavs": len(glob.glob(str(WAV_DIR / "*.wav"))), "imports_ok": imports_ok,
                "stt_root_exists": STT_ROOT.is_dir()}
        json.dump(info, open(args.out, "w"), indent=2)
        print(json.dumps(info))
        return

    sys.path.insert(0, str(STT_ROOT))
    # Force CPU + hne so we measure the T0-relevant path.
    os.environ["STT_DEVICE"] = "cpu"
    os.environ["STT_LANGUAGE"] = "hne"
    import importlib
    import src.config as config_mod
    importlib.reload(config_mod)
    import src.asr as asr_mod
    importlib.reload(asr_mod)
    import soundfile as sf
    import numpy as np

    engine = asr_mod.ChhattisgarhiMMSEngine()
    rows = []
    for w in sorted(glob.glob(str(WAV_DIR / "*.wav"))):
        audio, sr = sf.read(w, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        audio = np.asarray(audio, dtype=np.float32)
        t0 = time.monotonic(); p = engine.transcribe(audio, fast=True)
        t1 = time.monotonic(); f = engine.transcribe(audio, fast=False)
        t2 = time.monotonic()
        rows.append({"wav": os.path.basename(w), "dur_s": round(len(audio) / sr, 2),
                     "partial_ms": round((t1 - t0) * 1000, 1), "final_ms": round((t2 - t1) * 1000, 1),
                     "partial_text_len": len(p.text), "final_text_len": len(f.text)})
    pm = [r["partial_ms"] for r in rows]; fm = [r["final_ms"] for r in rows]
    summary = {"device": "cpu", "language": "hne", "n_wavs": len(rows), "rows": rows,
               "mean_partial_ms": round(sum(pm) / len(pm), 1) if pm else None,
               "mean_final_ms": round(sum(fm) / len(fm), 1) if fm else None,
               "note": "compares against the unverified 1850 ms slide (REPORT_01 §6). "
                       "First WAV includes one-time warmup; report warm numbers separately if needed."}
    json.dump(summary, open(args.out, "w"), indent=2)
    print(json.dumps({"mean_partial_ms": summary["mean_partial_ms"],
                      "mean_final_ms": summary["mean_final_ms"]}))


if __name__ == "__main__":
    main()
