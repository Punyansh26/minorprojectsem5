"""
LocalAgreement-n prefix committing for streaming ASR (FutureWork chapter 03 §2.1).

Whisper is an offline model: its hypothesis for the newest audio flickers until
more context arrives. The existing partial loop in ``session.py`` re-decodes the
last ``PARTIAL_WINDOW_MS`` of audio every ``PARTIAL_INTERVAL_MS`` and emits the
whole window each time, so earlier words can be *rewritten* by a later partial
(a "windowed re-decode", not a prefix-committing stream — see chapter 03 §2.3).

LocalAgreement-n fixes that WITHOUT a new model or dependency: only commit
(freeze and trust) the longest common prefix that has agreed across the last
``n`` consecutive hypotheses. With ``n = 2`` that is simply ``LCP(H_t, H_{t-1})``
minus what was already committed. A correct token therefore waits at most
``(n - 1)`` extra updates before it is trusted (commit delay ≈ ``(n-1)·Δ_update``),
in exchange for a flicker-free, append-only committed prefix that downstream
stages (preemptive routing/retrieval, chapter 03 §4) can safely act on.

This module is **pure Python, no third-party imports**, so its logic is unit
testable with plain string lists and never needs a model loaded. Tokenisation is
deliberately whitespace-based: Whisper emits space-delimited words for the
languages used here, and operating on whole words keeps the committed text a
clean prefix of the rendered transcript. The session passes the raw partial
string; this class owns the "what is safe to freeze" decision only.

Reference: Whisper-Streaming's self-adaptive-latency LocalAgreement policy
[R311, Reported]; SimulStreaming calls LocalAgreement "the second best-performing
policy, but much easier to implement" [R304, fetched].
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _tokenize(text: str) -> list[str]:
    """Whitespace word tokens. Empty/space-only input yields an empty list."""
    return text.split()


def longest_common_prefix(a: list[str], b: list[str]) -> list[str]:
    """Longest common prefix of two token lists (token-level, order-preserving)."""
    out: list[str] = []
    for x, y in zip(a, b):
        if x != y:
            break
        out.append(x)
    return out


@dataclass
class CommitResult:
    """Outcome of feeding one partial hypothesis to the committer.

    Attributes
    ----------
    committed_text:
        The full stable prefix committed SO FAR (monotonic, append-only across a
        single utterance). Safe to show as the confirmed caption and to act on.
    newly_committed_text:
        Only the tokens committed by *this* update (empty if nothing new froze).
        Useful for incremental downstream triggers.
    pending_text:
        The still-revisable tail of the latest hypothesis (everything after the
        committed prefix). For UI this is the "faint"/unconfirmed part.
    changed:
        True iff this update committed at least one new token.
    """

    committed_text: str
    newly_committed_text: str
    pending_text: str
    changed: bool


@dataclass
class PrefixCommitter:
    """Stateful LocalAgreement-n committer for one utterance.

    Call :meth:`update` with each new *full* partial hypothesis (the whole
    windowed partial string that the ASR produced). It returns a
    :class:`CommitResult`. Call :meth:`reset` between utterances (the session
    does this on finalize).

    With ``n = 2`` (the default and the chapter's recommended T0 setting), a
    token is committed once it has appeared, in the same position relative to the
    already-committed prefix, in two consecutive hypotheses.
    """

    n: int = 2
    _committed: list[str] = field(default_factory=list)
    # The last (n-1) hypotheses' *uncommitted tails*, oldest first.
    _recent_tails: list[list[str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.n < 1:
            raise ValueError("LocalAgreement-n requires n >= 1")

    @property
    def committed_tokens(self) -> list[str]:
        return list(self._committed)

    @property
    def committed_text(self) -> str:
        return " ".join(self._committed)

    def reset(self) -> None:
        """Clear all state for a fresh utterance."""
        self._committed.clear()
        self._recent_tails.clear()

    def update(self, hypothesis: str) -> CommitResult:
        """Feed one new full partial hypothesis; return what is now committed.

        The hypothesis is expected to already *start with* the committed prefix
        (the ASR re-decodes a growing/overlapping window, so earlier words
        normally reappear). If a hypothesis diverges from the committed prefix —
        e.g. the window slid past committed audio and the model now disagrees —
        we keep the existing committed prefix (never un-commit) and only consider
        the portion of the new hypothesis that lies *after* that prefix.
        """
        tokens = _tokenize(hypothesis)

        # The revisable tail is everything in the new hypothesis beyond the
        # prefix we already trust. We align on the committed prefix length: if
        # the new hypothesis still agrees with the committed prefix, drop exactly
        # that many tokens; otherwise fall back to the common-prefix length so a
        # divergent re-decode cannot shrink what we already committed.
        agree = len(longest_common_prefix(tokens, self._committed))
        if agree == len(self._committed):
            tail = tokens[len(self._committed):]
        else:
            # Hypothesis diverged inside the committed region: only look past the
            # agreed portion, and never remove already-committed tokens.
            tail = tokens[agree:]

        newly: list[str] = []
        if self.n == 1:
            # n=1 trusts every new tail token immediately (lowest latency,
            # highest correction risk) — included for completeness/testing.
            newly = tail
        else:
            # Need (n-1) prior tails to agree with this one. Commit the longest
            # common prefix across the last (n-1) tails AND the current tail.
            history = self._recent_tails[-(self.n - 1):]
            if len(history) >= (self.n - 1):
                agreed = tail
                for prev in history:
                    agreed = longest_common_prefix(agreed, prev)
                newly = agreed

        if newly:
            self._committed.extend(newly)

        # Record this hypothesis's tail (relative to the NEW committed prefix) for
        # the next round's agreement check.
        remaining_tail = tail[len(newly):]
        self._recent_tails.append(remaining_tail)
        # Keep only what the next agreement window needs.
        if self.n > 1:
            self._recent_tails = self._recent_tails[-(self.n - 1):]
        else:
            self._recent_tails.clear()

        return CommitResult(
            committed_text=" ".join(self._committed),
            newly_committed_text=" ".join(newly),
            pending_text=" ".join(remaining_tail),
            changed=bool(newly),
        )
