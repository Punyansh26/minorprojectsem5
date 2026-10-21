"""Compile the text helpdesk; each branch produces exactly one reply per turn."""
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from assistant.config import settings
from assistant.nodes import (
    classify_intent_node, escalate_node, generate_answer_node, handle_reminder_node,
    retrieve_node, route_after_classification, finalize_turn_node,
)
from assistant.state import AssistantState


def build_graph(checkpointer=None):
    """Allow an injected memory store for isolated tests and future session services."""
    graph = StateGraph(AssistantState)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate_answer", generate_answer_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("handle_reminder", handle_reminder_node)
    graph.add_node("finalize_turn", finalize_turn_node)
    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges("classify_intent", route_after_classification, {
        "knowledge": "retrieve", "handoff": "escalate", "reminder": "handle_reminder", "end": "finalize_turn",
    })
    graph.add_edge("retrieve", "generate_answer")
    graph.add_edge("generate_answer", "finalize_turn")
    graph.add_edge("escalate", "finalize_turn")
    graph.add_edge("handle_reminder", "finalize_turn")
    graph.add_edge("finalize_turn", END)
    if checkpointer is None:
        conn = sqlite3.connect(settings.CHECKPOINT_DB_PATH, check_same_thread=False,
                               timeout=settings.CHECKPOINT_TIMEOUT_SECONDS)
        checkpointer = SqliteSaver(conn)
    return graph.compile(checkpointer=checkpointer)
