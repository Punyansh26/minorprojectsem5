"""
Bridges real phone calls into this STT service.

Why this file exists: everything else in this codebase assumes 16kHz, 16-bit PCM audio —
that's what a browser mic or a WebRTC client sends. A real phone call does NOT send that.
Twilio Media Streams (the standard way to get PSTN phone audio into a websocket) sends
8kHz, 8-bit mu-law (G.711) encoded audio, base64-wrapped inside a JSON envelope. If you
feed that directly into src/session.py, you'll get garbage transcripts, not an error —
which is a nasty bug to chase, so isolate the conversion here.

This module does NOT connect to Twilio for you — it's a converter you call from a thin
adapter endpoint. A minimal Twilio-facing WebSocket endpoint looks like:

    @app.websocket("/twilio/stream")
    async def twilio_stream(websocket: WebSocket):
        await websocket.accept()
        session = SttSession(session_id=str(uuid.uuid4()))
        async for raw_message in websocket.iter_text():
            msg = json.loads(raw_message)
            if msg["event"] == "media":
                mulaw_bytes = base64.b64decode(msg["media"]["payload"])
                pcm16_16k = mulaw_8k_to_pcm16_16k(mulaw_bytes)
                events = await session.process_chunk(pcm16_16k)
                for event in events:
                    ... forward event["text"] to your LLM teammate, then to Twilio TTS/<Say>/<Play> back

Set up a Twilio phone number with a <Connect><Stream> TwiML instruction pointing at this
endpoint's public URL (needs to be reachable from the internet — use ngrok while developing,
a real domain + TLS in production, since Twilio requires wss://).
"""
try:
    import audioop  # stdlib on Python < 3.13
except ImportError:
    import audioop_lts as audioop  # pip install audioop-lts on Python >= 3.13

from src.config import settings

TWILIO_SAMPLE_RATE = 8000  # Hz — fixed by the telephony network (G.711), not configurable


def mulaw_8k_to_pcm16_16k(mulaw_bytes: bytes) -> bytes:
    """
    Convert one chunk of 8kHz mu-law (as sent by Twilio Media Streams) into 16kHz 16-bit PCM
    (as expected by src/session.py / the VAD / faster-whisper).

    Two steps: mu-law -> linear PCM (audioop.ulaw2lin), then upsample 8kHz -> 16kHz (audioop.ratecv).
    `state` for ratecv is intentionally not persisted across calls here for simplicity — for
    production-grade audio quality across chunk boundaries, keep the returned state and pass it
    into the next call (see audioop.ratecv docs); a small click at chunk boundaries is usually
    inaudible for speech recognition purposes even without this, but worth knowing about.
    """
    pcm16_8k = audioop.ulaw2lin(mulaw_bytes, 2)  # 2 = output sample width in bytes (16-bit)
    pcm16_16k, _state = audioop.ratecv(
        pcm16_8k, 2, 1, TWILIO_SAMPLE_RATE, settings.SAMPLE_RATE, None
    )
    return pcm16_16k
