#!/usr/bin/env python3
"""L0 — streaming ASR residual latency + LocalAgreement-2 correction rate.

Streams each WAV in L0_streaming/wavs/ to a RUNNING stt-service over the
WebSocket, real-time-paced, with STT_PREFIX_COMMIT_ENABLED=true. For each
utterance it records:
  * residual latency: wall time from the last audio chunk sent to the FINAL
    event (this is the "last-chunk" pass that streaming should shrink vs a
    whole-clip transcribe);
  * correction rate: fraction of committed tokens (committed_text) that the
    FINAL transcript did NOT keep as a prefix (LocalAgreement-2 should keep
    this small).

Start the service first, e.g.:
    cd code/STT/stt-service
    STT_PREFIX_COMMIT_ENABLED=true STT_LANGUAGE=en python run.py
Then:
    python l0_streaming_residual.py --out L0_streaming/summary.json

--check validates args + input folder + websockets import; it does NOT connect,
stream, or need a server.
"""
import argparse, asyncio, glob, json, os, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WAV_DIR = HERE / "L0_streaming" / "wavs"
URL = os.environ.get("STT_URL", "ws://127.0.0.1:8000/ws/stt/l0")
CHUNK_MS = 40


def _lcp_tokens(a, b):
    out = []
    for x, y in zip(a, b):
        if x != y:
            break
        out.append(x)
    return out


async def _stream_one(path, url):
    import soundfile as sf
    import websockets
    data, sr = sf.read(path, dtype="int16")
    if sr != 16000:
        return {"wav": os.path.basename(path), "error": f"expected 16k, got {sr}"}
    if data.ndim > 1:
        data = data[:, 0]
    raw = data.tobytes()
    bpc = int(sr * CHUNK_MS / 1000) * 2

    committed = ""
    final_text = None
    last_send = None
    final_ts = None

    async with websockets.connect(url, ping_interval=None) as ws:
        async def receiver():
            nonlocal committed, final_text, final_ts
            async for msg in ws:
                ev = json.loads(msg)
                if ev["type"] == "partial" and ev.get("committed_text"):
                    committed = ev["committed_text"]
                elif ev["type"] == "final":
                    final_text = ev.get("text", "")
                    final_ts = time.monotonic()
                    break
        rt = asyncio.create_task(receiver())
        for i in range(0, len(raw), bpc):
            await ws.send(raw[i:i + bpc])
            last_send = time.monotonic()
            await asyncio.sleep(CHUNK_MS / 1000)
        await ws.send(json.dumps({"action": "stop"}))
        try:
            await asyncio.wait_for(rt, timeout=30)
        except asyncio.TimeoutError:
            rt.cancel()

    residual_ms = (final_ts - last_send) * 1000 if (final_ts and last_send) else None
    ct = committed.split()
    ft = (final_text or "").split()
    kept = len(_lcp_tokens(ct, ft))
    corr = (len(ct) - kept) / len(ct) if ct else 0.0
    return {"wav": os.path.basename(path), "residual_ms": round(residual_ms, 1) if residual_ms else None,
            "committed_tokens": len(ct), "corrected_tokens": len(ct) - kept,
            "correction_rate": round(corr, 4), "final_text_len": len(ft)}


async def _run(out):
    wavs = sorted(glob.glob(str(WAV_DIR / "*.wav")))
    rows = []
    for w in wavs:
        rows.append(await _stream_one(w, URL))
    res = [r["residual_ms"] for r in rows if r.get("residual_ms")]
    corr = [r["correction_rate"] for r in rows if "correction_rate" in r]
    res.sort()
    summary = {"url": URL, "n_wavs": len(wavs), "rows": rows,
               "median_residual_ms": res[len(res) // 2] if res else None,
               "mean_correction_rate": round(sum(corr) / len(corr), 4) if corr else None,
               "note": "residual = last-chunk-send -> FINAL wall time; compare to a whole-clip "
                       "transcribe of the same WAV. LocalAgreement-2 target: low correction rate."}
    json.dump(summary, open(out, "w"), indent=2)
    print(json.dumps({"median_residual_ms": summary["median_residual_ms"],
                      "mean_correction_rate": summary["mean_correction_rate"]}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        try:
            import websockets, soundfile  # noqa: F401
            imports_ok = True
        except Exception as e:  # pragma: no cover
            imports_ok = f"{type(e).__name__}: {e}"
        info = {"check": True, "wav_dir": str(WAV_DIR), "wav_dir_exists": WAV_DIR.is_dir(),
                "n_wavs": len(glob.glob(str(WAV_DIR / "*.wav"))), "imports_ok": imports_ok}
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        json.dump(info, open(args.out, "w"), indent=2)
        print(json.dumps(info))
        return
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    asyncio.run(_run(args.out))


if __name__ == "__main__":
    main()
