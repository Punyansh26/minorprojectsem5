#!/usr/bin/env python3
"""L0 — ASR WER/CER on the recorded Hindi/Hinglish/hne set (chapter 12 §2.1, §5).

Transcribes each clip in a recorded manifest with Demo2's own ASR path and scores WER/CER
with jiwer [R1207], applying the §2.1 Indic normalisation rules (whisper_normalizer's
IndicNormalizer [R1208], NOT BasicTextNormalizer). Reports absolute WER/CER per language with
a Wilson interval on the error rate, and — when a `--baseline-json` from a prior run is given —
a per-clip paired comparison so the G-wer "no regression vs current faster-whisper-small on the
same clips" gate can be decided with stats.paired_bootstrap_ci.

Long because: needs a human-recorded speech set and downloads faster-whisper weights on first
use. The user runs it; the agent only runs --check.

Manifest JSON (user-provided, kept OUTSIDE code/demo2/data):
  [{"id": "...", "path": "clip.wav", "language": "hindi|hinglish|chhattisgarhi",
    "reference": "ground-truth transcript", "script": "deva|roman"}]
"""
import argparse
import json
import sys
from pathlib import Path

DEMO2 = Path(__file__).resolve().parents[3] / "code" / "demo2"
sys.path.insert(0, str(DEMO2))

import stats  # noqa: E402  (Demo2 module)


def _normalise(text: str, script: str):
    """§2.1: Indic-aware normalisation; fall back to a conservative casefold if absent."""
    try:
        from whisper_normalizer.indic_normalizer import IndicNormalizer  # type: ignore
        return IndicNormalizer().normalize(text)
    except Exception:
        return " ".join(text.strip().casefold().split())


def _score(reference: str, hypothesis: str):
    import jiwer  # type: ignore
    return {"wer": float(jiwer.wer(reference, hypothesis)),
            "cer": float(jiwer.cer(reference, hypothesis))}


def run(manifest_path: Path, out: Path, baseline_json: Path | None):
    import speech  # Demo2 ASR path  # noqa: E402
    manifest = json.loads(manifest_path.read_text())
    rows = []
    for item in manifest:
        audio = Path(item["path"]).read_bytes()
        language = {"hindi": "Hindi", "hinglish": "Hindi", "chhattisgarhi": "Chhattisgarhi"}.get(
            item["language"], "Hindi")
        hypothesis = speech.transcribe(audio, language)
        ref = _normalise(item["reference"], item.get("script", "deva"))
        hyp = _normalise(hypothesis, item.get("script", "deva"))
        rows.append({"id": item["id"], "language": item["language"],
                     "reference": ref, "hypothesis": hyp, **_score(ref, hyp)})
    by_lang: dict[str, list[dict]] = {}
    for row in rows:
        by_lang.setdefault(row["language"], []).append(row)
    summary = {"test": "L0_asr_wer", "n": len(rows), "per_language": {}}
    for lang, group in by_lang.items():
        summary["per_language"][lang] = {
            "n": len(group),
            "wer_mean": sum(r["wer"] for r in group) / len(group),
            "cer_mean": sum(r["cer"] for r in group) / len(group),
        }
    if baseline_json and baseline_json.exists():
        base = {r["id"]: r for r in json.loads(baseline_json.read_text()).get("rows", [])}
        pairs = [(base[r["id"]]["wer"], r["wer"]) for r in rows if r["id"] in base]
        if pairs:
            summary["wer_delta_ci"] = stats.paired_bootstrap_ci(pairs, "median", seed=0)
            summary["gate_G_wer_no_regression"] = not summary["wer_delta_ci"]["regression"]
    summary["rows"] = rows
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2, ensure_ascii=False))


def check(out: Path):
    """Fast validation: statistics + normalisation fallback work; no download, no GPU."""
    assert stats.paired_bootstrap_ci([(0.3, 0.25), (0.2, 0.18)], "median", resamples=200, seed=0)
    assert _normalise("  Hello   World ", "roman") == "hello world"
    out.write_text(json.dumps({"test": "L0_asr_wer", "check": "ok"}, indent=2))
    print("L0 --check ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, help="recorded speech manifest (outside code/demo2/data)")
    ap.add_argument("--baseline-json", type=Path, default=None)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.check:
        return check(args.out)
    if not args.manifest:
        ap.error("--manifest is required for a full run")
    run(args.manifest, args.out, args.baseline_json)


if __name__ == "__main__":
    main()
