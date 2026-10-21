"""Reviewed development targets, with family isolation and honest provenance."""
from collections import Counter, defaultdict
from pathlib import Path
import random

from .common import INSTITUTE, json_hash, normalized_message

CORPUS_PATH = Path(__file__).with_name("english_corpus.txt")


def rewrite_required(message, *, mixed=False, reference=False, english=True):
    """Label required query transformation, never optional teacher paraphrasing."""
    return bool(mixed or reference or not english or not INSTITUTE.search(message))


def development_rows():
    """Keep scenario relatives together; never manufacture a final test set."""
    sections = defaultdict(list)
    section = None
    for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            section = tuple(line[1:-1].split("|"))
            continue
        if section is None:
            raise ValueError("Missing corpus section")
        sections[section].append(line)
    # A mixed request and its clean relative must not cross splits. Values are
    # one-based clean general scenario numbers corresponding to each mixed row.
    mixed_relatives = [1, 6, 21, 2, 5, 17, 4, 19, 33, 16,
                       1, 8, 12, 20, 10, 27, 23, 18, 26, 11]
    general = sections[("knowledge", "general", "clean")]
    rows = []
    for (intent, category, kind), messages in sections.items():
        for index, message in enumerate(messages):
            parent = general[mixed_relatives[index] - 1] if kind == "mixed" else message
            # De-named last five knowledge questions have explicit near relatives
            # where applicable; retain those relatives in the same family.
            relatives = {
                ("hostel", 35): 4, ("hostel", 38): 22,
                ("cg_counselling", 35): 2, ("cg_counselling", 36): 0,
                ("cg_counselling", 37): 1, ("cg_counselling", 38): 4,
                ("cg_counselling", 39): 6, ("academics", 38): 12,
                ("general", 38): 11, ("general", 39): 26,
            }
            if intent == "knowledge" and kind == "clean" and (category, index) in relatives:
                parent = messages[relatives[(category, index)]]
            english = kind != "reject"
            family = json_hash(["english-v2-family", parent])[:20]
            rows.append({"id": json_hash(["english-v2", message])[:20], "family": family,
                         "message": message, "kind": kind,
                         "gold": {"intent": intent, "category": category,
                                  "language": "english" if english else "unsupported",
                                  "rewrite": intent == "knowledge" and rewrite_required(message, mixed=kind == "mixed")},
                         "critical": kind in {"mixed", "reject"} or intent in {"handoff", "reminder", "cancel"}})
    # Reserve entire families before selecting any training or calibration rows.
    from evaluate_helpdesk import CASES
    reserved = {normalized_message(q) for _, messages, _ in CASES for q in messages}
    blocked = {r["family"] for r in rows if normalized_message(r["message"]) in reserved}
    rows = [r for r in rows if r["family"] not in blocked]
    families = defaultdict(list)
    for row in rows:
        families[row["family"]].append(row)
    strata = defaultdict(list)
    for family, members in families.items():
        gold = members[0]["gold"]
        strata[(gold["intent"], gold["category"], gold["language"])].append(family)
    split_for = {}
    rng = random.Random(42)
    for group in strata.values():
        group.sort()
        rng.shuffle(group)
        train_end = round(.60 * len(group))
        val_end = train_end + round(.15 * len(group))
        for i, family in enumerate(group):
            split_for[family] = "train" if i < train_end else "validation" if i < val_end else "calibration"
    for row in rows:
        row["split"] = split_for[row["family"]]
    return sorted(rows, key=lambda row: row["id"])


def validate_rows(rows):
    """Refuse split leakage and malformed labels before training consumes them."""
    from .common import INTENTS, CATEGORIES
    families, messages, ids = {}, {}, set()
    for row in rows:
        split, gold = row["split"], row["gold"]
        if split not in {"train", "validation", "calibration"}:
            raise ValueError("English recovery accepts development splits only")
        if row["id"] in ids or not row["message"].strip():
            raise ValueError("Duplicate ID or empty message")
        ids.add(row["id"])
        message = normalized_message(row["message"])
        if message in messages:
            raise ValueError("Duplicate message")
        messages[message] = split
        if row["family"] in families and families[row["family"]] != split:
            raise ValueError("Family leakage")
        families[row["family"]] = split
        if (gold["intent"] not in INTENTS or gold["category"] not in CATEGORIES
                or gold["language"] not in {"english", "unsupported"}
                or not isinstance(gold["rewrite"], bool)):
            raise ValueError("Invalid reviewed label")
    if set(families.values()) != {"train", "validation", "calibration"}:
        raise ValueError("Missing development split")


def dataset_summary(rows):
    """Expose family support separately from row counts and independent review."""
    return {"rows": len(rows), "families": len({r["family"] for r in rows}),
            "splits": {s: {"rows": sum(r["split"] == s for r in rows),
                           "families": len({r["family"] for r in rows if r["split"] == s})}
                       for s in ("train", "validation", "calibration")},
            "languages": dict(Counter(r["gold"]["language"] for r in rows)),
            "label_source": "agent-authored public synthetic scenarios; explicit operational rubric",
            "reviewer": "Codex", "review_date": "2026-09-26", "independent_human_review": False,
            "limitations": "Development scenarios are not real traffic or statistically independent samples. No final test is supplied."}
