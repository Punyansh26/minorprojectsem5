"""Exercise evidence boundaries and release failure behavior without network/model downloads."""
import json
from dataclasses import replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from assistant.kb.common import active_release, read_json, write_json
from assistant.kb.extraction import html_rows, make_block
from assistant.kb.search import eligible
from assistant.kb.sources import approved_host, fetch_one
from assistant.kb.structured import create_database, lookup_cutoffs, rank_filters, validate_record
from assistant.kb import releases


def block(**kwargs):
    return {"id": "evidence", "source_sha256": "sha", "verification_status": "approved",
            "text": "Opening Rank: 120\nClosing Rank: 250", **kwargs}


def record(**kwargs):
    return {"kind": "cutoff", "year": 2026, "authority": "JoSAA", "round": "1", "programme": "CSE",
            "quota": "AI", "seat_category": "SC", "gender_pool": "Gender-Neutral", "rank_basis": "Category rank",
            "opening_rank": "120", "closing_rank": "250", "evidence_block_id": "evidence", "source_sha256": "sha", **kwargs}


def test_table_spans_retain_units_and_empty_cells():
    table = BeautifulSoup('<table><tr><th rowspan="2">Fee (INR)</th><th colspan="2">2026</th></tr><tr><th>Term 1</th><th>Term 2</th></tr><tr><td>Hostel</td><td>15000</td><td></td></tr></table>', "html.parser").table
    assert html_rows(table) == [["Fee (INR)", "2026", "2026"], ["Fee (INR)", "Term 1", "Term 2"], ["Hostel", "15000", ""]]


def test_explicit_row_years_override_filename_and_publication_year():
    meta = {"source_file": "NIRF2026.pdf", "years": "2024,2025", "verification_status": "approved"}
    assert eligible(meta, "placement in 2024")
    assert not eligible(meta, "placement in 2026")
    assert not eligible({**meta, "verification_status": "needs_review"}, "placement in 2024")
    assert not eligible({**meta, "historical": True}, "current placements")
    assert eligible({**meta, "historical": True}, "historical placements in 2025")


def test_exact_cutoff_filters_do_not_cross_quota_category_round_or_rank_basis(tmp_path):
    records = [record(), record(round="2", quota="CG"), record(seat_category="OPEN", rank_basis="CRL")]
    create_database(tmp_path / "facts.sqlite", records, {"evidence": block()})
    matches = lookup_cutoffs(tmp_path / "facts.sqlite", rank_filters("2026 JoSAA round 1 CSE SC all India opening rank"))
    assert len(matches) == 1 and matches[0]["seat_category"] == "SC"
    assert lookup_cutoffs(tmp_path / "facts.sqlite", {"quota": "NTPC"}) == []
    assert lookup_cutoffs(tmp_path / "facts.sqlite", {"seat_category": "SC", "rank_basis": "CRL"}) == []
    with pytest.raises(ValueError):
        lookup_cutoffs(tmp_path / "facts.sqlite", {"year OR 1=1": 2026})


@pytest.mark.parametrize("changes", [{"closing_rank": None}, {"rank_basis": ""}, {"source_sha256": "other"}, {"closing_rank": "9999"}])
def test_unverified_or_incomplete_numeric_records_rejected(changes):
    with pytest.raises(ValueError):
        validate_record(record(**changes), {"evidence": block()})


def test_finance_missing_eligibility_is_not_approval():
    r = {"kind": "finance", "name": "Scheme", "conditions": "Income up to 8 lakh",
         "institution_applicability": "unknown", "evidence_block_id": "evidence", "source_sha256": "sha"}
    validate_record(r, {"evidence": block(text="Income up to 8 lakh")})
    with pytest.raises(ValueError):
        validate_record({**r, "conditions": "Everyone is eligible"}, {"evidence": block(text="Income up to 8 lakh")})


def test_failed_fetch_preserves_cached_bytes_and_verification_date(tmp_path, monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: (_ for _ in ()).throw(requests.Timeout()))
    source = {"url": "https://www.iiitnr.ac.in/content/fees", "sha256": "old", "fetched_at": "2025-01-01", "path": "old.pdf"}
    result = fetch_one(source, tmp_path)
    assert result["fetch_status"] == "failed"
    assert result["sha256"] == "old" and result["fetched_at"] == "2025-01-01"
    assert result["path"] == "old.pdf"


def test_approved_domain_boundary():
    assert approved_host("https://josaa.admissions.nic.in/public")
    assert not approved_host("https://iiitnr.ac.in.evil.example/public")
    assert not approved_host("file:///etc/passwd")


def test_release_activation_requires_validation_and_keeps_previous(tmp_path):
    root = tmp_path / "releases/new"
    root.mkdir(parents=True)
    (root / "facts.sqlite").touch()
    write_json(root / "release.json", {"status": "complete"})
    write_json(tmp_path / "active.json", {"release": "old"})
    with pytest.raises(ValueError):
        releases.activate(tmp_path, "new")
    assert read_json(tmp_path / "active.json")["release"] == "old"
    write_json(root / "validation.json", {"passed": True})
    releases.activate(tmp_path, "new")
    assert read_json(tmp_path / "previous.json")["release"] == "old"
    assert active_release(tmp_path)[0] == root


def test_empty_build_cannot_replace_active_index(tmp_path):
    write_json(tmp_path / "blocks.json", [block(verification_status="needs_review")])
    write_json(tmp_path / "active.json", {"release": "old"})
    with pytest.raises(ValueError):
        releases.build_release(tmp_path)
    assert read_json(tmp_path / "active.json")["release"] == "old"


def test_ocr_encoding_errors_cannot_be_indexed():
    s = {"id": "source", "sha256": "hash", "title": "Notice"}
    assert make_block(s, 1, "text", "Amount \x00 unclear")["verification_status"] == "needs_review"


def test_pwd_query_does_not_invent_open_category():
    filters = rank_filters("2026 CSE PwD opening rank")
    assert "seat_category" not in filters
    assert filters["rank_basis"] == "PwD category rank"
    assert rank_filters("SC PwD closing rank")["seat_category"] == "SC (PwD)"


def test_embedding_failure_preserves_active_release(tmp_path):
    from langchain_core.embeddings import Embeddings

    class Tokenizer:
        def encode(self, text, **kwargs):
            return list(map(ord, text))

        def decode(self, tokens, **kwargs):
            return "".join(map(chr, tokens))

    class FailedEmbeddings(Embeddings):
        tokenizer = Tokenizer()

        def embed_documents(self, texts):
            raise RuntimeError("Simulated embedding interruption")

        def embed_query(self, text):
            raise AssertionError("No query expected while building")

    write_json(tmp_path / "active.json", {"release": "old"})
    write_json(tmp_path / "sources.json", {"sources": [{"id": "source", "sha256": "sha"}]})
    write_json(tmp_path / "blocks.json", [block(source_id="source", kind="text", title="Policy", category="general")])
    with pytest.raises(RuntimeError, match="interruption"):
        releases.build_release(tmp_path, embeddings=FailedEmbeddings())
    assert read_json(tmp_path / "active.json")["release"] == "old"
    manifests = list((tmp_path / "releases").glob("*/release.json"))
    assert len(manifests) == 1 and read_json(manifests[0])["status"] == "failed"


def test_rollback_restores_both_stores_via_one_pointer(tmp_path):
    for name in ("old", "new"):
        root = tmp_path / "releases" / name
        root.mkdir(parents=True)
        (root / "facts.sqlite").touch()
        write_json(root / "release.json", {"status": "complete"})
        write_json(root / "validation.json", {"passed": True})
    write_json(tmp_path / "active.json", {"release": "old"})
    releases.activate(tmp_path, "new")
    releases.rollback(tmp_path)
    assert active_release(tmp_path)[0].name == "old"
    assert read_json(tmp_path / "previous.json")["release"] == "new"
