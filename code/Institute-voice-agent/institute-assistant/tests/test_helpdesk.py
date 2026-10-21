"""Offline regression checks: no API calls, emails, downloads, or production databases."""
from dataclasses import replace
from unittest.mock import Mock

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from assistant import nodes
from assistant.dialogue import normalize_category, valid_email
from assistant.graph import build_graph
from assistant.llm import Evidence, GroundedAnswer, RoutingDecision
from assistant.retrieval import RetrievedChunk


@pytest.fixture
def chat(monkeypatch):
    model = Mock(side_effect=AssertionError("Unexpected model call"))
    retrieve = Mock(side_effect=AssertionError("Unexpected retrieval"))
    ticket = Mock(return_value=41)
    reminder = Mock(return_value=17)
    monkeypatch.setattr(nodes, "invoke_json", model)
    monkeypatch.setattr(nodes, "retrieve", retrieve)
    monkeypatch.setattr(nodes, "create_ticket", ticket)
    monkeypatch.setattr(nodes, "create_reminder", reminder)
    graph = build_graph(MemorySaver())

    def ask(text, session="student-a", **profile):
        return graph.invoke({"messages": [HumanMessage(content=text)], "student_id": "100",
                             "student_email": "student@example.org", "student_category": "general", **profile},
                            {"configurable": {"thread_id": session}})
    return ask, model, retrieve, ticket, reminder


def route(intent="knowledge", **kw):
    return RoutingDecision(intent=intent, **kw)


def chunk():
    return RetrievedChunk("Applicants must submit their Class 12 marksheet at reporting.", "admissions/reporting.txt", "admissions", 2, 0.2)


def answer(**kw):
    return GroundedAnswer(status="answered", answer="Bring your Class 12 marksheet for reporting.",
                          evidence=[Evidence(source_id=1, quote=chunk().text)], **kw)


def test_greeting_never_calls_model_retrieval_or_actions(chat):
    ask, model, search, ticket, reminder = chat
    result = ask("hey there")
    assert result["response_status"] == "smalltalk"
    assert "IIIT" in result["answer_text"]
    for mock in (model, search, ticket, reminder):
        mock.assert_not_called()


@pytest.mark.parametrize("question,language", [("whale facts", "english"), ("whale ke facts batao", "hinglish"), ("व्हेल के बारे में बताओ", "hindi")])
def test_off_topic_never_reaches_retrieval(chat, question, language):
    ask, model, search, ticket, reminder = chat
    model.side_effect = [route("out_of_scope", language=language)]
    result = ask(question)
    assert result["response_status"] == "out_of_scope"
    assert result["sources"] == []
    search.assert_not_called()
    ticket.assert_not_called()
    reminder.assert_not_called()


def test_grounded_answer_and_contextual_followup(chat):
    ask, model, search, _, _ = chat
    model.side_effect = [route(query="IIIT reporting documents", category="admissions"), answer(), answer(),
                         route(query="IIIT reporting documents for CG admissions", category="cg_counselling"), answer(), answer()]
    search.side_effect = None
    search.return_value = [chunk()]
    first = ask("What should I bring for reporting?")
    assert first["sources"][0]["page_number"] == 2
    followup = ask("And for CG?")
    search.assert_called_with("IIIT reporting documents for CG admissions", preferred_category="cg_counselling", release=None)
    history = model.call_args_list[3].args[2]["history"]
    assert any("reporting" in m["text"] for m in history)
    assert followup["response_status"] == "answered"


def test_unknown_offers_ticket_only_after_consent_and_resets_status(chat):
    ask, model, search, ticket, _ = chat
    model.side_effect = [route(query="Is hostel laundry free?", category="hostel")]
    search.side_effect = None
    search.return_value = []
    result = ask("Is laundry free?")
    assert result["response_status"] == "insufficient"
    ticket.assert_not_called()
    result = ask("yes")
    assert result["ticket_id"] == 41
    assert "No email has been sent" in result["answer_text"]
    assert ticket.call_args.kwargs["question"] == "Is hostel laundry free?"
    result = ask("hello")
    assert result["ticket_id"] is None and result["escalated"] is False
    assert result["sources"] == []
    assert ticket.call_count == 1


def test_declining_handoff_and_changing_topic_clear_pending(chat):
    ask, model, search, ticket, _ = chat
    model.side_effect = [route(query="Fees?"), route(query="Fees?"), route("out_of_scope")]
    search.side_effect = None
    search.return_value = []
    ask("Fees?")
    assert ask("no")["pending_action"] is None
    ask("Fees?")
    assert ask("whale facts")["pending_action"] is None
    ticket.assert_not_called()


@pytest.mark.parametrize("evidence", [[], [Evidence(source_id=2, quote="An invented source quotation")], [Evidence(source_id=1, quote="Fees are completely waived.")]])
def test_invalid_evidence_fails_closed(chat, evidence):
    ask, model, search, ticket, _ = chat
    model.side_effect = [route(query="Fees?"), GroundedAnswer(status="answered", answer="Fees are waived.", evidence=evidence), GroundedAnswer(status="answered", answer="Fees are waived.", evidence=evidence)]
    search.side_effect = None
    search.return_value = [chunk()]
    result = ask("Fees?")
    assert result["response_status"] == "insufficient"
    assert "waived" not in result["answer_text"]
    ticket.assert_not_called()


def test_retrieval_failure_does_not_create_kb_gap_ticket(chat):
    ask, model, search, ticket, _ = chat
    model.side_effect = [route(query="Fees?")]
    search.side_effect = RuntimeError("private backend details")
    result = ask("Fees?")
    assert result["response_status"] == "unavailable"
    assert "private" not in result["answer_text"]
    assert result.get("pending_action") is None
    ticket.assert_not_called()


def test_model_failure_and_empty_input_fail_closed(chat):
    ask, model, search, ticket, _ = chat
    model.side_effect = ValueError("malformed JSON")
    assert ask("What are the fees?")["response_status"] == "unavailable"
    assert ask(" ")["response_status"] == "clarification"
    search.assert_not_called()
    ticket.assert_not_called()


def test_separate_sessions_do_not_share_pending_actions(chat):
    ask, model, search, ticket, _ = chat
    model.side_effect = [route(query="Fees?"), route("clarification")]
    search.side_effect = None
    search.return_value = []
    ask("Fees?", session="a")
    assert ask("yes", session="b")["response_status"] == "clarification"
    ticket.assert_not_called()


def test_history_is_bounded(chat, monkeypatch):
    ask, *_ = chat
    monkeypatch.setattr(nodes, "settings", replace(nodes.settings, HISTORY_TURNS=2))
    for _ in range(8):
        result = ask("hello")
    assert len(result["messages"]) == 4


def test_reminders_disabled_by_default(chat):
    ask, model, _, _, reminder = chat
    model.side_effect = [route("reminder", reminder_message="Submit form", reminder_date="2099-01-01")]
    result = ask("Remind me to submit the admission form on 1 January 2099")
    assert result["response_status"] == "unavailable"
    reminder.assert_not_called()


def test_reminder_date_email_confirmation_followup(chat, monkeypatch):
    ask, model, _, _, reminder = chat
    monkeypatch.setattr(nodes, "settings", replace(nodes.settings, REMINDERS_ENABLED=True, SMTP_USER="test", SMTP_APP_PASSWORD="test"))
    model.side_effect = [route("reminder", reminder_message="Submit admission form"),
                         route("reminder", reminder_date="2099-10-15", reminder_message="Submit admission form")]
    assert ask("Remind me to submit admission form", student_email="abc")["pending_action"]["stage"] == "date"
    assert ask("15 October 2099")["pending_action"]["stage"] == "email"
    result = ask("valid@example.org")
    assert result["response_status"] == "confirmation"
    reminder.assert_not_called()
    result = ask("haan")
    assert result["reminder_id"] == 17
    reminder.assert_called_once_with("100", "valid@example.org", "Submit admission form", "2099-10-15")


@pytest.mark.parametrize("bad_date", ["2099-02-30", "2000-01-01", "garbage"])
def test_reminder_rejects_invalid_and_past_dates(chat, monkeypatch, bad_date):
    ask, model, _, _, reminder = chat
    monkeypatch.setattr(nodes, "settings", replace(nodes.settings, REMINDERS_ENABLED=True, SMTP_USER="test", SMTP_APP_PASSWORD="test"))
    model.side_effect = [route("reminder", reminder_message="Submit form", reminder_date=bad_date)]
    assert ask("remind me")["pending_action"]["stage"] == "date"
    reminder.assert_not_called()


def test_profile_validation():
    assert normalize_category("gen") == "general"
    assert normalize_category("cg") == "CG"
    assert not valid_email("abc")
    assert not valid_email("a@b.com\nBcc: bad@example.org")
    assert valid_email("a.b+test@example.org")


def test_old_report_never_reaches_answer_model_for_current_year(chat):
    ask, model, search, _, _ = chat
    model.side_effect = [route(query="BTech admission in 2026"), answer(), answer()]
    search.side_effect = None
    search.return_value = [RetrievedChunk("Outdated admission rule.", "AR_2022_23.pdf", "general", 21, 0.1),
                           RetrievedChunk(chunk().text, "BTECH_2026.pdf", "admissions", 7, 0.2),
                           RetrievedChunk("Undated and potentially stale policy.", "FAQ.pdf", "general", 2, 0.3)]
    result = ask("How are admissions decided in 2026?")
    assert result["response_status"] == "answered"
    supplied = model.call_args.args[2]["sources"]
    assert [c["source_file"] for c in supplied] == ["BTECH_2026.pdf"]


def test_ticket_save_failure_never_claims_success(chat):
    ask, model, _, ticket, _ = chat
    model.side_effect = [route("handoff", query="Please review my admission question")]
    ticket.side_effect = RuntimeError("database unavailable")
    result = ask("Please send my admission question to staff for review")
    assert result["response_status"] == "unavailable"
    assert result["ticket_id"] is None
    assert not result["escalated"]


def test_answer_generation_failure_has_no_stale_sources(chat):
    ask, model, search, _, _ = chat
    model.side_effect = [route(query="Reporting"), answer(), answer(), route(query="Reporting for CG"), ValueError("invalid JSON")]
    search.side_effect = None
    search.return_value = [chunk()]
    assert ask("What documents for reporting?")["sources"]
    result = ask("and for CG?")
    assert result["response_status"] == "unavailable"
    assert result["sources"] == []


def test_grounding_review_can_remove_unsupported_scope(chat):
    ask, model, search, _, _ = chat
    draft = GroundedAnswer(status="answered", answer="All quotas use JoSAA.", evidence=[Evidence(source_id=1, quote=chunk().text)])
    model.side_effect = [route(query="Admission basis"), draft, answer()]
    search.side_effect = None
    search.return_value = [chunk()]
    result = ask("Admission basis?")
    assert result["answer_text"] == answer().answer
    assert model.call_args.args[2]["draft"]["answer"] == "All quotas use JoSAA."


def test_grounding_rate_limit_explains_temporary_limit_without_showing_draft(chat, caplog):
    import httpx
    from groq import RateLimitError

    ask, model, search, ticket, reminder = chat
    error = RateLimitError("private provider details", response=httpx.Response(
        429, request=httpx.Request("POST", "https://example.org"),
        headers={"retry-after": "30"}), body=None)
    model.side_effect = [route(query="What is the fees structure?"), answer(), error]
    search.side_effect = None
    search.return_value = [chunk()]
    result = ask("What is the fees structure?")
    assert result["response_status"] == "unavailable"
    assert "temporarily rate-limited" in result["answer_text"]
    assert result["sources"] == []
    assert result.get("pending_action") is None
    assert "private provider details" not in caplog.text
    ticket.assert_not_called()
    reminder.assert_not_called()


def test_hinglish_overrides_router_hindi_label(chat):
    ask, model, _, _, _ = chat
    model.side_effect = [route("out_of_scope", language="hindi")]
    result = ask("whale ke facts batao")
    assert result["language"] == "hinglish"
    assert "Main IIIT" in result["answer_text"]


def test_missing_source_is_not_a_question_for_the_student(chat):
    ask, model, search, _, _ = chat
    model.side_effect = [route(query="Laundry price in 2027"),
                         GroundedAnswer(status="clarification", answer="Can you supply a source?")]
    search.side_effect = None
    search.return_value = [chunk()]
    result = ask("Laundry price in 2027?")
    assert result["response_status"] == "insufficient"
    assert "supply a source" not in result["answer_text"]


def test_escalation_node_requires_confirmation(monkeypatch):
    ticket = Mock()
    monkeypatch.setattr(nodes, "create_ticket", ticket)
    result = nodes.escalate_node({"messages": [HumanMessage(content="Fees?")]})
    assert result["pending_action"]["stage"] == "confirm"
    ticket.assert_not_called()
