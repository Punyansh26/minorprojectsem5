"""
Unit tests for LocalAgreement-N prefix committing (chapter 03 §2.1).

Pure logic — no ASR model, no audio, no server. Run from the stt-service root:

    conda activate minor
    cd code/STT/stt-service
    python -m pytest tests/test_prefix_commit.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.prefix_commit import PrefixCommitter, longest_common_prefix, CommitResult


# --- longest_common_prefix -------------------------------------------------

def test_lcp_basic():
    assert longest_common_prefix(["a", "b", "c"], ["a", "b", "x"]) == ["a", "b"]


def test_lcp_empty_and_disjoint():
    assert longest_common_prefix([], ["a"]) == []
    assert longest_common_prefix(["a"], ["b"]) == []


def test_lcp_full_prefix():
    assert longest_common_prefix(["a", "b"], ["a", "b", "c"]) == ["a", "b"]


# --- LocalAgreement-2 core behaviour --------------------------------------

def test_n2_commits_only_agreed_prefix():
    c = PrefixCommitter(n=2)
    # First hypothesis: nothing is committed yet (needs a second to agree).
    r1 = c.update("what is the")
    assert r1.committed_text == ""
    assert r1.pending_text == "what is the"
    assert r1.changed is False

    # Second hypothesis agrees on "what is the", extends with unstable tail.
    r2 = c.update("what is the fee")
    assert r2.committed_text == "what is the"
    assert r2.newly_committed_text == "what is the"
    assert r2.pending_text == "fee"
    assert r2.changed is True


def test_n2_unstable_tail_not_committed_until_agreed():
    c = PrefixCommitter(n=2)
    c.update("admission for")
    c.update("admission for ST")      # commits "admission for", tail "ST"
    r = c.update("admission for SC")  # tail changed to "SC" -> not committed
    assert r.committed_text == "admission for"
    assert r.changed is False
    # Next time "SC" repeats, it commits.
    r2 = c.update("admission for SC category")
    assert r2.committed_text == "admission for SC"
    assert "category" in r2.pending_text


def test_committed_prefix_is_monotonic():
    c = PrefixCommitter(n=2)
    seq = ["I", "I want", "I want to", "I want to apply", "I want to apply now"]
    prev_committed = ""
    for h in seq:
        r = c.update(h)
        assert r.committed_text.startswith(prev_committed)
        prev_committed = r.committed_text
    # After a stable growing sequence most tokens should have committed.
    assert c.committed_text.startswith("I want to apply")


def test_commit_never_shrinks_on_divergent_redecode():
    c = PrefixCommitter(n=2)
    c.update("the fee is")
    c.update("the fee is high")   # commits "the fee is", tail "high"
    committed_before = c.committed_text
    # A divergent re-decode of the window that disagrees inside committed region.
    r = c.update("fee is high indeed")
    assert c.committed_text.startswith(committed_before)
    assert len(c.committed_tokens) >= len(committed_before.split())


def test_reset_clears_state():
    c = PrefixCommitter(n=2)
    c.update("one two")
    c.update("one two three")
    assert c.committed_text != ""
    c.reset()
    assert c.committed_text == ""
    assert c.committed_tokens == []


# --- latency vs flicker knob (N) ------------------------------------------

def test_n1_commits_immediately():
    c = PrefixCommitter(n=1)
    r = c.update("hello world")
    assert r.committed_text == "hello world"
    assert r.changed is True


def test_n3_needs_three_agreements():
    c = PrefixCommitter(n=3)
    r1 = c.update("a b c")
    r2 = c.update("a b c")
    assert r1.committed_text == ""
    assert r2.committed_text == ""        # only 2 agreements so far
    r3 = c.update("a b c")
    assert r3.committed_text == "a b c"   # third agreement commits


def test_invalid_n_rejected():
    import pytest
    with pytest.raises(ValueError):
        PrefixCommitter(n=0)


# --- edge cases ------------------------------------------------------------

def test_empty_hypothesis_commits_nothing():
    c = PrefixCommitter(n=2)
    r = c.update("")
    assert r == CommitResult(committed_text="", newly_committed_text="",
                             pending_text="", changed=False)


def test_whitespace_is_normalised():
    c = PrefixCommitter(n=2)
    c.update("  the   fee  ")
    r = c.update("the fee is")
    assert r.committed_text == "the fee"
