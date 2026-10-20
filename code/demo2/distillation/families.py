"""§3.5 family-based splits to prevent leakage (Demo2-local, CPU-only, no model).

Chapter 09 §3 point 5: assign *whole topic families* (including translations and
template variants) to exactly one split before training, exactly as JEV does —
"430 authored families: 258 training, 65 validation, 107 calibration" with
"Clean/mixed/translated relatives in one family". Reusing a family across splits
inflates accuracy and voids the acceptance gate (:mod:`certificate`).

A family is the canonical topic of a triple, independent of surface language and
template wording. Two triples are in the same family when their questions reduce to
the same canonical form after:

* transliteration-insensitive normalization (strip accents/matras, casefold),
* stop-word removal (English + common Hindi/Hinglish fillers),
* sorting the remaining content tokens.

So "Who is the dean of academics?", "dean of academics kaun hai", and
"academics ka dean kaun hai" land in one family and can never be split across
train/calibration/test. The split itself is deterministic: families are ordered by a
stable hash of their key, so the same corpus always produces the same split, which is
what a reproducible gate requires.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Sequence

from .triples import Triple

# Function words that carry topic-independent surface variation. Kept small and
# explicit (not a learned list) so the family key is auditable.
_STOPWORDS = frozenset("""
a an the is are was were of for to in on at by and or as be do does did
who what which when where why how whom whose this that these those please tell me
about can could would i you your my our
kaun kya kaise kahan kab kyun hai hain ka ke ki ko se me mein
""".split())


def _canonical_tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s]", " ", text.casefold())
    tokens = [t for t in text.split() if t and t not in _STOPWORDS]
    return sorted(tokens)


def family_key(triple: Triple) -> str:
    """Canonical, language- and template-independent topic key for a triple.

    Falls back to the category + a hash of the answer when a question reduces to no
    content tokens (e.g. a bare "hello"), so empty-token questions do not all collapse
    into a single giant family.
    """
    tokens = _canonical_tokens(triple.question)
    if not tokens:
        digest = hashlib.sha1(triple.answer.encode("utf-8")).hexdigest()[:8]
        return f"{triple.category}:{digest}"
    return triple.category + ":" + " ".join(tokens)


def assign_families(triples: Iterable[Triple]) -> dict[str, list[Triple]]:
    """Group triples by :func:`family_key`, preserving insertion order within a family."""
    families: dict[str, list[Triple]] = {}
    for triple in triples:
        families.setdefault(family_key(triple), []).append(triple)
    return families


@dataclass(frozen=True)
class FamilySplit:
    """A disjoint split of triples by family. ``train``/``cal``/``test`` share no family."""

    train: list[Triple]
    cal: list[Triple]
    test: list[Triple]
    families: dict[str, str]  # family_key -> split name

    def is_disjoint(self) -> bool:
        """True iff no family appears in more than one split (the leakage invariant)."""
        def fams(triples: list[Triple]) -> set[str]:
            return {family_key(t) for t in triples}

        tr, ca, te = fams(self.train), fams(self.cal), fams(self.test)
        return not (tr & ca) and not (tr & te) and not (ca & te)

    def summary(self) -> dict:
        return {
            "families": len(self.families),
            "train_families": sum(v == "train" for v in self.families.values()),
            "cal_families": sum(v == "cal" for v in self.families.values()),
            "test_families": sum(v == "test" for v in self.families.values()),
            "train": len(self.train),
            "cal": len(self.cal),
            "test": len(self.test),
            "disjoint": self.is_disjoint(),
        }


def split_by_family(
    triples: Sequence[Triple],
    *,
    ratios: tuple[float, float, float] = (0.6, 0.15, 0.25),
    seed: str = "demo2-fw09",
) -> FamilySplit:
    """Split whole families into train/cal/test so no family crosses a split boundary.

    ``ratios`` are (train, cal, test) over *families*, not triples — the chapter splits
    by family precisely so a template's clones cannot straddle the boundary. The
    assignment is deterministic: each family is ordered by ``sha1(seed + key)`` and the
    sorted list is partitioned by the cumulative ratios, so the same corpus and seed
    always yield the same split (a reproducible gate requirement).
    """
    if abs(sum(ratios) - 1.0) > 1e-6 or any(r < 0 for r in ratios):
        raise ValueError("ratios must be non-negative and sum to 1.0")

    families = assign_families(triples)
    ordered = sorted(
        families, key=lambda k: hashlib.sha1((seed + "|" + k).encode()).hexdigest()
    )
    n = len(ordered)
    n_train = int(round(n * ratios[0]))
    n_cal = int(round(n * ratios[1]))
    # Guard tiny corpora: ensure test gets the remainder (never negative).
    n_train = min(n_train, n)
    n_cal = min(n_cal, n - n_train)

    assignment: dict[str, str] = {}
    for i, key in enumerate(ordered):
        if i < n_train:
            assignment[key] = "train"
        elif i < n_train + n_cal:
            assignment[key] = "cal"
        else:
            assignment[key] = "test"

    buckets: dict[str, list[Triple]] = {"train": [], "cal": [], "test": []}
    for key, members in families.items():
        buckets[assignment[key]].extend(members)

    return FamilySplit(
        train=buckets["train"],
        cal=buckets["cal"],
        test=buckets["test"],
        families=assignment,
    )
