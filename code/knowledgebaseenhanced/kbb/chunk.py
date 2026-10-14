"""Stage 6 — multi-granularity chunking engine.

Emits multiple retrieval granularities (doc 15 §6):
1. Parents (Evidence Blocks): The verified grounding blocks (<= 3500 chars) that the
   answering LLM reads and quotes.
2. Section Chunks: 250–450 tokens with heading path prefix.
3. Table Chunks: Atomic tables or split row groups with headers and caption repeated.
4. Row Facts: One serialised line per key table row (`Doc › Section › Row: Col=Val`).
5. Page Units: Whole-page text representations.
6. Summary Units: High-level section summaries.

All retrieval units store their `parent_ids` reference.
"""
from __future__ import annotations

import logging
from typing import Any

from .config import Config
from .models import Element, Parent, Unit, weakest
from .tables import detect_headers, row_lines
from .textnorm import clean, words

log = logging.getLogger(__name__)


def build_parents_and_units(
    cfg: Config,
    doc_id: str,
    elements: list[Element],
    doc_meta: dict[str, Any],
) -> tuple[list[Parent], list[Unit]]:
    """Build verified parents and multi-granularity retrieval units."""
    parents = _group_into_parents(cfg, doc_id, elements, doc_meta)
    units = _build_units_from_parents(cfg, doc_id, parents, elements, doc_meta)
    return parents, units


def _group_into_parents(
    cfg: Config,
    doc_id: str,
    elements: list[Element],
    doc_meta: dict[str, Any],
) -> list[Parent]:
    """Group elements under heading hierarchy into coherent evidence parents."""
    parents: list[Parent] = []
    current_heading_path: list[str] = [doc_meta.get("title", "Document")]
    cur_elements: list[Element] = []
    parent_idx = 1

    def flush_parent(kind: str = "text"):
        nonlocal parent_idx, cur_elements
        if not cur_elements:
            return

        texts = [e.text for e in cur_elements if e.text.strip()]
        if not texts:
            cur_elements = []
            return

        joined_text = "\n\n".join(texts)
        p_start = min((e.page for e in cur_elements if e.page > 0), default=-1)
        p_end = max((e.page for e in cur_elements if e.page > 0), default=-1)

        # Status is the weakest status among its elements
        from .models import weakest
        st = weakest(e.status for e in cur_elements)

        parent = Parent(
            id=f"{doc_id}:p{parent_idx:03d}",
            doc_id=doc_id,
            kind=kind,
            text=clean(joined_text),
            heading_path=list(current_heading_path),
            element_ids=[e.id for e in cur_elements],
            page_start=p_start,
            page_end=p_end,
            status=st,
            reasons=[r for e in cur_elements for r in e.reasons],
            readers=sorted({e.reader for e in cur_elements if e.reader}),
            meta=dict(doc_meta),
        )
        parents.append(parent)
        parent_idx += 1
        cur_elements = []

    for el in elements:
        # Parents never straddle pages, so every citation names exactly the page the text is on.
        if cur_elements and el.page > 0 and cur_elements[-1].page > 0 and el.page != cur_elements[-1].page:
            flush_parent("text")
        # Tables form their own atomic parent
        if el.type == "table":
            flush_parent("text")
            cur_elements.append(el)
            flush_parent("table")
            continue

        # Major headings start a new section
        if el.type == "heading" and (el.level or 2) <= 2:
            flush_parent("text")
            # Update heading path
            lvl = el.level or 2
            if lvl == 1:
                current_heading_path = [el.text]
            else:
                current_heading_path = current_heading_path[:1] + [el.text]
            cur_elements.append(el)
            continue

        cur_elements.append(el)
        # Flush if parent character limit reached
        total_len = sum(len(e.text) for e in cur_elements)
        if total_len >= cfg.chunking.parent_max_chars:
            flush_parent("text")

    flush_parent("text")
    return parents


def _build_units_from_parents(
    cfg: Config,
    doc_id: str,
    parents: list[Parent],
    elements: list[Element],
    doc_meta: dict[str, Any] | None = None,
) -> list[Unit]:
    """Generate multi-granularity retrieval units pointing to parents."""
    doc_meta = doc_meta or (parents[0].meta if parents else {})
    units: list[Unit] = []
    unit_idx = 1

    for parent in parents:
        header = f"[{' › '.join(parent.heading_path)}]"
        if parent.page_start > 0:
            header += f" (p. {parent.page_start})"

        # 1. Section / Body chunks
        if parent.kind == "text":
            toks = words(parent.text)
            if len(toks) <= cfg.chunking.target_tokens * 1.5:
                # Fits within target chunk size
                units.append(Unit(
                    id=f"{doc_id}:u{unit_idx:04d}",
                    type="section",
                    parent_ids=[parent.id],
                    doc_id=doc_id,
                    text=parent.text,
                    header=header,
                    page_start=parent.page_start,
                    page_end=parent.page_end,
                    status=parent.status,
                    meta=dict(parent.meta),
                ))
                unit_idx += 1
            else:
                # Split large text with overlap
                paras = parent.text.split("\n\n")
                buf: list[str] = []
                cur_words = 0
                for p in paras:
                    pw = len(words(p))
                    if cur_words + pw > cfg.chunking.target_tokens and buf:
                        units.append(Unit(
                            id=f"{doc_id}:u{unit_idx:04d}",
                            type="section",
                            parent_ids=[parent.id],
                            doc_id=doc_id,
                            text="\n\n".join(buf),
                            header=header,
                            page_start=parent.page_start,
                            page_end=parent.page_end,
                            status=parent.status,
                            meta=dict(parent.meta),
                        ))
                        unit_idx += 1
                        buf = buf[-1:] if len(buf) > 1 else buf
                        cur_words = sum(len(words(x)) for x in buf)
                    buf.append(p)
                    cur_words += pw

                if buf:
                    units.append(Unit(
                        id=f"{doc_id}:u{unit_idx:04d}",
                        type="section",
                        parent_ids=[parent.id],
                        doc_id=doc_id,
                        text="\n\n".join(buf),
                        header=header,
                        page_start=parent.page_start,
                        page_end=parent.page_end,
                        status=parent.status,
                        meta=dict(parent.meta),
                    ))
                    unit_idx += 1

        # 2. Table chunks & Row Facts
        elif parent.kind == "table":
            units.append(Unit(
                id=f"{doc_id}:u{unit_idx:04d}",
                type="table",
                parent_ids=[parent.id],
                doc_id=doc_id,
                text=parent.text,
                header=header,
                page_start=parent.page_start,
                page_end=parent.page_end,
                status=parent.status,
                meta=dict(parent.meta),
            ))
            unit_idx += 1

            # Emit row facts for key factoid retrieval
            table_els = [e for e in elements if e.id in parent.element_ids and e.type == "table" and e.table]
            for tel in table_els:
                rows = row_lines(tel.table, max_cols=cfg.chunking.row_facts_max_cols)
                for r_idx, r_text in rows[:cfg.chunking.row_facts_max_rows]:
                    units.append(Unit(
                        id=f"{doc_id}:u{unit_idx:04d}",
                        type="row",
                        parent_ids=[parent.id],
                        doc_id=doc_id,
                        text=r_text,
                        header=header,
                        page_start=parent.page_start,
                        page_end=parent.page_end,
                        status=parent.status,
                        meta=dict(parent.meta),
                    ))
                    unit_idx += 1

    # 3. Whole-page units (NVIDIA RAG study: lowest variance retrieval unit)
    pages_map: dict[int, list[Element]] = {}
    for el in elements:
        if el.page > 0:
            pages_map.setdefault(el.page, []).append(el)

    for p_num, p_els in pages_map.items():
        page_text = "\n".join(e.text for e in p_els if e.text.strip())
        matching_parents = [p.id for p in parents if p.page_start <= p_num <= p.page_end]
        page_status = weakest(e.status for e in p_els)
        if page_text and matching_parents:
            units.append(Unit(
                id=f"{doc_id}:p{p_num:03d}",
                type="page",
                parent_ids=matching_parents,
                doc_id=doc_id,
                text=page_text[:4000],
                header=f"[{doc_meta.get('title', 'Document')}] (Page {p_num})",
                page_start=p_num,
                page_end=p_num,
                status=page_status,
                meta=dict(doc_meta),
            ))

    return units
