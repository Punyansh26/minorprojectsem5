"""Reader for text, structured data, emails, and code files.

Handles:
- Delimited data (.csv, .tsv): parsed into canonical `Table` elements with header detection.
- Structured objects (.json, .jsonl, .yaml, .yml, .xml): serialised into readable sections or KV tables.
- Formatted text (.md, .rst, .txt): parses headings, paragraphs, and lists.
- Email files (.eml): extracts headers (Subject, From, Date, To) and message body; attachments handled.
"""
from __future__ import annotations

import csv
import email
from email import policy
import json
import logging
from pathlib import Path
import re
from typing import Any

import yaml

from ..config import Config
from ..models import Cell, Element, Table
from ..tables import render_rows
from ..textnorm import clean
from . import mk

log = logging.getLogger(__name__)


def read_csv(cfg: Config, path: str) -> list[Element]:
    """Parse CSV or TSV files into canonical Table elements."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    dialect = "excel-tab" if p.suffix.lower() == ".tsv" or "\t" in text[:1000] else "excel"

    try:
        reader = list(csv.reader(text.splitlines(), dialect=dialect))
    except Exception as exc:
        log.warning("CSV parse error in %s: %s, falling back to basic split", path, exc)
        reader = [line.split("\t" if dialect == "excel-tab" else ",") for line in text.splitlines()]

    if not reader:
        return []

    # Clean cells
    rows = [[clean(c) for c in r] for r in reader if any(c.strip() for c in r)]
    if not rows:
        return []

    max_rows = cfg.intake.csv_rows_per_table
    elements: list[Element] = []
    headers = rows[0]

    for part_idx, start in enumerate(range(0, len(rows), max_rows), 1):
        batch = rows[start:start + max_rows]
        # If this is a subsequent chunk and doesn't have the header, prepend it
        if start > 0 and len(rows) > max_rows:
            batch = [headers] + batch

        n_rows = len(batch)
        n_cols = max((len(r) for r in batch), default=0)
        cells = [Cell(r, c, (batch[r][c] if c < len(batch[r]) else ""), is_col_header=(r == 0))
                 for r in range(n_rows) for c in range(n_cols)]

        caption = p.stem.replace("_", " ").title()
        if len(rows) > max_rows:
            caption += f" (Part {part_idx})"

        t = Table(n_rows, n_cols, cells, caption, header_rows=1, header_cols=0)
        elements.append(mk("table", -1, render_rows(t), table=t, reader="csv"))

    return elements


def read_json_structured(cfg: Config, path: str) -> list[Element]:
    """Parse JSON or JSONL into structured elements."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace").strip()
    elements: list[Element] = []
    title = p.stem.replace("_", " ").title()
    elements.append(mk("heading", -1, title, level=1, reader="json"))

    try:
        if p.suffix.lower() == ".jsonl":
            data = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            data = json.loads(text)
    except Exception as exc:
        log.warning("JSON parse failed for %s: %s; reading as preformatted code", path, exc)
        return [mk("heading", -1, title, level=1, reader="json"),
                mk("code", -1, text, reader="json")]

    if isinstance(data, list) and data and all(isinstance(x, dict) for x in data):
        # List of records -> Table
        keys = []
        for d in data[:50]:
            for k in d.keys():
                if k not in keys:
                    keys.append(k)

        rows = [keys]
        for item in data:
            rows.append([str(item.get(k, "")) for k in keys])

        n_rows = len(rows)
        n_cols = len(keys)
        cells = [Cell(r, c, clean(rows[r][c]), is_col_header=(r == 0))
                 for r in range(n_rows) for c in range(n_cols)]
        t = Table(n_rows, n_cols, cells, title, header_rows=1, header_cols=0)
        elements.append(mk("table", -1, render_rows(t), table=t, reader="json"))
    elif isinstance(data, dict):
        # Key-Value pairs -> KV list / paragraphs
        for k, v in data.items():
            k_clean = str(k).replace("_", " ").title()
            if isinstance(v, (str, int, float, bool)):
                elements.append(mk("kv", -1, f"{k_clean}: {v}", reader="json"))
            else:
                formatted = json.dumps(v, ensure_ascii=False, indent=2)
                elements.append(mk("heading", -1, k_clean, level=2, reader="json"))
                elements.append(mk("code", -1, formatted, reader="json"))
    else:
        elements.append(mk("paragraph", -1, json.dumps(data, ensure_ascii=False, indent=2), reader="json"))

    return elements


def read_yaml(cfg: Config, path: str) -> list[Element]:
    """Parse YAML into structured elements."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    title = p.stem.replace("_", " ").title()
    elements: list[Element] = [mk("heading", -1, title, level=1, reader="yaml")]

    try:
        data = yaml.safe_load(text)
    except Exception as exc:
        log.warning("YAML parse error for %s: %s", path, exc)
        elements.append(mk("code", -1, text, reader="yaml"))
        return elements

    if isinstance(data, dict):
        for k, v in data.items():
            k_clean = str(k).replace("_", " ").title()
            if isinstance(v, (str, int, float, bool)):
                elements.append(mk("kv", -1, f"{k_clean}: {v}", reader="yaml"))
            else:
                elements.append(mk("heading", -1, k_clean, level=2, reader="yaml"))
                elements.append(mk("code", -1, yaml.dump(v, allow_unicode=True), reader="yaml"))
    else:
        elements.append(mk("paragraph", -1, text, reader="yaml"))

    return elements


def read_markdown_text(cfg: Config, path: str) -> list[Element]:
    """Parse Markdown or plain text into structured elements."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    elements: list[Element] = []

    # Simple line-oriented Markdown/Text parser
    lines = text.splitlines()
    in_table: list[str] = []
    in_code: list[str] = []
    cur_para: list[str] = []

    def flush_para():
        if cur_para:
            elements.append(mk("paragraph", -1, clean("\n".join(cur_para)), reader="markdown"))
            cur_para.clear()

    def flush_table():
        if in_table:
            from ..tables import from_markdown
            t = from_markdown("\n".join(in_table))
            if t and t.n_rows > 0:
                elements.append(mk("table", -1, render_rows(t), table=t, reader="markdown"))
            else:
                elements.append(mk("paragraph", -1, "\n".join(in_table), reader="markdown"))
            in_table.clear()

    for line in lines:
        stripped = line.strip()

        # Code fences
        if stripped.startswith("```"):
            if in_code:
                elements.append(mk("code", -1, "\n".join(in_code), reader="markdown"))
                in_code.clear()
            else:
                flush_para()
                flush_table()
                in_code.append(stripped)
            continue

        if in_code:
            in_code.append(line)
            continue

        # Markdown table lines
        if stripped.startswith("|") or (stripped.count("|") >= 2 and len(stripped) > 5):
            flush_para()
            in_table.append(line)
            continue
        elif in_table:
            flush_table()

        # Headings
        h_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if h_match:
            flush_para()
            level = len(h_match.group(1))
            heading_text = clean(h_match.group(2))
            elements.append(mk("heading", -1, heading_text, level=level, reader="markdown"))
            continue

        # List items
        list_match = re.match(r"^(\*|-|\+|\d+\.)\s+(.*)$", stripped)
        if list_match:
            flush_para()
            elements.append(mk("list_item", -1, clean(list_match.group(2)), reader="markdown"))
            continue

        # Blank line
        if not stripped:
            flush_para()
            continue

        cur_para.append(line)

    flush_para()
    flush_table()
    if in_code:
        elements.append(mk("code", -1, "\n".join(in_code), reader="markdown"))

    return elements


def read_email(cfg: Config, path: str) -> list[Element]:
    """Parse .eml email file into subject, metadata, and body."""
    p = Path(path)
    with p.open("rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)

    elements: list[Element] = []
    subject = msg.get("Subject", "Untitled Message")
    elements.append(mk("heading", -1, clean(subject), level=1, reader="email"))

    headers = []
    for h in ("From", "To", "Date", "Cc"):
        val = msg.get(h)
        if val:
            headers.append(f"{h}: {val}")
    if headers:
        elements.append(mk("kv", -1, "\n".join(headers), reader="email"))

    # Extract body
    body_part = msg.get_body(preferencelist=("plain", "html"))
    if body_part:
        content = body_part.get_content()
        if body_part.get_content_type() == "text/html":
            from .html_reader import read_html
            # Save temporary html or parse directly
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")
            body_text = clean(soup.get_text("\n"))
        else:
            body_text = clean(content)

        if body_text:
            elements.append(mk("paragraph", -1, body_text, reader="email"))

    return elements


def read_structured_file(cfg: Config, format_name: str, path: str) -> list[Element]:
    """Route any text/data format to its dedicated parser."""
    fmt = format_name.lower()
    if fmt == "csv":
        return read_csv(cfg, path)
    if fmt == "json":
        return read_json_structured(cfg, path)
    if fmt == "yaml":
        return read_yaml(cfg, path)
    if fmt == "email":
        return read_email(cfg, path)
    # Default text / markdown
    return read_markdown_text(cfg, path)
