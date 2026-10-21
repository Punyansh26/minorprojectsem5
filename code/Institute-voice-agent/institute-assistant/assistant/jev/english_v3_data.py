"""Authored routing scenarios and family-preserving query preparation examples."""
from collections import defaultdict
from pathlib import Path
import random
import re

from .common import INSTITUTE, json_hash, normalized_message
from .english_data import development_rows as v2_rows, dataset_summary
from .english_v3_policy import PUBLIC_RULE, QUERY_ACTIONS, REFERENCE

CORPUS_PATH = Path(__file__).with_name("english_v3_corpus.txt")


def development_rows():
    """Keep paraphrases, aliases and clean/mixed relatives in the same split."""
    rows = v2_rows()
    # Confirmation is already development exposure, never fresh gold.
    from .english_audit import confirmation_rows
    rows += confirmation_rows()
    for row in rows:
        gold = row["gold"]
        unsafe = row.get("kind") in {"mixed", "reference", "reject"} or (
            gold["rewrite"] and (INSTITUTE.search(row["message"]) or REFERENCE.search(row["message"])))
        action = "defer" if unsafe or gold["intent"] != "knowledge" or gold["language"] != "english" else (
            "copy" if INSTITUTE.search(row["message"]) or PUBLIC_RULE.search(row["message"]) else "scope_institute")
        gold.update(query_action=action, rewrite=gold["intent"] == "knowledge" and action == "defer")
        row["critical"] = bool(row["critical"] or gold["rewrite"])
    section = None
    for line in CORPUS_PATH.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("["):
            section = line[1:-1].split("|")
            continue
        intent, category, action = section
        family, message = line.split("|", 1)
        rows.append({"id": json_hash(["v3", message])[:20], "family": "v3-" + family,
                     "message": message, "kind": "authored", "critical": action == "defer" or intent not in {
                         "knowledge", "smalltalk", "clarification"},
                     "gold": {"intent": intent, "category": category, "language": "english",
                              "query_action": action, "rewrite": intent == "knowledge" and action == "defer"}})
    # These are variants, not new families. Their counts never satisfy family floors.
    variants = []
    for row in rows:
        if row["gold"]["intent"] != "knowledge" or row["gold"]["query_action"] != "copy" or not INSTITUTE.search(row["message"]):
            continue
        text = re.sub(r"\s+(?:at|of|for|in)\s+IIIT-NR(?=[?.!,]|$)", "", row["message"], flags=re.I)
        if text == row["message"] or INSTITUTE.search(text):
            continue
        variants.append({**row, "id": json_hash(["v3-unnamed", text])[:20], "message": text,
                         "gold": {**row["gold"], "query_action": "scope_institute", "rewrite": False}})
    rows += variants
    # Exact duplicates from earlier corpora merge their entire declared families.
    parents = {r["family"]: r["family"] for r in rows}
    def root(family):
        while parents[family] != family:
            family = parents[family]
        return family
    messages = {}
    for row in rows:
        key = normalized_message(INSTITUTE.sub("IIIT-NR", row["message"]))
        if key in messages:
            other = messages[key]
            if other["gold"] != row["gold"]:
                raise ValueError("Conflicting labels for equivalent messages")
            parents[root(row["family"])] = root(other["family"])
        else:
            messages[key] = row
    for row in rows:
        row["family"] = root(row["family"])
    from evaluate_helpdesk import CASES
    reserved = {normalized_message(INSTITUTE.sub("IIIT-NR", q)) for _, qs, _ in CASES for q in qs}
    blocked = {r["family"] for r in rows if normalized_message(INSTITUTE.sub("IIIT-NR", r["message"])) in reserved}
    rows = [r for r in messages.values() if r["family"] not in blocked]
    families = defaultdict(list)
    for row in rows:
        families[row["family"]].append(row)
    strata = defaultdict(list)
    for family, members in families.items():
        g = members[0]["gold"]
        strata[(g["intent"], g["category"], g["language"])].append(family)
    rng = random.Random(42)
    for group in strata.values():
        group.sort()
        rng.shuffle(group)
        train_end, val_size = round(.6 * len(group)), round(.15 * len(group))
        for i, family in enumerate(group):
            split = "train" if i < train_end else "validation" if i < train_end + val_size else "calibration"
            for row in families[family]:
                row["split"] = split
    return sorted(rows, key=lambda r: r["id"])


def validate_rows(rows):
    """Reuse split checks and validate the executable query target explicitly."""
    from .english_data import validate_rows as validate_base
    validate_base(rows)
    for row in rows:
        gold = row["gold"]
        if gold.get("query_action") not in QUERY_ACTIONS or gold["rewrite"] != (
                gold["intent"] == "knowledge" and gold["query_action"] == "defer"):
            raise ValueError("Invalid v3 query strategy label")
