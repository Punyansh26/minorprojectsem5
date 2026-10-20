"""Verify that api_server exposes identical Demo 2 semantics over HTTP."""
import io
import json
from pathlib import Path
import sys
import time
from unittest.mock import Mock

from fastapi.testclient import TestClient
import numpy as np
import soundfile as sf

import settings
settings.configure_agent()
if str(settings.AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(settings.AGENT_ROOT))

import agent_bridge
import api_server
import health
import jobs
import speech
from storage import Store


def wav(seconds=1.0, rate=16000):
    samples = 0.1 * np.sin(2 * np.pi * 220 * np.arange(int(seconds * rate)) / rate)
    output = io.BytesIO()
    sf.write(output, samples.astype(np.float32), rate, format="WAV")
    return output.getvalue()


def test_api_server_turn_lifecycle_audio_retry_and_delete(monkeypatch, tmp_path: Path):
    runtime = jobs.JobManager(Store(tmp_path))
    monkeypatch.setattr(jobs, "manager", lambda: runtime)
    monkeypatch.setattr(api_server, "manager", lambda: runtime)
    monkeypatch.setattr(
        health,
        "runtime_health",
        lambda: dict(release="20261014T005813186766Z", release_ok=True, jev_mode="off", jev_artifact="test", jev_activation="not_activated"),
    )
    ask = Mock(
        return_value={
            "answer_text": "Hostel fee is ₹ 24,000 per semester.",
            "language": "english",
            "sources": [{"source_file": "hostel/rules.pdf", "page_number": 2, "quote": "Hostel fee ₹ 24,000"}],
            "response_status": "answered",
            "ticket_id": None,
            "rag_metrics": {"model": "qwen3.5:9b", "model_calls": 2, "retrieval_cache": "miss", "draft_cache": "miss"},
        }
    )
    make_audio = Mock(
        return_value={
            "data": b"RIFF-fake-wav-bytes",
            "mime": "audio/wav",
            "extension": "wav",
            "spoken_text": "Hostel fee is 24000 rupees per semester.",
            "provider": "Local VITS",
        }
    )
    monkeypatch.setattr(agent_bridge, "ask", ask)
    monkeypatch.setattr(speech, "make_audio", make_audio)
    monkeypatch.setattr(speech, "transcribe", Mock(return_value="What is the hostel fee?"))

    try:
        client = TestClient(api_server.app)

        # 1. Create session
        s_res = client.post("/api/session/new")
        assert s_res.status_code == 200
        session_id = s_res.json()["session_id"]

        # 2. Submit text turn
        t_res = client.post(
            "/api/turns/text",
            json={
                "session_id": session_id,
                "question": "What is the hostel fee?",
                "provider": "ollama",
                "voice": "Female",
                "speed": 1.0,
                "spoken": True,
                "online_speech": True,
            },
        )
        assert t_res.status_code == 200
        turn_id = t_res.json()["id"]

        # Poll until complete
        snap = None
        for _ in range(50):
            poll = client.get(f"/api/turns/{session_id}/{turn_id}")
            assert poll.status_code == 200
            snap = poll.json()
            if snap["is_terminal"]:
                break
            time.sleep(0.02)

        assert snap is not None and snap["stage"] == "complete"
        assert snap["answer_text"] == "Hostel fee is ₹ 24,000 per semester."
        assert snap["sources"][0]["source_name"] == "rules.pdf"
        assert snap["audio"]["available"] is True

        # 3. Fetch binary audio stream
        aud_res = client.get(f"/api/turns/{session_id}/{turn_id}/audio")
        assert aud_res.status_code == 200
        assert aud_res.content == b"RIFF-fake-wav-bytes"

        # 4. Retry audio without re-running agent
        retry_res = client.post(
            f"/api/turns/{session_id}/{turn_id}/retry-audio",
            json={"voice": "Male", "speed": 1.1, "online_speech": True},
        )
        assert retry_res.status_code == 200
        for _ in range(50):
            if client.get(f"/api/turns/{session_id}/{turn_id}").json()["is_terminal"]:
                break
            time.sleep(0.02)
        assert ask.call_count == 1
        assert make_audio.call_count == 2

        # 5. Audio upload turn
        audio_bytes = wav(seconds=1.0)
        up_res = client.post(
            "/api/turns/audio",
            data={
                "session_id": session_id,
                "provider": "ollama",
                "voice": "Female",
                "speed": "1.0",
                "spoken": "false",
                "online_speech": "false",
                "input_language": "English",
            },
            files={"file": ("question.wav", audio_bytes, "audio/wav")},
        )
        assert up_res.status_code == 200
        rec_turn_id = up_res.json()["id"]
        assert rec_turn_id.startswith("recording:")
        for _ in range(50):
            if client.get(f"/api/turns/{session_id}/{rec_turn_id}").json()["is_terminal"]:
                break
            time.sleep(0.02)

        # 6. Delete session
        del_res = client.delete(f"/api/session/{session_id}")
        assert del_res.status_code == 200
        assert del_res.json()["deleted"] is True
    finally:
        runtime.close()


def test_api_server_streaming_turn_output(monkeypatch, tmp_path: Path):
    runtime = jobs.JobManager(Store(tmp_path))
    monkeypatch.setattr(jobs, "manager", lambda: runtime)
    monkeypatch.setattr(api_server, "manager", lambda: runtime)
    ask = Mock(
        return_value={
            "answer_text": "Hostel fee is 24000.",
            "language": "english",
            "sources": [],
            "response_status": "answered",
            "ticket_id": None,
            "rag_metrics": {},
        }
    )
    monkeypatch.setattr(agent_bridge, "ask", ask)
    monkeypatch.setattr(
        speech,
        "make_audio",
        Mock(return_value={"data": b"wav", "mime": "audio/wav", "extension": "wav", "spoken_text": "text", "provider": "local"}),
    )

    try:
        client = TestClient(api_server.app)
        s_res = client.post("/api/session/new")
        session_id = s_res.json()["session_id"]
        t_res = client.post(
            "/api/turns/text",
            json={
                "session_id": session_id,
                "question": "What is the fee?",
                "provider": "ollama",
                "voice": "Female",
                "speed": 1.0,
                "spoken": False,
                "online_speech": False,
            },
        )
        turn_id = t_res.json()["id"]

        with client.stream("GET", f"/api/turns/{session_id}/{turn_id}/stream") as response:
            assert response.status_code == 200
            events = []
            for line in response.iter_lines():
                if line and line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            event_types = [e.get("event") for e in events]
            assert "complete" in event_types
            tokens = [e["token"] for e in events if e.get("event") == "token"]
            assert "".join(tokens) == "Hostel fee is 24000."
    finally:
        runtime.close()

