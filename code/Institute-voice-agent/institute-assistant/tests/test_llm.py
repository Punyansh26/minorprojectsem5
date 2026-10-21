"""Exercise provider throttling without network calls or actual sleeps."""
from dataclasses import replace
from unittest.mock import Mock

import httpx
import pytest
from groq import RateLimitError
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from assistant import llm


def rate_limit(delay):
    return RateLimitError("private provider details", response=httpx.Response(
        429, request=httpx.Request("POST", "https://example.org"),
        headers={} if delay is None else {"retry-after": delay}), body=None)


@pytest.fixture
def provider(monkeypatch):
    client, sleep = Mock(), Mock()
    monkeypatch.setattr(llm, "get_llm", lambda: client)
    monkeypatch.setattr(llm.time, "sleep", sleep)
    monkeypatch.setattr(llm, "settings", replace(llm.settings, LLM_RATE_LIMIT_MAX_WAIT_SECONDS=10))
    return client, sleep


def test_short_rate_limit_retries_same_review_once(provider):
    client, sleep = provider
    client.invoke.side_effect = [rate_limit("2.5"), AIMessage(content='{"status":"insufficient","answer":"No evidence."}')]
    result = llm.invoke_json(llm.GroundedAnswer, "Review the answer", {"draft": "test"})
    assert result.status == "insufficient"
    sleep.assert_called_once_with(2.5)
    assert client.invoke.call_count == 2
    assert client.invoke.call_args_list[0] == client.invoke.call_args_list[1]


@pytest.mark.parametrize("delay", [None, "invalid", "nan", "inf"])
def test_missing_or_unparseable_retry_after_uses_default_fallback(provider, delay):
    """When no valid retry-after header exists, sleep for the 5s default fallback."""
    client, sleep = provider
    ok = AIMessage(content='{"intent":"knowledge","query":"test"}')
    client.invoke.side_effect = [rate_limit(delay), ok]
    result = llm.invoke_json(llm.RoutingDecision, "Route", {})
    assert result.intent == "knowledge"
    sleep.assert_called_once_with(5.0)
    assert client.invoke.call_count == 2


@pytest.mark.parametrize("delay", ["-1", "0", "11", "3600"])
def test_explicit_bad_delays_never_sleep_or_retry(provider, delay):
    client, sleep = provider
    client.invoke.side_effect = rate_limit(delay)
    with pytest.raises(RateLimitError):
        llm.invoke_json(llm.RoutingDecision, "Route", {})
    sleep.assert_not_called()
    assert client.invoke.call_count == 1


def test_repeated_rate_limit_is_bounded(provider):
    client, sleep = provider
    client.invoke.side_effect = rate_limit("1")
    with pytest.raises(RateLimitError):
        llm.invoke_json(llm.GroundedAnswer, "Review", {})
    sleep.assert_called_once_with(1)
    assert client.invoke.call_count == 2


def test_rate_limit_retry_can_be_disabled(provider, monkeypatch):
    client, sleep = provider
    monkeypatch.setattr(llm, "settings", replace(llm.settings, LLM_RATE_LIMIT_MAX_WAIT_SECONDS=0))
    client.invoke.side_effect = rate_limit("1")
    with pytest.raises(RateLimitError):
        llm.invoke_json(llm.RoutingDecision, "Route", {})
    sleep.assert_not_called()
    assert client.invoke.call_count == 1


def test_other_errors_are_not_retried(provider):
    client, sleep = provider
    client.invoke.side_effect = RuntimeError("Provider failure")
    with pytest.raises(RuntimeError):
        llm.invoke_json(llm.RoutingDecision, "Route", {})
    sleep.assert_not_called()
    assert client.invoke.call_count == 1


def test_malformed_json_retries_once_then_succeeds(provider):
    """A non-conforming 200 body is a transient formatting lapse, retried once."""
    client, sleep = provider
    client.invoke.side_effect = [
        AIMessage(content='{"intent":"not_a_valid_intent"}'),
        AIMessage(content='{"intent":"knowledge","query":"vocational training programme at IIIT Naya Raipur"}'),
    ]
    result = llm.invoke_json(llm.RoutingDecision, "Route", {})
    assert result.intent == "knowledge"
    sleep.assert_not_called()
    assert client.invoke.call_count == 2


def test_malformed_json_retry_is_bounded(provider):
    """A persistently malformed body raises after exactly one retry, never looping."""
    client, sleep = provider
    client.invoke.side_effect = [
        AIMessage(content='not json at all'),
        AIMessage(content='still not valid'),
    ]
    with pytest.raises(ValidationError):
        llm.invoke_json(llm.RoutingDecision, "Route", {})
    assert client.invoke.call_count == 2


@pytest.mark.parametrize("limited_stage", [0, 1, 2])
def test_graph_recovers_from_short_limit_at_each_model_stage(provider, monkeypatch, limited_stage):
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import MemorySaver

    from assistant import nodes
    from assistant.graph import build_graph
    from assistant.retrieval import RetrievedChunk

    client, sleep = provider
    source_text = "Applicants must submit their Class 12 marksheet at reporting."
    answer = llm.GroundedAnswer(status="answered", answer="Bring your Class 12 marksheet.",
                                evidence=[llm.Evidence(source_id=1, quote=source_text)])
    responses = [llm.RoutingDecision(intent="knowledge", query="Reporting documents"), answer, answer]
    calls = [AIMessage(content=result.model_dump_json()) for result in responses]
    calls.insert(limited_stage, rate_limit("1"))
    client.invoke.side_effect = calls
    monkeypatch.setattr(nodes, "retrieve", Mock(return_value=[
        RetrievedChunk(source_text, "reporting.txt", "admissions", 1, 0.1)]))
    ticket, reminder = Mock(), Mock()
    monkeypatch.setattr(nodes, "create_ticket", ticket)
    monkeypatch.setattr(nodes, "create_reminder", reminder)
    result = build_graph(MemorySaver()).invoke(
        {"messages": [HumanMessage(content="What documents do I need for reporting?")]},
        {"configurable": {"thread_id": "rate-limit-test"}})
    assert result["response_status"] == "answered"
    assert result["answer_text"] == answer.answer
    assert result["sources"][0]["quote"] == source_text
    assert client.invoke.call_count == 4
    sleep.assert_called_once_with(1)
    ticket.assert_not_called()
    reminder.assert_not_called()
