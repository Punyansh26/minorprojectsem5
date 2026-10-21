"""Search a verified release with temporal filters and exact cutoff dimensions."""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from assistant.config import settings
from assistant.kb.common import read_json
from assistant.kb.embeddings import LocalE5
from assistant.kb.structured import is_rank_question, lookup_cutoffs, rank_filters, record_text
from assistant.kb.provenance import PUBLIC_FIELDS
from assistant.kb.integrity import model_path


def metadata_years(metadata: dict) -> set[int]:
    """Use reviewed row/source periods instead of publication years in filenames."""
    years = metadata.get("years", [])
    if isinstance(years, str):
        return {int(v) for v in years.split(",") if v.strip().isdigit()}
    return set(years or [])


def requested_years(question: str) -> set[int]:
    """Resolve relative current-year requests at query time."""
    years = {int(y) for y in re.findall(r"(?<!\d)(20\d{2})(?!\d)", question)}
    if not years and re.search(r"this year|current year|इस साल|इस वर्ष", question, re.I):
        years.add(datetime.now(ZoneInfo(settings.TIMEZONE)).year)
    return years


def eligible(metadata: dict, question: str) -> bool:
    """Filter before candidate selection; undated evidence cannot assert a dated cutoff."""
    if metadata.get("source_status") == "retired" or metadata.get("verification_status") not in (None, "extracted", "approved"):
        return False
    src, query = metadata_years(metadata), requested_years(question)
    if query and src and not src.intersection(query):
        return False
    if metadata.get("historical") and not query and not re.search(r"historical|previous|past|history|पुरान", question, re.I):
        return False
    return True


def tokens(text: str) -> list[str]:
    """Retain Indic vowel marks and normalize common institute abbreviations."""
    from assistant.retrieval import _STOPWORDS
    words = re.findall(r"[^\W_]+(?:[\u0900-\u097f]+)?", text.casefold())
    return [w for w in words if len(w) > 1 and w not in _STOPWORDS]


def requirements_priority(question, parent):
    """Prefer the actual qualified requirements over links to certificate formats."""
    wanted = "AI" if re.search(r"josaa|csab|all india",question,re.I) else "CG_NTPC" if re.search(r"\bcg\b|chhattisgarh|ntpc",question,re.I) else None
    audience = parent.get("audience")
    if wanted and audience and wanted != audience:
        return -1
    if wanted and wanted == audience and re.search(r"documents?|certificates?|reporting",question,re.I):
        return 2
    return int(bool(re.search(r"\b(?:documents?|certificates?)\b", question, re.I)
                and re.search(r"\b(?:admission|reporting|verification)\b", question, re.I)
                and re.search(r"documents\s+to\s+be\s+submitted\s+at\s+the\s+time\s+of\s+admission",
                              parent.get("text", ""), re.I)
                and parent.get("verification_status") in {"approved", "extracted"}))


class SearchEngine:
    """Cache one model, lexical index and parent map per immutable release."""

    def __init__(self, root: Path, manifest: dict, embeddings=None):
        from langchain_chroma import Chroma
        from assistant.telemetry import chroma_settings
        self.root, self.manifest = root, manifest
        self.embeddings = embeddings or LocalE5(str(model_path(root,manifest)), revision=manifest["revision"])
        self.store = Chroma(collection_name=manifest["collection"], persist_directory=str(root / "chroma"),
                            embedding_function=self.embeddings, client_settings=chroma_settings(),
                            create_collection_if_not_exists=False)
        profile = self.store._collection.metadata or {}
        if profile.get("embedding_model") != manifest["model"] or profile.get("embedding_revision") != manifest["revision"] or profile.get("hnsw:space") != "cosine":
            raise ValueError("Release embedding profile mismatch")
        self.parents = read_json(root / "parents.json", {})
        data = self.store.get(include=["documents", "metadatas"])
        self.rows = [(text, meta, Counter(tokens(text))) for text, meta in zip(data["documents"], data["metadatas"])]
        self.frequency = Counter(t for _, _, counts in self.rows for t in counts)
        self.average = sum(sum(c.values()) for _, _, c in self.rows) / max(1, len(self.rows))

    def search(self, question: str, k: int, category=None, preferred_category=None, filters=None):
        """Return exact rank rows or ranked source passages with original provenance."""
        from assistant.retrieval import RetrievedChunk
        from assistant.kb.policies import matching_rule
        policy = matching_rule(self.root,question)
        if policy and policy.get("evidence"):
            bound = []
            for span in policy["evidence"]:
                parent = next((p for p in self.parents.values() if eligible(p,question)
                    and p.get("source_sha256") == span["source_sha256"] and p.get("page_number") == span["page_number"]
                    and " ".join(span["quote"].split()) in " ".join(p["text"].split())),None)
                if parent is None:
                    return []
                bound.append(self.chunk(span["quote"],parent,-1))
            return bound
        # Narrow source-grounded aliasing fixes the repayment gap without increasing top-k.
        if re.search(r"vidya.?laxmi|विद्या.?लक्ष्मी|विद्या.?लक्षमी",question,re.I) and re.search(r"चुक|वापस|repay|moratorium|किस्त|अवधि|period|duration",question,re.I):
            question += " education loan repayment period excluding moratorium शिक्षा ऋण चुकौती अवधि मोरेटोरियम"
        if is_rank_question(question):
            constraints = rank_filters(question)
            if requested_years(question) and "year" not in constraints and len(requested_years(question)) == 1:
                constraints["year"] = next(iter(requested_years(question)))
            constraints.update(filters or {})
            rows = lookup_cutoffs(self.root / "facts.sqlite", constraints, limit=k)
            if rows:
                results = []
                for record in rows:
                    block = self.parents[record["evidence_block_id"]]
                    results.append(self.chunk(record_text(record, block), block, -1))
                return results
            # Avoid presenting a different category/round's number as the missing cutoff.
            return []
        allowed = [(t, m, c) for t, m, c in self.rows if eligible(m, question) and (not category or m["category"] == category)]
        if not allowed:
            return []
        allowed_parents = sorted({m["parent_id"] for _, m, _ in allowed})
        where = {"parent_id": {"$in": allowed_parents}}
        if category:
            where = {"$and": [where, {"category": category}]}
        limit = max(k, settings.RETRIEVAL_FETCH_K)
        semantic = self.store.similarity_search_with_score(question, k=min(limit, len(allowed)), filter=where)
        query = set(tokens(question))
        lexical = []
        for text, meta, counts in allowed:
            score = 0.0
            length = sum(counts.values())
            for term in query:
                count = counts[term]
                if count:
                    idf = math.log(1 + (len(self.rows) - self.frequency[term] + .5) / (self.frequency[term] + .5))
                    score += idf * count * 2.5 / (count + 1.5 * (.25 + .75 * length / max(self.average, 1)))
            if score:
                lexical.append((text, meta, score))
        lexical.sort(key=lambda row: row[2], reverse=True)
        candidates = {}
        for rows, semantic_flag in (([(d.page_content, d.metadata, s) for d, s in semantic], True), (lexical[:limit], False)):
            for rank, (text, meta, score) in enumerate(rows, 1):
                key = (meta["parent_id"], text)
                value = candidates.setdefault(key, [text, meta, float(score) if semantic_flag else -1, 0.0])
                value[3] += 1 / (60 + rank)
        ranked = sorted(candidates.values(), key=lambda row: (
            requirements_priority(question, self.parents.get(row[1]["parent_id"], {})),
            row[3] * (1.1 if row[1]["category"] == preferred_category else 1)), reverse=True)
        results, seen = [], set()
        for text, meta, distance, score in ranked:
            parent_id = meta["parent_id"]
            if parent_id in seen:
                continue
            parent = self.parents.get(parent_id, {})
            # Restore complete short evidence blocks, never an arbitrarily clipped table.
            if parent.get("text") and len(parent["text"]) <= 3500:
                text = "\n".join(x for x in (parent["title"], parent.get("period", ""), parent["text"]) if x)
            if parent.get("scope_note"):
                text += "\nVerification note: " + parent["scope_note"]
            if parent.get("conflict_note"):
                text += "\nSource conflict: " + parent["conflict_note"]
            results.append(self.chunk(text, meta, distance))
            seen.add(parent_id)
            if len(results) == k:
                break
        # Scheme benefits and disqualifying conditions travel together, even when their
        # paragraphs occur on different pages of the official document.
        related = []
        for item in results:
            parent = self.parents.get(item.block_id, {})
            for key in parent.get("related_evidence_block_ids", []):
                if key not in seen and key in self.parents:
                    other = self.parents[key]
                    related.append(self.chunk(other["text"], other, -1))
                    seen.add(key)
        if related:
            results = results[:1] + related[:k-1] + results[1:max(1, k-len(related))]
        return results

    @staticmethod
    def chunk(text, meta, distance):
        """Keep the legacy result fields while adding inspectable source locations."""
        from assistant.retrieval import RetrievedChunk
        years = meta.get("years", "")
        return RetrievedChunk(text=text, source_file=meta["source_file"], category=meta["category"],
            page_number=int(meta.get("page_number", -1)), score=distance,
            source_url=meta.get("source_url", ""), title=meta.get("title", ""), period=meta.get("period", ""),
            years=",".join(map(str, years)) if isinstance(years, list) else years,
            block_id=meta.get("parent_id", meta.get("id", "")), kind=meta.get("kind", "text"),
            extraction_method=meta.get("extraction_method", "native"), asset=meta.get("asset", ""),
            historical=meta.get("historical", False), verified=True,
            **{key:meta.get(key,"") for key in PUBLIC_FIELDS})
