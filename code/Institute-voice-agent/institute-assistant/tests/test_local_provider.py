"""Exercise local transport, session routing and bounded evidence without model downloads."""
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import Mock

import httpx
import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from assistant import llm, nodes
from assistant.graph import build_graph
from assistant.retrieval import RetrievedChunk


@pytest.fixture
def local(monkeypatch):
    monkeypatch.setattr(llm, "settings", replace(llm.settings, LLM_PROVIDER="ollama", GROQ_API_KEY=""))
    monkeypatch.setattr(llm, "prompt_tokens", lambda *args: 100)
    monkeypatch.setattr(llm, "get_llm", Mock(side_effect=AssertionError("Unexpected cloud request")))


@pytest.fixture(autouse=True)
def _reset_local_caches():
    """Keep the lazily-cached digest and thinking-capability state from leaking across tests."""
    llm._LOCAL_DIGESTS.clear()
    llm._LOCAL_THINKING.clear()
    yield
    llm._LOCAL_DIGESTS.clear()
    llm._LOCAL_THINKING.clear()


def transport(monkeypatch, handler):
    def respond(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": llm.settings.OLLAMA_MODEL, "digest": "test-digest"}]})
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion", "thinking"]})
        return handler(request)
    client = httpx.Client(base_url="http://localhost:11434/", transport=httpx.MockTransport(respond))
    monkeypatch.setattr(llm, "_local_client", lambda *args: client)
    return client


def test_local_no_key_structural_schema_and_full_validation(local, monkeypatch):
    requests = []
    def reply(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"done": True, "done_reason": "stop",
            "message": {"content": '{"intent":"knowledge","query":"Reporting documents"}'}})
    with transport(monkeypatch, reply):
        result = llm.invoke_json(llm.RoutingDecision, "Route", {"message": "Documents?"})
    assert result.intent == "knowledge"
    sent = requests[0]
    assert sent["format"]["additionalProperties"] is False
    assert sent["format"]["properties"]["intent"]["enum"] == llm.RoutingDecision.model_json_schema()["properties"]["intent"]["enum"]
    assert "maxLength" not in sent["format"]["properties"]["query"]
    assert '"maxLength": 2000' in sent["messages"][0]["content"]
    assert sent["options"]["num_ctx"] == 8192
    llm.get_llm.assert_not_called()


@pytest.mark.parametrize("failure", ["connection", "timeout", "missing", "server", "malformed", "bound", "truncated"])
def test_local_failures_never_fall_back_or_expose_body(local, monkeypatch, failure):
    def reply(request):
        if failure == "connection":
            raise httpx.ConnectError("private", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private", request=request)
        if failure in {"missing", "server"}:
            return httpx.Response(404 if failure == "missing" else 500, text="private")
        content = '{"intent":"knowledge","query":"' + "x" * 2001 + '"}' if failure == "bound" else "private"
        return httpx.Response(200, json={"done": True,
            "done_reason": "length" if failure == "truncated" else "stop", "message": {"content": content}})
    with transport(monkeypatch, reply), pytest.raises(llm.LocalModelError) as error:
        llm.invoke_json(llm.RoutingDecision, "Route", {})
    assert "private" not in str(error.value)
    llm.get_llm.assert_not_called()


def test_budget_trims_whole_pairs_then_whole_sources(local, monkeypatch):
    monkeypatch.setattr(llm, "settings", replace(llm.settings, OLLAMA_NUM_CTX=4096, LLM_MAX_TOKENS=500, OLLAMA_NUM_PREDICT=500))
    monkeypatch.setattr(llm, "prompt_tokens", lambda schema, instruction, payload:
        1200 + len(payload.get("history", [])) * 300 + len(payload.get("sources", [])) * 1000)
    original = {"history": [{"role": "user"}, {"role": "assistant"}],
                "sources": [{"source_id": 1, "text": "Rank 100, SC, AI quota, 2026, round 5"},
                            {"source_id": 2, "text": "Other full source"}]}
    result = llm.prepare_payload(llm.GroundedAnswer, "Answer", original, review_instruction="Review")
    assert result["history"] == []
    assert result["sources"] == original["sources"][:1]
    assert len(original["history"]) == 2 and len(original["sources"]) == 2
    # Review must never drop cited evidence to make room.
    monkeypatch.setattr(llm, "prompt_tokens", lambda *args: 5000)
    with pytest.raises(llm.LocalModelError, match="exceed"):
        llm.prepare_payload(llm.GroundedAnswer, "Review", original)


def test_graph_provider_isolation_and_cache_partition(local, monkeypatch, tmp_path):
    monkeypatch.setattr(nodes, "settings", replace(nodes.settings, LLM_PROVIDER="ollama"))
    monkeypatch.setattr(nodes, "active_release", lambda _: (tmp_path / "release", {"status": "complete"}))
    text = "Applicants must bring their Class 12 marksheet for reporting."
    monkeypatch.setattr(nodes, "retrieve", Mock(return_value=[
        RetrievedChunk(text, "reporting.txt", "admissions", 1, -1, verified=True)]))
    observed = []
    def respond(schema, instruction, payload):
        provider = llm.selected_provider()
        observed.append((provider, schema.__name__))
        if schema is llm.RoutingDecision:
            return schema(intent="knowledge", query="IIIT reporting documents")
        return schema(status="answered", answer=text, evidence=[llm.Evidence(source_id=1, quote=text)])
    monkeypatch.setattr(nodes, "invoke_json", respond)
    graph = build_graph(MemorySaver())
    def ask(provider, session):
        return graph.invoke({"messages": [HumanMessage(content="Reporting documents?")]},
            {"configurable": {"thread_id": session, "llm_provider": provider}})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda item: ask(*item), [("ollama", "local"), ("groq", "cloud")]))
    assert {result["rag_metrics"]["provider"] for result in results} == {"ollama", "groq"}
    assert all(result["rag_metrics"]["draft_cache"] == "miss" for result in results)
    assert observed.count(("ollama", "GroundedAnswer")) == 2
    assert observed.count(("groq", "GroundedAnswer")) == 2
    for provider in ("ollama", "groq"):
        assert ask(provider, provider + "-repeat")["rag_metrics"]["draft_cache"] == "hit"


def test_missing_tokenizer_is_actionable_and_offline(monkeypatch, tmp_path):
    with pytest.raises(llm.LocalModelError, match="setup_local.py"):
        llm._tokenizer(str(tmp_path / "missing.json"))


def test_model_replacement_changes_cache_identity(local, monkeypatch):
    key = (llm.settings.OLLAMA_BASE_URL, llm.settings.OLLAMA_MODEL)
    monkeypatch.setitem(llm._LOCAL_DIGESTS, key, "original")
    before = llm.model_identity()
    monkeypatch.setitem(llm._LOCAL_DIGESTS, key, "replacement")
    assert llm.model_identity() != before


def test_local_evidence_grammar_uses_bounded_span_index_and_resolves_to_exact_span():
    """A7: the grammar emits source_id + an integer span index, not a free quote string.

    The index can only point at a real contiguous span, so fabricated or edited quotes
    are impossible; resolve_span_indices maps the index back to the exact verbatim span.
    """
    import jsonschema
    sources = [{"source_id": 1, "text": "Category: SC\nOpening Rank: 3627\nClosing Rank: 4832"},
               {"source_id": 2, "text": "Category: ST\nOpening Rank: 3215\nClosing Rank: 3315"}]
    payload = {"sources": sources}
    schema = llm.generation_schema(llm.GroundedAnswer, payload)
    # Each evidence branch is a bounded integer index, never a quotable string.
    branches = schema["$defs"]["Evidence"]["oneOf"]
    for branch in branches:
        assert branch["properties"]["span_index"]["type"] == "integer"
        assert "quote" not in branch["properties"]
        assert all(isinstance(i, int) for i in branch["properties"]["span_index"]["enum"])
    spans_one = llm.evidence_spans(sources[0]["text"])
    valid_index = spans_one.index("Opening Rank: 3627")
    answer = {"status": "answered", "answer": "The opening rank is 3627.",
              "evidence": [{"source_id": 1, "span_index": valid_index}]}
    jsonschema.validate(answer, schema)
    # Resolution reproduces the exact verbatim span for the real pipeline.
    resolved = llm.resolve_span_indices(payload, answer)
    assert resolved["evidence"] == [{"source_id": 1, "quote": "Opening Rank: 3627"}]
    # An out-of-range index for that source is rejected by the grammar...
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**answer, "evidence": [{"source_id": 1, "span_index": len(spans_one)}]}, schema)
    # ...and defensively dropped (fail closed) if it ever reaches the resolver.
    dropped = llm.resolve_span_indices(payload, {**answer, "evidence": [{"source_id": 1, "span_index": len(spans_one)}]})
    assert dropped["evidence"] == []


def test_evidence_candidates_preserve_original_substrings_and_bounds():
    text = "Eligibility conditions apply.\n" + "Long source text, " * 160 + "\nTotal: ₹1,81,000."
    spans = llm.evidence_spans(text)
    assert spans and all(10 <= len(span) <= 1500 and span in text for span in spans)
    assert "Total: ₹1,81,000." in spans


def test_thinking_disabled_and_not_exposed(local, monkeypatch):
    """A thinking-capable model gets think:false; its reasoning is never surfaced."""
    sent = []
    def reply(request):
        body = json.loads(request.content)
        sent.append(body)
        content = '{"intent":"knowledge","query":"Documents"}' if len(sent) == 1 else '{"status":"insufficient","answer":"Unknown"}'
        return httpx.Response(200, json={"done": True, "done_reason": "stop",
                                      "message": {"content": content, "thinking": "Not exposed"}})
    # transport() advertises the "thinking" capability, so think:false must be sent.
    with transport(monkeypatch, reply):
        llm.invoke_json(llm.RoutingDecision, "Route", {})
        answer = llm.invoke_json(llm.GroundedAnswer, "Answer", {})
    assert [body["think"] for body in sent] == [False, False]
    assert all(body["options"]["num_predict"] == llm.settings.OLLAMA_NUM_PREDICT for body in sent)
    assert "Not exposed" not in answer.model_dump_json()


def test_think_omitted_for_non_thinking_model(local, monkeypatch):
    """A model that does not advertise `thinking` must never receive the `think` field.

    Ollama returns HTTP 400 for `think` sent to such a model (observed with the Colab
    qwen3.5:9b build). Omitting it is output-equivalent to think:false everywhere, so the
    request must simply drop the field. The capability comes from /api/show."""
    sent = []
    def respond(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": llm.settings.OLLAMA_MODEL, "digest": "test-digest"}]})
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion"]})
        body = json.loads(request.content)
        sent.append(body)
        return httpx.Response(200, json={"done": True, "done_reason": "stop",
            "message": {"content": '{"intent":"knowledge","query":"Documents"}'}})
    client = httpx.Client(base_url="http://localhost:11434/", transport=httpx.MockTransport(respond))
    monkeypatch.setattr(llm, "_local_client", lambda *args: client)
    llm.invoke_json(llm.RoutingDecision, "Route", {})
    assert "think" not in sent[0]


def test_keep_alive_numeric_string_sent_as_integer(local, monkeypatch):
    """Ollama rejects keep_alive "-1" as a unitless Go duration (HTTP 400); a numeric
    string must be coerced to a JSON number, while real duration strings pass through."""
    sent = []
    def reply(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"done": True, "done_reason": "stop",
            "message": {"content": '{"intent":"knowledge","query":"Documents"}'}})
    # Numeric string -> integer (so Ollama reads it as "forever", not a bad duration).
    monkeypatch.setattr(llm, "settings", replace(llm.settings, LLM_PROVIDER="ollama",
                                                 GROQ_API_KEY="", OLLAMA_KEEP_ALIVE="-1"))
    with transport(monkeypatch, reply):
        llm.invoke_json(llm.RoutingDecision, "Route", {})
    assert sent[0]["keep_alive"] == -1 and isinstance(sent[0]["keep_alive"], int)
    # A real duration string is sent unchanged.
    sent.clear()
    monkeypatch.setattr(llm, "settings", replace(llm.settings, LLM_PROVIDER="ollama",
                                                 GROQ_API_KEY="", OLLAMA_KEEP_ALIVE="5m"))
    with transport(monkeypatch, reply):
        llm.invoke_json(llm.RoutingDecision, "Route", {})
    assert sent[0]["keep_alive"] == "5m"


def test_local_error_reaches_adapter_as_safe_detail(local, monkeypatch):
    monkeypatch.setattr(nodes, "invoke_json", Mock(side_effect=llm.LocalModelError("Start ollama serve.")))
    result = build_graph(MemorySaver()).invoke(
        {"messages": [HumanMessage(content="Reporting documents?")]},
        {"configurable": {"thread_id": "offline", "llm_provider": "ollama"}})
    assert result["response_status"] == "unavailable"
    assert result["llm_error"] == "Start ollama serve."
    assert not result["sources"] and not result["ticket_id"]


def test_report_labels_use_shared_provider(local, monkeypatch):
    from types import SimpleNamespace
    from assistant import report
    invoke = Mock(return_value=SimpleNamespace(label="Documents required for undergraduate reporting"))
    monkeypatch.setattr(report, "invoke_json", invoke)
    cluster = SimpleNamespace(questions=["Which reporting documents?"])
    assert report._label_cluster(cluster) == "Documents required for undergraduate reporting"
    invoke.side_effect = llm.LocalModelError("offline")
    assert report._label_cluster(cluster) == cluster.questions[0]


def _counting_transport(monkeypatch, handler):
    """Like transport() but records every path hit so lazy /api/tags can be asserted."""
    hits = []
    def respond(request):
        hits.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": llm.settings.OLLAMA_MODEL, "digest": "test-digest"}]})
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion", "thinking"]})
        return handler(request)
    client = httpx.Client(base_url="http://localhost:11434/", transport=httpx.MockTransport(respond))
    monkeypatch.setattr(llm, "_local_client", lambda *args: client)
    return hits


def test_digest_fetched_once_then_cached_and_refreshed_on_404(local, monkeypatch):
    """A3: /api/tags runs on the first local call, is cached, and refreshes after a 404."""
    key = (llm.settings.OLLAMA_BASE_URL, llm.settings.OLLAMA_MODEL)
    monkeypatch.delitem(llm._LOCAL_DIGESTS, key, raising=False)
    state = {"missing": False}
    def reply(request):
        if state["missing"]:
            return httpx.Response(404, text="model not found")
        return httpx.Response(200, json={"done": True, "done_reason": "stop",
            "message": {"content": '{"intent":"knowledge","query":"Documents"}'}})
    hits = _counting_transport(monkeypatch, reply)
    llm.invoke_json(llm.RoutingDecision, "Route", {"message": "Documents?"})
    llm.invoke_json(llm.RoutingDecision, "Route", {"message": "Documents again?"})
    # One /api/tags for the first call; the second reuses the cached digest.
    assert hits.count("/api/tags") == 1
    assert hits.count("/api/chat") == 2
    assert llm._LOCAL_DIGESTS.get(key) == "test-digest"
    # A 404 (model swapped/removed) drops the stale digest so the next call re-fetches it.
    state["missing"] = True
    with pytest.raises(llm.LocalModelError):
        llm.invoke_json(llm.RoutingDecision, "Route", {"message": "Documents?"})
    assert key not in llm._LOCAL_DIGESTS


def test_local_answer_span_index_resolves_to_verbatim_quote(local, monkeypatch):
    """A7: the model emits source_id + span_index; the server resolves the exact quote."""
    key = (llm.settings.OLLAMA_BASE_URL, llm.settings.OLLAMA_MODEL)
    monkeypatch.setitem(llm._LOCAL_DIGESTS, key, "cached")  # skip /api/tags for focus
    source_text = "Category: SC\nOpening Rank: 3627\nClosing Rank: 4832"
    sources = [{"source_id": 1, "text": source_text, "verified": True, "kind": "cutoff",
                "source_file": "cutoffs.txt", "page_number": 1, "category": "admissions"}]
    spans = llm.evidence_spans(source_text)
    target = "Opening Rank: 3627"
    index = spans.index(target)
    sent = []
    def reply(request):
        body = json.loads(request.content)
        sent.append(body)
        return httpx.Response(200, json={"done": True, "done_reason": "stop", "message": {"content":
            json.dumps({"status": "answered", "answer": "The opening rank is 3627.",
                        "evidence": [{"source_id": 1, "span_index": index}]})}})
    with transport(monkeypatch, reply):
        result = llm.invoke_json(llm.GroundedAnswer, "Answer", {"sources": sources, "question": "SC opening rank?"})
    # The grammar sent to Ollama constrains evidence to an integer index, not a quote string.
    evidence_defs = sent[0]["format"]["$defs"]["Evidence"]["oneOf"]
    assert all(branch["properties"]["span_index"]["type"] == "integer" for branch in evidence_defs)
    assert all("quote" not in branch["properties"] for branch in evidence_defs)
    # The prompt surfaces a numbered span menu so the index choice is meaningful.
    assert "span_options" in sent[0]["messages"][1]["content"]
    # The returned, validated evidence carries the exact verbatim span, not an index.
    assert result.status == "answered"
    assert result.evidence[0].source_id == 1
    assert result.evidence[0].quote == target
