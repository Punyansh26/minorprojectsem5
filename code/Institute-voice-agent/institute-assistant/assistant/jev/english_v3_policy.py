"""Prepare only bounded English queries, so useful routes avoid an LLM call."""
from dataclasses import dataclass
import math
import re

from .common import ACTION, CATEGORIES, INSTITUTE, SAFE_INTENTS
from .english_policy import MODEL_ID, MODEL_REVISION, MAX_TOKENS, non_english_hint

PROFILE = "english-v3"
BACKEND = "minilm-english-v3"
HEADS = ("intent", "category", "query_action", "english")
QUERY_ACTIONS = ("copy", "scope_institute", "defer")
DEFAULT_THRESHOLDS = {"policy": PROFILE, "supported": False,
                      "intent": .99, "category": .99, "english": .99, "query_action": .99}
REFERENCE = re.compile(r"\b(?:it|its|that|those|these|them|same|above|previous|former|latter)\b", re.I)
PUBLIC_RULE = re.compile(r"\b(?:PM[ -]?(?:Vidyalaxmi|USP)|CSIS|post[ -]matric|NSP|"
                         r"National Scholarship Portal|Central Sector Interest Subsidy)\b", re.I)
# A second institute must never be silently replaced by the helpdesk default.
OTHER_INSTITUTE = re.compile(r"\b(?:IIT|NIT|IIM|IIIT|university|college of)\b", re.I)
INSTITUTE_TOPIC = re.compile(
    r"\b(?:admission|applicant|application|undergraduate|postgraduate|doctoral|counselling|"
    r"tuition|fees?|scholarship|stipend|rank|ranks|cutoff|cutoffs|quota|NTPC|JoSAA|"
    r"hostel|mess|resident|residents|dining|room|rooms|campus|institute|college|"
    r"semester|exam|exams|examination|elective|electives|course|courses|credits?|"
    r"academic|degree|thesis|dissertation|transcript|library|laboratory|student|students|"
    r"alumni|placement|placements|GATE|JEE|B\.?Tech|M\.?Tech|Ph\.?D)\b", re.I)


@dataclass(frozen=True)
class LocalRoute:
    """Keep retrieval preference separate from the public routing decision."""
    decision: object
    retrieval_preference: str | None
    query_strategy: str


def validate_thresholds(value):
    """Refuse uncalibrated or incompatible policy shapes."""
    if set(value) != set(DEFAULT_THRESHOLDS) or value["policy"] != PROFILE or not isinstance(value["supported"], bool):
        raise ValueError("Invalid v3 routing policy")
    for name in HEADS:
        number = value[name]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not 0 <= number <= 1:
            raise ValueError("Invalid v3 threshold")


def preflight(message, history=(), pending=None, max_chars=2000):
    """Preserve action/language boundaries; inspect history at the query boundary."""
    if not message.strip() or len(message) > max_chars:
        return "input_size"
    if pending:
        return "pending_action"
    if ACTION.search(message):
        return "action_language"
    if non_english_hint(message):
        return "non_english"
    return None


def scoped_query(message):
    """Attach the institute only; never invent programme, year or student attributes."""
    return "For IIIT Naya Raipur: " + message


def exact_followup(message, history, pending=None):
    """Skip routing for a complete English category/round edit with known scope."""
    from assistant.history import exact_rank_followup, latest_resolved_query
    from assistant.kb.structured import rank_filters
    from assistant.llm import RoutingDecision
    if preflight(message, history, pending) or not history:
        return None
    # The shared helper supports Hindi too; v3 deliberately recognizes English only.
    if not re.fullmatch(r"(?:(?:and)\s+)?(?:for\s+)?(?:SC|ST|OBC(?:-NCL)?|GEN-EWS|EWS|OPEN|round\s*[-:]?\s*\d+)\s*[?.!]*",
                        message.strip(), re.I):
        return None
    previous = latest_resolved_query(history)
    before = rank_filters(previous)
    required = {"year", "authority", "round", "programme", "quota", "seat_category", "gender_pool"}
    if not required <= before.keys():
        return None
    query = exact_rank_followup(message, history)
    if not query:
        return None
    after = rank_filters(query)
    changed = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
    expected = "round" if re.search(r"\bround\b", message, re.I) else "seat_category"
    if changed - {expected}:
        return None
    decision = RoutingDecision(intent="knowledge", language="english", category="general", query=query)
    return LocalRoute(decision, None, "exact_rank_followup")


def route(message, prediction, thresholds, history=(), pending=None):
    """Accept a calibrated intent and query strategy, or retain selected-provider fallback."""
    from assistant.llm import RoutingDecision
    validate_thresholds(thresholds)
    reason = preflight(message, history, pending)
    if reason:
        return None, reason
    if not thresholds["supported"]:
        return None, "calibration_support"
    intent = prediction.get("intent")
    if intent not in SAFE_INTENTS:
        return None, "unsafe_intent"
    if prediction.get("language") != "english":
        return None, "non_english"
    names = ["intent", "english"] + (["query_action", "category"] if intent == "knowledge" else [])
    for name in names:
        value = prediction.get(name + "_probability")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            return None, "invalid_prediction"
        if name != "category" and value < thresholds[name]:
            return None, "low_" + name
    if intent != "knowledge":
        if history:
            return None, "conversation_history"
        return LocalRoute(RoutingDecision(intent=intent, language="english", category="general", query=""),
                          None, "reply"), None
    strategy = prediction.get("query_action")
    if strategy not in QUERY_ACTIONS or strategy == "defer":
        return None, "needs_rewrite"
    if REFERENCE.search(message):
        return None, "unresolved_reference"
    named = bool(INSTITUTE.search(message))
    if OTHER_INSTITUTE.search(INSTITUTE.sub("", message)):
        return None, "other_institute"
    if history and not (named and strategy == "copy"):
        return None, "conversation_history"
    if strategy == "copy" and not (named or PUBLIC_RULE.search(message)):
        return None, "institute_context"
    if strategy == "scope_institute" and (named or PUBLIC_RULE.search(message)):
        return None, "query_strategy_mismatch"
    if strategy == "scope_institute" and not INSTITUTE_TOPIC.search(message):
        return None, "missing_institute_topic"
    category = prediction.get("category")
    if category not in CATEGORIES:
        return None, "invalid_prediction"
    preference = category if prediction["category_probability"] >= thresholds["category"] else None
    query = message if strategy == "copy" else scoped_query(message)
    return LocalRoute(RoutingDecision(intent=intent, language="english", category=preference or "general", query=query),
                      preference, strategy), None
