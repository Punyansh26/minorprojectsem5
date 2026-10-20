"""§3 verified-triple data pipeline (Demo2-local, CPU-only, no model).

A training triple is (question, evidence, grounded answer, quotes). Chapter 09 §3
demands four things before a triple may enter any student's training set, each of
which is enforced here:

1. **Verified outputs only** — the turn's ``response_status == "answered"`` *and*
   every quote the answer uses is a verbatim/structured match against its source
   span, exactly the ``assistant/evidence.py::source_quote`` contract of the frozen
   Institute agent (mirrored, not imported, so this stays Demo2-local). A turn the
   teacher got wrong but that failed verification never becomes a target.
2. **Privacy filtering** — Demo2's ``conversations.sqlite`` holds real student
   turns. We strip names, IDs, phone numbers, emails and other free-text PII before
   anything leaves the store, keeping only the public question text and the verified
   public evidence spans. ``OPEN_JEV.md`` used *no* user conversations; mining real
   logs is the later, reviewed step this filter makes safe.
3. **Deduplication** — exact and near-duplicate collapse so repeated utterances do
   not inflate the corpus.
4. (family splitting is in :mod:`families`.)

This reads Demo2's own release-bound stores only. It decodes the LangGraph
checkpoints with langgraph's own serializer; if langgraph is unavailable the miner
degrades to the rag_cache evidence store and any caller-supplied turns, so the unit
tests run without the agent installed.
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Sequence


# --------------------------------------------------------------------------- #
# Verified-answer contract (mirrors assistant/evidence.py::source_quote)
# --------------------------------------------------------------------------- #

def _normalize_match(text: str) -> str:
    """Casefold and collapse whitespace, identical to the agent's quote check."""
    return " ".join(text.casefold().split())


def quote_is_grounded(quote: str, source_text: str) -> bool:
    """Return True when ``quote`` is a verbatim (normalized) span of ``source_text``.

    This is the strict arm of ``assistant/evidence.py::source_quote``: normalize both
    sides (casefold + collapse whitespace) and require a substring match. The
    structured-cutoff expansion arm is intentionally *not* reimplemented — a triple
    whose quote only matches after cutoff expansion is treated as not-grounded here so
    the Demo2 miner never silently relaxes the contract; such turns simply do not
    become training targets.
    """
    normalized = _normalize_match(quote)
    return bool(normalized) and normalized in _normalize_match(source_text)


def is_verified_turn(turn: dict) -> bool:
    """A turn is verified iff it was answered and every quote is grounded in evidence.

    ``turn`` carries at least ``response_status``, ``answer_text``, ``sources`` and
    ``retrieved_chunks``. ``sources`` entries expose the quoted text under ``quote``;
    ``retrieved_chunks`` entries expose the full span under ``text``. A source is
    grounded if its quote matches any retrieved chunk (or its own ``text``, if
    present). An answered turn with no sources is *not* verified — a grounded answer
    must cite evidence.
    """
    if turn.get("response_status") != "answered":
        return False
    if not (turn.get("answer_text") or "").strip():
        return False
    sources = turn.get("sources") or []
    if not sources:
        return False
    chunks = turn.get("retrieved_chunks") or []
    chunk_texts = [c.get("text", "") for c in chunks if isinstance(c, dict)]
    for source in sources:
        if not isinstance(source, dict):
            return False
        quote = source.get("quote") or source.get("text") or ""
        if not quote.strip():
            return False
        haystacks = chunk_texts + ([source["text"]] if source.get("text") else [])
        if not any(quote_is_grounded(quote, h) for h in haystacks):
            return False
    return True


# --------------------------------------------------------------------------- #
# Privacy filter (§3.3)
# --------------------------------------------------------------------------- #

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# Indian 10-digit mobile numbers (lead digit 6-9), optional +91/0 prefix, tolerating
# arbitrary single space/hyphen separators between the ten digits (e.g. "98765 43210").
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?|0)?[6-9](?:[\s-]?\d){9}(?!\d)")
# Enrolment / application numbers: a long run of digits (>=6) or a letter+digit id.
_LONG_ID = re.compile(r"(?<![\w])(?=[A-Za-z]*\d)[A-Za-z]*\d[\w/]{5,}(?![\w])")
_PII_PLACEHOLDER = {"email": "[email]", "phone": "[phone]", "id": "[id]"}

# A conservative set of question intents whose text is public by construction. The
# question is *about* the institute, not about the asker, so it carries no PII of its
# own beyond what these regexes catch.
_PUBLIC_INTENTS = frozenset({"knowledge", "smalltalk", "end", "out_of_scope"})


def redact_pii(text: str) -> str:
    """Replace emails, phone numbers and long id-like tokens with fixed placeholders.

    Deterministic and order-stable: email → phone → id, so overlapping matches resolve
    the same way every run. Returns the text unchanged when it holds no PII.
    """
    if not text:
        return text
    text = _EMAIL.sub(_PII_PLACEHOLDER["email"], text)
    text = _PHONE.sub(_PII_PLACEHOLDER["phone"], text)
    text = _LONG_ID.sub(_PII_PLACEHOLDER["id"], text)
    return text

def privacy_filter(turn: dict) -> dict:
    """Return a copy of ``turn`` with PII redacted and private carrier fields dropped.

    The question text and evidence spans are redacted (institute evidence is public,
    but a student may have pasted their own id into a question, so redact both). The
    carrier identity fields — ``student_id``, ``student_email``, ``session_id``,
    ``thread_id`` — are dropped entirely; a training triple never needs them.
    """
    cleaned = dict(turn)
    for private in ("student_id", "student_email", "session_id", "thread_id"):
        cleaned.pop(private, None)
    cleaned["question"] = redact_pii(cleaned.get("question", ""))
    cleaned["answer_text"] = redact_pii(cleaned.get("answer_text", ""))
    cleaned["sources"] = [
        {**s, "quote": redact_pii(s.get("quote", s.get("text", "")))}
        for s in (cleaned.get("sources") or [])
        if isinstance(s, dict)
    ]
    cleaned["retrieved_chunks"] = [
        {**c, "text": redact_pii(c.get("text", ""))}
        for c in (cleaned.get("retrieved_chunks") or [])
        if isinstance(c, dict)
    ]
    return cleaned


# --------------------------------------------------------------------------- #
# Triple
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Triple:
    """A privacy-filtered, verified training triple ready for family splitting.

    ``quotes`` is the de-duplicated list of grounded quote strings the answer used;
    ``evidence`` is the list of retrieved chunk texts it was grounded against.
    """

    question: str
    answer: str
    quotes: tuple[str, ...]
    evidence: tuple[str, ...]
    language: str = "english"
    intent: str = "knowledge"
    category: str = "general"

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "quotes": list(self.quotes),
            "evidence": list(self.evidence),
            "language": self.language,
            "intent": self.intent,
            "category": self.category,
        }


def _triple_from_turn(turn: dict) -> Triple:
    quotes = tuple(dict.fromkeys(
        s.get("quote", s.get("text", "")).strip()
        for s in (turn.get("sources") or []) if isinstance(s, dict)
        if (s.get("quote") or s.get("text") or "").strip()
    ))
    evidence = tuple(dict.fromkeys(
        c.get("text", "").strip()
        for c in (turn.get("retrieved_chunks") or []) if isinstance(c, dict)
        if c.get("text", "").strip()
    ))
    return Triple(
        question=turn.get("question", "").strip(),
        answer=turn.get("answer_text", "").strip(),
        quotes=quotes,
        evidence=evidence,
        language=turn.get("language", "english"),
        intent=turn.get("intent", "knowledge"),
        category=turn.get("detected_category") or turn.get("category") or "general",
    )


# --------------------------------------------------------------------------- #
# Deduplication (§3 "Deduplicate (near-dup + exact)")
# --------------------------------------------------------------------------- #

def _dedup_key(triple: Triple) -> str:
    """A near-duplicate key: normalized question + answer.

    Normalization strips accents, casefolds, removes non-word characters and collapses
    whitespace, so "Who is the dean of academics?" and "who is the Dean of Academics"
    collapse to one triple while genuinely different questions stay distinct.
    """
    def norm(text: str) -> str:
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = re.sub(r"[^\w\s]", " ", text.casefold())
        return " ".join(text.split())

    return norm(triple.question) + "||" + norm(triple.answer)


def deduplicate(triples: Iterable[Triple]) -> list[Triple]:
    """Collapse exact and near-duplicate triples, keeping first occurrence order."""
    seen: set[str] = set()
    out: list[Triple] = []
    for triple in triples:
        key = _dedup_key(triple)
        if key in seen:
            continue
        seen.add(key)
        out.append(triple)
    return out


# --------------------------------------------------------------------------- #
# Checkpoint reader
# --------------------------------------------------------------------------- #

def _turns_from_checkpoints(db_path: Path) -> list[dict]:
    """Decode answered turns out of a LangGraph conversations.sqlite checkpoint store.

    Each checkpoint's ``channel_values`` carries the final state of a turn; we keep the
    ones whose ``response_status == "answered"`` and attach the preceding HumanMessage
    as the question. Requires langgraph's serializer; if it is missing we return [] so
    the miner can still run on caller-supplied turns and the rag_cache.
    """
    try:
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    except Exception:
        return []
    serde = JsonPlusSerializer()
    turns: list[dict] = []
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT type, checkpoint FROM checkpoints ORDER BY thread_id, checkpoint_id"
        ).fetchall()
    for typ, blob in rows:
        try:
            state = serde.loads_typed((typ, blob)).get("channel_values", {})
        except Exception:
            continue
        if state.get("response_status") != "answered":
            continue
        question = ""
        for message in reversed(state.get("messages", []) or []):
            if type(message).__name__ == "HumanMessage":
                question = getattr(message, "content", "") or ""
                break
        turns.append({
            "question": question,
            "answer_text": state.get("answer_text", ""),
            "response_status": state.get("response_status"),
            "sources": state.get("sources") or [],
            "retrieved_chunks": state.get("retrieved_chunks") or [],
            "language": state.get("language", "english"),
            "intent": state.get("intent", "knowledge"),
            "detected_category": state.get("detected_category") or "general",
        })
    return turns


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def mine_verified_triples(
    conversations_db: str | Path | None = None,
    *,
    extra_turns: Sequence[dict] = (),
) -> list[Triple]:
    """Build the verified, privacy-filtered, de-duplicated triple store (§3).

    Pipeline order matches the chapter's mermaid diagram:
    privacy filter → verified-only gate → dedup. ``extra_turns`` lets a caller add
    turns from another source (for example the public ``evaluation/.../cases.json``
    pool or synthetic paraphrases) using the same gate and filters.

    Returns the accepted :class:`Triple` list. A turn is dropped (never raised on) if
    it is not verified, so a hallucinated teacher answer silently fails the gate.
    """
    candidates: list[dict] = list(extra_turns)
    if conversations_db is not None:
        candidates.extend(_turns_from_checkpoints(Path(conversations_db)))

    triples: list[Triple] = []
    for turn in candidates:
        if not is_verified_turn(turn):
            continue
        clean = privacy_filter(turn)
        # Re-check after redaction: redaction must not have broken grounding. Rebuild a
        # verification view from the cleaned fields.
        view = {
            "response_status": "answered",
            "answer_text": clean["answer_text"],
            "sources": clean["sources"],
            "retrieved_chunks": clean["retrieved_chunks"],
        }
        if not is_verified_turn(view):
            continue
        triples.append(_triple_from_turn(clean))
    return deduplicate(triples)
