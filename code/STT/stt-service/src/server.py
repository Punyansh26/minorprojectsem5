"""
WebSocket server exposing the STT pipeline.

Client protocol (what your LangChain/LLM teammate, or any client, needs to know):
  1. Connect to  ws://<host>:<port>/ws/stt/{session_id}
  2. Stream binary WebSocket frames of raw 16-bit PCM, mono, 16kHz audio (no WAV header, just samples)
     Any chunk size is fine (recommended: 20-100ms worth per frame, i.e. 640-3200 bytes)
  3. Receive JSON text frames back, each matching schemas.STTEvent, e.g.:
       {"type": "partial", "session_id": "...", "text": "book an appointment for", ...}
       {"type": "final",   "session_id": "...", "text": "book an appointment for tomorrow at 5pm", ...}
  4. Optionally send a JSON control frame {"action": "stop"} to force-flush and end the session cleanly.
  5. On disconnect, the server auto-flushes any buffered speech as a final FIRST, then closes.

The model is loaded ONCE at process startup (see lifespan below) and shared by every session —
loading it per-connection would make concurrent users painfully slow to first response.
"""
import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from src.asr import get_engine
from src.config import settings
from src.schemas import ClientControlMessage, EventType, STTEvent
from src.session import SttSession

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("stt-server")

# Bounds how many calls this process handles at once. When full, new connections are rejected
# immediately (see SESSION_REJECTED below) instead of the server getting slower for every call
# already in progress — for a clinic line, a clear "try again" beats a silently laggy assistant.
_capacity = asyncio.Semaphore(settings.MAX_CONCURRENT_SESSIONS)
_active_sessions = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Loading ASR model '{settings.ASR_MODEL_SIZE}' on {settings.ASR_DEVICE} ({settings.ASR_COMPUTE_TYPE})...")
    get_engine()  # warm the singleton so the first caller doesn't eat the load latency
    if not settings.API_KEY:
        logger.warning("STT_API_KEY is not set — server will accept unauthenticated connections. "
                        "Fine for localhost dev, NOT fine once this is reachable from the internet.")
    logger.info(f"Model loaded. Capacity: {settings.MAX_CONCURRENT_SESSIONS} concurrent calls. Server ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(title="Local STT Service", lifespan=lifespan)


@app.get("/health")
async def health():
    """
    Use this for your load balancer / uptime monitor. `at_capacity: true` is a real signal —
    it means the next caller will be rejected, which is your cue to scale out (see README).
    """
    return JSONResponse({
        "status": "ok",
        "model": settings.ASR_MODEL_SIZE,
        "device": settings.ASR_DEVICE,
        "active_sessions": _active_sessions,
        "max_sessions": settings.MAX_CONCURRENT_SESSIONS,
        "at_capacity": _active_sessions >= settings.MAX_CONCURRENT_SESSIONS,
    })


@app.websocket("/ws/stt/{session_id}")
async def stt_websocket(websocket: WebSocket, session_id: str = None):
    global _active_sessions

    # --- Auth: reject before accept() if a key is configured and missing/wrong ---
    if settings.API_KEY and websocket.query_params.get("api_key") != settings.API_KEY:
        await websocket.close(code=4401)  # custom close code in the 4000-4999 (app-defined) range
        logger.warning(f"[{session_id}] rejected: bad or missing api_key")
        return

    # --- Capacity: reject immediately rather than degrading everyone already on a call ---
    if _capacity.locked():
        await websocket.accept()
        await websocket.send_text(STTEvent(
            type=EventType.SESSION_REJECTED,
            session_id=session_id or "unknown",
            error_message="Server at capacity. Please try again shortly.",
        ).model_dump_json())
        await websocket.close(code=4503)
        logger.warning(f"[{session_id}] rejected: at capacity ({_active_sessions}/{settings.MAX_CONCURRENT_SESSIONS})")
        return

    await _capacity.acquire()
    _active_sessions += 1
    await websocket.accept()

    session_id = session_id or str(uuid.uuid4())
    session = SttSession(session_id)
    call_start = time.monotonic()
    logger.info(f"[{session_id}] connected ({_active_sessions}/{settings.MAX_CONCURRENT_SESSIONS} active)")

    try:
        await websocket.send_text((await session.start()).model_dump_json())

        while True:
            # Idle timeout: a client that never sends audio (dropped connection, stuck client,
            # or someone just probing the endpoint) shouldn't hold a capacity slot forever.
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=settings.IDLE_TIMEOUT_S)
            except asyncio.TimeoutError:
                logger.warning(f"[{session_id}] idle timeout after {settings.IDLE_TIMEOUT_S}s, closing")
                break

            if message.get("type") == "websocket.disconnect":
                break

            if "bytes" in message and message["bytes"] is not None:
                events = await session.process_chunk(message["bytes"])
                for event in events:
                    await websocket.send_text(event.model_dump_json())

            elif "text" in message and message["text"] is not None:
                try:
                    ctrl = ClientControlMessage.model_validate(json.loads(message["text"]))
                except Exception:
                    continue
                if ctrl.action == "stop":
                    final_event = await session.flush()
                    if final_event:
                        await websocket.send_text(final_event.model_dump_json())
                    break

    except WebSocketDisconnect:
        logger.info(f"[{session_id}] disconnected")
    finally:
        # Always try to flush trailing speech so a hung-up call doesn't silently drop the last utterance.
        try:
            final_event = await session.flush()
            if final_event:
                await websocket.send_text(final_event.model_dump_json())
        except Exception:
            pass
        _active_sessions -= 1
        _capacity.release()
        call_duration_s = time.monotonic() - call_start
        logger.info(f"[{session_id}] session closed — duration={call_duration_s:.1f}s, "
                     f"utterances={session._utterance_counter}, ({_active_sessions}/{settings.MAX_CONCURRENT_SESSIONS} active)")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.server:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        ws_ping_interval=settings.WS_PING_INTERVAL_S,
        ws_ping_timeout=settings.WS_PING_TIMEOUT_S,
    )
