"""Bound conversation context by complete turns, independently of retrieved evidence."""
import json
import re

from langchain_core.messages import AIMessage, HumanMessage


def latest_resolved_query(history: list[dict]) -> str:
    return next((item["resolved_query"] for item in reversed(history)
                 if item.get("role") == "assistant" and item.get("resolved_query")), "")


def exact_rank_followup(message: str, history: list[dict]) -> str | None:
    """Apply an unambiguous category/round edit to prior scope, never to prior facts.

    Only short, fully recognized follow-ups qualify. New topics and comparisons continue
    through the normal model rewrite. This prevents a model reverting to an older category.
    """
    from assistant.kb.structured import is_rank_question, rank_filters
    previous = latest_resolved_query(history)
    if not previous or not is_rank_question(previous):
        return None
    text = message.strip().rstrip("?.!।").strip()
    prefix = r"(?:(?:and|aur|और)\s+)?(?:for\s+)?"
    suffix = r"(?:\s+(?:(?:ke|के)\s+(?:liye|लिए)|mein|में))?"
    category = re.fullmatch(prefix + r"(SC|ST|OBC(?:-NCL)?|GEN-EWS|EWS|OPEN|एससी|एसटी|ओबीसी)" + suffix, text, re.I)
    round_match = re.fullmatch(prefix + r"(?:round|राउंड|चरण)\s*[-:]?\s*(\d+)" + suffix, text, re.I)
    old = rank_filters(previous)
    if category and old.get("seat_category") in {"SC", "ST", "OBC-NCL", "GEN-EWS", "OPEN"}:
        value = category.group(1).upper()
        value = {"एससी": "SC", "एसटी": "ST", "ओबीसी": "OBC-NCL", "OBC": "OBC-NCL", "EWS": "GEN-EWS"}.get(value, value)
        rewritten, count = re.subn(r"(?<!\w)" + re.escape(old["seat_category"]) + r"(?!\w)", value, previous, flags=re.I)
        return rewritten if count else None
    if round_match and old.get("round") and len(re.findall(r"(?:\bround|राउंड|चरण)\s*[-:]?\s*\d+", previous, re.I)) == 1:
        rewritten, count = re.subn(r"((?:\bround|राउंड|चरण)\s*[-:]?\s*)\d+\b",
                                  lambda match: match[1] + round_match[1], previous, flags=re.I)
        return rewritten if count else None
    return None


def completed_pairs(messages: list) -> list[tuple]:
    """Ignore incomplete or orphaned messages left by interrupted/older sessions."""
    pairs, human = [], None
    for message in messages:
        if isinstance(message, HumanMessage):
            human = message
        elif isinstance(message, AIMessage) and human is not None:
            pairs.append((human, message))
            human = None
    return pairs


def prompt_history(messages: list, turns: int, max_chars: int) -> list[dict]:
    """Take a contiguous suffix of whole pairs without repeating the current question."""
    history, size = [], 0
    for human, answer in reversed(completed_pairs(messages)[-turns:]):
        pair = [{"role": "user", "text": str(human.content)},
                {"role": "assistant", "text": str(answer.content)}]
        for field in ("resolved_query", "response_status"):
            if answer.additional_kwargs.get(field):
                pair[1][field] = answer.additional_kwargs[field]
        length = len(json.dumps(pair, ensure_ascii=False))
        if size + length > max_chars:
            break
        history = pair + history
        size += length
    return history
