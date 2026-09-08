"""
ASR engine abstraction.

`ASREngine` is the interface the rest of the app codes against. Today it's backed by
faster-whisper (CTranslate2). When you're ready to move to NVIDIA Parakeet-TDT for
production (better latency/accuracy on GPU), you implement `ParakeetEngine` with the
same two methods and swap one line in `get_engine()` — nothing else in the codebase changes.
"""
from __future__ import annotations

import time
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
from faster_whisper import WhisperModel

from src.config import settings

import torch

@dataclass
class Transcript:
    text: str
    avg_logprob: float  # ~confidence proxy, roughly in [-1, 0], closer to 0 = more confident
    no_speech_prob: float  # Whisper's own estimate that this segment was NOT speech (0-1)
    inference_ms: float


class ASREngine(ABC):
    @abstractmethod
    def transcribe(self, audio: np.ndarray, *, fast: bool) -> Transcript:
        """
        audio: float32 mono PCM at settings.SAMPLE_RATE, values in [-1, 1]
        fast:  True for partial transcripts (favor speed, greedy decoding),
               False for final transcripts (favor accuracy, beam search)
        """
        raise NotImplementedError


class FasterWhisperEngine(ASREngine):
    def __init__(self):
        self._model = WhisperModel(
            settings.ASR_MODEL_SIZE,
            device=settings.ASR_DEVICE,
            compute_type=settings.ASR_COMPUTE_TYPE,
        )

    def transcribe(self, audio: np.ndarray, *, fast: bool) -> Transcript:
        t0 = time.monotonic()
        segments, _info = self._model.transcribe(
            audio,
            language=settings.ASR_LANGUAGE,
            beam_size=settings.ASR_BEAM_SIZE if fast else settings.ASR_FINAL_BEAM_SIZE,
            vad_filter=False,  # we already did VAD ourselves upstream; don't double-gate
            condition_on_previous_text=False,  # avoids drift/hallucination across repeated re-transcriptions
            word_timestamps=False,
            # Biases decoding toward domain vocabulary (clinician names, procedures, etc.) —
            # measurably cuts misrecognitions on the proper nouns that matter most for booking
            # to actually go through correctly. See config.py ASR_INITIAL_PROMPT.
            initial_prompt=settings.ASR_INITIAL_PROMPT or None,
        )
        segments = list(segments)
        text = " ".join(s.text.strip() for s in segments).strip()
        avg_logprob = sum(s.avg_logprob for s in segments) / len(segments) if segments else -1.0
        no_speech_prob = max((s.no_speech_prob for s in segments), default=1.0)
        return Transcript(
            text=text,
            avg_logprob=avg_logprob,
            no_speech_prob=no_speech_prob,
            inference_ms=(time.monotonic() - t0) * 1000,
        )

def clean_mms_devanagari(text: str) -> str:
    """
    MMS's CTC output can insert stray spaces before Devanagari matras/vowel signs on
    lower-resource adapters, which detaches them from their base consonant and renders as a
    dotted circle (◌) instead of a proper conjunct. This rejoins them. Safe no-op on text
    that's already correctly formed.
    """
    if not text:
        return ""
    text = re.sub(r'\s+([\u093e-\u094c\u0901-\u0903\u094d])', r'\1', text)
    return re.sub(r'\s+', ' ', text).strip()

class ChhattisgarhiMMSEngine(ASREngine):
    """
    Meta MMS (facebook/mms-1b-all) for Chhattisgarhi ('hne') — Whisper doesn't cover this
    language, MMS does via a language-specific adapter on a shared Wav2Vec2 backbone.
    NOTE: this is a 1B-param model — noticeably heavier than tiny.en/small.en. Test actual
    CPU latency on your laptop before relying on it for live partials; if it's too slow,
    consider using it only for FINAL transcripts and keeping Whisper for PARTIAL in English.
    """
    def __init__(self):
        from transformers import Wav2Vec2ForCTC, AutoProcessor
        model_id = "facebook/mms-1b-all"
        self._device = "cuda" if (settings.ASR_DEVICE == "cuda" and torch.cuda.is_available()) else "cpu"
        if settings.MMS_DTYPE not in {"float32", "float16", "bfloat16"}:
            raise ValueError("STT_MMS_DTYPE must be float32, float16, or bfloat16")
        self._dtype = getattr(torch, settings.MMS_DTYPE) if self._device == "cuda" else torch.float32
        self._processor = AutoProcessor.from_pretrained(model_id)
        # Construct reduced-precision weights before moving to CUDA; converting
        # after .to(cuda) would still need room for the full float32 model.
        self._model = Wav2Vec2ForCTC.from_pretrained(model_id, torch_dtype=self._dtype)
        self._processor.tokenizer.set_target_lang("hne")
        self._model.load_adapter("hne")
        self._model.to(self._device).eval()

    def transcribe(self, audio: np.ndarray, *, fast: bool) -> Transcript:
        t0 = time.monotonic()
        inputs = self._processor(audio, sampling_rate=settings.SAMPLE_RATE, return_tensors="pt")
        inputs = {k: v.to(device=self._device, dtype=self._dtype) if v.is_floating_point()
                  else v.to(self._device) for k, v in inputs.items()}
        with torch.inference_mode():
            logits = self._model(**inputs).logits
        ids = torch.argmax(logits, dim=-1)[0]
        text = clean_mms_devanagari(self._processor.decode(ids).strip())
        return Transcript(
            text=text,
            avg_logprob=0.0,       # CTC doesn't produce this — don't rely on confidence filtering here
            no_speech_prob=0.0 if text else 1.0,  # crude proxy: empty output = treat as silence
            inference_ms=(time.monotonic() - t0) * 1000,
        )

_ENGINE_SINGLETON: ASREngine | None = None


def get_engine() -> ASREngine:
    """One model instance, shared by every concurrent session (thread-safe for inference calls)."""
    global _ENGINE_SINGLETON
    if _ENGINE_SINGLETON is None:
        if settings.ASR_LANGUAGE.lower() == "hne":
            _ENGINE_SINGLETON = ChhattisgarhiMMSEngine()
        else:
            _ENGINE_SINGLETON = FasterWhisperEngine()
    return _ENGINE_SINGLETON

def logprob_to_confidence(avg_logprob: float) -> float:
    """Rough, non-calibrated mapping of avg_logprob -> a 0..1 'confidence' for downstream UX decisions."""
    return max(0.0, min(1.0, 1.0 + avg_logprob))
