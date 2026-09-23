"""Reuse the STT singleton and the notebook's VITS synthesizer for completed audio turns."""
import io
import asyncio
import contextlib
import subprocess
import json
import re
import sys
import unicodedata
from math import gcd
from threading import RLock

import numpy as np
import soundfile as sf

import settings as cfg

_LOCK = RLock()
_SYNTHESIZER = None
_VOICE = None
_WHISPER = None
_DIGITS = "शून्य एक दो तीन चार पाँच छह सात आठ नौ".split()


def decode_audio(data: bytes) -> np.ndarray:
    """Bound decoding memory and normalize browser WAV or uploaded audio to STT PCM."""
    if not data or len(data) > cfg.MAX_AUDIO_BYTES:
        raise ValueError("Use a WAV/FLAC recording smaller than 12 MB.")
    try:
        with sf.SoundFile(io.BytesIO(data)) as source:
            rate = source.samplerate
            duration = len(source) / rate
            if not cfg.MIN_AUDIO_SECONDS <= duration <= cfg.MAX_AUDIO_SECONDS:
                raise ValueError(f"Record between {cfg.MIN_AUDIO_SECONDS} and {cfg.MAX_AUDIO_SECONDS} seconds.")
            if source.channels > 2 or rate > 192000:
                raise ValueError("Use mono or stereo audio at 192 kHz or below.")
            audio = source.read(dtype="float32", always_2d=True).mean(axis=1)
    except (sf.LibsndfileError, RuntimeError) as error:
        raise ValueError("This recording cannot be decoded. Upload a WAV or FLAC file.") from error
    if not np.isfinite(audio).all():
        raise ValueError("The recording contains invalid audio samples.")
    if rate != cfg.SAMPLE_RATE:
        from scipy.signal import resample_poly
        divisor = gcd(rate, cfg.SAMPLE_RATE)
        audio = resample_poly(audio, cfg.SAMPLE_RATE // divisor, rate // divisor)
    return np.ascontiguousarray(np.clip(audio, -1, 1), dtype=np.float32)


def transcribe(data: bytes, language: str = "Hindi") -> str:
    """Decode only a completed recording; silence never reaches the agent."""
    audio = decode_audio(data)
    if float(np.sqrt(np.mean(audio ** 2))) < cfg.SILENCE_RMS:
        return ""
    with _LOCK:
        cfg.configure_stt()
        if language not in cfg.INPUT_LANGUAGES:
            raise ValueError("Choose a supported recording language.")
        if not language.startswith("Chhattisgarhi"):
            global _WHISPER
            import torch
            from faster_whisper import WhisperModel
            if _WHISPER is None:
                device = cfg.STT_DEVICE
                if device == "auto":
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                try:
                    _WHISPER = WhisperModel(cfg.WHISPER_MODEL, device=device,
                        compute_type="float16" if device == "cuda" else "int8",
                        cpu_threads=cfg.SPEECH_THREADS)
                except RuntimeError as error:
                    if cfg.STT_DEVICE != "auto" or not re.search(r"cuda|cublas|cudnn", str(error), re.I):
                        raise
                    _WHISPER = WhisperModel(cfg.WHISPER_MODEL, device="cpu", compute_type="int8",
                                            cpu_threads=cfg.SPEECH_THREADS)
            def recognize():
                segments, _ = _WHISPER.transcribe(audio,
                    language={"Hindi": "hi", "English": "en", "Hinglish": None}[language],
                    beam_size=5, vad_filter=True, condition_on_previous_text=False,
                    initial_prompt="IIIT Naya Raipur, admissions, hostel, fees, प्रवेश, शुल्क")
                return " ".join(s.text.strip() for s in segments if s.no_speech_prob < 0.6).strip()
            try:
                return recognize()
            except RuntimeError as error:
                # Torch CUDA availability does not establish CTranslate2 CUDA compatibility.
                if cfg.STT_DEVICE != "auto" or not re.search(r"cuda|cublas|cudnn", str(error), re.I):
                    raise
                _WHISPER = WhisperModel(cfg.WHISPER_MODEL, device="cpu", compute_type="int8",
                                        cpu_threads=cfg.SPEECH_THREADS)
                return recognize()
        if str(cfg.STT_ROOT) not in sys.path:
            sys.path.insert(0, str(cfg.STT_ROOT))
        from src.asr import get_engine
        from src.config import settings
        result = get_engine().transcribe(audio, fast=False)
        return "" if result.no_speech_prob >= settings.NO_SPEECH_PROB_THRESHOLD else result.text.strip()


def prepare_speech(text: str, voice: str, translator=None) -> str:
    """Prevent VITS from silently dropping Latin names, numbers or unsupported symbols."""
    if voice not in cfg.VOICES:
        raise ValueError("Select a Female or Male voice.")
    if not text.strip() or len(text) > cfg.MAX_SPEECH_CHARS:
        raise ValueError("The answer is empty or too long for speech.")
    text = unicodedata.normalize("NFC", text)
    text = "".join(str(unicodedata.digit(c)) if c.isdecimal() else c for c in text)
    if re.search(r"[A-Za-z]", text):
        if translator is None:
            from agent_bridge import render_hindi
            translator = render_hindi
        original_numbers = re.findall(r"\d+", text)
        text = translator(text)
        if re.search(r"[A-Za-z]", text) or re.findall(r"\d+", text) != original_numbers:
            raise ValueError("Speech rendering changed a number or left English text. Read the original answer below.")
    text = text.replace("₹", " रुपये ").replace("%", " प्रतिशत ").replace("/", " स्लैश ")
    text = re.sub(r"\d", lambda m: " " + _DIGITS[int(m[0])] + " ", text)
    text = re.sub(r"[*_`#]", "", text)
    text = text.translate(str.maketrans({"“": '"', "”": '"', "’": "'", "–": "-", "—": "-"}))
    text = re.sub(r"\s+", " ", text).strip()
    config = json.loads((cfg.TTS_ROOT / voice / "config.json").read_text())
    chars = config["characters"]
    supported = set(chars["characters"] + chars["punctuations"] + " ")
    unsupported = set(text) - supported
    if unsupported or not re.search(r"[\u0900-\u097f]", text):
        raise ValueError("The local voice cannot pronounce part of this answer. The full text is available below.")
    if len(text) > cfg.MAX_SPEECH_CHARS:
        raise ValueError("The spoken answer is too long. Ask a shorter follow-up question.")
    return text


def _chunks(text: str) -> list[str]:
    chunks, current = [], ""
    for word in text.split():
        if len(word) > cfg.TTS_CHUNK_CHARS:
            raise ValueError("A word is too long for the voice model.")
        if current and len(current) + len(word) + 1 > cfg.TTS_CHUNK_CHARS:
            chunks.append(current)
            current = ""
        current = (current + " " + word).strip()
        if re.search(r"[।!?]$", word):
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


def synthesize(text: str, voice: str = "Female", length_scale: float = 1.0) -> bytes:
    """Return WAV bytes at the model's rate, with one cached voice and serialized inference."""
    global _SYNTHESIZER, _VOICE
    if voice not in cfg.VOICES or not 0.7 <= length_scale <= 1.5:
        raise ValueError("Invalid voice or speaking pace.")
    if not text.strip() or len(text) > cfg.MAX_SPEECH_CHARS:
        raise ValueError("The spoken answer is empty or too long.")
    with _LOCK:
        cfg.configure_agent()
        import torch
        from TTS.utils.synthesizer import Synthesizer
        if cfg.TTS_DEVICE not in {"cpu", "cuda"}:
            raise ValueError("DEMO2_TTS_DEVICE must be cpu or cuda.")
        if cfg.TTS_DEVICE == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA is unavailable. Set DEMO2_TTS_DEVICE=cpu and restart.")
        torch.set_num_threads(cfg.SPEECH_THREADS)
        if _SYNTHESIZER is None or _VOICE != voice:
            checkpoint = cfg.TTS_ROOT / voice / "best_model.pth"
            if not checkpoint.is_file() or checkpoint.stat().st_size < 1024:
                raise ValueError("Download the local VITS checkpoint; it is missing or a Git LFS pointer.")
            _SYNTHESIZER = None
            _VOICE = None
            _SYNTHESIZER = Synthesizer(tts_checkpoint=str(checkpoint),
                tts_config_path=str(checkpoint.with_name("config.json")),
                use_cuda=cfg.TTS_DEVICE == "cuda")
            _VOICE = voice
        _SYNTHESIZER.tts_model.length_scale = length_scale
        rate = _SYNTHESIZER.output_sample_rate
        pieces = []
        for chunk in _chunks(text):
            # Coqui prints the submitted text; suppress that so conversations stay out of logs.
            with contextlib.redirect_stdout(io.StringIO()):
                wav = np.asarray(_SYNTHESIZER.tts(text=chunk), dtype=np.float32)
            if not wav.size or not np.isfinite(wav).all():
                raise ValueError("The voice model produced invalid audio.")
            if pieces:
                pieces.append(np.zeros(int(rate * cfg.TTS_PAUSE_SECONDS), dtype=np.float32))
            pieces.append(wav)
        buffer = io.BytesIO()
        sf.write(buffer, np.concatenate(pieces), rate, format="WAV", subtype="PCM_16")
        return buffer.getvalue()


async def _edge_audio(text: str, voice: str, speed: float) -> bytes:
    import edge_tts
    rate = f"{round((speed - 1) * 100):+d}%"

    async def collect():
        audio = bytearray()
        async for chunk in edge_tts.Communicate(text, voice, rate=rate,
                                               connect_timeout=10, receive_timeout=20).stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
        if not audio:
            raise RuntimeError("Online speech returned no audio.")
        return bytes(audio)

    return await asyncio.wait_for(collect(), timeout=cfg.EDGE_TIMEOUT_SECONDS)


def make_audio(text: str, language: str, voice: str, speed: float = 1.0, *, provider: str | None = None) -> dict:
    """Route speech by answer language, keeping audio retry independent of agent actions."""
    if voice not in cfg.VOICES or not 0.7 <= speed <= 1.4:
        raise ValueError("Choose a supported voice and speed.")
    if not text.strip() or len(text) > cfg.MAX_SPEECH_CHARS:
        raise ValueError("The answer is empty or too long for speech.")
    if language == "hindi":
        from agent_bridge import render_hindi
        spoken = prepare_speech(text, voice, lambda value: render_hindi(value, provider=provider))
        return {"data": synthesize(spoken, voice, 1 / speed), "mime": "audio/wav",
                "extension": "wav", "spoken_text": spoken, "provider": "Local VITS"}
    if language not in cfg.EDGE_VOICES:
        raise ValueError("This answer language is unavailable for speech.")
    spoken = text
    if language == "hinglish":
        from agent_bridge import render_speech
        spoken = render_speech(text, language, provider=provider)
        if re.findall(r"\d+", spoken) != re.findall(r"\d+", text):
            raise ValueError("Speech rendering changed a number. Read the original answer below.")
    audio = online_audio(spoken, cfg.EDGE_VOICES[language][voice], speed)
    return {"data": audio, "mime": "audio/mpeg", "extension": "mp3",
            "spoken_text": spoken, "provider": "Online voice"}


def online_audio(text: str, voice: str, speed: float) -> bytes:
    """Bound online synthesis even when DNS cancellation hangs an asyncio worker thread."""
    result = subprocess.run([sys.executable, str(cfg.ROOT / "online_voice.py")],
        input=json.dumps({"text": text, "voice": voice, "speed": speed}).encode(),
        capture_output=True, timeout=cfg.EDGE_TIMEOUT_SECONDS, check=True)
    if not result.stdout:
        raise RuntimeError("Online speech returned no audio.")
    return result.stdout
