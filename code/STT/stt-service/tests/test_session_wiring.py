"""
Session-level wiring tests for chapter 03 changes.

Verifies that the SttSession integrates the prefix committer and the EOU gate
without regressing the legacy (silence-timer) endpoint. Uses a fake ASR engine
and a stubbed VAD so no real model is loaded and no audio device is needed.

Run from the stt-service root:
    conda activate minor
    cd code/STT/stt-service
    python -m pytest tests/test_session_wiring.py -q
"""
import asyncio
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.session as session_mod
from src.schemas import EventType
from src.asr import Transcript


class _FakeEngine:
    """Deterministic ASR stub: returns a scripted transcript per call."""

    def __init__(self, text="the fee is high"):
        self.text = text

    def transcribe(self, audio, *, fast):
        return Transcript(text=self.text, avg_logprob=-0.2,
                          no_speech_prob=0.0, inference_ms=1.0)


def _make_session(monkeypatch, engine=None):
    engine = engine or _FakeEngine()
    monkeypatch.setattr(session_mod, "get_engine", lambda: engine)
    s = session_mod.SttSession("t0")
    return s


def _pcm(ms, rate=16000):
    n = int(rate * ms / 1000)
    return (np.zeros(n, dtype=np.int16)).tobytes()


def test_speech_started_resets_committer(monkeypatch):
    s = _make_session(monkeypatch)
    s._committer.update("stale one")
    s._committer.update("stale one two")
    assert s._committer.committed_text != ""
    # Force a SILENCE->SPEAKING transition via a stubbed VAD "start".
    monkeypatch.setattr(s._vad, "process", lambda b: [{"start": 0}])
    events = asyncio.run(s.process_chunk(_pcm(40)))
    assert any(e.type == EventType.SPEECH_STARTED for e in events)
    assert s._committer.committed_text == ""
    assert s._last_eou_prob is None


def test_legacy_finalize_on_silence_when_eou_disabled(monkeypatch):
    # EOU disabled (default): finalize must still happen on the silence cap.
    s = _make_session(monkeypatch, _FakeEngine("admission open"))
    # Start speech.
    monkeypatch.setattr(s._vad, "process", lambda b: [{"start": 0}])
    asyncio.run(s.process_chunk(_pcm(500)))
    # Now feed silence; stub VAD to report an "end" so silence tracking begins.
    monkeypatch.setattr(s._vad, "process", lambda b: [{"end": 0}])
    asyncio.run(s.process_chunk(_pcm(40)))
    # Force the silence timer past the cap and drive one more chunk.
    import time
    s._silence_started_ts = time.monotonic() - 5.0  # 5 s of "silence"
    monkeypatch.setattr(s._vad, "process", lambda b: [])
    events = asyncio.run(s.process_chunk(_pcm(40)))
    finals = [e for e in events if e.type == EventType.FINAL]
    assert len(finals) == 1
    assert finals[0].text == "admission open"
    assert finals[0].eou_prob is None  # silence-timer path, no model consulted


def test_eou_gate_finalizes_on_confident_completion(monkeypatch):
    # Enable EOU and stub the probe to return a confident completion.
    import dataclasses
    patched = dataclasses.replace(session_mod.settings, EOU_ENABLED=True)
    monkeypatch.setattr(session_mod, "settings", patched)
    s = _make_session(monkeypatch, _FakeEngine("done now"))

    async def fake_probe():
        return 0.95
    monkeypatch.setattr(s, "_probe_eou", fake_probe)

    monkeypatch.setattr(s._vad, "process", lambda b: [{"start": 0}])
    asyncio.run(s.process_chunk(_pcm(500)))
    monkeypatch.setattr(s._vad, "process", lambda b: [{"end": 0}])
    asyncio.run(s.process_chunk(_pcm(40)))
    # Just past EOU_MIN_SILENCE_MS (300 ms) but well below any silence cap.
    import time
    s._silence_started_ts = time.monotonic() - 0.35
    monkeypatch.setattr(s._vad, "process", lambda b: [])
    events = asyncio.run(s.process_chunk(_pcm(40)))
    finals = [e for e in events if e.type == EventType.FINAL]
    assert len(finals) == 1
    assert finals[0].eou_prob == 0.95


def test_prefix_commit_populates_partial_fields(monkeypatch):
    import dataclasses
    patched = dataclasses.replace(session_mod.settings, PREFIX_COMMIT_ENABLED=True)
    monkeypatch.setattr(session_mod, "settings", patched)
    s = _make_session(monkeypatch, _FakeEngine("hello there"))
    monkeypatch.setattr(s._vad, "process", lambda b: [{"start": 0}])
    asyncio.run(s.process_chunk(_pcm(500)))
    # Emit two partials so LocalAgreement-2 can commit the agreed prefix.
    p1 = asyncio.run(s._emit_partial())
    p2 = asyncio.run(s._emit_partial())
    assert p1.committed_text == ""           # first partial: nothing agreed yet
    assert p2.committed_text == "hello there" # second partial agrees -> commits
    assert p2.text == "hello there"           # raw text unchanged for legacy clients
