"""
Voice Activity Detection wrapper around Silero VAD.

Why a wrapper instead of using silero_vad directly everywhere:
  - Keeps the rest of the codebase model-agnostic (swap VAD backends without touching session.py)
  - Silero expects exactly 512-sample frames at 16kHz (256 @ 8kHz) — we enforce that contract here
    so callers can't accidentally pass the wrong chunk size and get silently wrong results.

Silero VAD ships its own ONNX weights inside the pip package — no network call at runtime,
which matters for a production service that shouldn't depend on external downloads.
"""
import numpy as np
from silero_vad import load_silero_vad, VADIterator

from src.config import settings

# Silero requires exactly this many samples per call at 16kHz.
SILERO_FRAME_SAMPLES = 512 if settings.SAMPLE_RATE == 16000 else 256


class SpeechDetector:
    """
    Stateful per-session VAD. Feed it raw int16 PCM chunks of ARBITRARY size via `process()`;
    internally it slices them into the fixed frame size Silero needs and returns speech
    start/end events as they're detected.
    """

    def __init__(self):
        self._model = _shared_model()  # one shared ONNX model instance across all sessions
        self._iterator = VADIterator(
            self._model,
            threshold=settings.VAD_THRESHOLD,
            sampling_rate=settings.SAMPLE_RATE,
            min_silence_duration_ms=settings.VAD_MIN_SILENCE_MS,
        )
        self._residual = np.array([], dtype=np.float32)  # leftover samples smaller than one frame

    def process(self, pcm16_bytes: bytes) -> list[dict]:
        """
        Feed raw 16-bit PCM audio bytes (mono, settings.SAMPLE_RATE).
        Returns a list of events like {'start': <sample_idx>} or {'end': <sample_idx>}
        emitted by Silero during this call (usually 0 or 1 events per call).
        """
        samples = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        buf = np.concatenate([self._residual, samples])

        events = []
        n_frames = len(buf) // SILERO_FRAME_SAMPLES
        for i in range(n_frames):
            frame = buf[i * SILERO_FRAME_SAMPLES: (i + 1) * SILERO_FRAME_SAMPLES]
            result = self._iterator(frame, return_seconds=False)
            if result:
                events.append(result)

        self._residual = buf[n_frames * SILERO_FRAME_SAMPLES:]
        return events

    def reset(self):
        self._iterator.reset_states()
        self._residual = np.array([], dtype=np.float32)


_MODEL_SINGLETON = None


def _shared_model():
    """Load the Silero ONNX model once per process; every session reuses it (it's stateless per-call)."""
    global _MODEL_SINGLETON
    if _MODEL_SINGLETON is None:
        _MODEL_SINGLETON = load_silero_vad(onnx=True)
    return _MODEL_SINGLETON
