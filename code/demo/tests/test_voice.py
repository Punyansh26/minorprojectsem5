"""Reject invalid, silent, oversized or truncated audio before a provider call."""

import io
import wave

import numpy as np
import pytest

from voice import prepare_recording, validate_wav


def wav_bytes(seconds=1, rate=16000, silent=False):
    buffer = io.BytesIO()
    data = np.zeros(int(seconds * rate)) if silent else np.sin(np.arange(int(seconds * rate)) * 0.2) * 5000
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(data.astype("<i2").tobytes())
    return buffer.getvalue()


def test_valid_audio():
    assert validate_wav(wav_bytes()) == 1


@pytest.mark.parametrize("audio", [b"garbage", wav_bytes(silent=True), wav_bytes(rate=8000), wav_bytes(seconds=46), wav_bytes()[:-20]])
def test_invalid_audio(audio):
    with pytest.raises(ValueError):
        validate_wav(audio)


@pytest.mark.parametrize("rate,channels", [(44100, 1), (48000, 2), (16000, 1)])
def test_browser_recording_is_normalized(rate, channels):
    buffer = io.BytesIO()
    samples = (np.sin(2 * np.pi * 440 * np.arange(rate) / rate) * 5000).astype("<i2")
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(np.repeat(samples[:, None], channels, axis=1).tobytes())
    converted = prepare_recording(buffer.getvalue())
    assert validate_wav(converted) == 1
    with wave.open(io.BytesIO(converted), "rb") as wav:
        signal = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
    assert np.argmax(np.abs(np.fft.rfft(signal))) == 440


@pytest.mark.parametrize("audio", [b"garbage", wav_bytes(silent=True), wav_bytes(seconds=46), wav_bytes()[:-20]])
def test_bad_browser_recording_is_rejected(audio):
    with pytest.raises(ValueError):
        prepare_recording(audio)


def test_local_asr_receives_pcm_without_wav_header(monkeypatch):
    import voice
    calls = []
    def recognize(pcm):
        calls.append(pcm)
        return "धान बीज"
    monkeypatch.setattr(voice, "recognize", recognize)
    audio = wav_bytes()
    result = voice.transcribe(audio, "unused-key", "hne")
    with wave.open(io.BytesIO(audio), "rb") as wav:
        assert calls == [wav.readframes(wav.getnframes())]
    assert result["text"] == "धान बीज"
    assert result["asr_language"] == voice.STT_LANGUAGE


def test_local_tts_keeps_prices_and_quantities_audible(monkeypatch):
    import voice
    from speech_text import prepare_speech_text
    assert prepare_speech_text("2 × धान (SEED01): ₹900.50") == "दो गुना धान: नौ सौ रुपये पचास पैसे"
    calls = []
    monkeypatch.setattr(voice, "speak", lambda text: calls.append(text) or b"RIFF-local-wav")
    audio, _ = voice.synthesize("₹450.00", "hne")
    assert audio == b"RIFF-local-wav"
    assert calls == ["चार सौ पचास रुपये"]
    with pytest.raises(ValueError, match="Devanagari"):
        voice.synthesize("English text", "en")


def test_transcription_memory_failure_is_actionable():
    from voice import transcription_error
    oom = type("OutOfMemoryError", (RuntimeError,), {})
    message = transcription_error(oom("private provider/request detail"))
    assert "DEMO_STT_DTYPE=float16" in message
    assert "private" not in message
