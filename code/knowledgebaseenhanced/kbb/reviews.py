"""Recorded page reviews: the only way OCR text becomes servable.

A review compares the extracted text with the rendered page image.  It never rewrites silently:

* ``patches``      list of ``{"find", "replace"}`` - ``find`` must occur exactly once in the page text
* ``replace_text`` full page text transcribed from the image (used when OCR destroyed a table)
* ``decision``     ``approved`` or ``rejected``
* ``source_sha256`` binds the review to the exact source bytes; a changed source voids the review

Reviews live in ``review/page_reviews.json`` (committed) so every correction is auditable and the user can
override any row by editing that file.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .store import write_json

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "review" / "page_reviews.json"
DECISIONS = {"approved", "rejected"}


class ReviewError(ValueError):
    pass


def load_reviews(path: Path = DEFAULT_PATH) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("reviews", [])


def make_lookup(reviews: list[dict]):
    """``lookup(doc_id, page, source_sha256) -> review | None`` ignoring reviews of other source bytes."""
    index = {(r["doc_id"], int(r["page"])): r for r in reviews}

    def lookup(doc_id: str, page: int, sha256: str):
        review = index.get((doc_id, page))
        if review and review.get("source_sha256") and sha256 and review["source_sha256"] != sha256:
            return None
        return review
    return lookup


def apply_page_review(text: str, review: dict) -> tuple[str, str]:
    """Return (text, status).  Raises ``ReviewError`` if a patch no longer matches (stale review)."""
    if review["decision"] not in DECISIONS:
        raise ReviewError("decision must be approved or rejected")
    if review["decision"] == "rejected":
        return "", "rejected"
    if review.get("replace_text"):
        return review["replace_text"].strip("\n"), "approved"
    for patch in review.get("patches", []):
        count = text.count(patch["find"])
        if count != 1:
            raise ReviewError(f"patch {patch['find']!r} matches {count} times on page {review['page']}")
        text = text.replace(patch["find"], patch["replace"])
    return text, "approved"


def add_review(path: Path, review: dict) -> None:
    """Insert or replace one review (keyed by doc_id + page), stamping the time."""
    if review["decision"] not in DECISIONS:
        raise ReviewError("decision must be approved or rejected")
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"version": 1, "reviews": []}
    review = {**review, "reviewed_at": review.get("reviewed_at") or datetime.now(timezone.utc).isoformat(timespec="seconds")}
    data["reviews"] = [r for r in data["reviews"] if (r["doc_id"], int(r["page"])) != (review["doc_id"], int(review["page"]))] + [review]
    write_json(path, data)
