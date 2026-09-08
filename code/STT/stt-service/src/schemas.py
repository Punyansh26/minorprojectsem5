"""
This file IS the integration contract with your teammate's LangChain LLM service.
Every event the STT server ever sends over the WebSocket is one of these shapes.
Show your LLM teammate this file first — it's the entire interface they need to code against.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    SESSION_STARTED = "session_started"
    SPEECH_STARTED = "speech_started"     # VAD detected the caller started talking (barge-in signal)
    PARTIAL = "partial"                    # live, unstable transcript — for UI captions only, don't act on it
    FINAL = "final"                        # confirmed end-of-utterance transcript — THIS is what the LLM should consume
    ERROR = "error"
    SESSION_ENDED = "session_ended"
    SESSION_REJECTED = "session_rejected"  # server was at capacity or auth failed; connection will close


class STTEvent(BaseModel):
    type: EventType
    session_id: str
    text: str = ""
    # Timestamps in ms relative to the start of the session/connection
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    # Rough confidence proxy derived from avg_logprob (0-1). Not calibrated probability, but useful for
    # thresholding "should the LLM ask the user to repeat themselves?"
    confidence: Optional[float] = None
    # Monotonically increasing per finalized utterance, so a downstream consumer can dedupe/order.
    utterance_id: Optional[int] = None
    error_message: Optional[str] = None
    # True only on SPEECH_STARTED. Tells the LLM/TTS side: "the caller started talking again —
    # if you're mid-playback of a response, stop it now." This is the barge-in signal — without it,
    # your assistant talks over the patient and the call feels broken.
    interrupt_previous_response: bool = False

    class Config:
        use_enum_values = True


class ClientControlMessage(BaseModel):
    """
    Optional JSON control messages a client can send (as text frames) interleaved with
    binary audio frames. Everything is optional — the server works with sane defaults
    if the client only ever streams raw audio.
    """
    action: str = Field(..., description="'start' | 'stop' | 'flush'")
    language: Optional[str] = None
