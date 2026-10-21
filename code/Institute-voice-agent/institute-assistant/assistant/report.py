"""
Generates a dated markdown report from the current gap clusters — the actual artifact you'd
show a professor or admin staff: "here's what our system found missing this week."
"""
import os
from datetime import date

from pydantic import BaseModel, Field

from assistant.config import settings
from assistant.gap_analysis import GapCluster, analyze_gaps
from assistant.llm import invoke_json

LABEL_PROMPT = """You will be shown several questions that are all asking about the same
underlying topic. Respond with ONLY a short (5-8 word) label for what topic they share —
no punctuation, no explanation, nothing else."""


def _label_cluster(cluster: GapCluster) -> str:
    """Use the selected provider; preserve useful reports when inference is unavailable."""
    class Label(BaseModel):
        label: str = Field(min_length=1, max_length=120)
    try:
        return invoke_json(Label, LABEL_PROMPT, {"questions": cluster.questions}).label.strip()
    except Exception:
        return cluster.questions[0]


def generate_report() -> tuple[str, list[GapCluster]]:
    clusters = analyze_gaps()

    if not clusters:
        return "No escalated questions yet — nothing to analyze.", []

    lines = [
        f"# Knowledge Base Gap Report — {date.today().isoformat()}",
        "",
        f"Analyzed {sum(c.count for c in clusters)} unanswered question(s) across "
        f"{len(clusters)} distinct topic(s).",
        "",
    ]

    recurring = [c for c in clusters if c.count > 1]
    singles = [c for c in clusters if c.count == 1]

    if recurring:
        lines.append("## Recurring gaps (multiple students asked about this)")
        lines.append("")
        for i, cluster in enumerate(recurring, start=1):
            label = _label_cluster(cluster)
            lines.append(f"### Gap #{i}: {label}")
            lines.append(f"- **{cluster.count} question(s)**, category: `{cluster.dominant_category}`")
            lines.append(f"- Ticket IDs: {', '.join(str(t) for t in cluster.ticket_ids)}")
            lines.append("- Questions asked:")
            for q in cluster.questions:
                lines.append(f"  - \"{q}\"")
            lines.append(f"- **Suggested action:** add or expand a document covering this in "
                          f"`knowledge_base/{cluster.dominant_category}/`")
            lines.append("")

    if singles:
        lines.append("## One-off questions (asked once so far — worth watching, not yet a clear pattern)")
        lines.append("")
        for cluster in singles:
            lines.append(f"- \"{cluster.questions[0]}\" (category: `{cluster.dominant_category}`, "
                          f"ticket #{cluster.ticket_ids[0]})")
        lines.append("")

    return "\n".join(lines), clusters


def save_report() -> str:
    report_text, _ = generate_report()
    os.makedirs(settings.GAP_REPORTS_DIR, exist_ok=True)
    path = os.path.join(settings.GAP_REPORTS_DIR, f"gap_report_{date.today().isoformat()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report_text)
    return path
