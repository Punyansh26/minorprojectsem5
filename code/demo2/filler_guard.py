"""Deterministic fact-leakage guard for the acknowledgement talker (FutureWork 11 §5/§9).

Chapter 11's verdict: an end-to-end speech-to-speech model must **never** be the answer
back-end, because speech-native generation bypasses the grounding contract
(`evidence.py::source_quote` + exact `facts.sqlite` values). The only S2S-shaped change that
preserves grounding — and the chapter's "recommended first step" (§6.1) — is a small,
canned-phrase *talker* that fills the first silence ("एक पल…", "let me check…") while the
verified cascade produces the real answer.

That talker is only safe under one invariant (chapter §5, measured by §9):

    **The talker must never speak a fact.** It may acknowledge, backchannel and detect
    interruptions, but it may not utter a number, amount, date, percentage, or a
    knowledge-base entity — anything a user could mistake for the grounded answer.

Demo2 already ships the canned-phrase talker (``fillers.py``, built under Task 07) but it has
no mechanical enforcement of that invariant. This module supplies it as a **deterministic,
offline, zero-VRAM** check so the property is provable rather than assumed:

  * :func:`find_fact_tokens` — list every fact-bearing token in a phrase.
  * :func:`is_fact_free` / :func:`assert_fact_free` — the boolean / raising guard.
  * :func:`leakage_rate` — the chapter §9 metric (fraction of utterances that leak a fact).

The guard's definition of "fact" is bound to the **same vocabulary the TTS path actually
speaks** (``verbalization.py``): the Devanagari cardinal number words, the Indian unit words
(करोड़/लाख/हजार/सौ) and spoken currency/percent units, plus the entity ``LEXICON`` (IIIT,
JEE, JoSAA, fee/date terms, …). It also catches raw ASCII/Devanagari digits, ₹ and %, and
Latin digit groups — i.e. anything that would survive into speech as a concrete value. This
is intentionally conservative: a false positive merely rejects a candidate filler phrase; a
false negative would let the talker speak a fact, which §9 forbids outright (pass = 0%).

Design notes:
  * Pure standard-library + ``verbalization`` import. No model, no network, no GPU.
  * Order-free and language-agnostic: it scans one utterance of talker speech, not an answer.
  * It never inspects or constrains the grounded answer path; it only validates filler text.
"""
from __future__ import annotations

import re
import unicodedata

import verbalization as vb

# --------------------------------------------------------------------------- fact vocabulary

# Spoken Indian scale/unit words and the spoken currency/percent units a number expands into
# (verbalization.cardinal + normalize). Any ONE of these in talker speech means a concrete
# magnitude/amount was read — a hundred, a lakh, rupees, a percent, a decimal, a negative.
# These are always treated as fact tokens on their own.
_SCALE_UNIT_WORDS = ("करोड़", "लाख", "हजार", "सौ", "रुपये", "प्रतिशत", "दशमलव", "ऋण")

# The Devanagari cardinal words शून्य..निन्यानवे that verbalization emits for 0..99. A *lone*
# small-number word (e.g. "एक" in the idiomatic acknowledgement "एक पल" = "one moment") is NOT
# a grounded knowledge-base value, so a single one in isolation is allowed. A number word
# becomes a fact token only when it forms a real magnitude: adjacent to another number word
# or to a scale/unit word (e.g. "नब्बे हजार", "तीन दशमलव पाँच"). Every actual KB value a filler
# must never speak (fees, cutoffs, ranks, dates) is a digit string or such a multi-word
# magnitude, so this stays strict on real facts while permitting idiomatic acknowledgements.
_NUMBER_WORDS = tuple(vb._SMALL)

# Months are dates; speaking one implies a grounded date, so they are always fact tokens.
_MONTH_WORDS = tuple(vb._MONTHS)

# Knowledge-base entities the verbalizer knows how to pronounce. Speaking any of these from
# the talker (e.g. "JoSAA", "आईआईटी", "शुल्क") risks implying a grounded fact. We take both
# the English keys and their Devanagari renderings so the guard works pre- and post-verbalize.
_ENTITY_TERMS = tuple(vb.LEXICON.keys()) + tuple(vb.LEXICON.values())


def _build_term_pattern(terms: tuple[str, ...]) -> re.Pattern:
    """Longest-first alternation with script-aware boundaries (Latin vs Devanagari)."""
    ordered = sorted({t for t in terms if t.strip()}, key=len, reverse=True)
    alts = []
    for term in ordered:
        escaped = re.escape(term)
        if re.search(r"[A-Za-z]", term):
            # Latin (possibly mixed) term: guard with non-letter boundaries, ignore case.
            alts.append(rf"(?<![A-Za-z]){escaped}(?![A-Za-z])")
        else:
            # Pure Devanagari token: guard with Unicode-aware word boundaries.
            alts.append(rf"(?<![\u0900-\u097f]){escaped}(?![\u0900-\u097f])")
    return re.compile("|".join(alts), flags=re.IGNORECASE)


_NUMBER_WORD_PATTERN = _build_term_pattern(_NUMBER_WORDS)
_SCALE_UNIT_PATTERN = _build_term_pattern(_SCALE_UNIT_WORDS)
_MONTH_PATTERN = _build_term_pattern(_MONTH_WORDS)
_ENTITY_PATTERN = _build_term_pattern(_ENTITY_TERMS)

# Currency and percent symbols: raw value facts independent of language.
_SYMBOL_FACTS = ("₹", "%")


def _has_decimal_digit(text: str) -> bool:
    """True if any character is a decimal digit in ANY script (ASCII, Devanagari, …)."""
    return any(ch.isdecimal() for ch in text)


def _magnitude_number_words(text: str) -> list[str]:
    """Return small-number words (0..99) that participate in a real spoken magnitude.

    A lone small-number word (e.g. idiomatic "एक" in "एक पल") is allowed. A number word is a
    fact token only when it is adjacent — across whitespace — to another number word or to a
    scale/unit word, i.e. it forms an actual value like "नब्बे हजार" or "तीन दशमलव पाँच".
    """
    number_spans = [m.span() for m in _NUMBER_WORD_PATTERN.finditer(text)]
    if not number_spans:
        return []
    scale_spans = [m.span() for m in _SCALE_UNIT_PATTERN.finditer(text)]
    value_spans = sorted(number_spans + scale_spans)

    def _only_space_between(a_end: int, b_start: int) -> bool:
        gap = text[a_end:b_start]
        return gap != "" and gap.strip() == ""

    # A number-word span is a magnitude if an adjacent value span touches it with only
    # whitespace in between (on either side).
    hits: list[str] = []
    for n_start, n_end in number_spans:
        adjacent = False
        for v_start, v_end in value_spans:
            if (v_start, v_end) == (n_start, n_end):
                continue
            if _only_space_between(n_end, v_start) or _only_space_between(v_end, n_start):
                adjacent = True
                break
        if adjacent:
            hits.append(text[n_start:n_end])
    return hits


def find_fact_tokens(phrase: str) -> list[str]:
    """Return every fact-bearing token found in ``phrase`` (empty list == fact-free).

    A *fact token* is anything a listener could take as a concrete grounded value:
      * a decimal digit in any script, or the ``₹`` / ``%`` symbol;
      * a spoken scale/unit word (करोड़/लाख/हजार/सौ, रुपये, प्रतिशत, दशमलव, ऋण) — always;
      * a month name (an implied date) — always;
      * a spoken small-number word (शून्य..निन्यानवे) **only** when it forms a real magnitude
        with an adjacent number or scale word (e.g. "नब्बे हजार"); a lone idiomatic "एक" is
        allowed so neutral acknowledgements such as "एक पल" ("one moment") stay usable;
      * a knowledge-base entity term from ``verbalization.LEXICON`` (English key or Devanagari
        rendering, e.g. ``IIIT`` / ``आईआईटी``, ``JoSAA`` / ``जोसा``, ``Fees`` / ``शुल्क``).

    The scan is deterministic and offline. Duplicate hits are collapsed but order of first
    appearance is preserved, so callers can report *what* leaked, not just that it did.
    """
    text = unicodedata.normalize("NFC", phrase)
    found: list[str] = []

    def _add(token: str) -> None:
        if token and token not in found:
            found.append(token)

    # 1. Decimal digits in any script.
    for ch in text:
        if ch.isdecimal():
            _add(ch)
    # 2. Currency / percent symbols.
    for symbol in _SYMBOL_FACTS:
        if symbol in text:
            _add(symbol)
    # 3. Scale / unit words (always a magnitude).
    for match in _SCALE_UNIT_PATTERN.finditer(text):
        _add(match.group())
    # 4. Month names (an implied date).
    for match in _MONTH_PATTERN.finditer(text):
        _add(match.group())
    # 5. Small-number words only when they form a real magnitude.
    for token in _magnitude_number_words(text):
        _add(token)
    # 6. Knowledge-base entity terms.
    for match in _ENTITY_PATTERN.finditer(text):
        _add(match.group())
    return found


def is_fact_free(phrase: str) -> bool:
    """True iff ``phrase`` contains no fact token — i.e. it is safe for the talker to speak."""
    return not find_fact_tokens(phrase)


class FactLeakageError(ValueError):
    """Raised when a phrase meant for the fact-free talker contains a grounded value."""


def assert_fact_free(phrase: str, *, context: str = "filler") -> None:
    """Raise :class:`FactLeakageError` if ``phrase`` would leak a fact when spoken.

    Used as a definition-time and use-time guard on talker/filler phrases so the chapter §5
    invariant is enforced mechanically rather than trusted. ``context`` is woven into the
    message to point at the offending source (e.g. the language/index of a filler).
    """
    tokens = find_fact_tokens(phrase)
    if tokens:
        preview = ", ".join(repr(t) for t in tokens[:8])
        raise FactLeakageError(
            f"Talker {context} phrase would speak a knowledge-base fact "
            f"({len(tokens)} token(s): {preview}). The acknowledgement talker must never "
            f"speak a number, amount, date, percentage or KB entity (FutureWork 11 §5). "
            f"Offending phrase: {phrase!r}")


def leakage_rate(phrases) -> dict:
    """Compute the chapter §9 fact-leakage metric over an iterable of talker utterances.

    Returns a summary dict::

        {
          "total": <int>,                # utterances inspected
          "leaked": <int>,               # utterances with >=1 fact token
          "rate": <float>,               # leaked / total (0.0 when total == 0)
          "pass": <bool>,                # True iff rate == 0.0 (the §9 pass criterion)
          "offenders": [                 # per-leaking-utterance detail, for audit
            {"index": <int>, "phrase": <str>, "tokens": [<str>, ...]},
            ...
          ],
        }

    The pass criterion is **0%**: any single leak fails (chapter §9, "any leak fails").
    """
    phrases = list(phrases)
    offenders = []
    for index, phrase in enumerate(phrases):
        tokens = find_fact_tokens(phrase if isinstance(phrase, str) else str(phrase))
        if tokens:
            offenders.append({"index": index, "phrase": phrase, "tokens": tokens})
    total = len(phrases)
    leaked = len(offenders)
    rate = (leaked / total) if total else 0.0
    return {"total": total, "leaked": leaked, "rate": rate,
            "pass": leaked == 0, "offenders": offenders}
