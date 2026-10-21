"""Exercise real graph memory and SQLite reuse with deterministic, isolated providers."""
import json
import sqlite3
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from assistant import nodes
from assistant.cache import RagCache, cache_key
from assistant.config import Settings
from assistant.evidence import source_quote
from assistant.graph import build_graph
from assistant.history import completed_pairs, prompt_history
from assistant.llm import Evidence, GroundedAnswer, RoutingDecision
from assistant.retrieval import RetrievedChunk


@pytest.fixture
def cache_config(tmp_path):
    return replace(nodes.settings, RAG_CACHE_DB_PATH=str(tmp_path / "cache.sqlite"),
                   RAG_CACHE_MAX_ENTRIES=2, RAG_CACHE_TTL_SECONDS=60)


def test_cache_persists_expires_and_uses_frequency_then_age(cache_config):
    clock = Mock(return_value=100)
    cache = RagCache(cache_config, clock)
    cache.put("a", {"result": "one"})
    clock.return_value = 101
    cache.put("b", ["two"])
    assert cache.get("a") == {"result": "one"}
    clock.return_value = 102
    cache.put("c", ["three"])
    assert cache.get("b") is None  # a was more frequent
    assert RagCache(cache_config, clock).get("a") == {"result": "one"}
    clock.return_value = 160
    assert cache.get("a") is None  # hits do not extend expiry
    clock.return_value = 161
    cache.put("d", ["four"])
    clock.return_value = 162
    cache.put("e", ["five"])
    clock.return_value = 163
    cache.put("f", ["six"])
    assert cache.get("d") is None  # same frequency: oldest first
    assert cache.get("e") == ["five"]


@pytest.mark.parametrize("malformed", ["not JSON", sqlite3.Binary(b"wrong storage type")])
def test_cache_malformed_json_and_size_limits(cache_config, malformed):
    cache = RagCache(cache_config)
    cache.put("broken", {"ok": True})
    with sqlite3.connect(cache_config.RAG_CACHE_DB_PATH) as conn:
        conn.execute("UPDATE rag_cache SET value = ?", (malformed,))
    assert cache.get("broken") is None
    cache.put("huge", "x" * cache_config.RAG_CACHE_MAX_ENTRY_BYTES)
    assert cache.get("huge") is None
    cache.put("nan", float("nan"))
    assert cache.get("nan") is None


def test_disabled_or_unavailable_cache_is_disposable(cache_config, tmp_path):
    cache = RagCache(replace(cache_config, RAG_CACHE_ENABLED=False))
    cache.put("key", [1])
    assert cache.get("key") is None
    assert not (tmp_path / "cache.sqlite").exists()
    bad = RagCache(replace(cache_config, RAG_CACHE_DB_PATH=str(tmp_path)))
    bad.put("key", [1])
    assert bad.get("key") is None
    bad.delete("key")


def test_cache_locked_database_is_a_miss(cache_config):
    cache = RagCache(cache_config)
    cache.put("key", [1])
    with sqlite3.connect(cache_config.RAG_CACHE_DB_PATH) as conn:
        conn.execute("BEGIN EXCLUSIVE")
        assert cache.get("key") is None
        cache.put("new", [2])
    assert cache.get("key") == [1]
    assert cache.get("new") is None


def test_keys_are_exact_order_independent_and_hide_inputs():
    first = cache_key("draft", {"history": "private text", "year": 2026})
    assert first == cache_key("draft", {"year": 2026, "history": "private text"})
    assert first != cache_key("draft", {"history": "private text", "year": 2025})
    assert first != cache_key("retrieval", {"history": "private text", "year": 2026})
    assert len(first) == 64 and "private" not in first


def test_history_pairs_budget_and_orphaned_messages():
    messages = [AIMessage(content="orphan"), HumanMessage(content="interrupted"),
                HumanMessage(content="first"), AIMessage(content="one"),
                HumanMessage(content="second"), AIMessage(content="two", additional_kwargs={
                    "resolved_query": "fees for CG", "response_status": "answered"}),
                HumanMessage(content="current")]
    assert len(completed_pairs(messages)) == 2
    history = prompt_history(messages, 1, 1000)
    assert [m["text"] for m in history] == ["second", "two"]
    assert history[1]["resolved_query"] == "fees for CG"
    size = len(json.dumps(history, ensure_ascii=False))
    assert prompt_history(messages, 10, size) == history
    assert prompt_history(messages, 10, size - 1) == []


def test_history_config_compatibility():
    assert Settings(HISTORY_TURNS=None, HISTORY_MESSAGES=11).history_turns == 5
    assert Settings(HISTORY_TURNS=10, HISTORY_MESSAGES=4).history_turns == 10
    for kw in ({"HISTORY_TURNS": 0}, {"HISTORY_MAX_CHARS": 0},
               {"RAG_CACHE_TTL_SECONDS": float("nan")}, {"RAG_CACHE_MAX_ENTRIES": 0}):
        with pytest.raises(ValueError):
            Settings(**kw)


@pytest.fixture
def rag(monkeypatch, tmp_path):
    context = SimpleNamespace(
        release=(tmp_path / "release-a", {"status": "complete", "model": "fake", "revision": "1"}),
        query="What documents are needed for IIIT reporting in 2026?", language="english")
    evidence = RetrievedChunk("Applicants must submit their Class 12 marksheet at reporting.",
                              "reporting.txt", "admissions", 1, -1, years="2026", verified=True)
    grounded = GroundedAnswer(status="answered", answer="Bring your Class 12 marksheet.",
                             evidence=[Evidence(source_id=1, quote=evidence.text)])

    def model(schema, instruction, payload):
        if schema is RoutingDecision:
            return RoutingDecision(intent="knowledge", query=context.query,
                                   category="admissions", language=context.language)
        return grounded

    invoke = Mock(side_effect=model)
    search = Mock(return_value=[evidence])
    monkeypatch.setattr(nodes, "active_release", lambda _: context.release)
    monkeypatch.setattr(nodes, "invoke_json", invoke)
    monkeypatch.setattr(nodes, "retrieve", search)
    ticket = Mock(side_effect=AssertionError("Unexpected action"))
    monkeypatch.setattr(nodes, "create_ticket", ticket)
    monkeypatch.setattr(nodes, "create_reminder", ticket)
    graph = build_graph(MemorySaver())

    def ask(text="What should I bring for reporting?", session=None, **profile):
        return graph.invoke({"messages": [HumanMessage(content=text)],
                             "student_category": "general", **profile},
                            {"configurable": {"thread_id": session or str(uuid4())}})

    return SimpleNamespace(ask=ask, invoke=invoke, search=search, context=context, grounded=grounded,
                           graph=graph, evidence=evidence, ticket=ticket)


def test_matching_turn_reuses_evidence_and_draft_and_skips_review(rag):
    first = rag.ask()
    assert first["rag_metrics"]["model_calls"] == 3
    second = rag.ask()
    assert second["response_status"] == "answered"
    assert second["sources"] == first["sources"]
    assert second["rag_metrics"]["retrieval_cache"] == "hit"
    assert second["rag_metrics"]["draft_cache"] == "hit"
    # A2 (FutureWork 06 §4): a verified draft-cache hit skips the 9B re-review, so only the
    # routing call runs. Deterministic source_quote re-validation still runs (near-free) and
    # reproduces identical citations.
    assert second["rag_metrics"]["model_calls"] == 1
    assert len(second["messages"]) == 2
    assert second["messages"][-1].additional_kwargs["resolved_query"] == rag.context.query
    assert rag.invoke.call_args.args[1] == nodes.ROUTING_PROMPT
    assert rag.search.call_count == 1
    rag.ticket.assert_not_called()


@pytest.mark.parametrize("change", ["original", "history", "language", "profile", "model", "prompt", "review_prompt", "tokens", "day"])
def test_draft_key_covers_effective_inputs(rag, monkeypatch, change):
    rag.ask(session="first")
    kwargs = {}
    if change == "original":
        kwargs["text"] = "Which documents do I bring?"
    elif change == "history":
        kwargs["session"] = "first"
    elif change == "language":
        rag.context.language = "hinglish"
    elif change == "profile":
        kwargs["student_category"] = "CG"
    elif change in {"model", "tokens"}:
        updates = {"GROQ_CHAT_MODEL": "different-model"} if change == "model" else {"LLM_MAX_TOKENS": 900}
        monkeypatch.setattr(nodes, "settings", replace(nodes.settings, **updates))
    elif change == "day":
        from datetime import datetime
        monkeypatch.setattr(nodes, "datetime", SimpleNamespace(now=lambda _: datetime(2030, 1, 1)))
    else:
        field = "ANSWER_PROMPT" if change == "prompt" else "REVIEW_PROMPT"
        monkeypatch.setattr(nodes, field, getattr(nodes, field) + " Additional instruction.")
    result = rag.ask(**kwargs)
    assert result["rag_metrics"]["draft_cache"] == "miss"
    assert result["rag_metrics"]["model_calls"] == 3


@pytest.mark.parametrize("change", ["release", "query", "k"])
def test_retrieval_key_invalidation(rag, monkeypatch, change):
    rag.ask()
    if change == "release":
        root, manifest = rag.context.release
        rag.context.release = (root.with_name("release-b"), manifest)
    elif change == "query":
        rag.context.query = "What documents are needed for CG reporting in 2026?"
    else:
        monkeypatch.setattr(nodes, "settings", replace(nodes.settings, TOP_K=3))
    result = rag.ask()
    assert result["rag_metrics"]["retrieval_cache"] == "miss"
    assert rag.search.call_count == 2


def test_source_content_change_invalidates_draft(rag):
    rag.ask()
    # Expire retrieval only; a changed evidence payload must not match the old draft.
    with sqlite3.connect(nodes.settings.RAG_CACHE_DB_PATH) as conn:
        for key, value in conn.execute("SELECT key, value FROM rag_cache").fetchall():
            if isinstance(json.loads(value), list):
                conn.execute("DELETE FROM rag_cache WHERE key = ?", (key,))
    rag.search.return_value = [replace(rag.evidence, text=rag.evidence.text + " Bring originals.")]
    assert rag.ask()["rag_metrics"]["draft_cache"] == "miss"


def test_release_is_pinned_even_when_pointer_changes_during_search(rag):
    original = rag.context.release

    def search(*args, **kwargs):
        assert kwargs["release"] == original
        rag.context.release = (original[0].with_name("release-b"), original[1])
        return [rag.evidence]

    rag.search.side_effect = search
    first = rag.ask()
    assert first["kb_release"]["root"] == str(original[0])
    rag.search.side_effect = None
    assert rag.ask()["rag_metrics"]["retrieval_cache"] == "miss"


@pytest.mark.parametrize("kind", ["retrieval", "draft"])
def test_invalid_cache_schema_falls_back(rag, kind):
    rag.ask()
    with sqlite3.connect(nodes.settings.RAG_CACHE_DB_PATH) as conn:
        for key, value in conn.execute("SELECT key, value FROM rag_cache").fetchall():
            matches = isinstance(json.loads(value), list) == (kind == "retrieval")
            if matches:
                conn.execute("UPDATE rag_cache SET value = '{}' WHERE key = ?", (key,))
    result = rag.ask()
    assert result["response_status"] == "answered"
    assert result["rag_metrics"][kind + "_cache"] == "miss"


def test_cache_failure_falls_back_without_leaking_content(rag, monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(nodes, "settings", replace(nodes.settings, RAG_CACHE_DB_PATH=str(tmp_path)))
    result = rag.ask()
    assert result["response_status"] == "answered"
    assert result["rag_metrics"]["model_calls"] == 3
    assert rag.context.query not in caplog.text


def test_legacy_and_disabled_caches_are_bypassed(rag, monkeypatch):
    rag.context.release = None
    assert rag.ask()["rag_metrics"]["retrieval_cache"] == "bypass"
    assert rag.ask()["rag_metrics"]["draft_cache"] == "bypass"
    assert rag.search.call_count == 2
    monkeypatch.setattr(nodes, "settings", replace(nodes.settings, RAG_CACHE_ENABLED=False))
    assert rag.ask()["rag_metrics"]["model_calls"] == 3


def test_review_rejection_evicts_draft_and_never_creates_ticket(rag):
    # Under A2 the 9B review runs only on a fresh generation (a verified cache hit skips it),
    # so review rejection is exercised on the first turn: an answered draft rejected by review
    # must not be stored, leaving the next identical turn a draft-cache miss, and no ticket.
    rag.invoke.side_effect = [RoutingDecision(intent="knowledge", query=rag.context.query, category="admissions"),
                             rag.grounded,
                             GroundedAnswer(status="insufficient", answer="Cannot verify.")]
    result = rag.ask()
    assert result["rag_metrics"]["draft_cache"] == "miss"
    assert result["rag_metrics"]["model_calls"] == 3
    assert result["response_status"] == "insufficient"
    assert result["sources"] == []
    with sqlite3.connect(nodes.settings.RAG_CACHE_DB_PATH) as conn:
        values = [json.loads(row[0]) for row in conn.execute("SELECT value FROM rag_cache")]
    assert all(isinstance(value, list) for value in values)  # no draft (dict) persisted
    rag.ticket.assert_not_called()


@pytest.mark.parametrize("quote", ["Fees are completely waived.", " " * 12])
def test_invalid_quote_among_valid_quotes_rejects_entire_answer(rag, quote):
    invalid = rag.grounded.model_copy(update={"evidence": [*rag.grounded.evidence,
        Evidence(source_id=1, quote=quote)]})
    rag.invoke.side_effect = [RoutingDecision(intent="knowledge", query=rag.context.query), invalid, invalid]
    assert rag.ask()["response_status"] == "insufficient"


def test_provider_error_on_review_remains_unavailable(rag):
    # Under A2 a verified cache hit makes no model call, so a provider error can only surface
    # on a fresh generation's review call. It must fail closed (unavailable) and never leak
    # the provider body.
    rag.invoke.side_effect = [RoutingDecision(intent="knowledge", query=rag.context.query, category="admissions"),
                             rag.grounded,
                             RuntimeError("provider private body")]
    result = rag.ask()
    assert result["response_status"] == "unavailable"
    assert result["sources"] == []
    assert "private" not in result["answer_text"]
    rag.ticket.assert_not_called()


def test_missing_resolved_query_asks_for_clarification(rag):
    rag.invoke.side_effect = [RoutingDecision(intent="knowledge", query=" ")]
    result = rag.ask("And that one?")
    assert result["response_status"] == "clarification"
    rag.search.assert_not_called()


def test_cutoff_quote_with_omitted_line_is_expanded_to_source_span(rag):
    # Actual live failure: the reviewer copied all dimensions except the intervening
    # rank-basis line, so a factually correct answer was rejected as missing evidence.
    before = "Admission year: 2026\nCounselling: JoSAA\nRound: 4\nProgramme: CSE\nQuota: AI\nSeat category: ST\nSeat pool: Gender-Neutral"
    ranks = "Opening rank: 3215\nClosing rank: 3315"
    canonical = before + "\nRank basis: Category rank\n" + ranks
    source = "IIIT Naya Raipur published opening and closing ranks\n" + canonical + "\nSource row: original source row"
    rag.search.return_value = [replace(rag.evidence, text=source, kind="cutoff")]
    quoted = GroundedAnswer(status="answered", answer="Opening rank 3215, closing rank 3315.",
        evidence=[Evidence(source_id=1, quote=before + "\n" + ranks)])
    rag.invoke.side_effect = [RoutingDecision(intent="knowledge", query=rag.context.query, category="admissions"),
                             quoted, quoted,
                             RoutingDecision(intent="knowledge", query=rag.context.query, category="admissions"), quoted]
    result = rag.ask()
    assert result["response_status"] == "answered"
    assert result["sources"][0]["quote"] == canonical
    repeated = rag.ask()
    assert repeated["rag_metrics"]["draft_cache"] == "hit"
    assert repeated["sources"][0]["quote"] == canonical
    with sqlite3.connect(nodes.settings.RAG_CACHE_DB_PATH) as conn:
        drafts = [json.loads(row[0]) for row in conn.execute("SELECT value FROM rag_cache")
                  if isinstance(json.loads(row[0]), dict)]
    assert drafts[0]["evidence"][0]["quote"] == canonical


@pytest.mark.parametrize("change", ["number", "partial_line", "order", "duplicate", "legacy", "table", "translation"])
def test_cutoff_quote_repair_does_not_relax_evidence(change):
    source = {"verified": True, "kind": "cutoff", "text":
        "IIIT Naya Raipur published opening and closing ranks\n"
        "Seat pool: Gender-Neutral\nRank basis: Category rank\nOpening rank: 3215\nClosing rank: 3315\n"
        "Source row: original row"}
    quote = "Seat pool: Gender-Neutral\nOpening rank: 3215\nClosing rank: 3315"
    if change == "number":
        quote = quote.replace("3215", "9999")
    elif change == "partial_line":
        quote = quote.replace("Opening rank: 3215", "Opening rank: 32")
    elif change == "order":
        quote = "Closing rank: 3315\nSeat pool: Gender-Neutral\nOpening rank: 3215"
    elif change == "duplicate":
        source["text"] = source["text"].replace("Source row:", "Seat pool: Gender-Neutral\nSource row:")
    elif change == "legacy":
        source["verified"] = False
    elif change == "table":
        source["kind"] = "table"
    else:
        quote = quote.replace("Seat pool:", "सीट पूल:")
    assert source_quote(quote, source) is None


@pytest.mark.parametrize("empty", [True, False])
def test_failed_or_empty_retrieval_is_not_cached(rag, empty):
    rag.search.return_value = []
    rag.search.side_effect = None if empty else RuntimeError("database error")
    expected = "insufficient" if empty else "unavailable"
    assert rag.ask()["response_status"] == expected
    assert rag.ask()["response_status"] == expected
    assert rag.search.call_count == 2


@pytest.mark.parametrize("followup", ["And for CG?", "और सीजी के लिए?", "Aur CG ke liye?"])
def test_all_model_stages_receive_same_followup_history(rag, followup):
    rag.ask(session="same")
    prior_query = rag.context.query
    rag.context.query = "What documents are needed for IIIT CG reporting in 2026?"
    rag.ask(followup, session="same")
    calls = rag.invoke.call_args_list[-3:]
    histories = [call.args[2]["history"] for call in calls]
    assert histories[0] == histories[1] == histories[2]
    assert histories[0][1]["resolved_query"] == prior_query
    assert all(m["text"] != followup for m in histories[0])
    rag.ask("And for NTPC?", session="same")
    assert rag.invoke.call_args_list[-3].args[2]["history"][-1]["resolved_query"] == rag.context.query


def test_pair_window_includes_kth_previous_turn_and_resets_on_new_session(rag, monkeypatch):
    monkeypatch.setattr(nodes, "settings", replace(nodes.settings, HISTORY_TURNS=3))
    for _ in range(4):
        rag.ask("hello", session="same")
    result = rag.ask(session="same")
    assert result["rag_metrics"]["history_pairs"] == 3
    assert len(result["messages"]) == 6
    assert all(isinstance(result["messages"][i], HumanMessage) for i in (0, 2, 4))
    assert result["turn_history"] == []
    assert rag.ask()["rag_metrics"]["history_pairs"] == 0


def test_sqlite_checkpoint_reopen_preserves_resolved_history(rag, tmp_path):
    from langgraph.checkpoint.sqlite import SqliteSaver
    path = str(tmp_path / "history.sqlite")
    config = {"configurable": {"thread_id": "persistent"}}
    for question in ("Reporting documents?", "And for CG?"):
        with SqliteSaver.from_conn_string(path) as saver:
            graph = build_graph(saver)
            result = graph.invoke({"messages": [HumanMessage(content=question)]}, config)
    assert result["rag_metrics"]["history_pairs"] == 1
    assert rag.invoke.call_args_list[-3].args[2]["history"][1]["resolved_query"] == rag.context.query
