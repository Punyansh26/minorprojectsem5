"""Small voice adapters; no recordings or synthesized audio are written to disk."""

import io
from math import gcd
import wave
from time import perf_counter

from local_speech import recognize, speak
from speech_text import prepare_speech_text

from config import MAX_AUDIO_BYTES, MAX_AUDIO_SECONDS, STT_LANGUAGE, STT_MODEL


def prepare_recording(audio: bytes) -> bytes:
    """Convert browser-native PCM WAV recordings to the transcription contract."""
    import numpy as np
    from scipy.signal import resample_poly

    if not audio or len(audio) > MAX_AUDIO_BYTES:
        raise ValueError("Record a shorter clip (maximum 45 seconds / 4 MB).")
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            channels, rate, frames = wav.getnchannels(), wav.getframerate(), wav.getnframes()
            if channels not in (1, 2) or wav.getsampwidth() != 2 or not 8000 <= rate <= 96000:
                raise ValueError("The microphone must produce mono or stereo 16-bit PCM WAV audio.")
            if not 0.3 <= frames / rate <= MAX_AUDIO_SECONDS:
                raise ValueError("Record between 0.3 and 45 seconds of valid WAV audio.")
            decoded = wav.readframes(frames)
            if len(decoded) != frames * channels * 2:
                raise ValueError("The microphone recording is incomplete. Please try again.")
    except (wave.Error, EOFError) as exc:
        raise ValueError("The recording is not a valid PCM WAV file.") from exc
    samples = np.frombuffer(decoded, dtype="<i2").astype(np.float32).reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        divisor = gcd(rate, 16000)
        samples = resample_poly(samples, 16000 // divisor, rate // divisor)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(np.clip(np.rint(samples), -32768, 32767).astype("<i2").tobytes())
    converted = buffer.getvalue()
    validate_wav(converted)
    return converted


def validate_wav(audio: bytes) -> float:
    """Bound and inspect actual WAV bytes before local speech inference."""
    if not audio or len(audio) > MAX_AUDIO_BYTES:
        raise ValueError("Record a shorter clip (maximum 45 seconds / 4 MB).")
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16000:
                raise ValueError("Use mono 16 kHz, 16-bit PCM WAV audio.")
            frames = wav.getnframes()
            duration = frames / wav.getframerate()
            decoded = wav.readframes(frames)
            if not 0.3 <= duration <= MAX_AUDIO_SECONDS or len(decoded) != frames * 2:
                raise ValueError("Record between 0.3 and 45 seconds of valid WAV audio.")
            import numpy as np
            if np.max(np.abs(np.frombuffer(decoded, dtype='<i2').astype('int32'))) < 100:
                raise ValueError("The recording is silent or too quiet. Please try again.")
            return duration
    except (wave.Error, EOFError) as exc:
        raise ValueError("The recording is not a valid PCM WAV file.") from exc


def transcribe(audio: bytes, api_key: str = "", language: str = "hne") -> dict:
    """Transcribe a completed recording with the existing local STT engine; no audio API."""
    duration = validate_wav(audio)
    start = perf_counter()
    with wave.open(io.BytesIO(audio), "rb") as wav:
        pcm = wav.readframes(wav.getnframes())
    transcript = recognize(pcm)
    if not transcript:
        raise ValueError("No clear speech was recognized. Please record again or type.")
    return {"text": transcript, "asr_ms": round((perf_counter() - start) * 1000, 1),
            "audio_seconds": duration, "model": STT_MODEL, "asr_language": STT_LANGUAGE}


def transcription_error(exc: Exception) -> str:
    """Explain common local failures without exposing recordings or exception bodies."""
    name = type(exc).__name__
    if name == "OutOfMemoryError":
        return ("Local STT ran out of GPU memory. Close duplicate demo/notebook model processes, "
                "use DEMO_STT_DTYPE=float16, and try a shorter recording.")
    if isinstance(exc, MemoryError):
        return "Local STT ran out of system memory. Close unused model processes and try a shorter recording."
    if isinstance(exc, ImportError):
        return "A local speech dependency is missing. Run the app in the minor Conda environment."
    return (f"Local STT could not transcribe ({name}). Try a shorter recording; "
            "check the minor environment and cached model if this continues.")


def synthesize(text: str, language: str) -> tuple[bytes, float]:
    """Return in-memory WAV using the notebook's local Chhattisgarhi VITS checkpoint."""
    start = perf_counter()
    if language == "en":
        raise ValueError("The local VITS voices support Devanagari. Select Hindi or Chhattisgarhi for spoken replies.")
    return speak(prepare_speech_text(text)), round((perf_counter() - start) * 1000, 1)
