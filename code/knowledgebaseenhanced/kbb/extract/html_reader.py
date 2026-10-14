"""HTML reader: extract structured text, tables, and sections from web pages.

Handles:
- Standard HTML5 semantic layouts (<main>, <article>, headers, lists, tables).
- IIIT-NR Drupal CMS layout selectors and cleanup (nav, sidebar, footer stripping).
- Browser view-source dumps (e.g. view-source_https___www.iiitnr.ac.in_content_board.html
  with <td class="line-content"> rows containing raw HTML).
- MHTML / multipart email-web archives.
"""
from __future__ import annotations

import email
import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

from ..config import Config
from ..models import Element, Table
from ..tables import from_html, render_rows
from ..textnorm import clean
from . import mk

log = logging.getLogger(__name__)

# Boilerplate tags to strip
DISCARD_TAGS = {"script", "style", "noscript", "svg", "header", "footer", "nav", "aside", "form"}


def _unwrap_view_source(soup: BeautifulSoup) -> BeautifulSoup:
    """If the HTML is a Chrome/Firefox 'view-source' dump, reconstruct the actual DOM."""
    line_cells = soup.find_all("td", class_="line-content")
    if len(line_cells) > 10:
        raw_lines = [cell.get_text() for cell in line_cells]
        raw_html = "\n".join(raw_lines)
        return BeautifulSoup(raw_html, "html.parser")
    return soup


def _extract_main_content(soup: BeautifulSoup, selectors: list[str]) -> Tag:
    """Find the primary article body or fall back to <body>."""
    for sel in selectors:
        target = soup.select_one(sel)
        if target and len(target.get_text(strip=True)) > 40:
            return target
    return soup.body or soup


def _prune_link_lists(root: Tag) -> int:
    """Remove menu-like lists (three or more items, ~all text inside links).  Returns lists removed."""
    removed = 0
    for lst in list(root.find_all(["ul", "ol"])):
        if lst.parent is None:
            continue
        items = lst.find_all("li")
        if len(items) < 3:
            continue
        ratios = []
        for li in items:
            total = len(li.get_text(strip=True))
            linked = sum(len(a.get_text(strip=True)) for a in li.find_all("a"))
            ratios.append(linked / total if total else 0.0)
        if sum(ratios) / len(ratios) >= 0.9:
            lst.decompose()
            removed += 1
    return removed


def read_html(cfg: Config, path: str, *, prune_nav: bool = False) -> list[Element]:
    """Parse HTML file into structured Elements.

    ``prune_nav`` removes link-only menu lists (Drupal mega-menus) before extraction.
    """
    file_path = Path(path)
    raw_bytes = file_path.read_bytes()

    # Handle MHTML if needed
    if file_path.suffix.lower() == ".mhtml" or (raw_bytes.startswith(b"MIME-Version") and b"multipart/related" in raw_bytes[:1024]):
        msg = email.message_from_bytes(raw_bytes)
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    raw_bytes = payload
                    break

    # Encoding detection fallback
    try:
        html_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        html_text = raw_bytes.decode("latin-1", errors="replace")

    soup = BeautifulSoup(html_text, "html.parser")
    soup = _unwrap_view_source(soup)

    # Remove non-content tags
    for tag in soup.find_all(DISCARD_TAGS):
        tag.decompose()

    root = _extract_main_content(soup, cfg.extract.html_main_selectors)
    if prune_nav:
        _prune_link_lists(soup)
    elements: list[Element] = []

    # Process headings, paragraphs, lists, and tables in reading order
    for node in root.descendants:
        if not isinstance(node, Tag):
            continue

        tag_name = node.name.lower()

        # Tables
        if tag_name == "table":
            # Avoid processing nested tables multiple times if already handled
            if node.find_parent("table"):
                continue
            table_obj = from_html(str(node))
            if table_obj and table_obj.n_rows > 0:
                elements.append(mk("table", -1, render_rows(table_obj), table=table_obj, reader="html"))
            continue

        # Headings (h1 - h6)
        if re.match(r"^h[1-6]$", tag_name):
            txt = clean(node.get_text())
            if txt:
                level = int(tag_name[1])
                elements.append(mk("heading", -1, txt, level=level, reader="html"))
            continue

        # Paragraphs
        if tag_name == "p":
            if node.find_parent(["table", "ul", "ol"]):
                continue
            txt = clean(node.get_text())
            if txt:
                elements.append(mk("paragraph", -1, txt, reader="html"))
            continue

        # List items
        if tag_name == "li":
            if node.find_parent("table") or node.find(["ul", "ol"]):
                continue
            txt = clean(node.get_text())
            if txt:
                elements.append(mk("list_item", -1, txt, reader="html"))
            continue

        # Blockquotes or preformatted text
        if tag_name in {"blockquote", "pre"}:
            txt = clean(node.get_text())
            if txt:
                elements.append(mk("paragraph", -1, txt, reader="html"))
            continue

    # Deduplicate redundant consecutive elements that share text (e.g. from container nesting)
    deduped: list[Element] = []
    seen_texts: set[str] = set()
    for el in elements:
        if el.text in seen_texts and el.type != "table":
            continue
        seen_texts.add(el.text)
        deduped.append(el)

    return deduped
