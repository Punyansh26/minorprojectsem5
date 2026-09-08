"""Reuse the STT engine and notebook VITS inference without requiring a running notebook."""

import io
import sys
from threading import RLock

from config import (STT_ROOT, TTS_ROOT, TTS_VOICE, TTS_DEVICE, TTS_LENGTH_SCALE,
                    SPEECH_THREADS, TTS_MAX_CHARS, STT_DEVICE, configure_stt)

# Module lifetime survives Streamlit script reruns. Serialize loading and inference,
# including the mutable VITS length_scale and MMS adapter state across browser sessions.
_LOCK = RLock()
_SYNTHESIZER = None


def recognize(pcm16: bytes) -> str:
    """Use the research engine's final decoding on an already completed browser recording."""
    import numpy as np
    with _LOCK:
        configure_stt()
        if str(STT_ROOT) not in sys.path:
            sys.path.insert(0, str(STT_ROOT))
        import torch
        if STT_DEVICE == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable. Check the NVIDIA driver and restart the app.")
        from src.asr import get_engine
        from src.config import settings
        torch.set_num_threads(SPEECH_THREADS)
        engine = get_engine()
        # The Streamlit caller is synchronous; inference does not run in an async event loop.
        transcript = engine.transcribe(np.frombuffer(pcm16, dtype="<i2").astype(np.float32) / 32768.0,
                                       fast=False)
        if transcript.no_speech_prob >= settings.NO_SPEECH_PROB_THRESHOLD:
            return ""
        return transcript.text.strip()


def speak(text: str) -> bytes:
    """Cache the same Synthesizer used in Speech2Speech.ipynb and return 22050 Hz WAV."""
    import numpy as np
    import soundfile as sf
    import torch
    from TTS.utils.synthesizer import Synthesizer

    global _SYNTHESIZER
    with _LOCK:
        if TTS_VOICE not in {"Female", "Male"}:
            raise ValueError("DEMO_TTS_VOICE must be Female or Male.")
        if TTS_DEVICE not in {"cpu", "cuda"}:
            raise ValueError("DEMO_TTS_DEVICE must be cpu or cuda.")
        if TTS_LENGTH_SCALE <= 0:
            raise ValueError("DEMO_TTS_LENGTH_SCALE must be positive.")
        torch.set_num_threads(SPEECH_THREADS)
        if _SYNTHESIZER is None:
            checkpoint = TTS_ROOT / TTS_VOICE / "best_model.pth"
            if not checkpoint.exists() or checkpoint.stat().st_size < 1024:
                raise ValueError("The local TTS checkpoint is missing or is a Git LFS pointer.")
            _SYNTHESIZER = Synthesizer(tts_checkpoint=str(checkpoint),
                                     tts_config_path=str(TTS_ROOT / TTS_VOICE / "config.json"),
                                     use_cuda=TTS_DEVICE == "cuda" and torch.cuda.is_available())
        _SYNTHESIZER.tts_model.length_scale = TTS_LENGTH_SCALE
        wav = np.asarray(_SYNTHESIZER.tts(text=text[:TTS_MAX_CHARS]), dtype=np.float32)
        if not wav.size or not np.isfinite(wav).all():
            raise ValueError("The local voice returned invalid audio.")
        buffer = io.BytesIO()
        sf.write(buffer, wav, _SYNTHESIZER.output_sample_rate, format="WAV", subtype="PCM_16")
        return buffer.getvalue()
