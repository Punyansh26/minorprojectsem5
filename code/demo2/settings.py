"""Resolve sibling projects and isolate demo state without changing their configuration."""
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=False)
CODE_ROOT = Path(os.getenv("DEMO2_CODE_ROOT", str(ROOT.parent))).resolve()
AGENT_ROOT = CODE_ROOT / "Institute-voice-agent/institute-assistant"
KBB_ROOT = CODE_ROOT / "knowledgebaseenhanced"
STT_ROOT = CODE_ROOT / "STT/stt-service"
TTS_ROOT = CODE_ROOT / "TTS/chattisgarhi-tts-models"
DATA_ROOT = Path(os.getenv("DEMO2_DATA_DIR", str(ROOT / "data"))).resolve()
STT_LANGUAGE = os.getenv("DEMO2_STT_LANGUAGE", "hne")
STT_DEVICE = os.getenv("DEMO2_STT_DEVICE", "cpu")
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
QUEUE_CAPACITY = int(os.getenv("DEMO2_QUEUE_CAPACITY", "3"))
QUEUE_TIMEOUT_SECONDS = float(os.getenv("DEMO2_QUEUE_TIMEOUT_SECONDS", "60"))
TURN_TIMEOUT_SECONDS = float(os.getenv("DEMO2_TURN_TIMEOUT_SECONDS", "120"))
RETENTION_SECONDS = float(os.getenv("DEMO2_RETENTION_SECONDS", "86400"))
MAINTENANCE_SECONDS = float(os.getenv("DEMO2_MAINTENANCE_SECONDS", "300"))
VOICE_CACHE_SIZE = int(os.getenv("DEMO2_VOICE_CACHE_SIZE", "2"))
VOICE_CACHE_MAX_BYTES = int(os.getenv("DEMO2_VOICE_CACHE_MAX_BYTES", "6442450944"))
MAX_RECORDING_IDS = 128
# Pre-synthesised audio cache (Task 07 A5): release/voice/speed/model-keyed rendered WAV/MP3.
# Keyed by hash(normalized_text | voice | speed | model_version | kb_release) so a KB release
# or TTS model change simply misses and regenerates — never speaks a stale answer.
TTS_CACHE_ENABLED = os.getenv("DEMO2_TTS_CACHE_ENABLED", "true").lower() == "true"
TTS_CACHE_DB_PATH = os.getenv("DEMO2_TTS_CACHE_DB_PATH", str(DATA_ROOT / "tts_cache.sqlite"))
TTS_CACHE_TTL_SECONDS = float(os.getenv("DEMO2_TTS_CACHE_TTL_SECONDS", "604800"))
TTS_CACHE_MAX_ENTRIES = int(os.getenv("DEMO2_TTS_CACHE_MAX_ENTRIES", "512"))
TTS_CACHE_MAX_ENTRY_BYTES = int(os.getenv("DEMO2_TTS_CACHE_MAX_ENTRY_BYTES", "4194304"))
TTS_CACHE_MAX_BYTES = int(os.getenv("DEMO2_TTS_CACHE_MAX_BYTES", "268435456"))
TTS_CACHE_TIMEOUT_SECONDS = float(os.getenv("DEMO2_TTS_CACHE_TIMEOUT_SECONDS", "0.2"))

# Throughput / concurrency (FutureWork 10 §1.4). T0 keeps ONE reasoning worker; these knobs
# only reorder *when* queued turns run and shed overload earlier — never change *what* a turn
# computes (grounding, caches and exact SQL cutoffs are untouched).
# Short-turn priority: a trivial turn (greeting / thanks / yes-no / very short text, 0 LLM
# calls expected) jumps ahead of a heavy knowledge turn in a second priority deque.
SHORT_TURN_PRIORITY_ENABLED = os.getenv("DEMO2_SHORT_TURN_PRIORITY", "true").lower() == "true"
SHORT_TURN_MAX_CHARS = int(os.getenv("DEMO2_SHORT_TURN_MAX_CHARS", "40"))
# Predicted heavy-turn service time S (seconds); measured answered-turn mean is ~18.7 s on T0
# (FutureWork 01 §4.1). Used only for deadline-aware shedding and observability, never to
# interrupt a running turn.
PREDICTED_HEAVY_TURN_SECONDS = float(os.getenv("DEMO2_PREDICTED_HEAVY_TURN_SECONDS", "18.7"))
PREDICTED_SHORT_TURN_SECONDS = float(os.getenv("DEMO2_PREDICTED_SHORT_TURN_SECONDS", "1.0"))
# Deadline-aware shedding: reject (fast "busy") a turn whose predicted completion time —
# (work ahead of it) + (its own predicted service) — would exceed the queue deadline, rather
# than admitting it only to fail `queue_timeout`/`deadline_exceeded` later after spending STT.
# Default OFF: it changes which turns get a fast "busy" (an operator-visible policy change on
# top of the hard capacity cap), so it is opt-in. Short-turn priority above is safe and on.
DEADLINE_SHEDDING_ENABLED = os.getenv("DEMO2_DEADLINE_SHEDDING", "false").lower() == "true"

if TTS_CACHE_TTL_SECONDS <= 0 or TTS_CACHE_MAX_ENTRIES <= 0 or TTS_CACHE_MAX_ENTRY_BYTES <= 0 \
        or TTS_CACHE_MAX_BYTES <= 0 or TTS_CACHE_TIMEOUT_SECONDS <= 0:
    raise ValueError("TTS cache limits must be positive")

if SHORT_TURN_MAX_CHARS <= 0 or PREDICTED_HEAVY_TURN_SECONDS <= 0 or PREDICTED_SHORT_TURN_SECONDS <= 0:
    raise ValueError("Throughput prediction limits must be positive")

if not 0 <= QUEUE_CAPACITY <= 16 or not 1 <= VOICE_CACHE_SIZE <= 2:
    raise ValueError("Invalid queue or voice cache size")
if any(value <= 0 for value in (QUEUE_TIMEOUT_SECONDS, TURN_TIMEOUT_SECONDS, RETENTION_SECONDS,
                                MAINTENANCE_SECONDS, VOICE_CACHE_MAX_BYTES)):
    raise ValueError("Demo runtime limits must be positive")


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
    # The knowledge base is the kbb release by default; DEMO2_KB_BACKEND=legacy follows the old kb_state instead.
    backend = os.getenv("DEMO2_KB_BACKEND", "kbb")
    if backend not in {"kbb", "legacy"}:
        raise ValueError("DEMO2_KB_BACKEND must be kbb or legacy")
    os.environ["KB_BACKEND"] = backend
    if backend == "kbb":
        os.environ["KBB_ROOT"] = str(KBB_ROOT)
        os.environ["KB_STATE_DIR"] = os.getenv("DEMO2_KBB_STATE_DIR", str(KBB_ROOT / "data/kbb/serving"))
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
