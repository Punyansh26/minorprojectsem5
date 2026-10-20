"""Split normalized speech into clauses only at points that never break a value.

Task 07 §3. Streaming TTS synthesizes clause-by-clause. A naive split on commas or
terminators can cut a number ("नब्बे | हजार"), a range ("12 | से 15") or a negation
phrase apart, so the two halves are spoken as separate — and wrong — utterances. The
grounding guarantee requires numbers, currency, dates, ranges and negations to be read
verbatim, so this module computes *protected spans* with the same intent as the
verbalization regexes and forbids any clause break inside one.

The design follows §3 exactly:

  1. The caller normalizes the whole answer once (``verbalization.normalize``) so expansion
     is identical to the batch path — this module never re-expands text.
  2. Protected spans are computed on the *normalized* text: multi-token Devanagari number
     words (``cardinal`` output), explicit range/decimal connectors, and spelled-out
     currency/percent units stay glued to their number.
  3. A break at index ``k`` is legal iff ``k`` is a sentence terminator (``। ! ?``) or a
     comma / semicolon / danda that lies **outside** every protected span.
  4. The first clause is kept short (``FIRST_CLAUSE_CHARS``) to minimize TTS time-to-first-byte;
     later clauses fill up to ``max_chars`` (``settings.TTS_CHUNK_CHARS``) for throughput.

This is a correctness primitive, not a latency one: on non-streaming paths the concatenation
of all clauses equals the input, so batch synthesis is unaffected.
"""
import re

# Characters that end a spoken sentence. A break here is always safe.
_TERMINATORS = "।!?"
# Soft break characters: safe only when they fall outside a protected span.
_SOFT_BREAKS = ",;।"  # danda repeated harmlessly; kept for clarity of intent

# Connectors that verbalization.normalize emits *between* numeric tokens and must never
# be left dangling at a clause edge: Devanagari decimal ("दशमलव") and range ("से") words,
# plus the currency/percent units that trail a spoken number.
_GLUE_WORDS = ("दशमलव", "से")
_TRAILING_UNITS = ("रुपये", "प्रतिशत", "करोड़", "लाख", "हजार", "सौ")
# Leading sign word emitted for negative numbers; must stay attached to the number.
_LEADING_SIGN = "ऋण"

# A run of Devanagari number/connector/unit words forms one protected span. We match a
# maximal sequence of Devanagari words separated by single spaces where at least one word
# is numeric glue — this keeps "नब्बे हजार रुपये" and "बारह से पंद्रह" intact without
# protecting ordinary prose.
_DEVNAGARI_WORD = r"[\u0900-\u097f]+"
_SPAN_PATTERN = re.compile(
    rf"(?:{_DEVNAGARI_WORD})(?:\s+(?:{_DEVNAGARI_WORD}))*"
)


def _is_numeric_run(fragment: str) -> bool:
    """A Devanagari word run counts as protected if it carries a numeric connector/unit/sign."""
    words = fragment.split()
    if len(words) < 2:
        return False
    markers = set(_GLUE_WORDS) | set(_TRAILING_UNITS) | {_LEADING_SIGN}
    return any(word in markers for word in words)


def protected_spans(text: str) -> list[tuple[int, int]]:
    """Return [start, end) ranges inside which a clause break would corrupt a value.

    Spans cover multi-word spoken numbers/ranges/currency so a break never lands between,
    for example, the magnitude and its Indian unit word.
    """
    spans: list[tuple[int, int]] = []
    for match in _SPAN_PATTERN.finditer(text):
        if _is_numeric_run(match.group()):
            spans.append((match.start(), match.end()))
    return spans


def _inside_span(index: int, spans: list[tuple[int, int]]) -> bool:
    """A break at ``index`` is illegal if any span [a, b) has a < index < b."""
    return any(a < index < b for a, b in spans)


def segment(text: str, max_chars: int, first_clause_chars: int = 60) -> list[str]:
    """Split already-normalized ``text`` into clauses at safe boundaries.

    - ``max_chars`` bounds every clause (use ``settings.TTS_CHUNK_CHARS``).
    - ``first_clause_chars`` caps the first clause to minimize TTS TTFB (§2.1).
    - Returns a list whose concatenation (with single spaces re-joined) preserves the
      spoken content; protected numeric spans are never split.
    """
    text = text.strip()
    if not text:
        return []
    spans = protected_spans(text)

    # Candidate break positions: just after a terminator, or after a soft break that is
    # outside every protected span. Index points at the character *after* the break char.
    breaks: list[int] = []
    for i, char in enumerate(text):
        after = i + 1
        if char in _TERMINATORS:
            breaks.append(after)
        elif char in _SOFT_BREAKS and not _inside_span(i, spans):
            breaks.append(after)
    if not breaks or breaks[-1] != len(text):
        breaks.append(len(text))

    # Split into atomic pieces at every legal break, then greedily pack them into clauses.
    pieces: list[str] = []
    start = 0
    for boundary in breaks:
        piece = text[start:boundary].strip()
        if piece:
            pieces.append(piece)
        start = boundary

    clauses: list[str] = []
    for piece in pieces:
        # The first clause uses the short budget; all later clauses fill up to max_chars.
        budget = first_clause_chars if len(clauses) <= 1 else max_chars
        if clauses and len(clauses[-1]) + 1 + len(piece) <= budget:
            clauses[-1] = (clauses[-1] + " " + piece).strip()
        else:
            clauses.append(piece)
    return [clause for clause in clauses if clause]
