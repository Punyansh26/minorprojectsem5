"""Serializable conversation state shared by the CLI and future speech adapter."""
from typing import Annotated, TypedDict
# pyrefly: ignore [missing-import]
from langgraph.graph.message import add_messages


class AssistantState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    student_id: str
    student_email: str
    student_category: str
    language: str
    intent: str
    detected_category: str
    retrieval_preference: str | None
    search_query: str
    retrieved_chunks: list[dict]
    retrieval_error: bool
    answer_text: str
    response_status: str
    sources: list[dict]
    escalated: bool
    ticket_id: int | None
    reminder_id: int | None
    pending_action: dict | None
    action_confirmed: bool
    turn_history: list[dict]
    turn_date: str
    kb_release: dict | None
    rag_metrics: dict
    llm_error: str
