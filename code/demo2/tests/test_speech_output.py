"""Task 07 speech-output tests: clause segmenter, audio cache, streaming primitive.

These are short, offline tests (no model download, no synthesis of real audio). The
streaming primitive is exercised against a stub synthesizer so no VITS checkpoint is loaded.
"""
import io
import sys
from collections import OrderedDict

import numpy as np
import pytest
import soundfile as sf

import settings as cfg
import clause_segmenter as seg
import tts_cache
import speech
from verbalization import normalize


# --------------------------------------------------------------------------- segmenter

def test_segment_preserves_number_unit_span():
    """A spoken Indian number must never be split across a clause boundary."""
    text = normalize("सुरक्षा जमा ₹90,000 है, और यह वापसी योग्य है।", "hindi")
    clauses = seg.segment(text, cfg.TTS_CHUNK_CHARS)
    joined = " ".join(clauses)
    # "नब्बे हजार रुपये" (90,000) must stay contiguous in exactly one clause.
    assert "नब्बे हजार रुपये" in joined
    assert any("नब्बे हजार रुपये" in clause for clause in clauses), clauses
    # No clause may start or end mid-number (dangling unit word).
    for clause in clauses:
        assert not clause.strip().startswith("हजार")
        assert not clause.strip().endswith("नब्बे")


def test_segment_protects_range_connector():
    """A numeric range '12 से 15' must not be broken by the splitter."""
    text = normalize("रैंक 12-15 के बीच, प्रवेश संभव है।", "hindi")
    clauses = seg.segment(text, cfg.TTS_CHUNK_CHARS)
    joined = " ".join(clauses)
    assert "से" in joined
    assert any("से" in clause and clause.count("से") >= 1 for clause in clauses)
    for clause in clauses:
        assert clause.strip() != "से"
        assert not clause.strip().endswith("से")


def test_segment_first_clause_is_short():
    """The first clause stays within the short TTFB budget when the text has breaks."""
    text = normalize("पहला वाक्य। दूसरा लंबा वाक्य जिसमें बहुत सारे शब्द हैं और यह लंबा चलता रहता है।", "hindi")
    clauses = seg.segment(text, cfg.TTS_CHUNK_CHARS, first_clause_chars=30)
    assert len(clauses) >= 2
    assert len(clauses[0]) <= 30


def test_segment_concatenation_is_lossless():
    """Joining clauses reproduces the normalized content (no dropped/duplicated words)."""
    text = normalize("शुल्क ₹1,25,000 है। छात्रावास अलग है, मेस भी अलग है।", "hindi")
    clauses = seg.segment(text, cfg.TTS_CHUNK_CHARS)
    # Re-joining with single spaces and collapsing whitespace must equal the input tokens.
    assert " ".join(" ".join(clauses).split()) == " ".join(text.split())


def test_segment_empty_and_single():
    assert seg.segment("", cfg.TTS_CHUNK_CHARS) == []
    assert seg.segment("नमस्ते।", cfg.TTS_CHUNK_CHARS) == ["नमस्ते।"]


# ------------------------------------------------------------------------------- cache

@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(tts_cache.cfg, "TTS_CACHE_DB_PATH", str(tmp_path / "tts.sqlite"))
    monkeypatch.setattr(tts_cache.cfg, "TTS_CACHE_ENABLED", True)
    monkeypatch.setattr(tts_cache.cfg, "TTS_CACHE_TTL_SECONDS", 3600.0)
    monkeypatch.setattr(tts_cache.cfg, "TTS_CACHE_MAX_ENTRIES", 3)
    monkeypatch.setattr(tts_cache.cfg, "TTS_CACHE_MAX_ENTRY_BYTES", 1_000_000)
    monkeypatch.setattr(tts_cache.cfg, "TTS_CACHE_MAX_BYTES", 10_000_000)
    monkeypatch.setattr(tts_cache.cfg, "TTS_CACHE_TIMEOUT_SECONDS", 1.0)
    # Deterministic, cheap key inputs: pin release and model version.
    monkeypatch.setattr(tts_cache, "active_kb_release", lambda: "REL-A")
    monkeypatch.setattr(tts_cache, "model_version", lambda: "vits-test-aaaa")
    return tts_cache.AudioCache(settings=tts_cache.cfg)


def _payload(data=b"RIFFxxxxWAVE-audio"):
    return {"data": data, "mime": "audio/wav", "extension": "wav",
            "spoken_text": "नमस्ते", "provider": "Local VITS"}


def test_cache_roundtrip(cache):
    key = tts_cache.cache_key("नमस्ते", "Female", 1.0)
    assert cache.get(key) is None
    cache.put(key, _payload())
    hit = cache.get(key)
    assert hit is not None
    assert hit["data"] == b"RIFFxxxxWAVE-audio"
    assert hit["cache_hit"] is True


def test_cache_key_binds_release_and_model(monkeypatch):
    """Changing the KB release or model version changes the key — invalidation by design."""
    monkeypatch.setattr(tts_cache, "model_version", lambda: "vits-test-aaaa")
    monkeypatch.setattr(tts_cache, "active_kb_release", lambda: "REL-A")
    key_a = tts_cache.cache_key("नमस्ते", "Female", 1.0)
    monkeypatch.setattr(tts_cache, "active_kb_release", lambda: "REL-B")
    key_b = tts_cache.cache_key("नमस्ते", "Female", 1.0)
    monkeypatch.setattr(tts_cache, "active_kb_release", lambda: "REL-A")
    monkeypatch.setattr(tts_cache, "model_version", lambda: "vits-test-bbbb")
    key_c = tts_cache.cache_key("नमस्ते", "Female", 1.0)
    assert len({key_a, key_b, key_c}) == 3


def test_cache_release_bump_misses(cache, monkeypatch):
    """An entry written under one release is not served after a release bump."""
    key_old = tts_cache.cache_key("नमस्ते", "Female", 1.0)
    cache.put(key_old, _payload())
    assert cache.get(key_old) is not None
    monkeypatch.setattr(tts_cache, "active_kb_release", lambda: "REL-NEW")
    key_new = tts_cache.cache_key("नमस्ते", "Female", 1.0)
    assert key_new != key_old
    assert cache.get(key_new) is None  # stale audio is never served after a release change


def test_cache_key_varies_with_voice_and_speed():
    base = tts_cache.cache_key("नमस्ते", "Female", 1.0)
    assert base != tts_cache.cache_key("नमस्ते", "Male", 1.0)
    assert base != tts_cache.cache_key("नमस्ते", "Female", 1.1)


def test_cache_lfu_eviction_bounds_entries(cache):
    for i in range(5):
        cache.put(tts_cache.cache_key(f"phrase-{i}", "Female", 1.0), _payload())
    with tts_cache.sqlite3.connect(cache.settings.TTS_CACHE_DB_PATH) as conn:
        count = conn.execute("SELECT COUNT(*) FROM tts_cache").fetchone()[0]
    assert count <= cache.settings.TTS_CACHE_MAX_ENTRIES


def test_cache_disabled_bypasses(cache, monkeypatch):
    monkeypatch.setattr(cache.settings, "TTS_CACHE_ENABLED", False)
    key = tts_cache.cache_key("नमस्ते", "Female", 1.0)
    cache.put(key, _payload())
    assert cache.get(key) is None


def test_cache_rejects_oversized_entry(cache):
    key = tts_cache.cache_key("big", "Female", 1.0)
    cache.put(key, _payload(data=b"x" * (cache.settings.TTS_CACHE_MAX_ENTRY_BYTES + 1)))
    assert cache.get(key) is None


# -------------------------------------------------------------------- streaming primitive

class _StubModel:
    length_scale = 1.0


class _StubSynth:
    output_sample_rate = 22050

    def __init__(self):
        self.tts_model = _StubModel()
        self.calls = []

    def tts(self, text):
        self.calls.append(text)
        # One tenth of a second of silence per call; enough to encode a valid WAV.
        return list(np.zeros(2205, dtype=np.float32))


def test_synthesize_stream_yields_per_clause(monkeypatch):
    stub = _StubSynth()
    monkeypatch.setattr(speech, "_load_synthesizer", lambda voice: stub)
    clauses = ["पहला वाक्य।", "दूसरा वाक्य।", "तीसरा वाक्य।"]
    emitted = list(speech.synthesize_stream(clauses, "Female", 1.0))
    assert [i for i, _, _ in emitted] == [0, 1, 2]
    assert emitted[-1][2] is True  # last flag set on final clause
    assert all(not last for _, _, last in emitted[:-1])
    # Each yielded element is a standalone, decodable WAV.
    for _, wav_bytes, _ in emitted:
        info = sf.info(io.BytesIO(wav_bytes))
        assert info.samplerate == 22050
    assert stub.calls == clauses  # no re-normalization; clauses passed through verbatim


def test_synthesize_stream_rejects_empty(monkeypatch):
    monkeypatch.setattr(speech, "_load_synthesizer", lambda voice: _StubSynth())
    with pytest.raises(ValueError):
        list(speech.synthesize_stream([], "Female", 1.0))


def test_synthesize_stream_applies_length_scale(monkeypatch):
    stub = _StubSynth()
    monkeypatch.setattr(speech, "_load_synthesizer", lambda voice: stub)
    list(speech.synthesize_stream(["वाक्य।"], "Female", 1.3))
    assert stub.tts_model.length_scale == 1.3


# ------------------------------------------------------------------------ make_audio cache

def test_make_audio_uses_cache_when_cacheable(monkeypatch, tmp_path):
    """A second cacheable call returns the cached bytes without re-synthesising."""
    monkeypatch.setattr(speech.cfg, "TTS_CACHE_DB_PATH", str(tmp_path / "tts.sqlite"))
    monkeypatch.setattr(speech.cfg, "TTS_CACHE_ENABLED", True)
    monkeypatch.setattr(tts_cache, "active_kb_release", lambda: "REL-A")
    monkeypatch.setattr(tts_cache, "model_version", lambda: "vits-test")
    # Fresh cache instance pointed at the temp DB.
    monkeypatch.setattr(tts_cache, "_CACHE", tts_cache.AudioCache(settings=speech.cfg))
    calls = {"n": 0}

    def fake_synth(text, voice, length_scale):
        calls["n"] += 1
        return b"RIFFwav" + text.encode()

    monkeypatch.setattr(speech, "synthesize", fake_synth)
    monkeypatch.setattr(speech, "prepare_speech", lambda text, voice: "नमस्ते")

    first = speech.make_audio("नमस्ते", "hindi", "Female", 1.0, cacheable=True)
    second = speech.make_audio("नमस्ते", "hindi", "Female", 1.0, cacheable=True)
    assert calls["n"] == 1  # synthesised once, served from cache the second time
    assert second.get("cache_hit") is True
    assert first["data"] == second["data"]


def test_make_audio_skips_cache_when_not_cacheable(monkeypatch, tmp_path):
    monkeypatch.setattr(speech.cfg, "TTS_CACHE_DB_PATH", str(tmp_path / "tts.sqlite"))
    monkeypatch.setattr(speech.cfg, "TTS_CACHE_ENABLED", True)
    monkeypatch.setattr(tts_cache, "active_kb_release", lambda: "REL-A")
    monkeypatch.setattr(tts_cache, "model_version", lambda: "vits-test")
    monkeypatch.setattr(tts_cache, "_CACHE", tts_cache.AudioCache(settings=speech.cfg))
    calls = {"n": 0}

    def fake_synth(text, voice, length_scale):
        calls["n"] += 1
        return b"RIFFwav"

    monkeypatch.setattr(speech, "synthesize", fake_synth)
    monkeypatch.setattr(speech, "prepare_speech", lambda text, voice: "नमस्ते")
    speech.make_audio("नमस्ते", "hindi", "Female", 1.0, cacheable=False)
    speech.make_audio("नमस्ते", "hindi", "Female", 1.0, cacheable=False)
    assert calls["n"] == 2  # never cached, so synthesised each time
