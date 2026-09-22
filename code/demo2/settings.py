"""Resolve sibling projects and isolate demo state without changing their configuration."""
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=False)
CODE_ROOT = Path(os.getenv("DEMO2_CODE_ROOT", str(ROOT.parent))).resolve()
AGENT_ROOT = CODE_ROOT / "Institute-voice-agent/institute-assistant"
STT_ROOT = CODE_ROOT / "STT/stt-service"
TTS_ROOT = CODE_ROOT / "TTS/chattisgarhi-tts-models"
DATA_ROOT = Path(os.getenv("DEMO2_DATA_DIR", str(ROOT / "data"))).resolve()
STT_LANGUAGE = os.getenv("DEMO2_STT_LANGUAGE", "hne")
STT_DEVICE = os.getenv("DEMO2_STT_DEVICE", "auto")
WHISPER_MODEL = os.getenv("DEMO2_WHISPER_MODEL", "small")
TTS_DEVICE = os.getenv("DEMO2_TTS_DEVICE", "cpu")
SPEECH_THREADS = int(os.getenv("DEMO2_SPEECH_THREADS", "4"))
SAMPLE_RATE = 16000
MAX_AUDIO_SECONDS = 30
MAX_AUDIO_BYTES = 12 * 1024 * 1024
MAX_TEXT_CHARS = 2000
MAX_SPEECH_CHARS = 4000
MAX_HISTORY_TURNS = 12
MIN_AUDIO_SECONDS = 0.3
SILENCE_RMS = 0.002
TTS_CHUNK_CHARS = 220
TTS_PAUSE_SECONDS = 0.12
VOICES = ("Female", "Male")
INPUT_LANGUAGES = ("Hindi", "English", "Hinglish", "Chhattisgarhi (experimental)")
EDGE_VOICES = {
    "english": {"Female": "en-IN-NeerjaNeural", "Male": "en-IN-PrabhatNeural"},
    "hinglish": {"Female": "hi-IN-SwaraNeural", "Male": "hi-IN-MadhurNeural"},
}
EDGE_TIMEOUT_SECONDS = 45


def configure_agent():
    """Load existing credentials, but keep demo tickets and checkpoints in demo2."""
    if not (AGENT_ROOT / "assistant/graph.py").is_file():
        raise FileNotFoundError("Institute agent is missing. Check DEMO2_CODE_ROOT in .env.")
    values = dotenv_values(AGENT_ROOT / ".env")
    for key, value in values.items():
        if value is not None:
            os.environ.setdefault(key, value)
    for key, default in (("KB_DIR", "knowledge_base"), ("CHROMA_PERSIST_DIR", "chroma_index")):
        path = Path(os.environ.get(key, default))
        os.environ[key] = str(path if path.is_absolute() else AGENT_ROOT / path)
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    for key, name in (("CHECKPOINT_DB_PATH", "conversations.sqlite"),
                      ("TICKETS_DB_PATH", "tickets.sqlite"),
                      ("RAG_CACHE_DB_PATH", "rag_cache.sqlite"),
                      ("ESCALATION_LOG_PATH", "escalations.json")):
        os.environ[key] = str(DATA_ROOT / name)
    os.environ["REMINDERS_ENABLED"] = "false"
    os.environ.setdefault("HISTORY_TURNS", "10")
    os.environ.setdefault("NUMBA_CACHE_DIR", str(DATA_ROOT / "numba_cache"))
    os.environ.setdefault("MPLCONFIGDIR", str(DATA_ROOT / "matplotlib"))


def configure_stt():
    """Set the research service's environment before its singleton is imported."""
    import torch
    if STT_DEVICE not in {"auto", "cpu", "cuda"}:
        raise ValueError("DEMO2_STT_DEVICE must be auto, cpu, or cuda.")
    if STT_DEVICE == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA is unavailable. Set DEMO2_STT_DEVICE=cpu and restart.")
    for key, value in dotenv_values(STT_ROOT / ".env").items():
        if key.startswith("STT_") and value is not None:
            os.environ.setdefault(key, value)
    device = ("cuda" if torch.cuda.is_available() else "cpu") if STT_DEVICE == "auto" else STT_DEVICE
    os.environ["STT_DEVICE"] = device
    os.environ["STT_LANGUAGE"] = STT_LANGUAGE
    os.environ.setdefault("STT_MMS_DTYPE", "float16" if device == "cuda" else "float32")
    os.environ["STT_INITIAL_PROMPT"] = "IIIT Naya Raipur, admissions, hostel, fees, छात्रावास, प्रवेश, शुल्क"
    os.environ.setdefault("NUMBA_CACHE_DIR", str(DATA_ROOT / "numba_cache"))
    torch.set_num_threads(SPEECH_THREADS)
