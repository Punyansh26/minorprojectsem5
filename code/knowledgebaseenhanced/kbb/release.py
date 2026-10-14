"""Immutable knowledge-base releases: build, search, evaluate, activate, roll back.

Layout (``data/kbb``)::

    releases/<id>/  release.json  validation.json  parents.json  units.json  vectors.npy
                    facts.sqlite  policies.json  sources.json  extraction_report.json
    active.json  previous.json                      # pointer = release id + hashes of manifest and validation

``parents.json`` deliberately uses the block schema of the institute assistant (``source_file``,
``page_number``, ``verification_status`` ...) so its LangGraph nodes, policy rules, cache keys and citation code
consume a kbb release unchanged.  Hits expose the same fields as ``assistant.retrieval.RetrievedChunk``.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from . import facts as factdb
from .chunk import _build_units_from_parents, build_parents_and_units
from .config import Config
from .corpus import load_corpus
from .index import BM25Index, LocalEmbedder
from .integrity import IntegrityError, content_digest, content_hashes, file_hash, verify
from .legacy_import import PAGE_EXTRA_FIELDS, legacy_only_parents, load_legacy, page_overrides
from .models import Parent, Unit
from .reviews import load_reviews, make_lookup
from .store import read_json, write_json
from .textnorm import sha256

PIPELINE_VERSION = "kbb-3.0"
DOMAIN_WORDS = re.compile(r"(?i)\b(iiit[- ]?nr|iiit|naya|raipur|institute|college|campus|nr)\b")
SERVABLE = {"approved", "extracted", "machine_verified"}


@dataclass
class Hit:
    """Field-compatible with ``assistant.retrieval.RetrievedChunk``."""
    text: str
    source_file: str
    category: str
    page_number: int
    score: float
    source_url: str = ""
    title: str = ""
    period: str = ""
    years: str = ""
    block_id: str = ""
    kind: str = "text"
    extraction_method: str = "native"
    asset: str = ""
    historical: bool = False
    verified: bool = True
    source_sha256: str = ""
    audience: str = ""
    conflict_note: str = ""
    scope_note: str = ""
    source_owner: str = ""
    review_by: str = ""
    source_status: str = ""
    superseded_by: str = ""


# ----------------------------------------------------------------------------- query understanding
def is_rank_question(question: str) -> bool:
    return bool(re.search(r"\brank\b|\branks\b|cut.?off|रैंक|कट.?ऑफ", question, re.I))


def rank_filters(question: str) -> dict:
    """Explicit dimensions only; a student's category or quota is never guessed."""
    q = question.casefold()
    result: dict[str, Any] = {}
    years = re.findall(r"\b20\d{2}\b", q)
    if len(set(years)) == 1:
        result["year"] = int(years[0])
    rounds = re.search(r"(?:\bround|राउंड|चरण)\s*[-:]?\s*(\d+)\b", q)
    if rounds:
        result["round"] = rounds.group(1)
    programmes = [label for label, pat in (("DSAI", r"\bdsai\b|data science|डीएसएआई"), ("CSE", r"\bcse\b|computer science|सीएसई"),
                                           ("ECE", r"\bece\b|electronics|ईसीई")) if re.search(pat, q)]
    if len(programmes) == 1:
        result["programme"] = programmes[0]
    categories = [c for c, pat in (("OBC-NCL", r"\bobc(?:-ncl)?\b|ओबीसी"), ("GEN-EWS", r"\bews\b|ईडब्ल्यूएस"), ("SC", r"\bsc\b|एससी"),
                                   ("ST", r"\bst\b|एसटी"), ("OPEN", r"\bopen\b|\bgeneral category\b|सामान्य श्रेणी")) if re.search(pat, q)]
    if len(categories) == 1:
        result["seat_category"] = categories[0]
    if re.search(r"\bpwd\b", q):
        if "seat_category" in result:
            result["seat_category"] += " (PwD)"
        else:
            result["rank_basis"] = "PwD category rank"
    if "ntpc" in q:
        result["quota"] = "NTPC"
    elif re.search(r"\bcg\b|chhattisgarh quota|state quota", q):
        result["quota"] = "CG"
    elif "all india" in q or "ऑल इंडिया" in q:
        result["quota"] = "AI"
    for authority in ("JoSAA", "CSAB"):
        if authority.casefold() in q:
            result["authority"] = authority
    if "spot" in q:
        result["authority"] = "IIIT-NR Spot"
    if re.search(r"female|girls|women|महिला", q):
        result["gender_pool"] = "Female-only (including Supernumerary)"
    elif "gender-neutral" in q or "gender neutral" in q:
        result["gender_pool"] = "Gender-Neutral"
    if re.search(r"\bcrl\b|common rank", q):
        result["rank_basis"] = "CRL"
    return result


def rank_text(record: dict, evidence_text: str) -> str:
    labels = {"year": "Admission year", "authority": "Counselling", "round": "Round", "programme": "Programme",
              "quota": "Quota", "seat_category": "Seat category", "gender_pool": "Seat pool", "rank_basis": "Rank basis",
              "opening_rank": "Opening rank", "closing_rank": "Closing rank"}
    return ("IIIT Naya Raipur published opening and closing ranks\n"
            + "\n".join(f"{labels[k]}: {record[k]}" for k in labels) + "\nSource row: " + evidence_text)


def requested_years(question: str) -> set[int]:
    years = {int(y) for y in re.findall(r"(?<!\d)(20\d{2})(?!\d)", question)}
    if not years and re.search(r"this year|current year|इस साल|इस वर्ष", question, re.I):
        years.add(datetime.now().year)
    return years


def eligible(block: dict, question: str) -> bool:
    """Serve only servable, current-enough evidence for the years the user asked about."""
    if block.get("source_status") == "retired" or block.get("verification_status") not in SERVABLE:
        return False
    src, query = set(block.get("years") or []), requested_years(question)
    if query and src and not src & query:
        return False
    if block.get("historical") and not query and not re.search(r"historical|previous|past|history|पुरान|old", question, re.I):
        return False
    return True


# ----------------------------------------------------------------------------- build
def parent_to_block(p: Parent) -> dict:
    m = p.meta
    block = {"id": p.id, "source_id": m.get("doc_id", p.doc_id), "source_file": m.get("source_file", ""),
             "source_url": m.get("source_url", ""), "title": m.get("title", ""), "category": m.get("category", "general"),
             "topic": m.get("topic", m.get("category", "general")), "page_number": p.page_start, "kind": p.kind,
             "text": p.text, "source_sha256": m.get("source_sha256", ""), "years": list(m.get("years") or []),
             "period": m.get("period", ""), "programme": m.get("programme", ""), "historical": bool(m.get("historical")),
             "verification_status": p.status, "extraction_method": p.readers[0] if p.readers else "",
             "heading_path": p.heading_path, "asset": m.get("asset", ""), "published_at": m.get("published_at", "")}
    for key in PAGE_EXTRA_FIELDS:
        if m.get(key):
            block[key] = m[key]
    if p.related_parent_ids:
        block["related_evidence_block_ids"] = p.related_parent_ids
    if m.get("field_evidence"):
        block["field_evidence"] = m["field_evidence"]
    return block


def _record_parents(records: list[dict], parents: dict[str, Parent]) -> list[Parent]:
    """Indexable evidence for scholarship/finance records (conditions stay attached to their pages)."""
    out = []
    for rec in records:
        if rec["kind"] not in {"finance", "scholarship"} or rec.get("quote"):
            continue
        keys = list(dict.fromkeys([rec["evidence_block_id"], *rec.get("related_evidence_block_ids", [])]))
        spans = {}
        for field_name in ("benefit", "conditions"):
            value = rec.get(field_name)
            if value:
                src = next(parents[k] for k in keys if factdb.quote_in(value, parents[k].text))
                spans[field_name] = {"block_id": src.id, "page_number": src.page_start,
                                     "source_sha256": src.meta.get("source_sha256"), "quote": value}
        for index, key in enumerate(keys):
            original = parents[key]
            header = f"{rec['name']} ({rec['kind']})\nIIIT-NR applicability: {rec['institution_applicability']}\n"
            if rec["kind"] == "scholarship":
                header += f"Conditions: {rec['conditions']}\nBenefit: {rec.get('benefit', 'Not established by this evidence')}\n"
            clone = Parent(**{**asdict(original), "id": f"record-{rec['id']}-{index}", "kind": rec["kind"],
                              "text": (header if rec["kind"] == "scholarship" else "") + original.text,
                              "related_parent_ids": [k for k in keys if k != key]})
            clone.meta = {**original.meta, "scope_note": "General scheme rules; IIIT-NR applicability: " + rec["institution_applicability"],
                          "field_evidence": json.dumps(spans, ensure_ascii=False, sort_keys=True)}
            out.append(clone)
    return out


def build_release(cfg: Config, state: Path, *, processed_dir: Path, source_root: Path, legacy_state: Path,
                  curated_path: Path, record_reviews_path: Path, device: str = "cpu", embed: bool = True) -> dict:
    """Assemble one immutable release.  Raises if a policy rule or record loses its evidence."""
    started = time.monotonic()
    legacy = load_legacy(legacy_state)
    overrides, extras = page_overrides(legacy)
    docs = load_corpus(processed_dir, source_root, make_lookup(load_reviews()), overrides)
    parents: dict[str, Parent] = {}
    units: list[Unit] = []
    notes: dict[str, list[str]] = {}
    for doc in docs:
        if not doc.elements:
            notes[doc.meta["doc_id"]] = doc.notes + ["no servable text"]
            continue
        doc_parents, doc_units = build_parents_and_units(cfg, doc.meta["doc_id"], doc.elements, doc.meta)
        base = Path(doc.meta.get("source_file", "")).name
        for p in doc_parents:
            extra = extras.get((base, p.page_start))
            if extra:
                p.meta.update(extra)
                p.related_parent_ids = list(extra.get("related_evidence_block_ids", []))
        parents.update({p.id: p for p in doc_parents})
        units.extend(doc_units)
        if doc.notes:
            notes[doc.meta["doc_id"]] = doc.notes
    new_basenames = {Path(d.meta.get("source_file", "")).name for d in docs}
    imported = legacy_only_parents(legacy, new_basenames)
    by_doc: dict[str, list[Parent]] = {}
    for p in imported:
        parents[p.id] = p
        by_doc.setdefault(p.doc_id, []).append(p)
    for doc_id, group in by_doc.items():
        units.extend(u for u in _build_units_from_parents(cfg, doc_id, [g for g in group if g.kind != "cutoff"], [], group[0].meta))
    # --- typed records: derived from evidence + curated + migrated (cutoffs, scholarships, finance)
    curated = read_json(curated_path, []) if curated_path.exists() else []
    records, rejected = factdb.build_records(parents, curated)
    migrated, migration_rejected = [], []
    for rec in legacy["records"]:
        rec = {**rec, "id": rec.get("id") or sha256(json.dumps(rec, sort_keys=True))[:24], "migrated_validated": True}
        try:
            factdb.validate_record(rec, parents)
            migrated.append(rec)
        except factdb.FactError as error:
            migration_rejected.append({"id": rec.get("id"), "kind": rec.get("kind"), "reason": str(error)})
    if migration_rejected:
        raise ValueError(f"{len(migration_rejected)} migrated records lost their evidence: {migration_rejected[:3]}")
    records += migrated
    for p in _record_parents(migrated, parents):
        parents[p.id] = p
        as_text = Parent(**{**asdict(p), "kind": "text"})        # the unit builder indexes text/table parents
        units.extend(_build_units_from_parents(cfg, p.id, [as_text], [], p.meta))
    # --- policies must stay bound to real evidence
    policies = legacy["policies"]
    blocks = {pid: parent_to_block(p) for pid, p in parents.items()}
    unresolved = []
    for rule in policies.get("rules", []):
        for span in rule.get("evidence", []):
            if not any(b["source_sha256"] == span["source_sha256"] and b["page_number"] == span["page_number"]
                       and b["verification_status"] in SERVABLE and factdb.quote_in(span["quote"], b["text"]) for b in blocks.values()):
                unresolved.append({"rule": rule["id"], "page": span["page_number"], "quote": span["quote"][:60]})
    if unresolved:
        raise ValueError(f"policy evidence not found in new parents: {unresolved}")
    # --- write
    release_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = state / "releases" / release_id
    root.mkdir(parents=True)
    decisions = read_json(record_reviews_path, {"decisions": {}}).get("decisions", {}) if record_reviews_path.exists() else {}
    stored = factdb.create_database(root / "facts.sqlite", records, parents, decisions)
    servable_units = [u for u in units if u.status in cfg.retrieval.statuses and u.meta.get("kind") != "cutoff"]
    model_path = cfg.embedding.model_path if Path(cfg.embedding.model_path).exists() else cfg.embedding.model
    if embed:
        embedder = LocalEmbedder(model_path, cfg.embedding.max_tokens, cfg.embedding.family, device=device)
        vectors = embedder.embed_units([u.embed_text() for u in servable_units], batch_size=cfg.embedding.batch_size)
    else:
        vectors = np.zeros((len(servable_units), 384), dtype=np.float32)
    np.save(root / "vectors.npy", vectors.astype(np.float16))
    write_json(root / "units.json", [u.to_dict() for u in servable_units])
    write_json(root / "parents.json", blocks)
    write_json(root / "policies.json", policies)
    sources: dict[str, dict] = {}
    for b in blocks.values():
        s = sources.setdefault(b["source_id"], {"id": b["source_id"], "sha256": b["source_sha256"], "title": b["title"],
                                                "source_file": b["source_file"], "source_status": "active",
                                                "source_owner": b.get("source_owner", "unassigned"), "review_by": b.get("review_by", ""),
                                                "superseded_by": b.get("superseded_by", "")})
    write_json(root / "sources.json", {"sources": list(sources.values())})
    status_counts: dict[str, int] = {}
    for p in parents.values():
        status_counts[p.status] = status_counts.get(p.status, 0) + 1
    write_json(root / "extraction_report.json", {"documents": len(docs), "document_notes": notes, "rejected_records": rejected,
                                                  "parents_by_status": status_counts})
    manifest = {"release": release_id, "status": "complete", "engine": "kbb", "manifest_version": 3,
                "pipeline_version": PIPELINE_VERSION, "created_at": datetime.now(timezone.utc).isoformat(),
                "model": cfg.embedding.model, "revision": cfg.embedding.revision, "metric": "cosine",
                "chunks": len(servable_units), "evidence_blocks": len(blocks), "documents": len(docs) + len(by_doc),
                "structured_records": len(stored), "cutoff_records": sum(r["kind"] == "cutoff" for r in stored),
                "parents_by_status": status_counts, "records_by_status": factdb.stats(root / "facts.sqlite"),
                "rejected_records": len(rejected), "seconds": round(time.monotonic() - started, 1),
                "content_sha256": content_hashes(root)}
    write_json(root / "release.json", manifest)
    write_json(state / "latest_build.json", {"release": release_id})
    return manifest


# ----------------------------------------------------------------------------- search
class ReleaseSearch:
    """Policy -> exact rank lookup -> matched facts -> hybrid (dense + BM25) retrieval with parent expansion."""

    def __init__(self, root: Path, *, device: str = "cpu", check_integrity: bool = True):
        self.root = Path(root)
        self.manifest = read_json(self.root / "release.json")
        if check_integrity:
            verify(self.root, self.manifest)
        self.parents: dict[str, dict] = read_json(self.root / "parents.json")
        self.units = [Unit.from_dict(u) for u in read_json(self.root / "units.json")]
        self.vectors = np.load(self.root / "vectors.npy").astype(np.float32)
        self.unit_index = {u.id: i for i, u in enumerate(self.units)}
        self.bm25 = BM25Index()
        self.bm25.build([u.id for u in self.units], [u.embed_text() for u in self.units])
        self.policies = read_json(self.root / "policies.json", {"rules": []}).get("rules", [])
        from .config import get_config
        cfg = get_config()
        model_path = cfg.embedding.model_path if Path(cfg.embedding.model_path).exists() else cfg.embedding.model
        self.embedder = LocalEmbedder(model_path, cfg.embedding.max_tokens, cfg.embedding.family, device=device)
        self.cfg = cfg
        self.embeddings = self                         # `embed_questions` is used by knowledge-gap analysis

    def embed_questions(self, texts: list[str]) -> list[list[float]]:
        return [self.embedder.embed_query(t).tolist() for t in texts]

    # -- helpers
    def hit(self, text: str, block: dict, score: float = -1.0) -> Hit:
        years = block.get("years", "")
        return Hit(text=text, source_file=block["source_file"], category=block.get("category", "general"),
                   page_number=int(block.get("page_number", -1)), score=float(score), source_url=block.get("source_url", ""),
                   title=block.get("title", ""), period=block.get("period", ""),
                   years=",".join(map(str, years)) if isinstance(years, list) else str(years), block_id=block["id"],
                   kind=block.get("kind", "text"), extraction_method=block.get("extraction_method", ""),
                   asset=block.get("asset", ""), historical=bool(block.get("historical")), verified=True,
                   **{k: block.get(k, "") for k in ("source_sha256", "audience", "conflict_note", "scope_note",
                                                     "source_owner", "review_by", "source_status", "superseded_by")})

    def matching_policy(self, question: str):
        if re.search(r"\bm\.?tech|\bph\.?d|\bmbbs", question, re.I):
            return None
        for rule in self.policies:
            if not re.search(rule["match"], question, re.I) or (rule.get("exclude") and re.search(rule["exclude"], question, re.I)):
                continue
            requested = set(re.findall(r"\b20\d{2}\b", question))
            if rule.get("year") and requested and str(rule["year"]) not in requested:
                continue
            return rule
        return None

    def expand(self, block: dict, question: str, prefix: str = "") -> str:
        text = block["text"]
        if len(text) <= 3500:
            text = "\n".join(x for x in (block.get("title", ""), block.get("period", ""), text) if x)
        if block.get("scope_note"):
            text += "\nVerification note: " + block["scope_note"]
        if block.get("conflict_note"):
            text += "\nSource conflict: " + block["conflict_note"]
        return (prefix + "\n" if prefix else "") + text

    # -- search
    def search(self, question: str, k: int = 6, category=None, preferred_category=None, filters=None) -> list[Hit]:
        if not question.strip():
            return []
        if re.search(r"vidya.?laxmi|विद्या.?लक्ष्मी|विद्या.?लक्षमी", question, re.I) and re.search(
                r"चुक|वापस|repay|moratorium|किस्त|अवधि|period|duration", question, re.I):
            question += " education loan repayment period excluding moratorium शिक्षा ऋण चुकौती अवधि मोरेटोरियम"
        policy = self.matching_policy(question)
        if policy and policy.get("evidence"):
            bound = []
            for span in policy["evidence"]:
                block = next((b for b in self.parents.values() if eligible(b, question) and b["source_sha256"] == span["source_sha256"]
                              and b["page_number"] == span["page_number"] and factdb.quote_in(span["quote"], b["text"])), None)
                if block is None:
                    return []
                bound.append(self.hit(span["quote"], block))
            return bound
        if is_rank_question(question):
            constraints = rank_filters(question)
            if len(requested_years(question)) == 1 and "year" not in constraints:
                constraints["year"] = next(iter(requested_years(question)))
            constraints.update(filters or {})
            rows = factdb.lookup_cutoffs(self.root / "facts.sqlite", constraints, limit=k)
            return [self.hit(rank_text(r, self.parents[r["evidence_block_id"]]["text"]), self.parents[r["evidence_block_id"]]) for r in rows]
        matched = factdb.match_records(self.root / "facts.sqlite", question)
        scores: dict[str, float] = {}
        q_years = requested_years(question)
        q_vec = self.embedder.embed_query(question)
        sims = self.vectors @ q_vec
        n = self.cfg.retrieval.per_type_k * 2
        dense = [(self.units[i].id, float(sims[i])) for i in np.argsort(-sims)[:n * 3]]
        # Words present in nearly every page of this corpus carry no signal for the sparse channel.
        sparse = self.bm25.search(DOMAIN_WORDS.sub(" ", question), top_k=n * 3)
        for channel, weight in ((dense, self.cfg.retrieval.channel_weights.get("dense", 1.0)),
                                (sparse, self.cfg.retrieval.channel_weights.get("bm25", 1.0))):
            rank = 0
            best: dict[str, float] = {}                  # a parent counts once per channel (its best unit),
            for unit_id, _ in channel:                    # so big tables with many row units cannot drown prose
                unit = self.units[self.unit_index[unit_id]]
                live = [pid for pid in unit.parent_ids if pid in self.parents and eligible(self.parents[pid], question)
                        and (not category or self.parents[pid].get("category") == category)]
                if not live:
                    continue
                rank += 1
                if rank > n:
                    break
                for pid in live:
                    boost = 1.1 if preferred_category and self.parents[pid].get("category") == preferred_category else 1.0
                    if q_years and set(self.parents[pid].get("years") or []) & q_years:
                        boost *= 2.0
                    value = boost * weight * self.cfg.retrieval.type_weights.get(unit.type, 1.0) / (self.cfg.retrieval.rrf_k + rank)
                    best[pid] = max(best.get(pid, 0.0), value)
            for pid, value in best.items():
                scores[pid] = scores.get(pid, 0.0) + value
        ranked = [pid for pid, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
        results: list[Hit] = []
        seen: set[str] = set()

        def add(pid: str, prefix: str = "", score: float = 0.0):
            if pid in seen or pid not in self.parents or not eligible(self.parents[pid], question):
                return
            seen.add(pid)
            results.append(self.hit(self.expand(self.parents[pid], question, prefix), self.parents[pid], score))

        for rec in matched:                               # exact rows first; the parent keeps its citation
            add(rec["evidence_block_id"], "Matched source row: " + rec["quote"] if rec.get("quote") else "", 1.0)
        for pid in ranked:
            add(pid, "", scores[pid])
            if len(results) >= k:
                break
        for hit in list(results):                         # scheme benefits travel with their conditions
            for key in self.parents.get(hit.block_id, {}).get("related_evidence_block_ids", []):
                if len(results) < k + 2:
                    add(key)
        return results[:max(k, 1) + 2] if results else []


# ----------------------------------------------------------------------------- lifecycle
def latest_release(state: Path) -> str:
    return read_json(state / "latest_build.json")["release"]


def evaluate(state: Path, release_id: str, cases_path: Path, *, min_legacy_pass: float = 1.0, device: str = "cpu") -> dict:
    """Run the spot-check set and write ``validation.json`` (the gate for activation)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("spotcheck", Path(__file__).resolve().parent.parent / "scripts" / "spotcheck.py")
    sc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sc)
    root = state / "releases" / release_id
    manifest = read_json(root / "release.json")
    verify(root, manifest)
    cases = read_json(cases_path)
    engine = ReleaseSearch(root, device=device)
    rows = sc.run_engine(cases, lambda q, k: engine.search(q, k))
    summary = sc.summarize(rows)
    legacy_rows = [r for r in rows if r["origin"] == "legacy" and r["status"] in {"pass", "fail", "error"}]
    legacy_pass = sum(r["status"] == "pass" for r in legacy_rows) / max(1, len(legacy_rows))
    baseline = read_json(Path(cases_path).parent / "baseline_old.json", {})
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "cases_sha256": file_hash(cases_path),
              "content_digest": content_digest(manifest["content_sha256"]), "summary": summary,
              "legacy_origin_pass_rate": round(legacy_pass, 4), "baseline_answerable_terms_found": baseline.get("answerable_terms_found"),
              "min_legacy_pass": min_legacy_pass, "passed": legacy_pass >= min_legacy_pass,
              "failures": [r for r in rows if r["status"] in {"fail", "error"}][:100]}
    write_json(root / "validation.json", report)
    return report


def activate(state: Path, release_id: str) -> dict:
    root = (state / "releases" / release_id).resolve()
    if root.parent != (state / "releases").resolve():
        raise ValueError("invalid release id")
    manifest, validation = read_json(root / "release.json", {}), read_json(root / "validation.json", {})
    if manifest.get("status") != "complete":
        raise ValueError("cannot activate an incomplete release")
    if not validation.get("passed"):
        raise ValueError("release has not passed the spot-check gate")
    verify(root, manifest, validation)
    previous = read_json(state / "active.json")
    if previous:
        write_json(state / "previous.json", previous)
    pointer = {"release": release_id, "activated_at": datetime.now(timezone.utc).isoformat(),
               "manifest_sha256": file_hash(root / "release.json"), "validation_sha256": file_hash(root / "validation.json")}
    write_json(state / "active.json", pointer)
    return pointer


def rollback(state: Path) -> dict:
    previous = read_json(state / "previous.json")
    if not previous:
        raise ValueError("no previous release recorded")
    root = state / "releases" / previous["release"]
    verify(root, read_json(root / "release.json"), read_json(root / "validation.json"))
    current = read_json(state / "active.json")
    write_json(state / "active.json", {**previous, "activated_at": datetime.now(timezone.utc).isoformat()})
    if current:
        write_json(state / "previous.json", current)
    return read_json(state / "active.json")
