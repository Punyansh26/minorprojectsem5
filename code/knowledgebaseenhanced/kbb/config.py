"""Typed configuration: defaults here, overrides from ``kbb.yaml`` and ``KBB_*`` env vars.

Precedence (last wins): built-in defaults → ``kbb.yaml`` (or ``$KBB_CONFIG``) → environment
variables of the form ``KBB_<SECTION>__<FIELD>`` (double underscore separates nesting), e.g.
``KBB_LLM__MODEL=qwen3.5:4b`` or ``KBB_RUNTIME__CPU_WORKERS=4``.

Every threshold the pipeline uses lives here so that evaluation runs are reproducible: the
hash of the *relevant* config subset is part of each stage's cache key (see
``Config.fingerprint``).
"""
from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent          # code/knowledgebaseenhanced
LEGACY_ROOT = ROOT.parent / "Institute-voice-agent" / "institute-assistant"


class Paths(BaseModel):
    """Where sources come from and where every generated artefact goes."""
    sources: list[Path] = [ROOT / "data" / "knowledge_base"]
    # JSON/YAML files with per-file metadata. ``kb_sources.json`` ("local_sources" keyed by
    # path relative to a source root) is understood natively.
    metadata_files: list[Path] = [LEGACY_ROOT / "kb_sources.json", ROOT / "config" / "sources_meta.yaml"]
    work: Path = ROOT / "data" / "kbb"                  # all generated artefacts (git-ignored)
    prompts: Path = ROOT / "prompts"
    config_dir: Path = ROOT / "config"
    eval_dir: Path = ROOT / "eval"
    tessdata: Path | None = LEGACY_ROOT / "kb_state" / "models" / "tessdata"
    legacy_state: Path = LEGACY_ROOT / "kb_state"


class Runtime(BaseModel):
    cpu_workers: int = max(1, min(8, (os.cpu_count() or 2) // 2))
    docling_workers: int = 2           # each worker holds layout+TableFormer models (~1.5 GB RAM)
    ocr_threads: int = max(1, min(8, (os.cpu_count() or 2) // 2))
    device: Literal["auto", "cpu", "cuda"] = "auto"
    # On an 8 GB laptop GPU the chat model and the doc-VLM must not run together.
    unload_ollama_before_gpu: bool = False
    fail_fast: bool = False            # stop at the first document error (debugging)


class Intake(BaseModel):
    # Formats are sniffed from bytes first; this list only matters for extension-only types.
    # pdf | image (png jpg tif webp bmp gif) | html/xhtml/mhtml | docx pptx xlsx (Docling or
    # LibreOffice→PDF) | doc ppt xls odt ods odp rtf epub (LibreOffice→PDF) | csv tsv |
    # json jsonl xml yaml | txt md rst | eml (email body + attachments recursively)
    include_ext: list[str] = [".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp", ".gif",
                              ".html", ".htm", ".xhtml", ".mhtml", ".docx", ".pptx", ".xlsx",
                              ".doc", ".ppt", ".xls", ".odt", ".ods", ".odp", ".rtf", ".epub",
                              ".csv", ".tsv", ".json", ".jsonl", ".xml", ".yaml", ".yml",
                              ".txt", ".md", ".rst", ".eml"]
    # docx/pptx/xlsx: "docling" keeps style-based headings; "pdf" converts with LibreOffice
    # first (gives page numbers for citations).  Falls back to the other if unavailable.
    office_strategy: Literal["docling", "pdf"] = "docling"
    soffice: str = "soffice"
    soffice_timeout_s: int = 300
    csv_rows_per_table: int = 200              # long CSVs become several table elements
    ignore_globs: list[str] = ["**/.*", "**/~$*", "**/Thumbs.db"]
    # Images smaller than this (either side, px) are logos/icons, not documents.
    min_image_side_px: int = 300
    # Filenames matching these are registered but skipped (logos etc.); edit as needed.
    skip_name_patterns: list[str] = [r"(?i)\blogo\b"]
    max_file_mb: int = 400


class Triage(BaseModel):
    native_min_chars: int = 40                 # meaningful chars for a page to count as native
    scanned_image_area: float = 0.30           # image coverage that, with little text, means scanned
    figure_min_area_pt: tuple[float, float] = (90.0, 45.0)
    legacy_font_names: str = r"(?i)kruti|chanakya|devlys|walkman|shusha|krishna|agra"
    legacy_function_word_ratio: float = 0.03   # share of KrutiDev function words among tokens
    table_digit_ratio: float = 0.22
    table_min_paths: int = 30
    broken_markers: list[str] = ["(cid:", "\ufffd", "\x00"]
    render_dpi: int = 200                      # VLM input (PaddleOCR-VL resizes internally)
    ocr_dpi: int = 300                         # Tesseract / second read


class Extract(BaseModel):
    use_docling: bool = True                   # falls back to pdfplumber if not importable
    docling_table_mode: Literal["accurate", "fast"] = "accurate"
    docling_page_batch: int = 40               # bound memory on long reports
    docling_timeout_s: int = 900
    vlm_backend: Literal["paddleocr_vl", "none"] = "paddleocr_vl"
    # Python interpreter of the isolated env that has ``paddleocr[doc-parser]``.  Empty →
    # try in-process import, otherwise VLM routes degrade to OCR-only (needs_review).
    paddle_python: str = os.environ.get("KBB_PADDLE_PYTHON", "")
    paddle_pipeline_version: str = ""          # "" = library default (v1.5 at time of writing)
    paddle_device: str = "gpu:0"
    paddle_batch_pages: int = 64               # pages per worker launch (model loaded once)
    paddle_use_chart_recognition: bool = True
    # Cross-read native table-heavy pages with the VLM → keyed-cell agreement.
    native_table_policy: Literal["cross_read", "structural", "review"] = "cross_read"
    second_reader: Literal["docling_tesseract", "tesseract", "none"] = "docling_tesseract"
    tesseract_langs: str = "eng+hin"
    legacy_decoder: Literal["lipi", "none"] = "lipi"
    html_main_selectors: list[str] = ["main", "article", "#content", ".region-content",
                                      "#block-system-main", ".node__content", ".content"]


class Structure(BaseModel):
    heuristics: bool = True
    llm_patches: Literal["auto", "always", "never"] = "auto"
    # "auto": only when the parser's structure looks weak (few headings for many pages,
    # FAQ-like text, label-dot-value layouts).
    weak_heading_ratio: float = 0.34           # < 1 heading per 3 pages → weak
    patch_window_elements: int = 120
    patch_preview_chars: int = 80
    repeated_line_page_share: float = 0.6      # header/footer fallback rule (≥3 pages)


class Verify(BaseModel):
    coverage_min: float = 0.93                 # read-B words recalled by read A (OCR pages)
    coverage_min_devanagari: float = 0.85      # Devanagari OCR is noisier at the word level
    key_fuzzy_ratio: float = 90.0              # row/col header match across reads (rapidfuzz)
    text_cell_ratio: float = 90.0              # non-numeric cell agreement
    reading_order_tau: float = 0.9
    allow_machine_verified: bool = True
    # Non-native evidence about these topics needs a human even if both reads agree.
    critical_keywords: list[str] = [
        "fee", "fees", "tuition", "hostel charge", "refund", "शुल्क", "फीस",
        "last date", "deadline", "due date", "अंतिम तिथि", "eligibility", "eligible", "पात्रता",
        "cutoff", "cut-off", "opening rank", "closing rank", "loan", "scholarship amount",
        "stipend", "penalty", "fine"]


class Chunking(BaseModel):
    parent_max_chars: int = 3500               # matches legacy search.py parent expansion
    target_tokens: int = 380
    min_tokens: int = 60
    overlap_ratio: float = 0.12
    page_unit_max_tokens: int = 1024           # capped further by the embedder's max length
    row_facts_max_cols: int = 12
    row_facts_max_rows: int = 400
    unit_types: list[str] = ["section", "table", "row", "page", "proposition", "question", "summary"]


class LLM(BaseModel):
    backend: Literal["ollama", "openai"] = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str = os.environ.get("KBB_LLM_MODEL", "llama3.1:8b")
    # OpenAI-compatible (Groq, vLLM, LM Studio…).  Key read from this env var.
    openai_base_url: str = "https://api.groq.com/openai/v1"
    openai_model: str = "llama-3.3-70b-versatile"
    api_key_env: str = "GROQ_API_KEY"
    temperature: float = 0.0
    num_ctx: int = 4096
    keep_alive: str = "10m"
    think: bool = False
    concurrency: int = 2                       # match OLLAMA_NUM_PARALLEL
    requests_per_minute: int = 0               # 0 = unlimited (set ~25 for Groq free tier)
    timeout_s: int = 60
    max_retries: int = 2


class Enrich(BaseModel):
    enabled: bool = True
    context: bool = True
    questions: bool = True
    propositions: bool = True
    summaries: bool = True
    questions_per_parent: int = 3              # ≥1 Hindi/Hinglish enforced by validation
    max_parent_chars_in_prompt: int = 6000
    max_parents_per_run: int = 0               # 0 = all; use to spread work over nights
    proposition_min_overlap: float = 0.6       # content-word support in the parent


class Storage(BaseModel):
    """Per-document canonical store (see kbb/canonical.py for the format spec)."""
    gzip_elements_over_kb: int = 512           # elements.jsonl → elements.jsonl.gz above this size
    write_markdown_view: bool = True           # document.md: page-anchored, LLM/human readable
    write_corpus_bundle: bool = True           # work/corpus/documents.jsonl (one line per doc)
    keep_second_reads: bool = True             # needed by review UI and re-verification


class Embedding(BaseModel):
    model: str = "intfloat/multilingual-e5-small"
    # Prefer the exact local snapshot the legacy system uses (like-for-like A/B).
    model_path: str = str(LEGACY_ROOT / "kb_state" / "models" / "multilingual-e5-small")
    revision: str = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    family: Literal["e5", "bge-m3", "qwen3", "generic"] = "e5"
    max_tokens: int = 512
    batch_size: int = 64
    dtype_store: Literal["float16", "float32"] = "float16"


class Retrieval(BaseModel):
    per_type_k: int = 30
    rrf_k: int = 60
    channel_weights: dict[str, float] = {"dense": 1.0, "bm25": 1.0}
    type_weights: dict[str, float] = {"section": 1.0, "table": 1.0, "row": 1.0, "page": 0.8,
                                      "proposition": 1.0, "question": 1.0, "summary": 0.6}
    reranker: str = "BAAI/bge-reranker-v2-m3"
    rerank: bool = False                       # KBB_RETRIEVAL__RERANK=true; local weights only, never downloaded
    rerank_top: int = 20
    rerank_max_chars: int = 2000
    rerank_budget_s: float = 1.5               # chapter 04 §11: CPU rerank latency-gated <= 1.5 s, else fusion order
    ann_threshold: int = 300_000               # exact search below this many vectors
    statuses: list[str] = ["extracted", "approved", "machine_verified"]
    figure_weight: float = 0.5                 # figures never sole support for numbers


class Gate(BaseModel):
    min_recall_at_5_new: float = 0.90
    max_recall_regression: float = 0.0
    min_coverage: float = 0.80
    min_keyed_cell_accuracy: float = 0.995
    max_wrong_machine_verified: int = 0
    min_triage_accuracy: float = 0.95


class Config(BaseModel):
    paths: Paths = Field(default_factory=Paths)
    runtime: Runtime = Field(default_factory=Runtime)
    intake: Intake = Field(default_factory=Intake)
    triage: Triage = Field(default_factory=Triage)
    extract: Extract = Field(default_factory=Extract)
    structure: Structure = Field(default_factory=Structure)
    verify: Verify = Field(default_factory=Verify)
    chunking: Chunking = Field(default_factory=Chunking)
    llm: LLM = Field(default_factory=LLM)
    enrich: Enrich = Field(default_factory=Enrich)
    storage: Storage = Field(default_factory=Storage)
    embedding: Embedding = Field(default_factory=Embedding)
    retrieval: Retrieval = Field(default_factory=Retrieval)
    gate: Gate = Field(default_factory=Gate)

    def fingerprint(self, *sections: str) -> str:
        """Stable hash of config sections; part of stage cache keys."""
        data = {s: getattr(self, s).model_dump(mode="json") for s in sections}
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]

    # Convenience paths -------------------------------------------------------------
    @property
    def work(self) -> Path:
        return self.paths.work

    def doc_dir(self, doc_id: str) -> Path:
        return self.paths.work / "docs" / doc_id


def _deep_update(base: dict, other: dict) -> dict:
    for key, value in other.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _env_overrides(prefix: str = "KBB_") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, raw in os.environ.items():
        if not name.startswith(prefix) or "__" not in name:
            continue
        section, _, field = name[len(prefix):].lower().partition("__")
        try:
            value = yaml.safe_load(raw)   # "4" → 4, "true" → True, "[a, b]" → list
        except yaml.YAMLError:
            value = raw
        out.setdefault(section, {})[field] = value
    return out


def load_config(path: str | Path | None = None) -> Config:
    """Load defaults ← YAML ← env.  Relative paths in YAML resolve against ROOT."""
    data: dict[str, Any] = {}
    path = Path(path or os.environ.get("KBB_CONFIG", ROOT / "kbb.yaml"))
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _deep_update(data, _env_overrides())
    cfg = Config.model_validate(data)
    # Resolve relative paths against the project root, never the caller's cwd.
    for name, value in cfg.paths:
        if isinstance(value, Path) and not value.is_absolute():
            setattr(cfg.paths, name, (ROOT / value).resolve())
        elif isinstance(value, list):
            setattr(cfg.paths, name, [(ROOT / v).resolve() if not Path(v).is_absolute() else Path(v)
                                      for v in value])
    return cfg


@lru_cache(maxsize=1)
def get_config() -> Config:
    return load_config()
