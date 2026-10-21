"""
Groups similar escalated (unanswered) questions together, so instead of a flat list of
individual failures, you get "8 students asked variations of X" — the actual signal for
what the knowledge base is missing.

No heavy clustering library needed (no scikit-learn dependency) — at the scale of a student
project's escalation log (dozens to low hundreds of tickets), simple greedy similarity
grouping is fast, easy to reason about, and produces the same practical result.
"""
from dataclasses import dataclass, field

import numpy as np

from assistant.config import settings
from assistant.db import Ticket, list_tickets
from assistant.retrieval import embed_texts


@dataclass
class GapCluster:
    questions: list[str] = field(default_factory=list)
    ticket_ids: list[int] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.questions)

    @property
    def dominant_category(self) -> str:
        if not self.categories:
            return "other"
        return max(set(self.categories), key=self.categories.count)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0


def cluster_tickets(tickets: list[Ticket], threshold: float | None = None) -> list[GapCluster]:
    """
    Greedy single-pass clustering: each ticket joins the most similar existing cluster if
    it's above `threshold` similarity to that cluster's running centroid (average vector of
    its members so far); otherwise it starts a new cluster. Order doesn't materially change
    the result at this scale — this isn't meant to be a perfectly optimal clustering, just a
    good-enough grouping of "these are clearly asking the same thing."
    """
    threshold = threshold if threshold is not None else settings.GAP_SIMILARITY_THRESHOLD
    if not tickets:
        return []

    vectors = np.array(embed_texts([t.question for t in tickets]))
    clusters: list[GapCluster] = []
    centroids: list[np.ndarray] = []
    member_vector_lists: list[list[np.ndarray]] = []  # per-cluster running list of member vectors

    for ticket, vec in zip(tickets, vectors):
        best_idx, best_sim = -1, -1.0
        for i, centroid in enumerate(centroids):
            sim = _cosine_similarity(vec, centroid)
            if sim > best_sim:
                best_idx, best_sim = i, sim

        if best_idx != -1 and best_sim >= threshold:
            clusters[best_idx].questions.append(ticket.question)
            clusters[best_idx].ticket_ids.append(ticket.id)
            clusters[best_idx].categories.append(ticket.detected_category)
            member_vector_lists[best_idx].append(vec)
            centroids[best_idx] = np.mean(member_vector_lists[best_idx], axis=0)
        else:
            clusters.append(GapCluster(
                questions=[ticket.question],
                ticket_ids=[ticket.id],
                categories=[ticket.detected_category],
            ))
            centroids.append(vec)
            member_vector_lists.append([vec])

    clusters.sort(key=lambda c: c.count, reverse=True)
    return clusters


def analyze_gaps(include_sent: bool = True) -> list[GapCluster]:
    """
    Pulls escalation tickets and clusters them. Excludes 'rejected' tickets deliberately —
    a human already decided those weren't real knowledge gaps (off-topic, nonsensical, etc.),
    so including them would pollute the signal this report is meant to give.
    """
    statuses = ["pending", "sent"] if include_sent else ["pending"]
    tickets = []
    for status in statuses:
        tickets.extend(list_tickets(status=status))
    return cluster_tickets(tickets)