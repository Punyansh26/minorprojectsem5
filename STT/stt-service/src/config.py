"""
Central configuration for the STT service.
Everything tunable lives here and is overridable via environment variables,
so you never hunt through code to change a model size or a timing constant.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    # --- Audio format (fixed contract with clients) ---
    SAMPLE_RATE: int = int(os.getenv("STT_SAMPLE_RATE", "16000"))  # Hz, mono, 16-bit PCM
    FRAME_MS: int = 32  # size of each VAD analysis frame in ms (silero wants 512 samples @16k = 32ms)

    # --- ASR model ---
    # "tiny.en" / "base.en" / "small.en" / "medium.en" / "large-v3" (use *.en for English-only, it's faster+more accurate)
    ASR_MODEL_SIZE: str = os.getenv("STT_MODEL_SIZE", "small.en")
    ASR_DEVICE: str = os.getenv("STT_DEVICE", "cpu")            # "cpu" or "cuda"
    ASR_COMPUTE_TYPE: str = os.getenv("STT_COMPUTE_TYPE", "int8")  # "int8" (cpu) / "float16" (gpu) / "int8_float16"
    ASR_BEAM_SIZE: int = int(os.getenv("STT_BEAM_SIZE", "1"))    # 1 = greedy (fast, for partials). Use 5 for finals.
    ASR_FINAL_BEAM_SIZE: int = int(os.getenv("STT_FINAL_BEAM_SIZE", "5"))
    ASR_LANGUAGE: str = os.getenv("STT_LANGUAGE", "en")

    # --- VAD (Silero) ---
    VAD_THRESHOLD: float = float(os.getenv("STT_VAD_THRESHOLD", "0.5"))  # speech probability threshold
    VAD_MIN_SILENCE_MS: int = int(os.getenv("STT_VAD_MIN_SILENCE_MS", "100"))

    # --- Endpointing (turn-taking logic) ---
    # How long of continuous silence before we consider the utterance "done" and emit a final transcript.
    END_OF_SPEECH_SILENCE_MS: int = int(os.getenv("STT_EOS_SILENCE_MS", "600"))
    # Safety cap: force-finalize if someone talks for this long without pausing (avoid unbounded buffers).
    MAX_UTTERANCE_MS: int = int(os.getenv("STT_MAX_UTTERANCE_MS", "20000"))
    # How often (ms) to emit a partial transcript while the user is still speaking.
    PARTIAL_INTERVAL_MS: int = int(os.getenv("STT_PARTIAL_INTERVAL_MS", "700"))
    # Minimum ms of buffered speech before we bother emitting a partial (avoid transcribing 1 phoneme).
    MIN_SPEECH_MS_FOR_PARTIAL: int = int(os.getenv("STT_MIN_SPEECH_MS_FOR_PARTIAL", "300"))
    # Only the LAST N ms of the buffer is re-transcribed for partials — without this, a caller who
    # talks for 15s makes every partial call slower and slower because it re-processes all 15s each
    # time. Finals always use the FULL utterance buffer regardless of this setting.
    PARTIAL_WINDOW_MS: int = int(os.getenv("STT_PARTIAL_WINDOW_MS", "6000"))

    # --- Domain vocabulary biasing ---
    # Whisper reads this as a "hint" of prior context, which measurably improves recognition of
    # proper nouns / domain terms it would otherwise mishear (clinician names, procedures, etc.)
    # Set this per-deployment. Example for a dental clinic below.
    ASR_INITIAL_PROMPT: str = os.getenv(
        "STT_INITIAL_PROMPT",
        "Appointment booking call. Mentions of dentist, dental cleaning, root canal, filling, "
        "checkup, braces, extraction, insurance, morning, afternoon, evening, AM, PM, "
        "Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday, reschedule, cancel.",
    )
    # Above this, we treat a "final" transcript as hallucinated (often an echo of the initial
    # prompt) rather than real speech, and drop it instead of sending it to the LLM. Whisper
    # tends to do this on near-silent/noise-only audio segments that VAD let through.
    NO_SPEECH_PROB_THRESHOLD: float = float(os.getenv("STT_NO_SPEECH_PROB_THRESHOLD", "0.6"))
    # Minimum buffered audio before we even attempt a final transcription — segments shorter
    # than this are almost always a VAD blip (cough, click, breath), not real speech.
    MIN_FINAL_AUDIO_MS: int = int(os.getenv("STT_MIN_FINAL_AUDIO_MS", "300"))

    # --- Server ---
    HOST: str = os.getenv("STT_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("STT_PORT", "8000"))
    LOG_LEVEL: str = os.getenv("STT_LOG_LEVEL", "INFO")

    # --- Auth ---
    # If set, clients must connect with ?api_key=<value> in the WebSocket URL. Leave blank only
    # for local-only development; ALWAYS set this before exposing the server past localhost.
    API_KEY: str = os.getenv("STT_API_KEY", "")

    # --- Concurrency & resource protection ---
    # Number of worker threads for running (blocking) ASR inference off the asyncio event loop.
    ASR_WORKER_THREADS: int = int(os.getenv("STT_ASR_WORKER_THREADS", "4"))
    # Hard cap on simultaneous live calls this process will accept. Past this, new connections
    # are rejected immediately with a clear error instead of the server slowing down for everyone
    # already on a call. Size this to your hardware (see README "Capacity planning").
    MAX_CONCURRENT_SESSIONS: int = int(os.getenv("STT_MAX_CONCURRENT_SESSIONS", "8"))
    # If a connected client sends no audio at all for this long, the server closes the session.
    # Protects against dropped connections / bad clients holding a slot open forever.
    IDLE_TIMEOUT_S: int = int(os.getenv("STT_IDLE_TIMEOUT_S", "30"))

    # --- WebSocket keepalive ---
    # Uvicorn pings the client periodically to detect dead connections. If the server's event loop
    # is busy long enough — heavy CPU inference bursts on a slower machine can do this — it can miss
    # the ping window and the connection gets force-closed with a confusing socket error that has
    # nothing to do with your actual audio/transcription code (Windows in particular surfaces this
    # as "WinError 64: network name is no longer available"). We already have our own IDLE_TIMEOUT_S
    # for detecting genuinely dead sessions, so these can be generous.
    WS_PING_INTERVAL_S: float = float(os.getenv("STT_WS_PING_INTERVAL_S", "20"))
    WS_PING_TIMEOUT_S: float = float(os.getenv("STT_WS_PING_TIMEOUT_S", "60"))


settings = Settings()
