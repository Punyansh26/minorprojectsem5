"""
Semantic end-of-turn (EOU) detection for turn-taking (FutureWork chapter 03 §3.2).

A pure-silence endpoint (``silence_ms >= END_OF_SPEECH_SILENCE_MS``) cannot tell a
*thinking pause* ("admission… for ST category?") from a *finished turn*. A small
audio classifier that predicts ``p_complete`` from the last few seconds of audio
can, so the finalisation rule becomes (chapter 03 §3.2):

    silence_ms >= min_silence  AND  (p_complete >= tau  OR  silence_ms >= max_silence)

* ``min_silence`` keeps a short floor so we never cut on a 50 ms blip.
* ``p_complete >= tau`` lets a confident turn commit early (cuts dead air).
* ``max_silence`` is the safety cap so a low-confidence / absent model can never
  hang the turn — it degrades to the old behaviour at worst.

Recommended model: **vedants254/voice-turn-detection** (Whisper-Tiny encoder +
head, ~8M params, ONNX, English/Hindi/Hinglish, MIT) [R302]. Input is the last
8 s of 16 kHz mono audio left-padded to ``[1, 128000]``; output is a single
``p_complete`` logit/probability. Smart-Turn v3 (BSD-2) is a drop-in alternative.

**Graceful degradation is the core contract here.** If ``onnxruntime`` is missing,
or no model file is configured/present, or inference raises, the detector reports
``available = False`` and returns ``p_complete = None``. The session then relies
purely on the silence timer — i.e. *exactly today's behaviour*. Wiring this module
in therefore never regresses endpointing; it can only tighten it when a model is
present. No model weights are bundled or downloaded by this module.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np

from src.config import settings


# vedants254 input contract: 8 s @ 16 kHz, left-padded. [R302]
EOU_WINDOW_SECONDS = 8.0


@dataclass
class EouResult:
    """Outcome of one EOU probe.

    ``p_complete`` is ``None`` when no model ran (unavailable / disabled / error),
    which callers MUST treat as "no opinion" and fall back to the silence timer.
    """

    p_complete: float | None
    available: bool
    reason: str = ""


class SemanticTurnDetector:
    """Lazy, thread-safe ONNX EOU classifier with graceful degradation.

    The model is loaded on first use (not at import) so a service with EOU
    disabled, or without the weights present, starts and runs unaffected. One
    shared session per process; ONNX Runtime inference is itself thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False
        self._session = None  # onnxruntime.InferenceSession | None
        self._input_name: str | None = None
        self._load_error: str = ""

    # -- loading -----------------------------------------------------------

    @property
    def enabled(self) -> bool:
        """Whether EOU is switched on at all (config flag + a configured path)."""
        return bool(settings.EOU_ENABLED and settings.EOU_MODEL_PATH)

    def _ensure_loaded(self) -> bool:
        """Load the ONNX session once. Returns True iff a session is usable."""
        if self._loaded:
            return self._session is not None
        with self._lock:
            if self._loaded:
                return self._session is not None
            self._loaded = True
            if not self.enabled:
                self._load_error = "EOU disabled or no model path set"
                return False
            try:
                import os

                if not os.path.isfile(settings.EOU_MODEL_PATH):
                    self._load_error = f"model file not found: {settings.EOU_MODEL_PATH}"
                    return False
                import onnxruntime as ort

                sess = ort.InferenceSession(
                    settings.EOU_MODEL_PATH,
                    providers=["CPUExecutionProvider"],
                )
                self._session = sess
                self._input_name = sess.get_inputs()[0].name
                return True
            except Exception as exc:  # pragma: no cover - env dependent
                # ImportError (no onnxruntime), bad file, bad opset, etc.
                self._session = None
                self._load_error = f"{type(exc).__name__}: {exc}"
                return False

    # -- inference ---------------------------------------------------------

    def _prepare_input(self, audio: np.ndarray) -> np.ndarray:
        """Last 8 s, left-padded to [1, 128000] float32 (vedants254 contract)."""
        target = int(EOU_WINDOW_SECONDS * settings.SAMPLE_RATE)
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        if audio.shape[0] >= target:
            clip = audio[-target:]
        else:
            clip = np.zeros(target, dtype=np.float32)
            clip[target - audio.shape[0]:] = audio  # left-pad
        return clip.reshape(1, target)

    @staticmethod
    def _to_probability(raw: np.ndarray) -> float:
        """Coerce a model output to a scalar probability in [0, 1].

        Handles both already-sigmoided outputs and raw logits. We detect a logit
        by it falling outside [0, 1] and apply a sigmoid; a value already inside
        [0, 1] is taken as a probability.
        """
        val = float(np.asarray(raw).reshape(-1)[0])
        if 0.0 <= val <= 1.0:
            return val
        return float(1.0 / (1.0 + np.exp(-val)))

    def predict(self, audio: np.ndarray) -> EouResult:
        """Return ``p_complete`` for the given audio, or a no-opinion result.

        Never raises for model/availability problems: any failure degrades to
        ``available=False`` so the caller falls back to the silence timer.
        """
        if not self._ensure_loaded():
            return EouResult(p_complete=None, available=False, reason=self._load_error)
        try:
            x = self._prepare_input(audio)
            outputs = self._session.run(None, {self._input_name: x})
            p = self._to_probability(outputs[0])
            return EouResult(p_complete=max(0.0, min(1.0, p)), available=True)
        except Exception as exc:  # pragma: no cover - env dependent
            return EouResult(
                p_complete=None, available=False, reason=f"{type(exc).__name__}: {exc}"
            )


def should_finalize(
    *,
    silence_ms: float,
    utterance_ms: float,
    eou_p: float | None,
    min_silence_ms: float,
    max_silence_ms: float,
    eou_tau: float,
    max_utterance_ms: float,
) -> bool:
    """The chapter 03 §3.2 finalisation decision, as a pure function.

    Finalises when EITHER:
      * the utterance hit the hard length cap (``utterance_ms >= max_utterance_ms``), OR
      * we have at least ``min_silence_ms`` of trailing silence AND
          - a confident semantic completion (``eou_p >= eou_tau``), OR
          - the silence safety cap (``silence_ms >= max_silence_ms``).

    When ``eou_p is None`` (model absent / disabled / errored) the semantic clause
    is simply false, so the rule reduces to ``silence_ms >= max_silence_ms`` — set
    ``max_silence_ms`` equal to the legacy ``END_OF_SPEECH_SILENCE_MS`` to exactly
    reproduce today's endpointing when no model is present.
    """
    if utterance_ms >= max_utterance_ms:
        return True
    if silence_ms < min_silence_ms:
        return False
    if eou_p is not None and eou_p >= eou_tau:
        return True
    return silence_ms >= max_silence_ms


# One shared detector per process (mirrors the VAD/ASR singletons).
_DETECTOR_SINGLETON: SemanticTurnDetector | None = None


def get_turn_detector() -> SemanticTurnDetector:
    global _DETECTOR_SINGLETON
    if _DETECTOR_SINGLETON is None:
        _DETECTOR_SINGLETON = SemanticTurnDetector()
    return _DETECTOR_SINGLETON
