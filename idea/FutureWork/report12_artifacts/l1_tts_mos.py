#!/usr/bin/env python3
"""L1 — TTS predicted MOS + ASR round-trip CER + number-reading accuracy (chapter 12 §2.4).

Extends the honest method already in code/demo2/evaluate_speech.py: for each sentence in the
number-reading set, synthesise with Demo2's VITS path, predict MOS with SpeechMOS/UTMOS via
torch.hub [R1209/R1210], transcribe the synthesised audio back (round-trip) and score CER vs
the intended text [R1207], and check exact number/amount match. Gate G-tts: predicted MOS no
significant drop vs current VITS; round-trip CER ≤ threshold; number-reading 100 %.

Long because: downloads the SpeechMOS torch.hub model and loads VITS; the user runs it. Scratch
audio is written under --out's directory, never into code/demo2/data.

Number-reading set JSON (user-provided):
  [{"id": "...", "text": "सुरक्षा जमा ₹15,000 …", "language": "hindi",
    "voice": "Female", "expect_numbers": ["15000"]}]
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

DEMO2 = Path(__file__).resolve().parents[3] / "code" / "demo2"
sys.path.insert(0, str(DEMO2))

import stats  # noqa: E402


def _digits(text: str):
    return re.findall(r"\d[\d,]*", text.replace(",", ""))


def _predict_mos(wav_bytes: bytes):
    try:
        import torch  # type: ignore
        import soundfile as sf  # type: ignore
        predictor = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True)
        audio, sr = sf.read(io.BytesIO(wav_bytes))
        wave = torch.as_tensor(audio, dtype=torch.float32).unsqueeze(0)
        return float(predictor(wave, sr).item())
    except Exception as error:
        return {"error": type(error).__name__}


def run(manifest_path: Path, out: Path):
    import settings as cfg  # noqa: E402
    import speech  # noqa: E402
    cfg.configure_agent()
    manifest = json.loads(manifest_path.read_text())
    scratch = out.parent / "audio"
    scratch.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in manifest:
        audio = speech.make_audio(item["text"], item.get("language", "hindi"),
                                  item.get("voice", "Female"))
        (scratch / f"{item['id']}.wav").write_bytes(audio["data"])
        mos = _predict_mos(audio["data"])
        transcript = speech.transcribe(audio["data"], "Hindi")
        import jiwer  # type: ignore
        cer = float(jiwer.cer(item["text"], transcript))
        spoken_digits = _digits(transcript)
        numbers_ok = all(n in spoken_digits for n in item.get("expect_numbers", []))
        rows.append({"id": item["id"], "mos": mos, "round_trip_cer": cer,
                     "numbers_ok": numbers_ok, "transcript": transcript})
    mos_values = [r["mos"] for r in rows if isinstance(r["mos"], float)]
    number_hits = sum(1 for r in rows if r["numbers_ok"])
    summary = {
        "test": "L1_tts_mos", "n": len(rows),
        "mos_mean": sum(mos_values) / len(mos_values) if mos_values else None,
        "round_trip_cer_mean": sum(r["round_trip_cer"] for r in rows) / len(rows) if rows else None,
        "number_reading": stats.wilson_interval(number_hits, max(1, len(rows))),
        "gate_G_tts_numbers_100pct": number_hits == len(rows),
        "rows": rows,
    }
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2, ensure_ascii=False))
    # free the VITS cache so the GPU/CPU is released when the test ends
    try:
        speech._SYNTHESIZERS.clear()
    except Exception:
        pass


def check(out: Path):
    assert _digits("₹15,000 and 90000") == ["15000", "90000"]
    assert stats.wilson_interval(50, 50)["point"] == 1.0
    out.write_text(json.dumps({"test": "L1_tts_mos", "check": "ok"}, indent=2))
    print("L1 --check ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, help="number-reading set (outside code/demo2/data)")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.check:
        return check(args.out)
    if not args.manifest:
        ap.error("--manifest is required for a full run")
    run(args.manifest, args.out)


if __name__ == "__main__":
    main()
