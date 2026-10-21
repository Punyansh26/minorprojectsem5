"""
Voice loop: mic -> stt-service (WebSocket) -> institute-assistant graph -> (TTS placeholder).

This is a thin orchestrator. It contains NO speech recognition or LLM logic of its own —
it just wires two already-independently-working systems together. That's the whole point:
stt-service and institute-assistant were each built and tested standalone; this script is
the only place that knows about both.

TTS integration point is marked explicitly below — once your teammate's model is ready,
that's a one-line addition, not a restructuring of anything here.

Prerequisites before running this:
  1. stt-service must already be running (`python run.py` in that project).
  2. institute-assistant's knowledge base index must already be built.
  3. This project's dependencies installed (see README.md).
"""
import asyncio
import json
import os
import queue

import sounddevice as sd
import websockets
from dotenv import load_dotenv

# Load THIS project's .env first, then institute-assistant's — both need to end up in the
# process environment before institute-assistant's own config.py runs (it calls load_dotenv()
# too, but with no path, so it wouldn't find institute-assistant's .env from THIS project's
# working directory). load_dotenv() never overwrites a variable that's already set, so loading
# order here is what makes both configs available correctly.
load_dotenv(".env")
load_dotenv(os.getenv("INSTITUTE_ASSISTANT_ENV_PATH", "../institute-assistant/.env"))

from langchain_core.messages import HumanMessage  # noqa: E402
from assistant.graph import build_graph  # noqa: E402  (works because of `pip install -e`, no path hack)

SAMPLE_RATE = 16000
CHUNK_MS = 40
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)

_audio_q: "queue.Queue[bytes]" = queue.Queue()


def _mic_callback(indata, frames, time_info, status):
    if status:
        print(status)
    _audio_q.put(bytes(indata))


async def _send_mic_audio(ws):
    loop = asyncio.get_event_loop()
    while True:
        chunk = await loop.run_in_executor(None, _audio_q.get)
        await ws.send(chunk)


async def main():
    print("Voice Orchestrator — mic -> STT -> Institute Assistant\n")
    student_id = input("Student ID: ").strip() or "test-student"
    student_email = input("Student email: ").strip()
    category = input("Admission category [general/CG]: ").strip() or "general"

    graph = build_graph()
    graph_config = {"configurable": {"thread_id": student_id}}

    stt_base_url = os.getenv("STT_WS_BASE_URL", "ws://localhost:8000/ws/stt")
    stt_ws_url = f"{stt_base_url}/{student_id}"
    print(f"Connecting to STT service at {stt_ws_url} ...")

    async with websockets.connect(stt_ws_url, ping_interval=None) as ws:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE, blocksize=CHUNK_SAMPLES, dtype="int16", channels=1,
            callback=_mic_callback,
        ):
            print("🎙️  Listening... speak a question. Ctrl+C to stop.\n")
            send_task = asyncio.create_task(_send_mic_audio(ws))

            try:
                async for message in ws:
                    event = json.loads(message)

                    if event["type"] == "partial":
                        print(f"  ...{event.get('text', '')}", end="\r")

                    elif event["type"] == "final":
                        question = event.get("text", "").strip()
                        if not question:
                            continue
                        print(f"\n[STT FINAL] {question}")

                        result = graph.invoke(
                            {
                                "messages": [HumanMessage(content=question)],
                                "student_id": student_id,
                                "student_email": student_email,
                                "student_category": category,
                            },
                            config=graph_config,
                        )
                        reply = result["messages"][-1].content
                        print(f"[ASSISTANT] {reply}\n")

                        # --- TTS PLUGS IN RIGHT HERE, once your teammate's model is ready ---
                        # from TTS.utils.synthesizer import Synthesizer
                        # tts.tts(text=reply) -> play the resulting audio
                        # Nothing else in this file needs to change for that addition.

            except KeyboardInterrupt:
                pass
            finally:
                send_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())