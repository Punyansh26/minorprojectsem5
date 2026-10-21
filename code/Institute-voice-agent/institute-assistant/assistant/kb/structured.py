"""Keep cutoff dimensions and financial-support conditions attached to exact evidence."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from assistant.kb.common import digest

RANK_FIELDS = ("year", "authority", "round", "programme", "quota", "seat_category", "gender_pool", "rank_basis", "opening_rank", "closing_rank")
FILTER_FIELDS = ("year", "authority", "round", "programme", "quota", "seat_category", "gender_pool", "rank_basis")


def is_rank_question(question: str) -> bool:
    """Recognize rank lookups after the existing English query rewrite."""
    return bool(re.search(r"\brank\b|\branks\b|cut.?off|रैंक|कट.?ऑफ", question, re.I))


def rank_filters(question: str) -> dict:
    """Extract only explicit dimensions; never invent a student's category or quota."""
    q = question.casefold()
    result = {}
    years = re.findall(r"\b20\d{2}\b", q)
    if len(set(years)) == 1:
        result["year"] = int(years[0])
    rounds = re.search(r"(?:\bround|राउंड|चरण)\s*[-:]?\s*(\d+)\b", q)
    if rounds:
        result["round"] = rounds.group(1)
    programmes = []
    for label, pattern in (("DSAI", r"\bdsai\b|data science|डीएसएआई"), ("CSE", r"\bcse\b|computer science|सीएसई"), ("ECE", r"\bece\b|electronics|ईसीई")):
        if re.search(pattern, q):
            programmes.append(label)
    if len(programmes) == 1:
        result["programme"] = programmes[0]
    categories = []
    for category, pattern in (("OBC-NCL", r"\bobc(?:-ncl)?\b|ओबीसी"), ("GEN-EWS", r"\bews\b|ईडब्ल्यूएस"), ("SC", r"\bsc\b|एससी"), ("ST", r"\bst\b|एसटी"), ("OPEN", r"\bopen\b|\bgeneral category\b|सामान्य श्रेणी")):
        if re.search(pattern, q):
            categories.append(category)
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


def validate_record(record: dict, blocks: dict) -> None:
    """Reject unsupported records before they enter either database."""
    evidence = blocks.get(record.get("evidence_block_id"))
    if not evidence or evidence["verification_status"] not in {"approved", "extracted"}:
        raise ValueError("Structured record requires approved evidence")
    if record.get("source_sha256") != evidence["source_sha256"]:
        raise ValueError("Structured record source has changed")
    if record.get("kind") == "cutoff":
        if any(record.get(k) in (None, "") for k in RANK_FIELDS):
            raise ValueError("Cutoff record lacks an explicit rank dimension")
        for name in ("opening_rank", "closing_rank"):
            if not re.fullmatch(r"\d+(?:\.\d+)?P?", str(record[name])):
                raise ValueError("Invalid published rank value")
            if str(record[name]) not in evidence["text"]:
                raise ValueError("Rank absent from approved source row")
        if float(str(record["opening_rank"]).rstrip("P")) > float(str(record["closing_rank"]).rstrip("P")):
            raise ValueError("Opening rank exceeds closing rank")
    elif record.get("kind") in {"scholarship", "finance"}:
        if not record.get("name") or not record.get("conditions") or record.get("institution_applicability") not in {"verified", "unknown", "not_applicable"}:
            raise ValueError("Financial support must preserve conditions and applicability")
        # Curated fields are source extracts; never generated eligibility assertions.
        linked = [evidence]
        for key in record.get("related_evidence_block_ids", []):
            other = blocks.get(key)
            if not other or other["verification_status"] not in {"approved", "extracted"} or other["source_sha256"] != record["source_sha256"]:
                raise ValueError("Financial conditions require approved evidence from the same source")
            linked.append(other)
        text = "\n".join(b["text"] for b in linked)
        for key in ("conditions", "benefit"):
            if record.get(key) and " ".join(record[key].split()) not in " ".join(text.split()):
                raise ValueError("Financial support field is not a source extract")
    else:
        raise ValueError("Unsupported structured record")


def record_text(record: dict, evidence: dict, related_blocks: list[dict] | None = None) -> str:
    """Render deterministic facts with every qualifier visible to the grounding reviewer."""
    if record["kind"] == "cutoff":
        labels = {"year": "Admission year", "authority": "Counselling", "round": "Round", "programme": "Programme",
                  "quota": "Quota", "seat_category": "Seat category", "gender_pool": "Seat pool",
                  "rank_basis": "Rank basis", "opening_rank": "Opening rank", "closing_rank": "Closing rank"}
        return "IIIT Naya Raipur published opening and closing ranks\n" + "\n".join(f"{labels[k]}: {record[k]}" for k in RANK_FIELDS) + "\nSource row: " + evidence["text"]
    base = (f"{record['name']} ({record['kind']})\nIIIT-NR applicability: {record['institution_applicability']}\n"
            f"Conditions: {record['conditions']}\nBenefit: {record.get('benefit', 'Not established by this evidence')}\n")
    if related_blocks:
        blocks = [evidence] + related_blocks
        return base + "\n".join(f"[Page {b.get('page_number', 'unknown')}] {b['text']}" for b in blocks)
    return base + evidence["text"]


def create_database(path: Path, records: list[dict], blocks: dict) -> list[dict]:
    """Create the sidecar only from validated records and the same release's evidence."""
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, year INTEGER, authority TEXT, round TEXT, programme TEXT, quota TEXT, seat_category TEXT, gender_pool TEXT, rank_basis TEXT, evidence_block_id TEXT NOT NULL, payload TEXT NOT NULL)")
        conn.execute("CREATE INDEX cutoff_dimensions ON records(kind,year,authority,programme,quota,seat_category,round)")
        result = []
        for record in records:
            validate_record(record, blocks)
            record = {**record, "id": record.get("id") or digest(json.dumps(record, sort_keys=True))[:24]}
            columns = ("id", "kind", *FILTER_FIELDS, "evidence_block_id")
            conn.execute(f"INSERT INTO records ({','.join(columns)},payload) VALUES ({','.join('?' for _ in range(len(columns)+1))})",
                         [record.get(k) for k in columns] + [json.dumps(record, ensure_ascii=False)])
            result.append(record)
    return result


def lookup_cutoffs(path: Path, filters: dict, limit: int = 12) -> list[dict]:
    """Apply exact parameterized dimensions; no vector similarity can change a cutoff."""
    if not path.exists():
        return []
    unknown = set(filters) - set(FILTER_FIELDS)
    if unknown:
        raise ValueError("Unsupported cutoff filter")
    clauses, args = ["kind = 'cutoff'"], []
    for key, value in filters.items():
        clauses.append(f"{key} = ?")
        args.append(value)
    with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT payload FROM records WHERE " + " AND ".join(clauses) + " ORDER BY year DESC, CAST(round AS INTEGER) DESC,programme,seat_category,gender_pool LIMIT ?", [*args, limit]).fetchall()
    return [json.loads(row[0]) for row in rows]
