"""Exercise audio contracts and turn lifecycle without model downloads or provider calls."""
import io
import json
import sys
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
import soundfile as sf
from streamlit.testing.v1 import AppTest

import agent_bridge
import settings
import speech
import workflow


def wav(seconds=1, rate=48000, stereo=True, silence=False):
    samples = np.zeros(int(seconds * rate), dtype=np.float32) if silence else (
        0.1 * np.sin(2 * np.pi * 220 * np.arange(int(seconds * rate)) / rate))
    if stereo:
        samples = np.column_stack((samples, samples))
    output = io.BytesIO()
    sf.write(output, samples, rate, format="WAV")
    return output.getvalue()


def test_resampling_and_silence(monkeypatch):
    result = speech.decode_audio(wav())
    assert result.shape == (16000,)
    assert result.dtype == np.float32
    assert 0.06 < np.sqrt(np.mean(result ** 2)) < 0.08
    monkeypatch.setattr(settings, "configure_stt", Mock(side_effect=AssertionError("No model on silence")))
    assert speech.transcribe(wav(silence=True)) == ""


@pytest.mark.parametrize("data", [b"", b"not audio", wav(seconds=0.1), wav(seconds=31)])
def test_invalid_recordings(data):
    with pytest.raises(ValueError):
        speech.decode_audio(data)


def test_speech_numbers_and_translation_guard(tmp_path, monkeypatch):
    folder = tmp_path / "Female"
    folder.mkdir()
    characters = "".join(chr(c) for c in range(0x0900, 0x0980))
    (folder / "config.json").write_text(json.dumps({"characters": {
        "characters": characters, "punctuations": " .,-"}}))
    monkeypatch.setattr(settings, "TTS_ROOT", tmp_path)
    result = speech.prepare_speech("Fee 120", "Female", lambda _: "शुल्क 120")
    assert "एक दो शून्य" in result
    with pytest.raises(ValueError, match="changed a number"):
        speech.prepare_speech("Fee 120", "Female", lambda _: "शुल्क 100")


def test_turn_dedup_retry_and_isolation(monkeypatch):
    ask = Mock(return_value={"answer_text": "नमस्ते", "language": "hindi", "sources": [],
                             "response_status": "smalltalk", "ticket_id": None})
    audio = Mock(side_effect=RuntimeError("private provider body"))
    monkeypatch.setattr(agent_bridge, "ask", ask)
    monkeypatch.setattr(speech, "make_audio", audio)
    session = workflow.new_session()
    other = workflow.new_session()
    assert session["id"] != other["id"]
    turn = workflow.run_turn(session, "नमस्ते", {}, "Female", 1, turn_id="one")
    assert turn["answer_text"] == "नमस्ते"
    assert "private" not in turn["audio_error"]
    assert workflow.run_turn(session, "नमस्ते", {}, "Female", 1, turn_id="one") is turn
    assert ask.call_count == 1
    audio.side_effect = None
    audio.return_value = {"data": b"audio"}
    workflow.speak_turn(turn, "Male", 1)
    assert ask.call_count == 1
    assert turn["audio"] and not turn["audio_error"]
    assert other["turns"] == []


def test_bridge_uses_real_graph_history_and_persistent_cache(monkeypatch, tmp_path):
    from dataclasses import replace
    from langgraph.checkpoint.memory import MemorySaver

    monkeypatch.syspath_prepend(str(settings.AGENT_ROOT))
    from assistant import nodes
    from assistant.graph import build_graph
    from assistant.llm import RoutingDecision, GroundedAnswer, Evidence
    from assistant.retrieval import RetrievedChunk

    monkeypatch.setattr(nodes, "settings", replace(nodes.settings, HISTORY_TURNS=2,
        KB_STATE_DIR=str(tmp_path / "kb"), RAG_CACHE_DB_PATH=str(tmp_path / "cache.sqlite")))
    monkeypatch.setattr(nodes, "active_release", lambda _: (tmp_path / "release", {"status": "complete"}))
    text = "Applicants must bring a Class 12 marksheet for reporting."
    search = Mock(return_value=[RetrievedChunk(text, "reporting.txt", "admissions", 1, 0.1, verified=True)])
    monkeypatch.setattr(nodes, "retrieve", search)

    def respond(schema, prompt, payload):
        if schema is RoutingDecision:
            return RoutingDecision(intent="knowledge", query="IIIT reporting documents", category="admissions")
        return GroundedAnswer(status="answered", answer=text,
                              evidence=[Evidence(source_id=1, quote=text)])

    monkeypatch.setattr(nodes, "invoke_json", respond)
    graph = build_graph(MemorySaver())
    monkeypatch.setattr(agent_bridge, "get_graph", lambda: graph)
    session = workflow.new_session()
    first = workflow.run_turn(session, "Reporting documents?", {}, "Female", 1, spoken=False)
    second = workflow.run_turn(session, "And for CG?", {}, "Female", 1, spoken=False)
    assert first["rag_metrics"]["history_pairs"] == 0
    assert second["rag_metrics"]["history_pairs"] == 1
    assert second["rag_metrics"]["draft_cache"] == "miss"
    other = workflow.new_session()
    repeated = workflow.run_turn(other, "Reporting documents?", {}, "Female", 1, spoken=False)
    assert repeated["rag_metrics"]["history_pairs"] == 0
    assert repeated["rag_metrics"]["draft_cache"] == "hit"
    assert repeated["rag_metrics"]["model_calls"] == 2
    assert repeated["sources"] == first["sources"]
    assert search.call_count == 1


def test_demo_config_keeps_cache_separate_and_defaults_to_ten_pairs(monkeypatch, tmp_path):
    root = tmp_path / "agent"
    (root / "assistant").mkdir(parents=True)
    (root / "assistant" / "graph.py").write_text("")
    (root / ".env").write_text("HISTORY_MESSAGES=4\nRAG_CACHE_DB_PATH=cli-cache.sqlite\n")
    monkeypatch.setattr(settings, "AGENT_ROOT", root)
    monkeypatch.setattr(settings, "DATA_ROOT", tmp_path / "demo")
    # Isolate environment mutations made by configure_agent from other tests.
    environment = dict(settings.os.environ)
    for key in ("HISTORY_TURNS", "HISTORY_MESSAGES", "RAG_CACHE_DB_PATH", "KB_DIR", "CHROMA_PERSIST_DIR"):
        environment.pop(key, None)
    monkeypatch.setattr(settings.os, "environ", environment)
    settings.configure_agent()
    assert environment["HISTORY_TURNS"] == "10"
    assert environment["RAG_CACHE_DB_PATH"] == str(tmp_path / "demo" / "rag_cache.sqlite")


def test_recording_is_consumed_even_on_failure(monkeypatch):
    decode = Mock(side_effect=RuntimeError("failed"))
    monkeypatch.setattr(speech, "transcribe", decode)
    session = workflow.new_session()
    with pytest.raises(RuntimeError):
        workflow.consume_recording(session, "file-one", b"audio", "Hindi")
    assert workflow.consume_recording(session, "file-one", b"audio", "Hindi") is None
    assert decode.call_count == 1


def test_online_english_routing(monkeypatch):
    calls = []
    def online(text, voice, speed):
        calls.append((text, voice, speed))
        return b"mp3"
    monkeypatch.setattr(speech, "online_audio", online)
    result = speech.make_audio("Hello", "english", "Male", 1.2)
    assert result["mime"] == "audio/mpeg"
    assert calls == [("Hello", "en-IN-PrabhatNeural", 1.2)]


@pytest.mark.parametrize("fail_at", ["load", "decode"])
def test_whisper_auto_falls_back_to_cpu(monkeypatch, fail_at):
    devices = []
    def create_model(model, device, **kwargs):
        devices.append(device)
        if device == "cuda" and fail_at == "load":
            raise RuntimeError("CUDA library unavailable")
        def transcribe(*args, **kwargs):
            if device == "cuda":
                raise RuntimeError("Library libcublas.so.12 is not found")
            return [SimpleNamespace(text="recognized", no_speech_prob=0.1)], None
        return SimpleNamespace(transcribe=transcribe)
    monkeypatch.setattr(settings, "configure_stt", lambda: None)
    monkeypatch.setattr(settings, "STT_DEVICE", "auto")
    monkeypatch.setattr(speech, "_WHISPER", None)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True)))
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=create_model))
    assert speech.transcribe(wav(), "English") == "recognized"
    assert speech.transcribe(wav(), "Hindi") == "recognized"
    assert devices == ["cuda", "cpu"]


def test_online_timeout_is_bounded(monkeypatch):
    import subprocess
    run = Mock(side_effect=subprocess.TimeoutExpired("online_voice", 45))
    monkeypatch.setattr(speech.subprocess, "run", run)
    with pytest.raises(subprocess.TimeoutExpired):
        speech.online_audio("Hello", "en-IN-NeerjaNeural", 1)
    assert run.call_args.kwargs["timeout"] == settings.EDGE_TIMEOUT_SECONDS


def test_app_text_turn_rerun_and_reset(monkeypatch):
    ask = Mock(return_value={"answer_text": "Test answer", "language": "english", "sources": [
        {"source_file": "admissions/guide.pdf", "page_number": 3, "quote": "Exact source quote"}],
        "response_status": "answered", "ticket_id": None})
    monkeypatch.setattr(agent_bridge, "ask", ask)
    monkeypatch.setattr(speech, "make_audio", Mock(side_effect=RuntimeError("offline")))
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"), default_timeout=15).run()
    assert not app.exception
    app.chat_input[0].set_value("What are admission requirements?").run()
    assert not app.exception
    assert ask.call_count == 1
    assert any(t.value == "Exact source quote" for t in app.text)
    app.run()
    assert ask.call_count == 1
    retry = next(b for b in app.button if b.label == "Retry audio")
    retry.click().run()
    assert ask.call_count == 1
    previous = app.session_state["conversation"]["id"]
    next(b for b in app.button if b.label == "New conversation").click().run()
    assert app.session_state["conversation"]["id"] != previous
    assert app.session_state["conversation"]["turns"] == []
    assert not app.exception
