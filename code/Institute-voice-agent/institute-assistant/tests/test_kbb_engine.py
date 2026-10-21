"""Contract tests: the kbb release serves the graph through the unchanged RetrievedChunk interface.

These run against the active kbb release (built by ``kbb_cli.py build-release``); they are skipped when
no kbb release is active, so the legacy-only checkout keeps passing.
"""
from dataclasses import asdict
from pathlib import Path

import pytest

from assistant.config import settings

STATE = Path(settings.KBB_STATE_DIR)
pytestmark = pytest.mark.skipif(not (STATE / "active.json").exists(), reason="no active kbb release")


@pytest.fixture(scope="module")
def engine():
    from assistant import retrieval
    original = retrieval.settings.KB_STATE_DIR
    object.__setattr__(retrieval.settings, "KB_STATE_DIR", str(STATE))      # Settings is a frozen dataclass
    retrieval._RELEASE_ENGINE = None
    yield retrieval.get_release_engine()
    retrieval._RELEASE_ENGINE = None
    object.__setattr__(retrieval.settings, "KB_STATE_DIR", original)


def test_dispatch_selects_kbb_engine(engine):
    assert type(engine).__name__ == "KbbSearchEngine"
    assert engine.manifest["engine"] == "kbb"


def test_hits_are_retrieved_chunks_with_provenance(engine):
    from assistant.retrieval import RetrievedChunk
    hits = engine.search("What is the B.Tech tuition fee for the 2026 cohort?", 6)
    assert hits and all(isinstance(h, RetrievedChunk) for h in hits)
    fee = next(h for h in hits if "90000" in h.text)
    assert fee.verified and fee.page_number == 11 and fee.source_file.endswith("B TECH_2026.pdf")
    assert len(fee.source_sha256) == 64


def test_exact_cutoff_lookup_and_missing_rank_returns_nothing(engine):
    hits = engine.search("What is the 2026 CSE OPEN closing rank in JoSAA round 5 for All India gender neutral CRL?", 6)
    assert hits and hits[0].kind == "cutoff" and "15883" in hits[0].text and "20333" in hits[0].text
    # No such row exists: the engine must answer nothing rather than a neighbouring number.
    assert engine.search("What is the 2026 CSE SC NTPC opening rank?", 6) == []


def test_matched_fact_row_is_cited_on_its_own_page(engine):
    hits = engine.search("What is the mess advance for B.Tech 2026?", 6)
    assert hits[0].page_number == 11 and "Matched source row" in hits[0].text


def test_unreviewed_ocr_is_never_served(engine):
    parents = engine._engine.parents
    served = {h.block_id for q in ("guest house tariff", "UGC recognition letter", "AIU membership") for h in engine.search(q, 6)}
    assert all(parents[b]["verification_status"] in {"approved", "extracted", "machine_verified"} for b in served)


def test_chunks_pass_the_graph_eligibility_filter(engine):
    from assistant.kb.search import eligible
    hits = engine.search("Who is the dean of academics?", 6)
    assert hits and all(eligible(asdict(h), "Who is the dean of academics?") for h in hits)


def test_embed_questions_for_gap_analysis(engine):
    vectors = engine.embeddings.embed_questions(["fee", "hostel"])
    assert len(vectors) == 2 and len(vectors[0]) == 384
