"""English-only selective routing; all rejected decisions use the existing router."""
import math
import re

from .common import CATEGORIES, INSTITUTE, SAFE_INTENTS

PROFILE = "english-v2"
BACKEND = "minilm-english-v2"
MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
MAX_TOKENS = 256
HEADS = ("intent", "category", "rewrite", "english")
DEFAULT_THRESHOLDS = {"policy": PROFILE, "supported": False, "intent": .99,
                      "category": .99, "english": .99, "rewrite": .05}
# A conservative extra signal, not a language detector. The learned English head
# must also pass: many non-English languages and Roman Hindi use Latin letters.
FOREIGN_WORDS = re.compile(
    r"\b(?:kya|kaise|batao|bataiye|chahiye|kitna|kitni|mujhe|hai|hain|hoga|hogi|"
    r"padhai|samjhao|dhanyavad|namaste|bonjour|merci|quels|quelle|cuanto|cuesta|"
    r"gracias|hola|danke|bitte|gebuhren|combien|inscription)\b", re.I)


def non_english_hint(message):
    """Reject clear language signals without treating ASCII as proof of English."""
    from assistant.dialogue import language_hint
    return bool(language_hint(message) or FOREIGN_WORDS.search(message)
                or any(c.isalpha() and not c.isascii() for c in message))


def validate_thresholds(value):
    """Reject incompatible calibration policies before any model can serve traffic."""
    if (set(value) != set(DEFAULT_THRESHOLDS) or value["policy"] != PROFILE
            or not isinstance(value["supported"], bool)):
        raise ValueError("Invalid English calibration policy")
    for name in ("intent", "category", "english", "rewrite"):
        number = value[name]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not 0 <= number <= 1:
            raise ValueError("Invalid English threshold")


def route(message, prediction, thresholds):
    """Return an English route and a text-free, inspectable rejection reason."""
    from assistant.llm import RoutingDecision
    validate_thresholds(thresholds)
    if non_english_hint(message) or prediction.get("language") != "english":
        return None, "non_english"
    if not thresholds["supported"]:
        return None, "calibration_support"
    intent = prediction.get("intent")
    if intent not in SAFE_INTENTS:
        return None, "unsafe_intent"
    names = ["intent", "english"] + (["category", "rewrite"] if intent == "knowledge" else [])
    for name in names:
        value = prediction.get(name + "_probability")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            return None, "invalid_prediction"
        if (value > thresholds[name] if name == "rewrite" else value < thresholds[name]):
            return None, "needs_rewrite" if name == "rewrite" else "low_" + name
    if intent == "knowledge":
        if not INSTITUTE.search(message):
            return None, "institute_context"
        if prediction.get("category") not in CATEGORIES:
            return None, "invalid_prediction"
    return RoutingDecision(intent=intent, language="english",
                           category=prediction["category"] if intent == "knowledge" else "general",
                           query=message if intent == "knowledge" else ""), None
