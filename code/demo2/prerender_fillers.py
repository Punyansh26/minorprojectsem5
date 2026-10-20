"""Build-time pre-render of neutral acknowledgement fillers into the audio cache (Task 07 A4).

Run once per voice/speed set after a KB release or TTS model change so that neutral fillers
("एक पल…") play with ~0 ms synthesis at request time. Writes rendered audio into the
release-bound pre-synthesised cache at ``DATA_ROOT/tts_cache.sqlite``.

Usage (in the `minor` env):
    python prerender_fillers.py --voices Female Male --speeds 1.0
"""
import argparse
import json

import settings as cfg
import fillers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voices", nargs="+", default=list(cfg.VOICES))
    parser.add_argument("--speeds", nargs="+", type=float, default=[1.0])
    parser.add_argument("--languages", nargs="+", default=["hindi"])
    args = parser.parse_args()
    cfg.configure_agent()
    reports = []
    for voice in args.voices:
        if voice not in cfg.VOICES:
            raise SystemExit(f"Unknown voice: {voice}")
        reports.append(fillers.prerender(voice, tuple(args.speeds), tuple(args.languages)))
    print(json.dumps({"reports": reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
