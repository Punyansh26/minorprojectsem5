#!/usr/bin/env python3
"""L1 — EOU false-cut rate and added delay, swept over the threshold tau.

Loads the vedants254-style ONNX model at $EOU_MODEL and runs the stt-service
SemanticTurnDetector directly on labelled turns, offline (no server, no audio
device). Each line of L1_eou/turns.jsonl is:
    {"wav": "path/to/clip.wav", "complete": true|false}
where `complete` is the ground-truth "was the turn actually finished at the end
of this clip". For a sweep of tau it computes, treating `p_complete >= tau` as
"declare done":
    * false-cut rate   = P(declared done | NOT complete)
    * missed rate      = P(declared NOT done | complete)  (these fall back to the
                         silence cap -> added dead air)
Pick the smallest tau with false-cut <= 5% (chapter 03 §12).

Run:
    export EOU_MODEL=/path/to/voice-turn-detection.onnx
    python l1_eou_sweep.py --out L1_eou/summary.json

--check validates onnxruntime import, the model path, and the turns file WITHOUT
loading the model or running inference.
"""
import argparse, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STT_ROOT = HERE.parent.parent.parent / "code" / "STT" / "stt-service"
TURNS = HERE / "L1_eou" / "turns.jsonl"
TAUS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]


def _load_turns():
    rows = []
    with open(TURNS) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    model = os.environ.get("EOU_MODEL", "")

    if args.check:
        try:
            import onnxruntime  # noqa: F401
            ort_ok = True
        except Exception as e:  # pragma: no cover
            ort_ok = f"{type(e).__name__}: {e}"
        info = {"check": True, "eou_model_env": model, "model_exists": bool(model) and os.path.isfile(model),
                "turns_file": str(TURNS), "turns_exists": TURNS.is_file(), "onnxruntime_ok": ort_ok,
                "stt_root_exists": STT_ROOT.is_dir()}
        json.dump(info, open(args.out, "w"), indent=2)
        print(json.dumps(info))
        return

    if not model or not os.path.isfile(model):
        json.dump({"error": f"EOU_MODEL not found: {model!r}"}, open(args.out, "w"), indent=2)
        print("EOU_MODEL not set or missing"); sys.exit(1)

    # Reuse the service's own detector so we test the shipped code path.
    sys.path.insert(0, str(STT_ROOT))
    os.environ["STT_EOU_ENABLED"] = "true"
    os.environ["STT_EOU_MODEL_PATH"] = model
    import importlib, dataclasses
    import src.config as config_mod
    importlib.reload(config_mod)
    import src.turn_detector as td
    importlib.reload(td)
    import soundfile as sf
    import numpy as np

    det = td.SemanticTurnDetector()
    turns = _load_turns()
    probs = []
    for t in turns:
        audio, sr = sf.read(t["wav"], dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        r = det.predict(np.asarray(audio, dtype=np.float32))
        probs.append((r.p_complete, bool(t["complete"])))

    sweep = []
    for tau in TAUS:
        fp = sum(1 for p, c in probs if p is not None and p >= tau and not c)
        n_neg = sum(1 for _, c in probs if not c)
        fn = sum(1 for p, c in probs if (p is None or p < tau) and c)
        n_pos = sum(1 for _, c in probs if c)
        sweep.append({"tau": tau,
                      "false_cut_rate": round(fp / n_neg, 4) if n_neg else None,
                      "missed_rate": round(fn / n_pos, 4) if n_pos else None})
    ok = [s for s in sweep if s["false_cut_rate"] is not None and s["false_cut_rate"] <= 0.05]
    summary = {"model": model, "n_turns": len(turns), "sweep": sweep,
               "recommended_tau": (min(s["tau"] for s in ok) if ok else None),
               "note": "recommended_tau = smallest tau with false-cut <= 5% (chapter 03 §12). "
                       "Add per-language turns to calibrate a per-language tau."}
    json.dump(summary, open(args.out, "w"), indent=2)
    print(json.dumps({"recommended_tau": summary["recommended_tau"]}))


if __name__ == "__main__":
    main()
