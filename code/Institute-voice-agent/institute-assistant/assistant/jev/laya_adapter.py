"""Laya System 1 routing over the Jev-compatible HTTP wire protocol.

Laya (https://github.com/NandhaKishorM/laya) is a non-autoregressive System 1
decision engine. It answers typed `choice`/`noul` questions in a single forward
pass (tens of milliseconds), with no local training or activation step that the
custom/english Open Jev backends require.

Because Laya depends on transformers 5.x while this project pins the shared model
stack (faster-whisper, Coqui TTS, sentence-transformers) to transformers 4.x, Laya
runs in its OWN isolated virtual environment as `laya-serve`, and this module talks
to it over `POST /v1/systemone` -- the same wire protocol TypeSafe Jev exposes and
Laya re-implements byte-compatibly. Nothing here imports torch or transformers, so
importing this module never touches the shared stack.

The adapter maps Laya's answer payload onto the exact `prediction` dict the existing
routing policies consume (see `common.prediction_rows` for the shape), so every
downstream safety gate -- intent/category/language thresholds, the institute regex,
the rewrite ceiling -- is reused unchanged. A dedicated `laya_route` policy adds
bilingual (English + Hindi/Hinglish) acceptance on top of that shared contract.
"""
from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request

from .common import CATEGORIES, INSTITUTE, INTENTS

# The typed questions sent to Laya, as JSON for the HTTP body. Instruction wording is
# tuned so the zero-shot checkpoints read the state rather than the bare label words.
#
# NOTE: language is deliberately NOT a question here. Asking the checkpoint a
# `choice` language question is unreliable zero-shot (it mislabels Hindi as
# "unsupported" and English greetings as "hindi"). Laya's router already detects
# the script and language in <0.5 ms of dependency-free analysis before the forward
# pass, and that detection is accurate; `language_from_detection` reads it instead.
LAYA_QUESTIONS = {
    "intent": {
        "type": "choice",
        "instructions": "What does the sender of this helpdesk message want?",
        "criteria": {
            "knowledge": "asking for information, facts, fees, dates, eligibility or procedures",
            "smalltalk": "a greeting, thanks, or casual chit-chat with no request",
            "out_of_scope": "a topic unrelated to this institute helpdesk",
            "clarification": "the message is unclear, empty or incomplete",
            "handoff": "asking to reach a human, staff or to escalate",
            "reminder": "asking to be reminded or to schedule something",
            "cancel": "asking to cancel or stop a previous request",
        },
    },
    "category": {
        "type": "choice",
        "instructions": "Which institute department should handle this message?",
        "criteria": {
            "admissions": "admission, application, eligibility, cutoffs, ranks, fees to apply",
            "hostel": "hostel, mess, dining, rooms, residence, accommodation",
            "cg_counselling": "career guidance, counselling, mentoring, well-being",
            "academics": "courses, exams, credits, electives, grades, academic calendar",
            "general": "anything else about the institute",
        },
    },
    "rewrite": {
        "type": "noul",
        "instructions": (
            "Does this message need translation, pronoun or reference resolution, "
            "or removal of an unrelated request before it can be searched as-is?"
        ),
    },
}

# Routing languages this bilingual policy will accept a local route for.
LOCAL_LANGUAGES = ("english", "hindi", "hinglish")
_DEVANAGARI = re.compile(r"[\u0900-\u097f]")
# The institute named in Devanagari ("IIIT नया रायपुर") or English. The shared
# `common.INSTITUTE` regex is English-only; this adds the Hindi spelling so a
# Hindi knowledge query can still be grounded to this institute.
_INSTITUTE_HINDI = re.compile(r"IIIT\s*नया\s*रायपुर|आई\.?आई\.?आई\.?टी", re.I)


def institute_mentioned(message):
    """True when the message names this institute in English or Hindi."""
    return bool(INSTITUTE.search(message) or _INSTITUTE_HINDI.search(message))


class LayaUnavailable(RuntimeError):
    """Raised when laya-serve cannot be reached or returns an unusable payload."""


def language_from_detection(message, routing):
    """Derive the message language from Laya's reliable script/language detection.

    Returns one of the project's supported languages (english/hindi/hinglish) or
    None when the text is some other language the local path should not handle.
    This mirrors `dialogue.language_hint`: Devanagari is Hindi; otherwise an
    English detection is English, and Latin-script non-English is treated as
    Hinglish (Roman Hindi) only when the detector could not place it as a foreign
    language, matching the demo's Roman-Hindi handling.
    """
    if _DEVANAGARI.search(message):
        return "hindi"
    detection = (routing or {}).get("detection") or {}
    script = detection.get("script")
    if script and script != "latin":
        return None  # non-Latin, non-Devanagari: not a supported local language
    if detection.get("is_english"):
        return "english"
    language = detection.get("language")
    if language in (None, "en", "eng", "english"):
        # Latin text the detector could not place -> treat as Roman Hindi (hinglish),
        # which the demo supports; a confident foreign language is excluded below.
        return "hinglish"
    # The detector named a specific non-English language for Latin text.
    return None


def _confidence(answer):
    """Use the calibrated max-probability (answer_confidence) when present.

    Laya's `confidence` is 1 - normalised entropy (option-count dependent), while
    `answer_confidence` is max(p) -- the field temperature scaling fits and the one
    the project's probability thresholds were written against. Fall back to
    `confidence` only if the server omits `answer_confidence`.
    """
    value = answer.get("answer_confidence", answer.get("confidence"))
    return float(value) if value is not None else float("nan")


def to_prediction(payload, message):
    """Map a laya-serve /v1/systemone response onto the project's prediction dict.

    Returns the keys the routing policy validates. Language is taken from Laya's
    routing detection (accurate) rather than a model question (unreliable), so the
    `language`/`language_probability`/`language_confidence` fields reflect the
    script/language detection, with probability/confidence set to 1.0 when the
    detector placed the text and 0.0 when it did not.
    """
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise LayaUnavailable("Laya response missing answers")
    labels = {"intent": INTENTS, "category": CATEGORIES}
    prediction = {}
    for name in ("intent", "category"):
        answer = answers.get(name) or {}
        choice = answer.get("choice")
        probabilities = answer.get("probabilities") or {}
        if choice not in labels[name]:
            raise LayaUnavailable(f"Laya returned an unknown {name}: {choice!r}")
        distribution = [float(probabilities.get(label, 0.0)) for label in labels[name]]
        total = sum(distribution)
        if not math.isfinite(total) or total <= 0:
            raise LayaUnavailable(f"Laya returned an invalid {name} distribution")
        prediction[name] = choice
        prediction[name + "_probability"] = float(probabilities.get(choice, 0.0))
        prediction[name + "_confidence"] = _confidence(answer)
        prediction[name + "_distribution"] = distribution
    rewrite = answers.get("rewrite") or {}
    noul = rewrite.get("noul")
    if noul is None or not math.isfinite(float(noul)):
        raise LayaUnavailable("Laya returned an invalid rewrite probability")
    prediction["rewrite_probability"] = float(noul)
    # Language from detection: supported language -> full confidence; else none.
    language = language_from_detection(message, payload.get("routing"))
    prediction["language"] = language or "unsupported"
    prediction["language_probability"] = 1.0 if language else 0.0
    prediction["language_confidence"] = 1.0 if language else 0.0
    return prediction


def request_prediction(base_url, message, timeout):
    """POST one state to laya-serve and return the mapped prediction dict.

    Only the message text leaves this process, and only to the configured local
    laya-serve URL. No history or profile values are ever sent.
    """
    body = json.dumps({"state": {"body": message}, "questions": LAYA_QUESTIONS}).encode("utf-8")
    url = base_url.rstrip("/") + "/v1/systemone"
    request = urllib.request.Request(url, data=body, method="POST",
                                     headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as error:
        raise LayaUnavailable("laya-serve request failed") from error
    return to_prediction(payload, message)


def laya_route(message, prediction, thresholds):
    """Accept a confident English OR Hindi/Hinglish route, else fall through.

    This is the bilingual counterpart to `common.accepted` (English only). It reuses
    the same confidence/probability gates and institute-topic requirement, but keeps
    Hindi and Hinglish (language derived from Laya's script detection) instead of
    rejecting them, so the local fast path covers the demo's Hindi traffic too. Any
    rejection returns (None, reason) so the caller can record a text-free fallback
    reason and use the existing LLM router.
    """
    from assistant.jev.common import SAFE_INTENTS
    from assistant.llm import RoutingDecision

    probability = thresholds["probability"]
    confidence = thresholds["confidence"]
    rewrite_ceiling = thresholds["rewrite"]

    intent = prediction.get("intent")
    if intent not in SAFE_INTENTS:
        return None, "unsafe_intent"
    language = prediction.get("language")
    if language not in LOCAL_LANGUAGES:
        return None, "unsupported_language"

    for name in ("intent",):
        prob = prediction.get(name + "_probability")
        conf = prediction.get(name + "_confidence")
        for value in (prob, conf):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                return None, "invalid_prediction"
        if prob < probability:
            return None, "low_" + name + "_probability"
        if conf < confidence:
            return None, "low_" + name + "_confidence"

    if intent != "knowledge":
        return RoutingDecision(intent=intent, language="english", category="general", query=""), None

    # Knowledge routes must be grounded in this institute and need no rewrite.
    if not institute_mentioned(message):
        return None, "institute_context"
    # A knowledge query is sent verbatim to retrieval, which expects English. Laya
    # does not translate, so Devanagari (Hindi) knowledge queries defer to the LLM
    # router, which rewrites them to English first. Roman Hindi / English knowledge
    # queries route locally (retrieval reads Latin text directly).
    if _DEVANAGARI.search(message):
        return None, "needs_translation"
    rewrite = prediction.get("rewrite_probability")
    if isinstance(rewrite, bool) or not isinstance(rewrite, (int, float)) or not math.isfinite(rewrite) or not 0 <= rewrite <= 1:
        return None, "invalid_prediction"
    if rewrite > rewrite_ceiling:
        return None, "needs_rewrite"
    category = prediction.get("category")
    if category not in CATEGORIES:
        return None, "invalid_prediction"
    preference = category if prediction["category_probability"] >= probability else "general"
    # The query carries the original message; dialogue.language_hint picks the reply
    # language downstream, so an English RoutingDecision.language is safe here.
    return RoutingDecision(intent=intent, language="english", category=preference, query=message), None
