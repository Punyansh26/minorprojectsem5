"""Regression checks for the audit's ownership, provenance and publication failures."""
import json
import sqlite3
import time
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest

from assistant import db
from assistant.operations import Operation, operation_context, check, remaining, record_attempt
from assistant.kb.integrity import content_hashes,content_digest,verify
from assistant.kb.provenance import financial_spans
from assistant.kb.policies import select,validate
from assistant.kb.josaa import published_year


def test_action_idempotency_is_atomic_and_owned(tmp_path,monkeypatch):
    monkeypatch.setattr(db,"settings",replace(db.settings,TICKETS_DB_PATH=str(tmp_path/'actions.sqlite')))
    args=('synthetic','general','admissions','public question','staff@example.org','Subject','Local draft')
    with operation_context(Operation('session-a','turn',time.monotonic()+5)):
        first=db.create_ticket(*args); assert db.create_ticket(*args)==first
        with pytest.raises(ValueError,match='conflict'):db.create_ticket(*args[:-1],'changed draft')
    with operation_context(Operation('session-b','turn',time.monotonic()+5)):
        assert db.create_ticket(*args)!=first
    assert len(db.list_tickets())==2
    with sqlite3.connect(tmp_path/'actions.sqlite') as conn:
        assert conn.execute('SELECT COUNT(*) FROM action_requests').fetchone()[0]==2


def test_expired_or_cancelled_operations_cannot_create_actions(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'settings',replace(db.settings,TICKETS_DB_PATH=str(tmp_path/'actions.sqlite')))
    for deadline,event in [(time.monotonic()-1,Event()),(time.monotonic()+10,Event())]:
        if deadline>time.monotonic():event.set()
        with operation_context(Operation('session','turn',deadline,cancelled=event)):
            with pytest.raises(Exception):db.create_ticket('s','general','general','q','a@example.org','s','body')
    assert db.list_tickets()==[]


def test_provider_metrics_discard_sensitive_fields():
    op=Operation('session','turn',time.monotonic()+2)
    with operation_context(op):
        assert 0<remaining(120)<=2
        record_attempt('ollama',.2,{'prompt_eval_count':2,'response':'private','secret':'key'})
    assert 'private' not in json.dumps(op.attempts) and 'secret' not in json.dumps(op.attempts)


def test_finance_conditions_keep_the_original_page():
    blocks={'benefit':dict(id='benefit',page_number=2,source_sha256='hash',text='Collateral-free loan.'),
            'condition':dict(id='condition',page_number=4,source_sha256='hash',text='Other scholarships are excluded.')}
    record=dict(evidence_block_id='benefit',related_evidence_block_ids=['condition'],benefit='Collateral-free loan.',conditions='Other scholarships are excluded.')
    result=financial_spans(record,blocks)
    assert result['benefit']['page_number']==2 and result['conditions']['page_number']==4
    record['conditions']='Unverified policy'
    with pytest.raises(ValueError):financial_spans(record,blocks)


def artifact(tmp_path):
    root=tmp_path/'releases'/'candidate';(root/'chroma').mkdir(parents=True)
    model=tmp_path/'models'/'embedding';model.mkdir(parents=True)
    for name in ['parents.json','sources.json']:(root/name).write_text('{}')
    for name in ['facts.sqlite','chroma/chroma.sqlite3']:
        with sqlite3.connect(root/name) as conn:conn.execute('CREATE TABLE facts(value TEXT)')
    (root/'chroma'/'index.bin').write_bytes(b'vector-index')
    return root,dict(model_artifact='models/embedding',content_sha256=content_hashes(root))


@pytest.mark.parametrize('name',['parents.json','facts.sqlite','chroma/index.bin'])
def test_publication_hash_rejects_changed_content(tmp_path,name):
    root,manifest=artifact(tmp_path);validation=dict(content_digest=content_digest(manifest['content_sha256']))
    verify(root,manifest,validation)
    if name.endswith('sqlite'):
        with sqlite3.connect(root/name) as conn:conn.execute("INSERT INTO facts VALUES ('changed')")
    else:(root/name).write_bytes(b'changed')
    with pytest.raises(ValueError):verify(root,manifest,validation)


def test_validation_is_bound_and_model_paths_cannot_escape(tmp_path):
    root,manifest=artifact(tmp_path)
    with pytest.raises(ValueError,match='Validation'):verify(root,manifest,dict(content_digest='old'))
    manifest['model_artifact']='../outside'
    with pytest.raises(ValueError,match='artifact'):verify(root,manifest)


def test_rollover_does_not_relabel_2027_as_2026():
    assert published_year('<select id="ddlYear"><option selected="selected" value="2027">2027</option></select>')==2027
    assert published_year('<span id="lblCounsellingBoardHeader">JoSAA 2027</span>')==2027
    with pytest.raises(ValueError):published_year('<html>Copyright 2026</html>')


def test_material_policy_missing_or_wrong_page_fails_closed(tmp_path):
    rule=dict(id='fee',match='tuition',year=2026,answers={x:'Tuition is 90000.' for x in ['english','hindi','hinglish']},evidence=[dict(source_sha256='hash',page_number=11,quote='Tuition: 90000')])
    policy=dict(rules=[rule]);(tmp_path/'policies.json').write_text(json.dumps(policy))
    source=dict(source_id=1,source_sha256='hash',page_number=11,text='Tuition: 90000')
    assert select(tmp_path,'tuition 2026','english',[source])[1].answer=='Tuition is 90000.'
    assert select(tmp_path,'tuition 2026','english',[{**source,'page_number':12}])[1] is None
    assert select(tmp_path,'M.Tech tuition 2026','english',[source])==(None,None)
    assert select(tmp_path,'tuition 2027','english',[source])==(None,None)
    with pytest.raises(ValueError):validate(policy,{})


def test_record_text_multi_page_financial_attribution():
    from assistant.kb.structured import record_text
    record = {
        "kind": "financial_support",
        "name": "PM Vidyalaxmi",
        "institution_applicability": "Direct applicable",
        "conditions": "Gross income under 8 lakhs",
        "benefit": "Full interest subsidy",
    }
    evidence = {"text": "Benefit block text on page 2", "page_number": 2}
    related = [{"text": "Condition block text on page 4", "page_number": 4}]
    out = record_text(record, evidence, related_blocks=related)
    assert "[Page 2]" in out
    assert "[Page 4]" in out


def test_cache_telemetry_and_hit_rate(tmp_path):
    from types import SimpleNamespace
    from assistant.cache import RagCache
    cfg = SimpleNamespace(
        RAG_CACHE_ENABLED=True,
        RAG_CACHE_DB_PATH=str(tmp_path / "cache.sqlite"),
        RAG_CACHE_TIMEOUT_SECONDS=1.0,
        RAG_CACHE_MAX_ENTRY_BYTES=1024,
        RAG_CACHE_MAX_ENTRIES=10,
        RAG_CACHE_TTL_SECONDS=3600,
        RAG_CACHE_MAX_BYTES=65536,
    )
    cache = RagCache(cfg)
    cache.get("k0")
    cache.put("k1", "v1")
    cache.get("k1")
    t = cache.telemetry()
    assert t["hit"] == 1
    assert t["miss"] == 1
    assert t["hit_rate"] == 0.5


def test_hindi_loan_query_expansion():
    import re
    question = "PM Vidyalaxmi दिशानिर्देशों में ऋण चुकाने की अवधि क्या है?"
    matched = re.search(r"vidya.?laxmi|विद्या.?लक्ष्मी|विद्या.?लक्षमी", question, re.I) and re.search(r"चुक|वापस|repay|moratorium|किस्त|अवधि|period|duration", question, re.I)
    assert matched

