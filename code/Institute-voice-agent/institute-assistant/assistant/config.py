"""
Single source of truth for every setting in the project — retrieval, embeddings, the agent,
and (from Phase 2 onward) notifications and reminders. Everything overridable via .env.

Extensibility note: when a future phase needs new settings (e.g. SMTP credentials for
notify.py, or a scheduler interval for reminders), add the field here with a sensible
default — never read os.getenv() anywhere else in the codebase. One place to look, always.
"""
import os
import math
from pathlib import Path
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # --- Knowledge base / retrieval ---
    KB_DIR: str = os.getenv("KB_DIR", "knowledge_base")
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "chroma_index")
    CHROMA_COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME", "iiitnr_kb")
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "150"))
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    TOP_K: int = int(os.getenv("TOP_K", "6"))
    RETRIEVAL_FETCH_K: int = int(os.getenv("RETRIEVAL_FETCH_K", "32"))
    RETRIEVAL_MAX_DISTANCE: float = float(os.getenv("RETRIEVAL_MAX_DISTANCE", "1.5"))
    MAX_CONTEXT_CHARS: int = int(os.getenv("MAX_CONTEXT_CHARS", "14000"))
    # Deprecated message count is read only when HISTORY_TURNS is not configured.
    HISTORY_MESSAGES: int = int(os.getenv("HISTORY_MESSAGES", "20"))
    HISTORY_TURNS: int | None = int(os.environ["HISTORY_TURNS"]) if "HISTORY_TURNS" in os.environ else None
    HISTORY_MAX_CHARS: int = int(os.getenv("HISTORY_MAX_CHARS", "12000"))
    RAG_CACHE_ENABLED: bool = os.getenv("RAG_CACHE_ENABLED", "true").lower() == "true"
    RAG_CACHE_DB_PATH: str = os.getenv("RAG_CACHE_DB_PATH", "rag_cache.sqlite")
    RAG_CACHE_TTL_SECONDS: float = float(os.getenv("RAG_CACHE_TTL_SECONDS", "3600"))
    RAG_CACHE_MAX_ENTRIES: int = int(os.getenv("RAG_CACHE_MAX_ENTRIES", "2000"))
    RAG_CACHE_MAX_ENTRY_BYTES: int = int(os.getenv("RAG_CACHE_MAX_ENTRY_BYTES", "131072"))
    RAG_CACHE_MAX_BYTES: int = int(os.getenv("RAG_CACHE_MAX_BYTES", "67108864"))
    RAG_CACHE_TIMEOUT_SECONDS: float = float(os.getenv("RAG_CACHE_TIMEOUT_SECONDS", "0.1"))
    # Versioned corpus releases are shared by the CLI and Demo 2 through KB_DIR.
    KB_STATE_DIR: str = os.getenv("KB_STATE_DIR", str(Path(os.getenv("KB_DIR", "knowledge_base")).resolve().parent / "kb_state"))
    # "legacy" = releases built by kb_pipeline.py in KB_STATE_DIR; "kbb" = releases built by the kbb package
    # (code/knowledgebaseenhanced).  A release declares its own engine in release.json; this setting only
    # tells callers such as Demo 2 which state directory to follow.
    KB_BACKEND: str = os.getenv("KB_BACKEND", "legacy")
    KBB_STATE_DIR: str = os.getenv("KBB_STATE_DIR", str(Path(__file__).resolve().parents[3] / "knowledgebaseenhanced" / "data" / "kbb" / "serving"))
    KB_EMBEDDING_MODEL: str = os.getenv("KB_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    KB_EMBEDDING_REVISION: str = os.getenv("KB_EMBEDDING_REVISION", "614241f622f53c4eeff9890bdc4f31cfecc418b3")
    KB_CHUNK_TOKENS: int = int(os.getenv("KB_CHUNK_TOKENS", "350"))
    KB_OVERLAP_TOKENS: int = int(os.getenv("KB_OVERLAP_TOKENS", "50"))
    KB_BATCH_SIZE: int = int(os.getenv("KB_BATCH_SIZE", "32"))
    KB_OCR_DPI: int = int(os.getenv("KB_OCR_DPI", "300"))
    KB_HTTP_TIMEOUT: int = int(os.getenv("KB_HTTP_TIMEOUT", "20"))
    KB_MAX_DOWNLOAD_BYTES: int = int(os.getenv("KB_MAX_DOWNLOAD_BYTES", "60000000"))
    KB_MAX_SOURCES: int = int(os.getenv("KB_MAX_SOURCES", "160"))
    KB_THREADS: int = int(os.getenv("KB_THREADS", "4"))
    MAX_QUESTION_CHARS: int = int(os.getenv("MAX_QUESTION_CHARS", "2000"))

    # --- Categories — must match folder names under KB_DIR. Adding a new category is just
    # creating a new folder AND adding its name here (used for classification + CG-style gating). ---
    CATEGORIES: tuple = ("admissions", "hostel", "cg_counselling", "academics", "general")

    # Local Open Jev is opt-in; enabled mode also requires a passing activation record.
    JEV_ROUTING_MODE: str = os.getenv("JEV_ROUTING_MODE", "off")
    JEV_ARTIFACT_DIR: str = os.getenv("JEV_ARTIFACT_DIR", str(Path.home() / ".cache/institute-assistant/open-jev/pilot-v1"))
    JEV_CPU_THREADS: int = int(os.getenv("JEV_CPU_THREADS", "2"))
    JEV_TIMEOUT_SECONDS: float = float(os.getenv("JEV_TIMEOUT_SECONDS", "10"))

    # Laya System 1 routing (JEV_ROUTING_MODE=laya). Laya runs as an isolated
    # laya-serve process (its own transformers 5.x), so the shared model stack is
    # untouched; the agent reaches it over the Jev-compatible /v1/systemone HTTP wire.
    # No artifact or activation is required -- Laya is a published zero-shot checkpoint.
    LAYA_BASE_URL: str = os.getenv("LAYA_BASE_URL", "http://127.0.0.1:8077")
    LAYA_PROBABILITY_THRESHOLD: float = float(os.getenv("LAYA_PROBABILITY_THRESHOLD", "0.5"))
    LAYA_CONFIDENCE_THRESHOLD: float = float(os.getenv("LAYA_CONFIDENCE_THRESHOLD", "0.5"))
    LAYA_REWRITE_THRESHOLD: float = float(os.getenv("LAYA_REWRITE_THRESHOLD", "0.5"))

    # --- LLM providers (local by default; cloud is explicitly selected) ---
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
    OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
    OLLAMA_TIMEOUT_SECONDS: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    OLLAMA_KEEP_ALIVE: str = os.getenv("OLLAMA_KEEP_ALIVE", "5m")
    # Local decode budget (num_predict). Answers are 1-3 short sentences plus <=8 evidence
    # quotes, so a tight budget bounds worst-case decode and the p95 tail without truncating
    # real answers (a "length" stop fails safe to unavailable). Kept separate from
    # LLM_MAX_TOKENS, which still reserves context headroom for draft+review. See 05 §E.2.
    OLLAMA_NUM_PREDICT: int = int(os.getenv("OLLAMA_NUM_PREDICT", "512"))
    OLLAMA_TOKENIZER_PATH: str = os.getenv("OLLAMA_TOKENIZER_PATH", str(
        Path(__file__).resolve().parent.parent / ".cache" / (OLLAMA_MODEL.split(":")[0] + "-tokenizer.json")))
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_CHAT_MODEL: str = os.getenv("GROQ_CHAT_MODEL", "openai/gpt-oss-120b")
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "0"))
    LLM_RATE_LIMIT_MAX_WAIT_SECONDS: float = float(os.getenv("LLM_RATE_LIMIT_MAX_WAIT_SECONDS", "45"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1600"))
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")
    REMINDERS_ENABLED: bool = os.getenv("REMINDERS_ENABLED", "false").lower() == "true"

    # --- Agent memory & escalation ---
    CHECKPOINT_DB_PATH: str = os.getenv("CHECKPOINT_DB_PATH", "agent_memory.sqlite")
    CHECKPOINT_TIMEOUT_SECONDS: float = float(os.getenv("CHECKPOINT_TIMEOUT_SECONDS", "0.25"))
    ESCALATION_LOG_PATH: str = os.getenv("ESCALATION_LOG_PATH", "escalations.json")

    # --- Phase 2: escalation email drafting + sending ---
    TICKETS_DB_PATH: str = os.getenv("TICKETS_DB_PATH", "tickets.sqlite")

    # --- Phase 4: knowledge base gap analysis ---
    # How similar (cosine similarity, 0-1) two questions must be to count as "the same gap."
    # Higher = stricter grouping (fewer, tighter clusters); lower = looser grouping.
    GAP_SIMILARITY_THRESHOLD: float = float(os.getenv("GAP_SIMILARITY_THRESHOLD", "0.75"))
    GAP_REPORTS_DIR: str = os.getenv("GAP_REPORTS_DIR", "gap_reports")
    
    # SMTP for actually sending approved emails. Use a project-dedicated email account with an
    # "app password" (Gmail: Account Settings -> Security -> App Passwords) — never your real
    # personal or institute email credentials here.
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_TIMEOUT_SECONDS: float = float(os.getenv("SMTP_TIMEOUT_SECONDS", "20"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_APP_PASSWORD: str = os.getenv("SMTP_APP_PASSWORD", "")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "IIIT-NR Institute Assistant")

    # Which real office email each category's escalations get drafted to. Edit these to your
    # actual office addresses before using this for real — these are placeholders.
    OFFICE_EMAILS: dict = None  # set below, dataclass fields can't have mutable defaults directly

    def __post_init__(self):
        if self.KB_BACKEND not in {"legacy", "kbb"}:
            raise ValueError("KB_BACKEND must be legacy or kbb")
        if self.JEV_ROUTING_MODE not in {"off", "shadow", "enabled", "laya"}:
            raise ValueError("JEV_ROUTING_MODE must be off, shadow, enabled or laya")
        if not 1 <= self.JEV_CPU_THREADS <= 8:
            raise ValueError("JEV_CPU_THREADS must be between 1 and 8")
        if not math.isfinite(self.JEV_TIMEOUT_SECONDS) or not 0 < self.JEV_TIMEOUT_SECONDS <= 30:
            raise ValueError("JEV_TIMEOUT_SECONDS must be finite and between 0 and 30")
        if not self.LAYA_BASE_URL.startswith(("http://", "https://")):
            raise ValueError("LAYA_BASE_URL must be an http(s) URL")
        for name in ("LAYA_PROBABILITY_THRESHOLD", "LAYA_CONFIDENCE_THRESHOLD", "LAYA_REWRITE_THRESHOLD"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be a probability between 0 and 1")
        if self.LLM_PROVIDER not in {"ollama", "groq"}:
            raise ValueError("LLM_PROVIDER must be ollama or groq")
        if not self.OLLAMA_BASE_URL.startswith(("http://", "https://")) or not self.OLLAMA_MODEL.strip():
            raise ValueError("Configure an Ollama HTTP URL and model")
        if self.OLLAMA_NUM_CTX <= 2 * self.LLM_MAX_TOKENS + 512:
            raise ValueError("OLLAMA_NUM_CTX must reserve room for prompts, draft and review output")
        if not 0 < self.OLLAMA_NUM_PREDICT <= self.LLM_MAX_TOKENS:
            raise ValueError("OLLAMA_NUM_PREDICT must be positive and within the reserved LLM_MAX_TOKENS headroom")
        if not math.isfinite(self.OLLAMA_TIMEOUT_SECONDS) or self.OLLAMA_TIMEOUT_SECONDS <= 0:
            raise ValueError("OLLAMA_TIMEOUT_SECONDS must be finite and positive")
        if not 0 <= self.KB_OVERLAP_TOKENS < self.KB_CHUNK_TOKENS <= 450:
            raise ValueError("Use 0 <= KB_OVERLAP_TOKENS < KB_CHUNK_TOKENS <= 450")
        for name in ("KB_BATCH_SIZE", "KB_OCR_DPI", "KB_HTTP_TIMEOUT", "KB_MAX_DOWNLOAD_BYTES", "KB_MAX_SOURCES", "KB_THREADS"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in ("TOP_K", "RETRIEVAL_FETCH_K", "MAX_CONTEXT_CHARS", "HISTORY_MESSAGES",
                     "CHECKPOINT_TIMEOUT_SECONDS",
                     "HISTORY_MAX_CHARS", "RAG_CACHE_TTL_SECONDS", "RAG_CACHE_MAX_ENTRIES",
                     "RAG_CACHE_MAX_ENTRY_BYTES", "RAG_CACHE_TIMEOUT_SECONDS",
                     "RAG_CACHE_MAX_BYTES",
                     "MAX_QUESTION_CHARS", "CHUNK_SIZE", "LLM_MAX_TOKENS",
                     "LLM_TIMEOUT_SECONDS", "SMTP_TIMEOUT_SECONDS", "RETRIEVAL_MAX_DISTANCE"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.HISTORY_MESSAGES < 2 or not 0 <= self.CHUNK_OVERLAP < self.CHUNK_SIZE:
            raise ValueError("Use HISTORY_MESSAGES >= 2 and 0 <= CHUNK_OVERLAP < CHUNK_SIZE")
        if self.HISTORY_TURNS is not None and self.HISTORY_TURNS < 1:
            raise ValueError("HISTORY_TURNS must be positive")
        if self.LLM_MAX_RETRIES < 0:
            raise ValueError("LLM_MAX_RETRIES must be nonnegative")
        if not math.isfinite(self.LLM_RATE_LIMIT_MAX_WAIT_SECONDS) or not 0 <= self.LLM_RATE_LIMIT_MAX_WAIT_SECONDS <= 60:
            raise ValueError("LLM_RATE_LIMIT_MAX_WAIT_SECONDS must be between 0 and 60")
        ZoneInfo(self.TIMEZONE)
        object.__setattr__(self, "OFFICE_EMAILS", {
            "admissions": os.getenv("OFFICE_EMAIL_ADMISSIONS", "admissions@iiitnr.example.edu"),
            "hostel": os.getenv("OFFICE_EMAIL_HOSTEL", "hostel@iiitnr.example.edu"),
            "cg_counselling": os.getenv("OFFICE_EMAIL_CG", "cgcounselling@iiitnr.example.edu"),
            "academics": os.getenv("OFFICE_EMAIL_ACADEMICS", "academics@iiitnr.example.edu"),
            "general": os.getenv("OFFICE_EMAIL_GENERAL", "helpdesk@iiitnr.example.edu"),
            "other": os.getenv("OFFICE_EMAIL_GENERAL", "helpdesk@iiitnr.example.edu"),
        })

    @property
    def history_turns(self) -> int:
        """Honor explicit pair counts while accepting older message-count configuration."""
        return self.HISTORY_TURNS if self.HISTORY_TURNS is not None else self.HISTORY_MESSAGES // 2


settings = Settings()
