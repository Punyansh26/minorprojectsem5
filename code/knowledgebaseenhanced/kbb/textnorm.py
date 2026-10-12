"""Text normalisation shared by verification, BM25, chunking and evaluation.

Normalisation is used for *comparison and search only*.  Evidence text is never rewritten
with these functions (only whitespace-cleaned with ``clean``).
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
# Normalise look-alike punctuation that OCR engines emit inconsistently.
_PUNCT = str.maketrans({"\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2018": "'", "\u2019": "'",
                        "\u201c": '"', "\u201d": '"', "\u00a0": " ", "\u2009": " ", "\u202f": " ",
                        "\uff0c": ",", "\u066b": ".", "\u2024": "."})

WORD_RE = re.compile(r"[a-z0-9\u00c0-\u024f]+|[\u0900-\u0963\u0966-\u097f\u200c\u200d]+")
DEVANAGARI_RE = re.compile(r"[\u0900-\u097f]")
LATIN_RE = re.compile(r"[A-Za-z]")

# Numbers: dates first (so 15/07/2026 stays one token), then grouped numbers (Indian
# 1,25,000 and international 125,000), then plain decimals.
DATE_RE = re.compile(r"(?<![\d])(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})(?![\d])")
NUM_RE = re.compile(r"(?<![\d.])\d{1,3}(?:[,\s]\d{2,3})+(?:\.\d+)?(?![\d])|(?<![\d])\d+(?:\.\d+)?(?![\d])")

EN_STOP = set("""a an the and or of to in on for at by with from as is are was were be been it its this
that these those which who whom what when where how than then there here do does did not no can
could will would shall should may might must has have had i you he she we they them our your their
his her about into over under also any all per via etc""".split())
HI_STOP = set("""का के की को से में है हैं था थे थी और या पर भी तो ही यह वह ये वे इस उस एक लिए
द्वारा तक जो कि ने हो होता होती होते गया गई गए रहा रही रहे""".split())
STOPWORDS = EN_STOP | HI_STOP


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def clean(text: str) -> str:
    """Whitespace-only cleanup (safe for evidence): collapse runs, drop blank lines."""
    lines = (re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in nfc(text or "").splitlines())
    return "\n".join(ln for ln in lines if ln)


def norm_for_compare(text: str) -> str:
    """Aggressive normalisation for cross-read comparison and fuzzy key matching."""
    text = nfc(text or "").translate(DEVANAGARI_DIGITS).translate(_PUNCT).casefold()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .:;|-_*")


def words(text: str, *, drop_stop: bool = False) -> list[str]:
    text = nfc(text or "").translate(DEVANAGARI_DIGITS).translate(_PUNCT).casefold()
    toks = WORD_RE.findall(text)
    if drop_stop:
        toks = [t for t in toks if t not in STOPWORDS and len(t) > 1]
    return toks


def number_tokens(text: str) -> list[str]:
    """Canonical number tokens: dates → 'd/m/yyyy', grouped numbers → digits only.

    ₹ / Rs. / INR markers are ignored (both reads print the same digits); the digits and
    their order inside a keyed cell are what verification protects.
    """
    text = nfc(text or "").translate(DEVANAGARI_DIGITS).translate(_PUNCT)
    out: list[str] = []

    def date_sub(m: re.Match) -> str:
        d, mo, y = (int(g) for g in m.groups())
        if len(m.group(3)) == 2:
            y += 2000 if y < 70 else 1900
        out.append(f"{d}/{mo}/{y}")
        return " "

    text = DATE_RE.sub(date_sub, text)
    for m in NUM_RE.finditer(text):
        tok = re.sub(r"[,\s]", "", m.group(0))
        if "." in tok:
            tok = tok.rstrip("0").rstrip(".") if re.fullmatch(r"\d+\.\d+", tok) else tok
        tok = tok.lstrip("0") or "0"
        out.append(tok)
    return out


def number_multiset(text: str) -> Counter:
    return Counter(number_tokens(text))


def has_number(text: str) -> bool:
    return bool(NUM_RE.search((text or "").translate(DEVANAGARI_DIGITS)))


def is_numeric_cell(text: str) -> bool:
    """True if the cell's meaning is carried by digits (amount, rank, date, %)."""
    t = norm_for_compare(text)
    if not t:
        return False
    digits = sum(ch.isdigit() for ch in t)
    letters = sum(ch.isalpha() for ch in t)
    return digits > 0 and digits >= letters


def devanagari_share(text: str) -> float:
    dev = len(DEVANAGARI_RE.findall(text or ""))
    lat = len(LATIN_RE.findall(text or ""))
    return dev / (dev + lat) if dev + lat else 0.0


def language_of(text: str) -> str:
    share = devanagari_share(text)
    return "hi" if share > 0.7 else "mixed" if share > 0.15 else "en"


_SENT_RE = re.compile(r"(?<=[.!?।॥])\s+(?=[\"'(\[]?[A-Z0-9\u0900-\u097f])")


def sentences(text: str) -> list[str]:
    parts: list[str] = []
    for para in text.split("\n"):
        para = para.strip()
        if para:
            parts.extend(s for s in _SENT_RE.split(para) if s.strip())
    return parts


def sha256(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def short_hash(*parts: object, n: int = 16) -> str:
    return sha256("\x1f".join(str(p) for p in parts))[:n]


def slug(text: str, max_len: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text[:max_len].rstrip("-")) or "doc"


def contains_keyword(text: str, keywords: list[str]) -> bool:
    t = norm_for_compare(text)
    return any(re.search(r"(?<!\w)" + re.escape(k.casefold()) + r"(?!\w)", t) for k in keywords)


def content_overlap(claim: str, source: str) -> float:
    """Share of the claim's content words found in the source (support proxy)."""
    c = set(words(claim, drop_stop=True))
    if not c:
        return 0.0
    s = set(words(source, drop_stop=True))
    return len(c & s) / len(c)
