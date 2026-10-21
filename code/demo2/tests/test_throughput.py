"""Short-turn priority and deadline-aware shedding (FutureWork 10 §1.4), plus observability
(§7). Every test drives JobManager directly with no model/provider calls and never runs the
120-case load benchmark (that is a long test owned by the user). Grounding is never touched by
these changes, so there is nothing grounding-related to assert here; the admission layer only
reorders *when* turns run and sheds overload earlier."""
import time
from unittest.mock import Mock

import pytest

import agent_bridge
import jobs
import settings
import workflow
from storage import Store


# --- Pure predictor unit tests (no manager, no store) -------------------------------------

@pytest.mark.parametrize("text", [
    "hi", "Hello", "thanks", "Thank you", "thank you!", "yes", "No.", "ok", "bye",
    "namaste", "Good morning", "धन्यवाद", "नमस्ते", "हाँ",
])
def test_predict_short_turn_flags_trivial(text):
    assert jobs.predict_short_turn(text, settings.SHORT_TURN_MAX_CHARS) is True


@pytest.mark.parametrize("text", [
    "",
    "   ",
    "What are the B.Tech admission requirements for CSE?",
    "How much is the hostel fee?",
    "thanks, but what is the JEE cutoff for CSE in 2024?",  # has '?', must stay heavy
    "Tell me everything about the fee structure and refund policy in detail please",  # long
    "What is the cutoff?",  # question mark -> heavy
])
def test_predict_short_turn_leaves_heavy(text):
    assert jobs.predict_short_turn(text, settings.SHORT_TURN_MAX_CHARS) is False


def test_predicted_service_seconds_uses_settings():
    assert jobs.predicted_service_seconds(True) == settings.PREDICTED_SHORT_TURN_SECONDS
    assert jobs.predicted_service_seconds(False) == settings.PREDICTED_HEAVY_TURN_SECONDS


# --- Admission ordering (worker not started, so deques are inspectable) --------------------

def _manager(tmp_path):
    return jobs.JobManager(Store(tmp_path), start=False)


def test_short_turn_jumps_ahead_of_heavy(tmp_path):
    runtime = _manager(tmp_path)
    try:
        # Distinct sessions so conversation_busy does not reject concurrent waiters.
        runtime.submit("sA", "t1", "What is the hostel fee structure?", {}, "ollama", "Female", 1, spoken=False)
        runtime.submit("sB", "t2", "thanks", {}, "ollama", "Female", 1, spoken=False)
        # Heavy went to the normal queue; the trivial "thanks" went to the priority queue.
        assert [j.turn_id for j in runtime.queue] == ["t1"]
        assert [j.turn_id for j in runtime.priority] == ["t2"]
        # The worker would drain priority first.
        drained = runtime.priority.popleft() if runtime.priority else runtime.queue.popleft()
        assert drained.turn_id == "t2"
    finally:
        runtime.close()


def test_priority_disabled_keeps_single_fifo(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SHORT_TURN_PRIORITY_ENABLED", False)
    runtime = _manager(tmp_path)
    try:
        runtime.submit("sA", "t1", "What is the hostel fee?", {}, "ollama", "Female", 1, spoken=False)
        runtime.submit("sB", "t2", "thanks", {}, "ollama", "Female", 1, spoken=False)
        assert [j.turn_id for j in runtime.queue] == ["t1", "t2"]
        assert len(runtime.priority) == 0
    finally:
        runtime.close()


def test_recording_is_always_heavy(tmp_path):
    runtime = _manager(tmp_path)
    try:
        # A recording's text is unknown at admission, so even a "short-looking" turn_id must
        # not be prioritised. Recording path uses the question only after transcription.
        runtime.submit("sA", "recording:1", "", {}, "ollama", "Female", 1,
                       spoken=False, recording=b"RIFFfake")
        assert len(runtime.priority) == 0
        assert [j.turn_id for j in runtime.queue] == ["recording:1"]
        assert runtime.queue[0].short_turn is False
    finally:
        runtime.close()


# --- Deadline-aware shedding ---------------------------------------------------------------

def test_heavy_turn_shed_when_predicted_exceeds_deadline(tmp_path, monkeypatch):
    # Force a tight deadline so two queued heavy turns already exceed it.
    monkeypatch.setattr(settings, "DEADLINE_SHEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "QUEUE_TIMEOUT_SECONDS", 30.0)
    monkeypatch.setattr(settings, "PREDICTED_HEAVY_TURN_SECONDS", 18.7)
    runtime = _manager(tmp_path)
    try:
        runtime.submit("sA", "t1", "Fee structure in detail?", {}, "ollama", "Female", 1, spoken=False)
        # ahead = 18.7 (t1 queued) + own 18.7 = 37.4 > 30 -> shed.
        with pytest.raises(ValueError, match="busy"):
            runtime.submit("sB", "t2", "Refund policy in detail?", {}, "ollama", "Female", 1, spoken=False)
        assert runtime.stats()["overload_predicted"] == 1
    finally:
        runtime.close()


def test_short_turn_never_shed_by_deadline(tmp_path, monkeypatch):
    runtime = _manager(tmp_path)
    try:
        # Pre-fill the queue into a shedding state with shedding OFF, then turn it on and
        # confirm a trivial "thanks" is still admitted while a heavy turn would be rejected.
        monkeypatch.setattr(settings, "DEADLINE_SHEDDING_ENABLED", False)
        runtime.submit("sA", "t1", "Fee structure in detail?", {}, "ollama", "Female", 1, spoken=False)
        monkeypatch.setattr(settings, "DEADLINE_SHEDDING_ENABLED", True)
        monkeypatch.setattr(settings, "QUEUE_TIMEOUT_SECONDS", 1.0)  # absurdly tight
        with pytest.raises(ValueError, match="busy"):
            runtime.submit("sC", "t3", "Refund policy in detail?", {}, "ollama", "Female", 1, spoken=False)
        # The trivial "thanks" bypasses shedding entirely and is admitted to the priority queue.
        runtime.submit("sB", "t2", "thanks", {}, "ollama", "Female", 1, spoken=False)
        assert [j.turn_id for j in runtime.priority] == ["t2"]
    finally:
        runtime.close()


def test_shedding_disabled_admits_up_to_capacity(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DEADLINE_SHEDDING_ENABLED", False)
    monkeypatch.setattr(settings, "QUEUE_TIMEOUT_SECONDS", 1.0)
    runtime = _manager(tmp_path)
    try:
        # capacity is QUEUE_CAPACITY + 1 outstanding; admit that many heavy turns with shedding off.
        for i in range(settings.QUEUE_CAPACITY + 1):
            runtime.submit(f"s{i}", f"t{i}", "Fee structure in detail?", {}, "ollama", "Female", 1, spoken=False)
        assert len(runtime.queue) == settings.QUEUE_CAPACITY + 1
        # The next one is rejected by the hard capacity check, not the deadline predictor.
        with pytest.raises(ValueError, match="busy"):
            runtime.submit("extra", "tx", "Fee structure in detail?", {}, "ollama", "Female", 1, spoken=False)
        assert runtime.stats()["overload"] == 1
        assert runtime.stats().get("overload_predicted", 0) == 0
    finally:
        runtime.close()


# --- Observability --------------------------------------------------------------------------

def test_stats_exposes_live_gauges(tmp_path):
    runtime = _manager(tmp_path)
    try:
        runtime.submit("sA", "t1", "Fee structure in detail?", {}, "ollama", "Female", 1, spoken=False)
        runtime.submit("sB", "t2", "thanks", {}, "ollama", "Female", 1, spoken=False)
        stats = runtime.stats()
        assert stats["gauge:queue_depth"] == 1
        assert stats["gauge:priority_depth"] == 1
        assert stats["gauge:queue_depth_total"] == 2
        assert stats["gauge:active_jobs"] == 2
        assert stats["gauge:queue_capacity"] == settings.QUEUE_CAPACITY + 1
        assert stats["admitted:short"] == 1
        assert stats["admitted:normal"] == 1
        assert stats["gauge:overload_rate"] == 0.0  # nothing shed yet
    finally:
        runtime.close()


def test_overload_rate_reflects_shedding(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DEADLINE_SHEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "QUEUE_TIMEOUT_SECONDS", 30.0)
    runtime = _manager(tmp_path)
    try:
        runtime.submit("sA", "t1", "Fee structure in detail?", {}, "ollama", "Female", 1, spoken=False)
        with pytest.raises(ValueError, match="busy"):
            runtime.submit("sB", "t2", "Refund policy in detail?", {}, "ollama", "Female", 1, spoken=False)
        stats = runtime.stats()
        # 1 admitted + 1 shed -> overload_rate 0.5
        assert stats["gauge:overload_rate"] == 0.5
    finally:
        runtime.close()


# --- Regression: a running worker still completes a prioritised short turn -----------------

def test_priority_turn_completes_end_to_end(tmp_path, monkeypatch):
    # The reasoning worker imports assistant.operations lazily inside _run, so the agent root
    # must be importable (as the real app arranges via jobs.manager()).
    monkeypatch.syspath_prepend(str(settings.AGENT_ROOT))
    monkeypatch.setattr(agent_bridge, "ask", Mock(return_value={
        "answer_text": "नमस्ते", "language": "hindi", "sources": [],
        "response_status": "smalltalk", "ticket_id": None}))
    runtime = jobs.JobManager(Store(tmp_path))
    try:
        time.sleep(.2)  # let worker reach its wait, as in the live app
        session = workflow.new_session()["id"]
        runtime.submit(session, "t1", "thanks", {}, "ollama", "Female", 1, spoken=False)
        for _ in range(200):
            if runtime.snapshot(session, "t1")["stage"] in jobs.TERMINAL:
                break
            time.sleep(.01)
        assert runtime.snapshot(session, "t1")["stage"] == "complete"
        assert runtime.stats()["admitted:short"] == 1
    finally:
        runtime.close()
