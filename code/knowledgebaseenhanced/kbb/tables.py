"""Table utilities: parse reader outputs into cell grids, find headers, emit *keyed cells*.

Keyed cells are the unit of table verification (review doc 14 §3.1): a multiset of values
cannot see a swapped column; a set of ``(row_key, col_key, value)`` triples can.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Cell, Table
from .textnorm import clean, is_numeric_cell, norm_for_compare, number_tokens


# ------------------------------------------------------------------ parsing
def from_html(html: str, caption: str = "") -> Table | None:
    """Parse an HTML ``<table>`` (PaddleOCR-VL / web pages) honouring row/col spans."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return None
    if not caption and table.find("caption"):
        caption = clean(table.find("caption").get_text(" ", strip=True))
    occupied: set[tuple[int, int]] = set()
    cells: list[Cell] = []
    rows = [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]
    n_cols = 0
    for r, tr in enumerate(rows):
        c = 0
        in_thead = tr.find_parent("thead") is not None
        for td in tr.find_all(["td", "th"], recursive=False):
            while (r, c) in occupied:
                c += 1
            rs = max(1, min(200, _int(td.get("rowspan"), 1)))
            cs = max(1, min(100, _int(td.get("colspan"), 1)))
            for dr in range(rs):
                for dc in range(cs):
                    occupied.add((r + dr, c + dc))
            cells.append(Cell(r, c, clean(td.get_text(" ", strip=True)), rs, cs,
                              is_col_header=(td.name == "th" and not _row_header_th(td)) or in_thead,
                              is_row_header=td.name == "th" and _row_header_th(td)))
            c += cs
            n_cols = max(n_cols, c)
    n_rows = max((r for r, _ in occupied), default=-1) + 1
    if n_rows == 0 or n_cols == 0:
        return None
    return Table(n_rows, n_cols, cells, caption)


def _row_header_th(td) -> bool:
    return td.get("scope") == "row"


def _int(value, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


_MD_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def from_markdown(md: str, caption: str = "") -> Table | None:
    lines = [ln for ln in md.splitlines() if ln.strip().startswith("|") or ln.count("|") >= 2]
    if not lines:
        return None
    rows, header_rows = [], 0
    for ln in lines:
        if _MD_SEP.match(ln):
            header_rows = len(rows)
            continue
        parts = [p.strip() for p in ln.strip().strip("|").split("|")]
        rows.append(parts)
    if not rows:
        return None
    t = Table.from_grid(rows, caption)
    if header_rows:
        for cell in t.cells:
            cell.is_col_header = cell.row < header_rows
    return t


def from_content(content: str, caption: str = "") -> Table | None:
    content = content or ""
    if "<table" in content.lower():
        return from_html(content, caption)
    return from_markdown(content, caption)


# ------------------------------------------------------------------ headers
def detect_headers(table: Table) -> tuple[int, int]:
    """Number of header rows and row-header columns.

    Prefer the reader's own flags (TableFormer / HTML ``th``); otherwise infer: leading rows
    that are mostly non-numeric while the body below is numeric are headers; the first column
    is a row header if it is mostly non-numeric.
    """
    if table.header_rows is not None and table.header_cols is not None:
        return table.header_rows, table.header_cols
    grid = table.grid()
    n_rows, n_cols = table.n_rows, table.n_cols
    flagged_rows = {c.row + k for c in table.cells if c.is_col_header for k in range(c.row_span)}
    flagged_cols = {c.col + k for c in table.cells if c.is_row_header for k in range(c.col_span)}
    hr = 0
    while hr in flagged_rows and hr < n_rows - 1:
        hr += 1
    if hr == 0 and n_rows >= 2:
        def numeric_share(row):
            vals = [v for v in row if v.strip()]
            return sum(is_numeric_cell(v) for v in vals) / len(vals) if vals else 0.0
        body_numeric = sum(numeric_share(r) for r in grid[1:]) / max(1, n_rows - 1)
        for r in range(min(3, n_rows - 1)):
            if numeric_share(grid[r][1:] if n_cols > 1 else grid[r]) <= 0.2 and (body_numeric >= 0.3 or r == 0):
                hr = r + 1
            else:
                break
        hr = max(hr, 1) if n_rows >= 2 else 0
    hc = 0
    while hc in flagged_cols and hc < n_cols - 1:
        hc += 1
    if hc == 0 and n_cols >= 2:
        body = [grid[r][0] for r in range(hr, n_rows) if grid[r][0].strip()]
        if body and sum(not is_numeric_cell(v) for v in body) / len(body) >= 0.6:
            hc = 1
    table.header_rows, table.header_cols = hr, hc
    return hr, hc


# ------------------------------------------------------------------ keyed cells
@dataclass(frozen=True)
class KeyedCell:
    row_key: str
    col_key: str
    value: str          # verbatim (cleaned) cell text
    row: int
    col: int

    @property
    def numeric(self) -> bool:
        return is_numeric_cell(self.value)

    @property
    def value_norm(self) -> str:
        return " ".join(number_tokens(self.value)) if self.numeric else norm_for_compare(self.value)


def _join_unique(parts: list[str]) -> str:
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p and (not out or out[-1] != p):
            out.append(p)
    return " › ".join(out)


def keyed_cells(table: Table) -> list[KeyedCell]:
    """Body cells with their row-header path and column-header path."""
    hr, hc = detect_headers(table)
    grid = table.grid()
    out: list[KeyedCell] = []
    for r in range(hr, table.n_rows):
        row_key = _join_unique([grid[r][c] for c in range(hc)]) or f"row {r - hr + 1}"
        for c in range(hc, table.n_cols):
            value = grid[r][c].strip()
            if not value:
                continue
            col_key = _join_unique([grid[h][c] for h in range(hr)]) or f"col {c - hc + 1}"
            out.append(KeyedCell(row_key, col_key, value, r, c))
    return out


# ------------------------------------------------------------------ rendering
def render_rows(table: Table, *, with_caption: bool = True) -> str:
    """Legacy-compatible rendering: caption line + one ``a | b | c`` line per row.

    Matches ``institute-assistant/assistant/kb/extraction.py::table_text`` so exported
    blocks look like existing evidence and quote checks behave identically.
    """
    lines = []
    if with_caption and table.caption:
        lines.append(table.caption)
    for row in table.grid():
        lines.append(" | ".join(clean(v) for v in row))
    return "\n".join(lines)


def render_markdown(table: Table) -> str:
    hr, _ = detect_headers(table)
    grid = table.grid()
    if not grid:
        return ""
    esc = lambda v: clean(v).replace("|", "\\|").replace("\n", " ")
    lines = []
    head = grid[:max(1, hr)]
    for row in head:
        lines.append("| " + " | ".join(esc(v) for v in row) + " |")
    lines.append("|" + "|".join("---" for _ in grid[0]) + "|")
    for row in grid[max(1, hr):]:
        lines.append("| " + " | ".join(esc(v) for v in row) + " |")
    return "\n".join(lines)


def row_lines(table: Table, max_cols: int = 12) -> list[tuple[int, str]]:
    """One self-describing line per body row: ``RowKey: Col1 = v1; Col2 = v2``."""
    hr, hc = detect_headers(table)
    grid = table.grid()
    out = []
    for r in range(hr, table.n_rows):
        row_key = _join_unique([grid[r][c] for c in range(hc)]) or f"Row {r - hr + 1}"
        pairs = []
        for c in range(hc, min(table.n_cols, hc + max_cols)):
            v = grid[r][c].strip()
            if v:
                ck = _join_unique([grid[h][c] for h in range(hr)]) or f"Col {c - hc + 1}"
                pairs.append(f"{ck} = {v}")
        if pairs:
            out.append((r, f"{row_key}: " + "; ".join(pairs)))
    return out


def sane(table: Table) -> list[str]:
    """Structural sanity problems (empty when the grid looks trustworthy)."""
    problems = []
    if table.n_rows < 2 or table.n_cols < 2:
        problems.append("degenerate table (<2 rows or cols)")
    grid = table.grid()
    empty = sum(1 for row in grid for v in row if not v.strip())
    if grid and empty / (table.n_rows * table.n_cols) > 0.6:
        problems.append("table mostly empty")
    hr, _ = detect_headers(table)
    if hr == 0:
        problems.append("no header row detected")
    for c in range(table.n_cols):
        if all(not grid[r][c].strip() for r in range(table.n_rows)):
            problems.append(f"empty column {c}")
            break
    return problems
