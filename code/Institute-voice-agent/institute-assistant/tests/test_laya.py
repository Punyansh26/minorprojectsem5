"""Laya System 1 routing: schema mapping, language detection, policy and runtime wiring.

All tests are offline: no laya-serve, no checkpoints, no torch/transformers. The HTTP
call and the Laya payload are faked, so these run anywhere the agent package imports.
"""
import pytest

from assistant.config import Settings
from assistant.jev import laya_adapter, runtime
from assistant.jev.laya_adapter import (LayaUnavailable, laya_route,
                                        language_from_detection, to_prediction)
from assistant.llm import RoutingDecision

THRESHOLDS = {"probability": 0.6, "confidence": 0.6, "rewrite": 0.5}


def payload(intent="knowledge", intent_p=0.95, category="hostel", category_p=0.9,
            rewrite=0.05, routing_model="english", is_english=True, script="latin",
            language=None):
    """Build a laya-serve /v1/systemone-shaped response for the three questions."""
    def choice(choice_label, p, labels):
        probs = {label: (p if label == choice_label else (1 - p) / (len(labels) - 1)) for label in labels}
        return {"type": "choice", "choice": choice_label, "probabilities": probs,
                "confidence": p, "answer_confidence": p}
    intents = ("knowledge", "smalltalk", "out_of_scope", "clarification", "handoff", "reminder", "cancel")
    categories = ("admissions", "hostel", "cg_counselling", "academics", "general")
    return {
        "answers": {
            "intent": choice(intent, intent_p, intents),
            "category": choice(category, category_p, categories),
            "rewrite": {"type": "noul", "noul": rewrite, "confidence": 0.9, "answer_confidence": 0.9},
        },
        "routing": {"model": routing_model,
                    "detection": {"script": script, "is_english": is_english, "language": language}},
        "usage": {"input_tokens": 10, "output_tokens": 0},
    }


# --- language detection -------------------------------------------------------

@pytest.mark.parametrize("message,routing,expected", [
    ("What are the hostel fees?", {"detection": {"script": "latin", "is_english": True, "language": "en"}}, "english"),
    ("IIIT नया रायपुर फीस", {"detection": {"script": "devanagari", "is_english": False, "language": None}}, "hindi"),
    ("hostel fees kitni hai", {"detection": {"script": "latin", "is_english": False, "language": None}}, "hinglish"),
    ("Bonjour tout le monde", {"detection": {"script": "latin", "is_english": False, "language": "fr"}}, None),
    ("안녕하세요", {"detection": {"script": "hangul", "is_english": False, "language": "ko"}}, None),
])
def test_language_from_detection(message, routing, expected):
    assert language_from_detection(message, routing) == expected


# --- schema mapping -----------------------------------------------------------

def test_to_prediction_maps_all_fields():
    pred = to_prediction(payload(), "What are the hostel fees at IIIT Naya Raipur?")
    assert pred["intent"] == "knowledge"
    assert pred["category"] == "hostel"
    assert pred["language"] == "english"
    assert 0 <= pred["intent_probability"] <= 1
    assert 0 <= pred["category_confidence"] <= 1
    assert pred["rewrite_probability"] == 0.05
    assert len(pred["intent_distribution"]) == 7
    assert len(pred["category_distribution"]) == 5


def test_to_prediction_rejects_unknown_label():
    bad = payload()
    bad["answers"]["intent"]["choice"] = "nonsense"
    with pytest.raises(LayaUnavailable):
        to_prediction(bad, "x")


def test_to_prediction_rejects_missing_answers():
    with pytest.raises(LayaUnavailable):
        to_prediction({"routing": {}}, "x")


def test_to_prediction_unsupported_language_marked():
    pred = to_prediction(payload(script="hangul", is_english=False, language="ko"), "안녕")
    assert pred["language"] == "unsupported"
    assert pred["language_probability"] == 0.0


# --- bilingual routing policy -------------------------------------------------

def test_english_knowledge_named_institute_routes():
    pred = to_prediction(payload(), "What are the hostel fees at IIIT Naya Raipur?")
    decision, reason = laya_route("What are the hostel fees at IIIT Naya Raipur?", pred, THRESHOLDS)
    assert isinstance(decision, RoutingDecision)
    assert decision.intent == "knowledge"
    assert decision.category == "hostel"
    assert decision.query  # original message carried through
    assert reason is None


def test_knowledge_without_institute_defers():
    pred = to_prediction(payload(), "What are the hostel fees?")
    decision, reason = laya_route("What are the hostel fees?", pred, THRESHOLDS)
    assert decision is None and reason == "institute_context"


def test_devanagari_knowledge_defers_for_translation():
    msg = "IIIT नया रायपुर में छात्रावास की फीस क्या है?"
    pred = to_prediction(payload(routing_model="multilingual", is_english=False,
                                 script="devanagari", language=None), msg)
    assert pred["language"] == "hindi"
    decision, reason = laya_route(msg, pred, THRESHOLDS)
    assert decision is None and reason == "needs_translation"


def test_hinglish_knowledge_routes_locally():
    msg = "IIIT Naya Raipur hostel fees kitni hai"
    pred = to_prediction(payload(is_english=False, language=None), msg)
    assert pred["language"] == "hinglish"
    decision, reason = laya_route(msg, pred, THRESHOLDS)
    assert isinstance(decision, RoutingDecision) and reason is None


def test_smalltalk_routes_without_query():
    pred = to_prediction(payload(intent="smalltalk", intent_p=0.99), "Thanks a lot!")
    decision, reason = laya_route("Thanks a lot!", pred, THRESHOLDS)
    assert decision.intent == "smalltalk" and decision.query == "" and reason is None


def test_low_intent_confidence_defers():
    pred = to_prediction(payload(intent_p=0.4), "What are the hostel fees at IIIT Naya Raipur?")
    decision, reason = laya_route("What are the hostel fees at IIIT Naya Raipur?", pred, THRESHOLDS)
    assert decision is None and reason == "low_intent_probability"


def test_unsafe_intent_defers():
    pred = to_prediction(payload(intent="handoff", intent_p=0.99), "Connect me to staff at IIIT Naya Raipur")
    decision, reason = laya_route("Connect me to staff at IIIT Naya Raipur", pred, THRESHOLDS)
    assert decision is None and reason == "unsafe_intent"


def test_high_rewrite_defers():
    pred = to_prediction(payload(rewrite=0.9), "What about it at IIIT Naya Raipur?")
    decision, reason = laya_route("What about it at IIIT Naya Raipur?", pred, THRESHOLDS)
    assert decision is None and reason == "needs_rewrite"


# --- runtime wiring (try_route laya mode) -------------------------------------

def _settings():
    return Settings(JEV_ROUTING_MODE="laya", LAYA_PROBABILITY_THRESHOLD=0.6,
                    LAYA_CONFIDENCE_THRESHOLD=0.6, LAYA_REWRITE_THRESHOLD=0.5)


def test_try_route_laya_success(monkeypatch):
    msg = "What are the hostel fees at IIIT Naya Raipur?"
    monkeypatch.setattr(laya_adapter, "request_prediction",
                        lambda base, m, t: to_prediction(payload(), m))
    metrics = {}
    decision = runtime.try_route(msg, [], {}, _settings(), metrics)
    assert isinstance(decision, RoutingDecision)
    assert metrics["router_path"] == "laya"
    assert metrics["router_backend"] == "laya"
    assert metrics["router_fallback"] is None


def test_try_route_laya_history_defers(monkeypatch):
    called = []
    monkeypatch.setattr(laya_adapter, "request_prediction",
                        lambda base, m, t: called.append(m) or to_prediction(payload(), m))
    metrics = {}
    decision = runtime.try_route("follow up", [{"role": "user", "text": "hi"}], {}, _settings(), metrics)
    assert decision is None
    assert metrics["router_fallback"] == "conversation_history"
    assert called == []  # history short-circuits before any HTTP call


def test_try_route_laya_action_defers_without_http(monkeypatch):
    called = []
    monkeypatch.setattr(laya_adapter, "request_prediction",
                        lambda base, m, t: called.append(m) or to_prediction(payload(), m))
    metrics = {}
    decision = runtime.try_route("Please remind me to pay fees", [], {}, _settings(), metrics)
    assert decision is None
    assert metrics["router_fallback"] == "action_language"
    assert called == []


def test_try_route_laya_unavailable_fails_safe(monkeypatch):
    def boom(base, m, t):
        raise LayaUnavailable("down")
    monkeypatch.setattr(laya_adapter, "request_prediction", boom)
    metrics = {}
    decision = runtime.try_route("What are the hostel fees at IIIT Naya Raipur?", [], {}, _settings(), metrics)
    assert decision is None
    assert metrics["router_fallback"] == "laya_unavailable"
    assert metrics["router_path"] == "llm"
