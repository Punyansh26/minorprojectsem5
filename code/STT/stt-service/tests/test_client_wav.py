"""
Streams a WAV file to the STT server in real-time-paced chunks, exactly like a live caller
would, and prints every partial/final event as it arrives.

Usage:
    python tests/test_client_wav.py path/to/audio.wav
    python tests/test_client_wav.py path/to/audio.wav --url ws://localhost:8000/ws/stt/test-1

The WAV must be mono 16kHz 16-bit PCM. If yours isn't, resample first, e.g.:
    ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 audio.wav
"""
import argparse
import asyncio
import json
import time

import soundfile as sf
import websockets

CHUNK_MS = 40  # send audio in 40ms frames, like a real mic stream would


async def stream_file(path: str, url: str):
    data, sr = sf.read(path, dtype="int16")
    if sr != 16000:
        raise SystemExit(f"Expected 16kHz audio, got {sr}Hz. Resample first (see file docstring).")
    if data.ndim > 1:
        data = data[:, 0]  # take first channel if stereo

    chunk_samples = int(sr * CHUNK_MS / 1000)
    raw = data.tobytes()
    bytes_per_chunk = chunk_samples * 2  # 16-bit

    async with websockets.connect(url, ping_interval=None) as ws:
        async def receiver():
            async for msg in ws:
                event = json.loads(msg)
                tag = event["type"].upper()
                text = event.get("text", "")
                print(f"[{tag:16}] {text}")

        recv_task = asyncio.create_task(receiver())

        for i in range(0, len(raw), bytes_per_chunk):
            await ws.send(raw[i:i + bytes_per_chunk])
            await asyncio.sleep(CHUNK_MS / 1000)  # pace it like real-time audio

        await ws.send(json.dumps({"action": "stop"}))
        await asyncio.sleep(1.0)  # give the final transcript time to arrive
        recv_task.cancel()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("wav_path")
    parser.add_argument("--url", default="ws://localhost:8000/ws/stt/test-session")
    args = parser.parse_args()

    asyncio.run(stream_file(args.wav_path, args.url))