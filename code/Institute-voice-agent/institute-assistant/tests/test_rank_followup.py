"""Protect narrow scope edits from local-model reversion to an older question."""
import pytest

from assistant.history import exact_rank_followup
from assistant.kb.structured import rank_filters

BASE = "What are the opening and closing ranks for 2026 JoSAA round 5 CSE SC All India Gender-Neutral?"


@pytest.mark.parametrize("category,round_question", [
    ("And for ST?", "And round 4?"),
    ("और एसटी के लिए?", "और राउंड 4 में?"),
    ("Aur ST ke liye?", "Aur round 4 ke liye?"),
])
def test_chain_changes_only_requested_dimension(category, round_question):
    history = [{"role": "assistant", "resolved_query": BASE}]
    next_query = exact_rank_followup(category, history)
    first = rank_filters(next_query)
    assert first == {**rank_filters(BASE), "seat_category": "ST"}
    history += [{"role": "assistant", "resolved_query": next_query},
                {"role": "assistant", "text": "You're welcome."}]
    assert rank_filters(exact_rank_followup(round_question, history)) == {**first, "round": "4"}


@pytest.mark.parametrize("message", ["What documents are required for B.Tech reporting?",
    "Compare SC and ST", "And for SC and ST?", "ST scholarship income limit?", "Aur CG quota ke liye?"])
def test_new_topics_and_unsupported_edits_stay_with_router(message):
    assert exact_rank_followup(message, [{"role": "assistant", "resolved_query": BASE}]) is None


def test_no_history_no_invented_rank_scope():
    assert exact_rank_followup("And round 4?", []) is None
    assert exact_rank_followup("And for ST?", [{"role": "assistant", "resolved_query": "What are the fees?"}]) is None
