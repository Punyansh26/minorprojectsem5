"""Central settings for local speech, JSON shopping state, and Groq routing."""

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
STATE_PATH = Path(os.getenv("DEMO_STATE_PATH") or ROOT / "data/shop.json").resolve()
API_KEY = os.getenv("GROQ_API_KEY", "")
CHAT_MODEL = os.getenv("GROQ_CHAT_MODEL", "openai/gpt-oss-120b")
STT_ROOT = ROOT.parent / "STT/stt-service"
TTS_ROOT = ROOT.parent / "TTS/chattisgarhi-tts-models"
STT_ENV = {**dotenv_values(STT_ROOT / ".env"), **{k: v for k, v in os.environ.items() if k.startswith("STT_")}}
STT_LANGUAGE = STT_ENV.get("STT_LANGUAGE", "hne")
STT_DEVICE = os.getenv("DEMO_STT_DEVICE", "cuda").strip().lower()
STT_DTYPE = os.getenv("DEMO_STT_DTYPE", "float16").strip().lower()
STT_MODEL = "facebook/mms-1b-all (hne)" if STT_LANGUAGE == "hne" else STT_ENV.get("STT_MODEL_SIZE", "base")
TTS_VOICE = os.getenv("DEMO_TTS_VOICE", "Female")
TTS_DEVICE = os.getenv("DEMO_TTS_DEVICE", "cpu")
TTS_LENGTH_SCALE = float(os.getenv("DEMO_TTS_LENGTH_SCALE", "1.0"))
SPEECH_THREADS = int(os.getenv("DEMO_SPEECH_THREADS", "4"))
TTS_MAX_CHARS = 1800
SESSION_ID = os.getenv("DEMO_SESSION_ID", "inspector-demo")
TURN_ID = os.getenv("DEMO_TURN_ID", "inspector-turn")
CONFIRM_TOKEN = os.getenv("DEMO_CONFIRM_TOKEN", "")
API_TIMEOUT = 25.0
MCP_TIMEOUT = 20.0
MAX_ROUNDS = 4
MAX_QUANTITY = 100
MAX_AUDIO_BYTES = 4 * 1024 * 1024
MAX_AUDIO_SECONDS = 45
MAX_TEXT_CHARS = 1500


def configure_stt():
    """Load the existing STT configuration before its singleton is first imported."""
    if STT_DEVICE not in {"cpu", "cuda"}:
        raise ValueError("DEMO_STT_DEVICE must be cpu or cuda.")
    for name, value in STT_ENV.items():
        if name.startswith("STT_") and value is not None:
            os.environ.setdefault(name, value)
    os.environ.setdefault("STT_LANGUAGE", STT_LANGUAGE)
    if STT_DTYPE not in {"float32", "float16", "bfloat16"}:
        raise ValueError("DEMO_STT_DTYPE must be float32, float16, or bfloat16.")
    # The demo uses reduced-precision CUDA weights without changing the
    # research service's precision default.
    os.environ["STT_DEVICE"] = STT_DEVICE
    os.environ["STT_MMS_DTYPE"] = STT_DTYPE
