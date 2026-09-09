"""
Streams your live microphone to the STT server and prints partial/final transcripts
as you speak. This is the closest thing to "actually talking to the voice assistant."

Usage:
    python tests/test_client_mic.py
    Ctrl+C to stop.
"""
import asyncio
import json
import queue

import sounddevice as sd
import websockets

SAMPLE_RATE = 16000
CHUNK_MS = 40
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)
URL = "ws://localhost:8000/ws/stt/mic-session"

_audio_q: "queue.Queue[bytes]" = queue.Queue()


def _callback(indata, frames, time_info, status):
    if status:
        print(status)
    _audio_q.put(bytes(indata))


async def main():
    print("Connecting to", URL)
    # ping_interval=None: don't let THIS client's own keepalive kill the connection if the server
    # is momentarily busy running inference. The client will still auto-respond to any pings the
    # server sends (server-side timeout is already generous, see src/config.py WS_PING_TIMEOUT_S).
    async with websockets.connect(URL, ping_interval=None) as ws:
        async def receiver():
            async for msg in ws:
                event = json.loads(msg)
                tag = event["type"].upper()
                text = event.get("text", "")
                if text:
                    print(f"[{tag:16}] {text}")

        recv_task = asyncio.create_task(receiver())

        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK_SAMPLES,
            dtype="int16",
            channels=1,
            callback=_callback,
        ):
            print("🎙️  Listening... speak into your mic. Ctrl+C to stop.")
            try:
                while True:
                    chunk = await asyncio.get_event_loop().run_in_executor(None, _audio_q.get)
                    await ws.send(chunk)
            except KeyboardInterrupt:
                pass

        await ws.send(json.dumps({"action": "stop"}))
        await asyncio.sleep(1.0)
        recv_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())