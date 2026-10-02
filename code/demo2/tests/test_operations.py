"""Exercise real SQLite ownership and worker boundaries with fake inference."""
import json
import sqlite3
import sys
import time
from threading import Event
from unittest.mock import Mock

import pytest

import settings
sys.path.insert(0,str(settings.AGENT_ROOT))
import agent_bridge
import jobs
import speech
from storage import Store, connection
from verbalization import normalize


def wait_for(runtime, session, turn, predicate, timeout=3):
    end = time.monotonic()+timeout
    while time.monotonic()<end:
        value = runtime.snapshot(session,turn)
        if predicate(value):
            return value
        time.sleep(.01)
    raise AssertionError(runtime.snapshot(session,turn))


def answer(question, session, profile, **kwargs):
    return dict(answer_text=question,language="english",sources=[],response_status="answered")


def submit(runtime, session="one", turn="turn", spoken=False):
    return runtime.submit(session,turn,"public question",{},"ollama","Female",1,spoken,False)


def test_text_visible_before_speech_and_retry_never_reasons(tmp_path,monkeypatch):
    release=Event(); entered=Event(); ask=Mock(side_effect=answer)
    def slow(*a,**kw):
        entered.set(); release.wait(2); raise RuntimeError("private provider details")
    monkeypatch.setattr(agent_bridge,"ask",ask); monkeypatch.setattr(speech,"make_audio",slow)
    runtime=jobs.JobManager(Store(tmp_path))
    try:
        submit(runtime,spoken=True); assert entered.wait(2)
        row=runtime.snapshot("one","turn")
        assert row["answer_text"]=="public question" and row["stage"]=="speech"
        assert row["timings"]["reviewed_text_seconds"]<1
        release.set()
        row=wait_for(runtime,"one","turn",lambda x:x["stage"]=="complete")
        assert "private" not in row["audio_error"]
        runtime.retry_audio("one","turn","Male",1,True)
        wait_for(runtime,"one","turn",lambda x:x["stage"]=="complete")
        assert ask.call_count==1
    finally:
        release.set(); runtime.close()


def test_fifo_capacity_same_session_and_cancellation(tmp_path,monkeypatch):
    release=Event(); entered=Event(); order=[]
    def slow(q,s,p,**kw):
        order.append(s); entered.set(); release.wait(2); return answer(q,s,p)
    monkeypatch.setattr(agent_bridge,"ask",slow)
    runtime=jobs.JobManager(Store(tmp_path))
    try:
        submit(runtime,"a"); assert entered.wait(1)
        for session in ["b","c","d"]: submit(runtime,session)
        with pytest.raises(ValueError,match="busy"):submit(runtime,"e")
        with pytest.raises(ValueError,match="conversation_busy"):submit(runtime,"a","two")
        runtime.cancel("b"); release.set()
        wait_for(runtime,"d","turn",lambda x:x["stage"]=="complete")
        assert order==["a","c","d"]
        assert runtime.snapshot("b","turn")["stage"]=="cancelled"
        assert runtime.snapshot("c","turn")["question"]=="public question"
    finally: release.set(); runtime.close()


def test_deadline_suppresses_late_answer_and_holds_capacity(tmp_path,monkeypatch):
    release=Event(); entered=Event()
    def slow(q,s,p,**kw):entered.set(); release.wait(2); return answer(q,s,p)
    monkeypatch.setattr(agent_bridge,"ask",slow)
    monkeypatch.setattr(settings,"TURN_TIMEOUT_SECONDS",.02)
    runtime=jobs.JobManager(Store(tmp_path))
    try:
        submit(runtime); assert entered.wait(1); time.sleep(.03)
        row=runtime.snapshot("one","turn")
        assert row["error_code"]=="deadline_exceeded" and "answer_text" not in row
        assert not runtime.delete("one")
        release.set(); wait_for(runtime,"one","turn",lambda x:x["stage"] in jobs.TERMINAL)
        assert runtime.delete("one") and runtime.snapshot("one","turn") is None
    finally:release.set();runtime.close()


def test_durable_replay_survives_manager_restart(tmp_path,monkeypatch):
    ask=Mock(side_effect=answer);monkeypatch.setattr(agent_bridge,"ask",ask)
    runtime=jobs.JobManager(Store(tmp_path));submit(runtime)
    wait_for(runtime,"one","turn",lambda x:x["stage"]=="complete");runtime.close()
    runtime=jobs.JobManager(Store(tmp_path))
    try:
        submit(runtime)
        assert runtime.snapshot("one","turn")["answer_text"]=="public question"
        assert ask.call_count==1
    finally:runtime.close()


def test_retention_deletion_backup_restore_and_reuse(tmp_path):
    now=[1000.];store=Store(tmp_path/"data",10,lambda:now[0])
    store.request("old","t",{"question":"synthetic"});store.complete("old","t",dict(answer_text="answer",audio=b"private"))
    with connection(store.root/"conversations.sqlite") as conn:
        conn.executescript("CREATE TABLE checkpoints(thread_id TEXT,checkpoint_id TEXT);CREATE TABLE writes(thread_id TEXT,checkpoint_id TEXT);")
        conn.executemany("INSERT INTO checkpoints VALUES (?,?)",[("old",str(x).zfill(2)) for x in range(20)])
        conn.executemany("INSERT INTO writes VALUES (?,?)",[("old",str(x).zfill(2)) for x in range(20)])
    store.compact("old")
    with connection(store.root/"conversations.sqlite") as conn:
        assert conn.execute("SELECT count(*) FROM checkpoints").fetchone()[0]==2
        assert conn.execute("SELECT count(*) FROM writes").fetchone()[0]==2
    backup=store.backup();restored=store.restore_into(backup,tmp_path/"restore")
    assert restored.request("old","t",{"question":"synthetic"})["answer_text"]=="answer"
    with pytest.raises(ValueError,match="request_conflict"):store.request("old","t",{"question":"changed"})
    now[0]=1005;store.register("new");now[0]=1011
    store.maintain();assert store.session_ids()=={"new"} and not backup.exists()
    with connection(store.root/"conversations.sqlite") as conn:
        assert conn.execute("SELECT count(*) FROM checkpoints").fetchone()[0]==0
    with pytest.raises(ValueError,match="deleted"):store.register("old")
    store.delete("new");assert not store.session_ids()


def test_backup_corruption_rejected(tmp_path):
    store=Store(tmp_path/"data");store.register("one");backup=store.backup()
    with (backup/"sessions.sqlite").open("ab") as f:f.write(b"corrupt")
    with pytest.raises(ValueError,match="integrity"):store.restore_into(backup,tmp_path/"restored")
    assert not (tmp_path/"restored").exists()


def test_essential_storage_lock_has_short_timeout(tmp_path):
    store=Store(tmp_path)
    with sqlite3.connect(store.path) as lock:
        lock.execute("BEGIN EXCLUSIVE");started=time.monotonic()
        with pytest.raises(sqlite3.OperationalError):store.register("one")
        assert time.monotonic()-started<.75
    store.register("one")


@pytest.mark.parametrize("text,expected",[
    ("₹90,000", "नब्बे हजार"),("3.5%", "तीन दशमलव पाँच प्रतिशत"),
    ("50–60", "पचास से साठ"),("2026-04-01", "एक अप्रैल दो हजार छब्बीस"),
    ("01/04/2026", "एक अप्रैल दो हजार छब्बीस"),("-5", "ऋण पाँच"),
    ("शुल्क वापस नहीं होगा", "वापस नहीं होगा"),("eligible nahi hai", "eligible नहीं है")])
def test_deterministic_values_and_negation(text,expected):
    assert expected in normalize(text,"hinglish")


def test_online_speech_requires_explicit_consent(monkeypatch):
    online=Mock(return_value=b"audio");monkeypatch.setattr(speech,"online_audio",online)
    with pytest.raises(speech.SpeechError):speech.make_audio("Hello","english","Female")
    online.assert_not_called()
    assert speech.make_audio("Hello","english","Female",allow_online=True)["data"]==b"audio"
