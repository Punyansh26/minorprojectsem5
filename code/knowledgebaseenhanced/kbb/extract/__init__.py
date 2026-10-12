"""Readers: each turns one source format into a list of canonical ``Element`` objects.

Readers never paraphrase.  They return verbatim text plus structure (type, heading level,
table cells, page, bbox).  Final element ids and global order are assigned later by
``kbb.canonical`` so that every reader can stay simple.
"""
from __future__ import annotations

from ..models import Element


def mk(type_: str, page: int, text: str, *, bbox=None, level=None, table=None, reader="",
       confidence=None, **attrs) -> Element:
    return Element(id="", type=type_, page=page, text=text or "", bbox=list(bbox) if bbox is not None else None,
                   level=level, table=table, reader=reader, confidence=confidence, attrs=attrs)
