"""FutureWork 11 §5/§9 tests: the acknowledgement-talker fact-leakage guard.

Short, offline tests (no model, no network, no GPU). They verify that:
  * the deterministic guard detects every class of fact token the TTS path can speak;
  * neutral acknowledgement phrases are correctly judged fact-free;
  * the shipped canned-phrase talker (``fillers.FILLERS``) scores a 0% leakage rate (§9);
  * ``fillers`` refuses to hand back a fact-bearing phrase even if the table is tampered with;
  * the §9 leakage-rate metric and its pass criterion behave as specified.
"""
import pytest

import filler_guard
import fillers
import verbalization as vb


# --------------------------------------------------------------------------- fact detection

@pytest.mark.parametrize("phrase", [
    "₹90,000",                       # currency symbol + ASCII digits
    "50%",                           # percent symbol + digits
    "2026-10-21",                    # ISO date (digits)
    "rank 15",                       # bare ASCII number
    "नब्बे हजार रुपये",               # spoken Indian amount (number + unit words)
    "तीन दशमलव पाँच प्रतिशत",          # spoken decimal percent
    "JoSAA",                         # KB entity (English key)
    "जोसा",                          # KB entity (Devanagari rendering)
    "IIIT Naya Raipur",             # multi-word KB entity
    "शुल्क",                         # KB entity 'Fees' in Devanagari
    "१२३",                           # Devanagari digits
    "January",                       # month name (treated as a date fact)
])
def test_detects_fact_tokens(phrase):
    """Every fact-bearing phrase must be flagged (false negatives are forbidden by §9)."""
    assert not filler_guard.is_fact_free(phrase), phrase
    assert filler_guard.find_fact_tokens(phrase), phrase
    with pytest.raises(filler_guard.FactLeakageError):
        filler_guard.assert_fact_free(phrase)


@pytest.mark.parametrize("phrase", [
    "एक पल।",                        # 'one moment' — lone idiomatic 'एक', no magnitude
    "देख रहा हूँ।",                   # 'I am looking'
    "One moment please.",
    "Let me check that for you.",
    "ठीक है।",                        # 'okay'
    "समझ गया।",                       # 'understood'
    "Ek pal.",                       # romanised 'one moment'
    "Dekh raha hoon.",
])
def test_neutral_phrases(phrase):
    """Neutral acknowledgements that carry no grounded *value* must pass.

    A lone small-number word such as 'एक' ('one') in an idiomatic acknowledgement is allowed;
    it only becomes a fact token when it forms a magnitude with an adjacent number/scale word.
    """
    assert filler_guard.is_fact_free(phrase), filler_guard.find_fact_tokens(phrase)
    filler_guard.assert_fact_free(phrase)  # must not raise


def test_lone_number_word_is_allowed_but_magnitude_is_flagged():
    """Design rule: lone 'एक' passes; 'नब्बे हजार' (a real magnitude) is flagged."""
    assert filler_guard.is_fact_free("एक पल।")
    assert filler_guard.find_fact_tokens("नब्बे हजार")          # number + scale word
    assert filler_guard.find_fact_tokens("दो सौ")               # number + scale word
    assert filler_guard.find_fact_tokens("तीन चार")             # adjacent number words


# --------------------------------------------------------------------------- shipped fillers

def test_shipped_fillers_present():
    """Sanity: the canned-phrase talker exposes the expected languages."""
    assert set(fillers.FILLERS) == {"hindi", "english", "hinglish"}
    assert all(fillers.FILLERS.values())


def test_leakage_rate_over_all_fillers_is_zero():
    """Chapter §9 metric: the whole shipped talker must score 0% fact-leakage."""
    all_phrases = [p for phrases in fillers.FILLERS.values() for p in phrases]
    result = filler_guard.leakage_rate(all_phrases)
    assert result["pass"], result["offenders"]
    assert result["rate"] == 0.0
    assert result["leaked"] == 0
    assert result["total"] == len(all_phrases)


def test_filler_text_returns_fact_free_phrase():
    """Every accessor result must survive the guard at use time."""
    for language in fillers.FILLERS:
        for index in range(len(fillers.FILLERS[language]) + 1):  # +1 exercises wraparound
            phrase = fillers.filler_text(language, index)
            assert filler_guard.is_fact_free(phrase), phrase


def test_tampered_filler_is_rejected(monkeypatch):
    """If the table is mutated to leak a fact, the use-time guard must refuse it."""
    monkeypatch.setitem(fillers.FILLERS, "hindi", ["शुल्क ₹90,000 है।"])
    with pytest.raises(filler_guard.FactLeakageError):
        fillers.filler_text("hindi", 0)


def test_import_time_validation_rejects_leaky_table():
    """_validate_fillers must raise if any phrase in the table leaks a fact."""
    original = dict(fillers.FILLERS)
    try:
        fillers.FILLERS["hindi"] = ["रैंक 100 तक।"]
        with pytest.raises(filler_guard.FactLeakageError):
            fillers._validate_fillers()
    finally:
        fillers.FILLERS.clear()
        fillers.FILLERS.update(original)


# --------------------------------------------------------------------------- §9 metric shape

def test_leakage_rate_counts_and_offenders():
    """The metric reports counts, rate, pass flag and per-offender detail."""
    phrases = ["One moment.", "The fee is ₹90,000.", "Let me check.", "rank 15"]
    result = filler_guard.leakage_rate(phrases)
    assert result["total"] == 4
    assert result["leaked"] == 2
    assert result["rate"] == pytest.approx(0.5)
    assert result["pass"] is False
    offender_indices = {o["index"] for o in result["offenders"]}
    assert offender_indices == {1, 3}
    assert all(o["tokens"] for o in result["offenders"])


def test_leakage_rate_empty_is_pass():
    """No utterances is vacuously a pass (rate 0.0), matching the §9 definition."""
    result = filler_guard.leakage_rate([])
    assert result["pass"] is True
    assert result["rate"] == 0.0
    assert result["total"] == 0


def test_fact_vocabulary_is_bound_to_verbalization():
    """The guard's fact vocabulary must track what the TTS path actually speaks."""
    # A scale/unit word and an entity rendering from verbalization must both be detected.
    assert not filler_guard.is_fact_free("हजार")                 # scale word (always a fact)
    sample_entity = next(iter(vb.LEXICON.values()))
    assert not filler_guard.is_fact_free(sample_entity)
    # A real magnitude built from verbalization's cardinal output must be detected.
    assert filler_guard.find_fact_tokens(vb.cardinal(90000))     # 'नब्बे हजार'
