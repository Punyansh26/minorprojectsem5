"""Canonical data model shared by every stage.

Coordinates: every ``bbox`` is ``[x0, y0, x1, y1]`` in **PDF points, top-left origin**.
For image sources one "point" is one pixel of the original image.  Pageless sources (HTML,
DOCX, TXT) use ``page = -1`` and rely on ``order`` for provenance.

Statuses (trust order, high → low):
    approved > extracted > machine_verified > needs_review > rejected
``extracted``        native text layer, structural checks passed.
``machine_verified`` OCR/VLM/decoded text where two independent reads agree on every
                     number and keyed table cell (and topic is not critical).
``needs_review``     anything else; never answerable until a human approves it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

STATUS_RANK = {"approved": 4, "extracted": 3, "machine_verified": 2, "needs_review": 1,
               "visual_only": 0, "rejected": -1}

ELEMENT_TYPES = {"title", "heading", "paragraph", "list_item", "table", "figure", "caption",
                 "footnote", "page_header", "page_footer", "formula", "code", "kv"}
NON_CONTENT = {"page_header", "page_footer"}


def weakest(statuses) -> str:
    """The parent's status is its least trusted element's status."""
    statuses = list(statuses)
    return min(statuses, key=lambda s: STATUS_RANK.get(s, 0)) if statuses else "needs_review"


@dataclass
class Cell:
    row: int
    col: int
    text: str
    row_span: int = 1
    col_span: int = 1
    is_col_header: bool = False
    is_row_header: bool = False


@dataclass
class Table:
    n_rows: int
    n_cols: int
    cells: list[Cell] = field(default_factory=list)
    caption: str = ""
    header_rows: int | None = None     # resolved by tables.detect_headers
    header_cols: int | None = None

    def grid(self) -> list[list[str]]:
        """Dense grid with spans expanded (value repeated into every covered slot)."""
        grid = [["" for _ in range(self.n_cols)] for _ in range(self.n_rows)]
        for c in self.cells:
            for r in range(c.row, min(self.n_rows, c.row + max(1, c.row_span))):
                for k in range(c.col, min(self.n_cols, c.col + max(1, c.col_span))):
                    grid[r][k] = c.text
        return grid

    @staticmethod
    def from_grid(rows: list[list[str]], caption: str = "") -> "Table":
        n_cols = max((len(r) for r in rows), default=0)
        cells = [Cell(r, c, (rows[r][c] if c < len(rows[r]) else "") or "")
                 for r in range(len(rows)) for c in range(n_cols)]
        return Table(len(rows), n_cols, cells, caption)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict | None) -> "Table | None":
        if not d:
            return None
        return Table(d["n_rows"], d["n_cols"], [Cell(**c) for c in d.get("cells", [])],
                     d.get("caption", ""), d.get("header_rows"), d.get("header_cols"))


@dataclass
class Element:
    id: str                         # unique within the document, stable for same input
    type: str                       # one of ELEMENT_TYPES
    page: int                       # 1-based; -1 for pageless sources
    text: str                       # verbatim reader output (never LLM-generated)
    bbox: list[float] | None = None
    level: int | None = None        # heading level (1 = top)
    table: Table | None = None
    reader: str = ""                # docling | paddleocr-vl | lipi+docling | tesseract | html | ...
    confidence: float | None = None
    order: int = 0                  # global reading order inside the document
    attrs: dict[str, Any] = field(default_factory=dict)
    # Filled by verify.py
    status: str = "needs_review"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["table"] = self.table.to_dict() if self.table else None
        return d

    @staticmethod
    def from_dict(d: dict) -> "Element":
        d = dict(d)
        d["table"] = Table.from_dict(d.get("table"))
        return Element(**d)


@dataclass
class PageInfo:
    page: int
    route: str                      # native | legacy_font | scanned | broken_text | blank | image | pageless
    width: float = 0.0
    height: float = 0.0
    chars: int = 0
    devanagari_share: float = 0.0
    image_area: float = 0.0
    table_heavy: bool = False
    has_figures: bool = False
    fonts: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    primary_reader: str = ""
    second_reader: str = ""
    status: str = ""                # page-level verification outcome
    coverage: float | None = None


@dataclass
class SecondRead:
    """Independent read of one page, used only for verification (never as evidence)."""
    page: int
    reader: str
    text: str
    elements: list[Element] = field(default_factory=list)
    words: list[dict] = field(default_factory=list)   # {text, bbox, conf}

    def to_dict(self) -> dict:
        return {"page": self.page, "reader": self.reader, "text": self.text,
                "elements": [e.to_dict() for e in self.elements], "words": self.words}

    @staticmethod
    def from_dict(d: dict) -> "SecondRead":
        return SecondRead(d["page"], d["reader"], d["text"],
                          [Element.from_dict(e) for e in d.get("elements", [])], d.get("words", []))


@dataclass
class Parent:
    """Evidence block: what the answering LLM reads and quotes.  Text is verbatim."""
    id: str
    doc_id: str
    kind: str                       # text | table | faq | list | figure
    text: str
    heading_path: list[str]
    element_ids: list[str]
    page_start: int
    page_end: int
    status: str
    reasons: list[str] = field(default_factory=list)
    readers: list[str] = field(default_factory=list)
    bbox: list[float] | None = None              # union bbox on page_start
    table: dict | None = None                    # Table.to_dict() for table parents
    language: str = "en"
    critical: bool = False
    related_parent_ids: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)   # source metadata copy
    # Retrieval aids (generated; never evidence)
    context: str = ""
    questions: list[str] = field(default_factory=list)
    propositions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Parent":
        return Parent(**d)


@dataclass
class Unit:
    """A retrieval unit.  Matches queries; always resolves to one or more parents."""
    id: str
    type: str                       # section | table | row | page | proposition | question | summary
    parent_ids: list[str]
    doc_id: str
    text: str                       # the unit body
    header: str = ""                # heading-path header line
    context: str = ""               # contextual prefix (shared per parent)
    page_start: int = -1
    page_end: int = -1
    status: str = "needs_review"
    meta: dict[str, Any] = field(default_factory=dict)

    def embed_text(self) -> str:
        return "\n".join(x for x in (self.header, self.context, self.text) if x)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Unit":
        return Unit(**d)
