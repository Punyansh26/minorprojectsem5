"""Keep completed turns and audio retries stable across Streamlit reruns."""
from time import monotonic
from uuid import uuid4

import agent_bridge
import speech
from settings import MAX_HISTORY_TURNS


def new_session() -> dict:
    """Give each browser conversation an independent agent checkpoint identity."""
    return {"id": str(uuid4()), "turns": [], "consumed_audio": set(), "autoplay_id": None}


def speak_turn(turn: dict, voice: str, speed: float):
    """Retry only synthesis, so ticket creation or other agent actions cannot replay."""
    turn["audio"] = None
    turn["audio_error"] = None
    started = monotonic()
    try:
        turn["audio"] = speech.make_audio(turn["answer_text"], turn["language"], voice, speed,
                                          provider=turn.get("llm_provider"))
    except Exception as error:
        turn["audio_error"] = (
            "Speech is unavailable. Check the voice model or internet connection, then retry audio. "
            f"({type(error).__name__})")
    turn["speech_seconds"] = monotonic() - started


def run_turn(session: dict, question: str, profile: dict, voice: str, speed: float,
             spoken: bool = True, turn_id: str | None = None, *, provider: str | None = None) -> dict:
    """Save the answer before synthesis and never replay an already submitted turn."""
    turn_id = turn_id or str(uuid4())
    for existing in session["turns"]:
        if existing["id"] == turn_id:
            return existing
    turn = {"id": turn_id, "question": question, "answer_text": "", "sources": [],
            "audio": None, "audio_error": None, "error": None, "llm_provider": provider}
    session["turns"].append(turn)
    session["turns"] = session["turns"][-MAX_HISTORY_TURNS:]
    started = monotonic()
    try:
        turn.update(agent_bridge.ask(question, session["id"], profile, provider=provider))
        turn["llm_provider"] = (turn.get("rag_metrics") or {}).get("provider") or provider
    except Exception as error:
        turn["error"] = f"The question could not be completed. Please try again. ({type(error).__name__})"
    turn["agent_seconds"] = monotonic() - started
    if spoken and turn["answer_text"]:
        speak_turn(turn, voice, speed)
    if turn["audio"]:
        session["autoplay_id"] = turn_id
    return turn


def consume_recording(session: dict, recording_id: str, data: bytes, language: str) -> str | None:
    """Consume before processing so widget reruns cannot submit a recording twice."""
    if recording_id in session["consumed_audio"]:
        return None
    session["consumed_audio"].add(recording_id)
    return speech.transcribe(data, language)
