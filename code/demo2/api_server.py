"""FastAPI product backend for IIIT-NR Voice Helpdesk (Demo 2).

Wraps the exact Demo 2 runtime (JobManager, Store, speech STT/TTS, verbalization v2,
agent_bridge LangGraph 6-node workflow, and verified KBB release) without altering
existing Streamlit or pytest behavior.
"""
from __future__ import annotations

from collections import OrderedDict
import asyncio
from contextlib import asynccontextmanager
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

import settings as cfg
import workflow
from agent_bridge import valid_profile_email
from health import runtime_health
from jobs import Job, TERMINAL, manager
import speech
from storage import DATABASES, connection, tables
import verbalization


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    rt = manager()
    try:
        yield
    finally:
        rt.close()


app = FastAPI(
    title="IIIT-NR Voice Helpdesk API",
    description="Grounded Voice-to-Voice Institutional RAG, Admissions & Policy Assistant (Demo 2)",
    version="2.1.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ERRORS: dict[str, str] = {
    "busy": "The helpdesk is at capacity. Try again shortly.",
    "conversation_busy": "This conversation already has a request running. Wait or cancel it.",
    "queue_timeout": "The queue wait expired. Retry when the helpdesk is less busy.",
    "deadline_exceeded": "This request reached its time limit. You can retry it safely.",
    "storage_busy": "Conversation storage is busy. Your request can be retried safely.",
    "invalid_audio": "This recording could not be decoded. Use a mono/stereo WAV or FLAC, 0.3–30 seconds, up to 12 MB.",
    "no_speech": "No clear speech was detected. Retry transcription, record again, or type your question.",
    "turn_failed": "The request could not be completed. Check Runtime status and retry.",
    "conversation_expired": "This conversation has expired. Start a new conversation.",
    "conversation_deleted": "This conversation was deleted. Start a new conversation.",
    "request_conflict": "This request identifier belongs to a different submission. Start a new question.",
}

LABELS: dict[str, str] = {
    "queued": "Waiting in the admission queue",
    "transcribing": "Transcribing your recording",
    "reasoning": "Starting your question",
    "routing": "Understanding your question & resolving context",
    "routing_model": "Rewriting query & classifying intent",
    "retrieval": "Searching verified 3-way hybrid knowledge base",
    "answer": "Preparing a grounded answer",
    "generation_model": "Drafting source-cited answer (Pass 1)",
    "review_model": "Cross-examining claims against verbatim sources (Pass 2)",
    "speech": "Preparing neural speech — reviewed text is ready",
    "saving_action": "Saving your local staff-review draft",
    "complete": "Complete",
    "failed": "Failed",
    "cancelled": "Cancelled",
}

# Bounded in-memory cache of raw uploaded audio per (session_id, turn_id) so failed
# transcriptions can be retried with one click just like in Streamlit session_state.
_RECORDING_BUFFER: OrderedDict[tuple[str, str], bytes] = OrderedDict()
_SESSION_TURNS: OrderedDict[str, list[str]] = OrderedDict()


def _remember_turn(session_id: str, turn_id: str) -> None:
    turns = _SESSION_TURNS.setdefault(session_id, [])
    if turn_id not in turns:
        turns.append(turn_id)
    _SESSION_TURNS[session_id] = turns[-cfg.MAX_HISTORY_TURNS :]
    _SESSION_TURNS.move_to_end(session_id)
    while len(_SESSION_TURNS) > 256:
        _SESSION_TURNS.popitem(last=False)


def _remember_recording(session_id: str, turn_id: str, data: bytes) -> None:
    key = (session_id, turn_id)
    _RECORDING_BUFFER[key] = data
    _RECORDING_BUFFER.move_to_end(key)
    while len(_RECORDING_BUFFER) > 32:
        _RECORDING_BUFFER.popitem(last=False)


def _active_release_root() -> tuple[Path | None, dict[str, Any]]:
    cfg.configure_agent()
    if str(cfg.AGENT_ROOT) not in sys.path:
        sys.path.insert(0, str(cfg.AGENT_ROOT))
    from assistant.config import settings as agent_settings
    from assistant.kb.common import active_release

    state_dir = Path(cfg.os.environ.get("KB_STATE_DIR", agent_settings.KB_STATE_DIR))
    active = active_release(state_dir)
    if not active:
        return None, {}
    return active[0], active[1]


def _serialize_turn(session_id: str, turn_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    turn = dict(raw)
    stage = turn.get("stage", "queued")
    turn["stage_label"] = LABELS.get(stage, "Processing your request")
    turn["is_terminal"] = stage in TERMINAL
    error_code = turn.get("error_code")
    turn["error_message"] = ERRORS.get(error_code, "The request could not be completed.") if error_code else None

    # Enrich sources with clean file basename
    sources = []
    for src in turn.get("sources") or []:
        s = dict(src)
        sf_path = s.get("source_file", "Source")
        s["source_name"] = Path(sf_path).name
        sources.append(s)
    turn["sources"] = sources

    # Replace raw audio bytes with lightweight metadata + streaming URL
    audio = turn.get("audio")
    if isinstance(audio, dict) and audio.get("data"):
        data_bytes = audio["data"]
        audio_hash = sha256(data_bytes[:4096] + str(len(data_bytes)).encode()).hexdigest()[:12]
        turn["audio"] = {
            "available": True,
            "mime": audio.get("mime", "audio/wav"),
            "extension": audio.get("extension", "wav"),
            "spoken_text": audio.get("spoken_text", ""),
            "provider": audio.get("provider", "Local VITS"),
            "size_bytes": len(data_bytes),
            "url": f"/api/turns/{session_id}/{turn_id}/audio?v={audio_hash}",
        }
    else:
        turn["audio"] = None

    turn["can_retry_transcription"] = (
        stage == "failed"
        and turn_id.startswith("recording:")
        and (session_id, turn_id) in _RECORDING_BUFFER
    )
    turn["can_retry_question"] = (
        stage == "failed"
        and bool(turn.get("question"))
        and not turn_id.startswith("recording:")
    )
    return turn


def _session_tickets(session_id: str) -> list[dict[str, Any]]:
    path = cfg.DATA_ROOT / "tickets.sqlite"
    if not path.exists():
        return []
    try:
        with connection(path) as conn:
            conn.row_factory = sqlite3.Row
            avail = tables(conn)
            if not {"tickets", "action_requests"}.issubset(avail):
                return []
            rows = conn.execute(
                """
                SELECT t.id, t.timestamp, t.student_id, t.student_category,
                       t.detected_category, t.question, t.recipient_email,
                       t.email_subject, t.email_body, t.status, a.turn_id
                FROM tickets t
                JOIN action_requests a ON a.action_id = t.id
                WHERE a.conversation_id = ? AND a.kind = 'ticket'
                ORDER BY t.id DESC
                """,
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


class ProfileModel(BaseModel):
    student_id: str = Field(default="", max_length=100)
    student_email: str = Field(default="", max_length=254)
    student_category: str = Field(default="general")


class NewSessionRequest(BaseModel):
    previous_session_id: str | None = None


class TextTurnRequest(BaseModel):
    session_id: str
    turn_id: str | None = None
    question: str = Field(..., min_length=1, max_length=cfg.MAX_TEXT_CHARS)
    profile: ProfileModel = Field(default_factory=ProfileModel)
    provider: str = Field(default="ollama")
    voice: str = Field(default="Female")
    speed: float = Field(default=1.0, ge=0.7, le=1.4)
    spoken: bool = Field(default=True)
    online_speech: bool = Field(default=False)
    input_language: str = Field(default="Hindi")


class RetryAudioRequest(BaseModel):
    voice: str = Field(default="Female")
    speed: float = Field(default=1.0, ge=0.7, le=1.4)
    online_speech: bool = Field(default=False)


class CancelRequest(BaseModel):
    turn_id: str | None = None


class VerbalizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=cfg.MAX_SPEECH_CHARS)
    language: str = Field(default="hindi")
    voice: str = Field(default="Female")


@app.get("/api/health")
def get_health() -> dict[str, Any]:
    rt = manager()
    health = runtime_health()
    health["job_stats"] = rt.stats()

    # Live queue & active turn counts
    with rt.condition:
        active_jobs = sum(j.stage not in TERMINAL for j in rt.jobs.values())
        queued_jobs = len(rt.queue)
        total_tracked = len(rt.jobs)
    health["queue"] = {
        "active_jobs": active_jobs,
        "queued_jobs": queued_jobs,
        "capacity": cfg.QUEUE_CAPACITY,
        "max_concurrent_reasoning": 1,
        "total_tracked_jobs": total_tracked,
        "queue_timeout_seconds": cfg.QUEUE_TIMEOUT_SECONDS,
        "turn_timeout_seconds": cfg.TURN_TIMEOUT_SECONDS,
        "retention_hours": cfg.RETENTION_SECONDS / 3600.0,
    }

    # SQLite stores inspection
    storage_info: dict[str, Any] = {}
    for name in DATABASES:
        path = cfg.DATA_ROOT / name
        if path.exists():
            try:
                with connection(path) as conn:
                    storage_info[name] = {
                        "bytes": path.stat().st_size,
                        "integrity": conn.execute("PRAGMA quick_check").fetchone()[0],
                        "rows": {
                            tbl: conn.execute(f'SELECT COUNT(*) FROM "{tbl}"').fetchone()[0]
                            for tbl in tables(conn)
                            if not tbl.startswith("sqlite_")
                        },
                    }
            except Exception as exc:
                storage_info[name] = {"error": type(exc).__name__}
    health["storage"] = storage_info

    # RAG Cache telemetry
    try:
        if str(cfg.AGENT_ROOT) not in sys.path:
            sys.path.insert(0, str(cfg.AGENT_ROOT))
        from assistant.nodes import _CACHE
        health["cache_telemetry"] = _CACHE.telemetry()
    except Exception:
        health["cache_telemetry"] = None

    health["config"] = {
        "input_languages": list(cfg.INPUT_LANGUAGES),
        "voices": list(cfg.VOICES),
        "edge_voices": cfg.EDGE_VOICES,
        "max_audio_seconds": cfg.MAX_AUDIO_SECONDS,
        "min_audio_seconds": cfg.MIN_AUDIO_SECONDS,
        "max_audio_bytes": cfg.MAX_AUDIO_BYTES,
        "max_text_chars": cfg.MAX_TEXT_CHARS,
        "max_history_turns": cfg.MAX_HISTORY_TURNS,
        "verbalization_version": verbalization.VERSION,
    }
    return health


@app.post("/api/session/new")
def create_session(req: NewSessionRequest | None = None) -> dict[str, Any]:
    rt = manager()
    if req and req.previous_session_id:
        rt.cancel(req.previous_session_id)
    session = workflow.new_session()
    _SESSION_TURNS[session["id"]] = []
    return {
        "session_id": session["id"],
        "retention_seconds": cfg.RETENTION_SECONDS,
        "max_history_turns": cfg.MAX_HISTORY_TURNS,
        "max_text_chars": cfg.MAX_TEXT_CHARS,
        "max_audio_seconds": cfg.MAX_AUDIO_SECONDS,
    }


def _durable_turns(session_id: str) -> dict[str, dict[str, Any]]:
    path = cfg.DATA_ROOT / "sessions.sqlite"
    if not path.exists():
        return {}
    try:
        with connection(path) as conn:
            conn.row_factory = sqlite3.Row
            if "requests" not in tables(conn):
                return {}
            rows = conn.execute(
                "SELECT turn_id, result FROM requests WHERE session_id = ? AND result IS NOT NULL ORDER BY rowid ASC",
                (session_id,),
            ).fetchall()
            out: dict[str, dict[str, Any]] = {}
            for r in rows:
                res = json.loads(r["result"])
                out[r["turn_id"]] = {
                    "id": r["turn_id"],
                    "question": res.get("question", ""),
                    "stage": "complete",
                    "error_code": None,
                    "timings": {},
                    **res,
                }
            return out
    except Exception:
        return {}


@app.get("/api/session/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    rt = manager()
    durable = _durable_turns(session_id)
    turn_ids = list(_SESSION_TURNS.get(session_id, []))
    for tid in durable:
        if tid not in turn_ids:
            turn_ids.append(tid)
    # Also discover any active/recent jobs in JobManager for this session_id
    with rt.condition:
        for (sid, tid) in rt.jobs:
            if sid == session_id and tid not in turn_ids:
                turn_ids.append(tid)
    turns = []
    for tid in turn_ids[-cfg.MAX_HISTORY_TURNS :]:
        snap = rt.snapshot(session_id, tid) or durable.get(tid)
        if snap:
            turns.append(_serialize_turn(session_id, tid, snap))
    return {
        "session_id": session_id,
        "turns": turns,
        "tickets": _session_tickets(session_id),
    }


@app.post("/api/session/{session_id}/cancel")
def cancel_session(session_id: str, req: CancelRequest | None = None) -> dict[str, Any]:
    rt = manager()
    turn_id = req.turn_id if req else None
    rt.cancel(session_id, turn_id)
    return {"cancelled": True, "session_id": session_id, "turn_id": turn_id}


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str) -> dict[str, Any]:
    rt = manager()
    deleted = rt.delete(session_id)
    if deleted:
        _SESSION_TURNS.pop(session_id, None)
        for key in [k for k in _RECORDING_BUFFER if k[0] == session_id]:
            _RECORDING_BUFFER.pop(key, None)
    return {
        "deleted": deleted,
        "status": "deleted" if deleted else "draining",
        "session_id": session_id,
    }


@app.post("/api/turns/text")
def submit_text_turn(req: TextTurnRequest) -> dict[str, Any]:
    if not valid_profile_email(req.profile.student_email):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_email", "message": "Enter a valid follow-up email or leave it blank."},
        )
    if req.provider not in {"ollama", "groq"}:
        raise HTTPException(status_code=400, detail={"code": "invalid_provider", "message": "Select ollama or groq."})
    if req.voice not in cfg.VOICES:
        raise HTTPException(status_code=400, detail={"code": "invalid_voice", "message": "Select Female or Male voice."})

    rt = manager()
    turn_id = req.turn_id or str(uuid4())
    profile_dict = req.profile.model_dump()
    try:
        rt.submit(
            req.session_id,
            turn_id,
            req.question.strip(),
            profile_dict,
            req.provider,
            req.voice,
            req.speed,
            req.spoken,
            req.online_speech,
            None,
            req.input_language,
        )
        _remember_turn(req.session_id, turn_id)
    except Exception as exc:
        code = str(exc)
        msg = ERRORS.get(code, "The request could not be submitted. Please retry.")
        status_code = 429 if code in {"busy", "conversation_busy"} else 400
        raise HTTPException(status_code=status_code, detail={"code": code, "message": msg}) from exc

    snap = rt.snapshot(req.session_id, turn_id) or {"id": turn_id, "question": req.question, "stage": "queued"}
    return _serialize_turn(req.session_id, turn_id, snap)


@app.post("/api/turns/audio")
async def submit_audio_turn(
    session_id: str = Form(...),
    turn_id: str | None = Form(default=None),
    provider: str = Form(default="ollama"),
    voice: str = Form(default="Female"),
    speed: float = Form(default=1.0),
    spoken: bool = Form(default=True),
    online_speech: bool = Form(default=False),
    input_language: str = Form(default="Hindi"),
    student_id: str = Form(default=""),
    student_email: str = Form(default=""),
    student_category: str = Form(default="general"),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    if not valid_profile_email(student_email):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_email", "message": "Enter a valid follow-up email or leave it blank."},
        )
    data = await file.read()
    if not data or len(data) > cfg.MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_audio", "message": ERRORS["invalid_audio"]},
        )

    recording_id = turn_id or ("recording:" + sha256(data).hexdigest())
    profile_dict = {
        "student_id": student_id.strip(),
        "student_email": student_email.strip(),
        "student_category": student_category.strip() or "general",
    }

    rt = manager()
    _remember_recording(session_id, recording_id, data)
    try:
        rt.submit(
            session_id,
            recording_id,
            "",
            profile_dict,
            provider,
            voice,
            speed,
            spoken,
            online_speech,
            data,
            input_language,
        )
        _remember_turn(session_id, recording_id)
    except Exception as exc:
        code = str(exc)
        msg = ERRORS.get(code, "The recording could not be submitted. Please retry.")
        status_code = 429 if code in {"busy", "conversation_busy"} else 400
        raise HTTPException(status_code=status_code, detail={"code": code, "message": msg}) from exc

    snap = rt.snapshot(session_id, recording_id) or {"id": recording_id, "question": "", "stage": "queued"}
    return _serialize_turn(session_id, recording_id, snap)


@app.get("/api/turns/{session_id}/{turn_id}")
def get_turn_snapshot(session_id: str, turn_id: str) -> dict[str, Any]:
    rt = manager()
    snap = rt.snapshot(session_id, turn_id)
    if not snap:
        durable = _durable_turns(session_id).get(turn_id)
        if not durable:
            raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Turn not found."})
        snap = durable
    return _serialize_turn(session_id, turn_id, snap)


@app.get("/api/turns/{session_id}/{turn_id}/stream")
async def stream_turn_output(session_id: str, turn_id: str):
    """Stream token/word-by-word inferencing output via Server-Sent Events (SSE)."""
    rt = manager()

    async def event_generator():
        last_stage = None
        for _ in range(300):
            snap = rt.snapshot(session_id, turn_id)
            if not snap:
                durable = _durable_turns(session_id).get(turn_id)
                if durable:
                    snap = durable
            if not snap:
                yield f"data: {json.dumps({'event': 'error', 'message': 'Turn not found'})}\n\n"
                return

            stage = snap.get("stage")
            if stage != last_stage:
                last_stage = stage
                yield f"data: {json.dumps({'event': 'stage', 'stage': stage, 'label': LABELS.get(stage, 'Processing your request')})}\n\n"

            answer = snap.get("answer_text")
            if answer:
                tokens = re.findall(r"\S+|\s+", answer)
                accumulated = ""
                for token in tokens:
                    accumulated += token
                    yield f"data: {json.dumps({'event': 'token', 'token': token, 'accumulated': accumulated})}\n\n"
                    if token.strip():
                        await asyncio.sleep(0.02)
                full_turn = _serialize_turn(session_id, turn_id, snap)
                yield f"data: {json.dumps({'event': 'complete', 'turn': full_turn})}\n\n"
                return

            if stage in TERMINAL:
                full_turn = _serialize_turn(session_id, turn_id, snap)
                yield f"data: {json.dumps({'event': 'complete', 'turn': full_turn})}\n\n"
                return

            await asyncio.sleep(0.2)

        yield f"data: {json.dumps({'event': 'timeout', 'message': 'Inference wait limit reached'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/turns/{session_id}/{turn_id}/audio")
def get_turn_audio(session_id: str, turn_id: str, download: bool = Query(default=False)) -> Response:
    rt = manager()
    snap = rt.snapshot(session_id, turn_id)
    if not snap or not snap.get("audio") or not snap["audio"].get("data"):
        raise HTTPException(status_code=404, detail={"code": "audio_not_found", "message": "Audio not available."})
    audio = snap["audio"]
    ext = audio.get("extension", "wav")
    mime = audio.get("mime", "audio/wav")
    disposition = "attachment" if download else "inline"
    filename = f"iiitnr-reply-{turn_id[:8]}.{ext}"
    return Response(
        content=audio["data"],
        media_type=mime,
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


@app.post("/api/turns/{session_id}/{turn_id}/retry-audio")
def retry_turn_audio(session_id: str, turn_id: str, req: RetryAudioRequest) -> dict[str, Any]:
    rt = manager()
    with rt.condition:
        if (session_id, turn_id) not in rt.jobs:
            durable = _durable_turns(session_id).get(turn_id)
            if durable:
                job = Job(
                    session_id=session_id,
                    turn_id=turn_id,
                    question=durable.get("question", ""),
                    profile={},
                    provider=durable.get("llm_provider", "ollama"),
                    voice=req.voice,
                    speed=req.speed,
                    spoken=True,
                    online_speech=req.online_speech,
                    stage="complete",
                    result=durable,
                )
                rt.jobs[(session_id, turn_id)] = job
    try:
        rt.retry_audio(session_id, turn_id, req.voice, req.speed, req.online_speech)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Turn not found."}) from exc
    except Exception as exc:
        code = str(exc)
        msg = ERRORS.get(code, "Could not retry audio while conversation is busy.")
        raise HTTPException(status_code=409, detail={"code": code, "message": msg}) from exc
    snap = rt.snapshot(session_id, turn_id)
    return _serialize_turn(session_id, turn_id, snap)


@app.post("/api/turns/{session_id}/{turn_id}/retry")
def retry_failed_turn(session_id: str, turn_id: str) -> dict[str, Any]:
    rt = manager()
    recording = _RECORDING_BUFFER.get((session_id, turn_id)) if turn_id.startswith("recording:") else None
    if turn_id.startswith("recording:") and recording is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "recording_missing", "message": "Please record or upload the audio again."},
        )
    try:
        rt.retry(session_id, turn_id, recording)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Turn not found."}) from exc
    except Exception as exc:
        code = str(exc)
        msg = ERRORS.get(code, "The request could not be retried.")
        raise HTTPException(status_code=400, detail={"code": code, "message": msg}) from exc
    snap = rt.snapshot(session_id, turn_id)
    return _serialize_turn(session_id, turn_id, snap)


@app.post("/api/verbalize")
def preview_verbalization(req: VerbalizeRequest) -> dict[str, Any]:
    lang = req.language.strip().lower()
    if lang not in {"hindi", "english", "hinglish"}:
        raise HTTPException(status_code=400, detail={"message": "Language must be hindi, english, or hinglish."})
    normalized = verbalization.normalize(req.text, lang)
    vits_ready = False
    vits_note = None
    if lang == "hindi":
        try:
            speech.prepare_speech(req.text, req.voice if req.voice in cfg.VOICES else "Female")
            vits_ready = True
        except Exception as exc:
            vits_note = str(exc)
    return {
        "original": req.text,
        "language": lang,
        "normalized": normalized,
        "version": verbalization.VERSION,
        "vits_ready": vits_ready,
        "vits_note": vits_note,
    }


@app.get("/api/kb/overview")
def get_kb_overview() -> dict[str, Any]:
    root, manifest = _active_release_root()
    if not root:
        raise HTTPException(status_code=503, detail={"message": "No active knowledge base release found."})
    validation = {}
    val_path = root / "validation.json"
    if val_path.is_file():
        validation = json.loads(val_path.read_text())
    sources_list = []
    src_path = root / "sources.json"
    if src_path.is_file():
        raw_sources = json.loads(src_path.read_text())
        sources_list = raw_sources.get("sources", []) if isinstance(raw_sources, dict) else raw_sources
    return {
        "release": manifest.get("release"),
        "created_at": manifest.get("created_at"),
        "engine": manifest.get("engine", "kbb"),
        "pipeline_version": manifest.get("pipeline_version"),
        "embedding_model": manifest.get("model"),
        "chunks": manifest.get("chunks"),
        "documents": manifest.get("documents"),
        "evidence_blocks": manifest.get("evidence_blocks"),
        "structured_records": manifest.get("structured_records"),
        "cutoff_records": manifest.get("cutoff_records"),
        "records_by_status": manifest.get("records_by_status", {}),
        "parents_by_status": manifest.get("parents_by_status", {}),
        "validation": validation.get("summary", {}),
        "sources": sources_list,
    }


@app.get("/api/kb/cutoffs")
def get_kb_cutoffs(
    year: int | None = Query(default=None),
    authority: str | None = Query(default=None),
    programme: str | None = Query(default=None),
    quota: str | None = Query(default=None),
    seat_category: str | None = Query(default=None),
    gender_pool: str | None = Query(default=None),
    round_num: str | None = Query(default=None, alias="round"),
    limit: int = Query(default=150, ge=1, le=650),
) -> dict[str, Any]:
    root, _ = _active_release_root()
    if not root or not (root / "facts.sqlite").is_file():
        raise HTTPException(status_code=503, detail={"message": "Cutoff database unavailable."})

    with connection(root / "facts.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        # Collect filter facets for the UI
        facets: dict[str, list[Any]] = {}
        for col in ("year", "authority", "programme", "quota", "seat_category", "gender_pool", "round"):
            vals = [
                r[0]
                for r in conn.execute(
                    f"SELECT DISTINCT {col} FROM records WHERE kind='cutoff' AND {col} IS NOT NULL ORDER BY {col}"
                ).fetchall()
            ]
            facets[col] = vals

        clauses = ["kind = 'cutoff'"]
        params: list[Any] = []
        for col, val in (
            ("year", year),
            ("authority", authority),
            ("programme", programme),
            ("quota", quota),
            ("seat_category", seat_category),
            ("gender_pool", gender_pool),
            ("round", round_num),
        ):
            if val is not None and str(val).strip() != "":
                clauses.append(f"{col} = ?")
                params.append(val)

        where_sql = " AND ".join(clauses)
        total = conn.execute(f"SELECT COUNT(*) FROM records WHERE {where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, year, authority, round, programme, quota, seat_category,
                   gender_pool, rank_basis, review_status, payload
            FROM records
            WHERE {where_sql}
            ORDER BY year DESC, authority ASC, programme ASC, CAST(round AS INTEGER) ASC, seat_category ASC
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()

        records = []
        for r in rows:
            payload = json.loads(r["payload"])
            records.append(
                {
                    "id": r["id"],
                    "year": r["year"],
                    "authority": r["authority"],
                    "round": r["round"],
                    "programme": r["programme"],
                    "quota": r["quota"],
                    "seat_category": r["seat_category"],
                    "gender_pool": r["gender_pool"],
                    "rank_basis": r["rank_basis"],
                    "opening_rank": payload.get("opening_rank"),
                    "closing_rank": payload.get("closing_rank"),
                    "source_file": payload.get("source_file"),
                    "page_number": payload.get("page_number"),
                    "quote": payload.get("quote"),
                }
            )

    return {"total": total, "facets": facets, "records": records}


@app.get("/api/kb/records")
def get_kb_structured_records(
    kind: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> dict[str, Any]:
    root, _ = _active_release_root()
    if not root or not (root / "facts.sqlite").is_file():
        raise HTTPException(status_code=503, detail={"message": "Structured records database unavailable."})

    with connection(root / "facts.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        clauses = ["kind != 'cutoff'"]
        params: list[Any] = []
        if kind and kind.strip():
            clauses.append("kind = ?")
            params.append(kind.strip())
        if search and search.strip():
            clauses.append("(label LIKE ? OR payload LIKE ?)")
            q = f"%{search.strip()}%"
            params.extend([q, q])

        where_sql = " AND ".join(clauses)
        rows = conn.execute(
            f"""
            SELECT id, kind, year, programme, quota, seat_category,
                   evidence_block_id, review_status, label, payload
            FROM records
            WHERE {where_sql}
            ORDER BY kind ASC, id ASC
            LIMIT 200
            """,
            params,
        ).fetchall()

        items = []
        for r in rows:
            p = json.loads(r["payload"])
            items.append(
                {
                    "id": r["id"],
                    "kind": r["kind"],
                    "label": r["label"] or p.get("name") or p.get("event") or p.get("metric") or r["kind"].title(),
                    "evidence_block_id": r["evidence_block_id"],
                    "review_status": r["review_status"],
                    "payload": p,
                }
            )

    return {"total": len(items), "records": items}


@app.get("/api/kb/document")
def get_kb_document(path: str = Query(..., description="Relative source_file path inside knowledge_base")) -> FileResponse:
    kb_root = (cfg.AGENT_ROOT / "knowledge_base").resolve()
    target = (kb_root / path).resolve()
    if not str(target).startswith(str(kb_root)) or not target.is_file():
        raise HTTPException(status_code=404, detail={"message": "Source document file not found locally."})
    media_type = "application/pdf" if target.suffix.lower() == ".pdf" else "text/plain; charset=utf-8"
    return FileResponse(path=target, media_type=media_type, filename=target.name)
