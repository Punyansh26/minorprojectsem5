"""Stage 6 — enrichment: contextual prefixes, bilingual questions, and atomic propositions.

All enrichment is:
1. Generated offline and cached content-addressed in SQLite.
2. Index-only: improves dense and sparse retrieval ranking.
3. NEVER treated as evidence or shown in quotes (doc 15 §6). Quotes always come
   from the original verified parent text.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from .config import Config
from .llm import LLMClient
from .models import Parent, Unit
from .textnorm import content_overlap

log = logging.getLogger(__name__)

PROMPT_CONTEXT = """<document_summary>{doc_summary}</document_summary>
<section_path>{heading_path}</section_path>
<section>{parent_text}</section>
Write 1–3 short sentences (50–100 tokens) situating this section within the document for search retrieval.
Name the institution (IIIT-NR), the document, and the exact topic. Do NOT restate numbers or fees.
Return ONLY the short context string."""

PROMPT_QUESTIONS = """Given this document section:
<section>{parent_text}</section>
Write 3 short questions a student might ask that this section answers directly:
- Exactly 2 questions in English
- Exactly 1 question in Hindi (Devanagari) or Hinglish
Return a JSON array of strings only. Example: ["Question 1", "Question 2", "प्रश्न 3"]"""


def enrich_parents_and_units(
    cfg: Config,
    llm: LLMClient,
    parents: list[Parent],
    units: list[Unit],
    doc_summary: str = "",
) -> list[Unit]:
    """Apply contextual prefixes and bilingual questions to retrieval units."""
    if not cfg.enrich.enabled:
        return units

    parent_map = {p.id: p for p in parents}

    for parent in parents:
        # 1. Contextual prefix
        if cfg.enrich.context and not parent.context:
            prompt = PROMPT_CONTEXT.format(
                doc_summary=doc_summary or parent.meta.get("title", ""),
                heading_path=" › ".join(parent.heading_path),
                parent_text=parent.text[:cfg.enrich.max_parent_chars_in_prompt],
            )
            try:
                ctx = llm.generate(prompt)
                parent.context = ctx.strip()
            except Exception as exc:
                log.warning("Context generation failed for parent %s: %s", parent.id, exc)

        # 2. Bilingual questions
        if cfg.enrich.questions and not parent.questions:
            prompt = PROMPT_QUESTIONS.format(
                parent_text=parent.text[:cfg.enrich.max_parent_chars_in_prompt]
            )
            try:
                res = llm.generate(prompt, json_mode=True)
                data = json.loads(res)
                if isinstance(data, list):
                    parent.questions = [str(q).strip() for q in data if str(q).strip()]
                elif isinstance(data, dict) and "questions" in data:
                    parent.questions = [str(q).strip() for q in data["questions"]]
            except Exception as exc:
                log.warning("Questions generation failed for parent %s: %s", parent.id, exc)

    # Propagate generated context and questions to retrieval units
    extra_question_units: list[Unit] = []
    for u in units:
        p = parent_map.get(u.parent_ids[0]) if u.parent_ids else None
        if p and p.context:
            u.context = p.context

        # Add questions as dedicated small retrieval units pointing to the same parent
        if p and p.questions and u.type in {"section", "table"}:
            for q_idx, q in enumerate(p.questions, 1):
                extra_question_units.append(Unit(
                    id=f"{u.id}:q{q_idx}",
                    type="question",
                    parent_ids=list(u.parent_ids),
                    doc_id=u.doc_id,
                    text=q,
                    header=u.header,
                    status=u.status,
                    meta=dict(u.meta),
                ))

    return units + extra_question_units
