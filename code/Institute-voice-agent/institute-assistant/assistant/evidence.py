"""Validate quotations and recover omitted context only from verified structured rows."""


def source_quote(quote: str, source: dict) -> str | None:
    """Expand ordered literal cutoff lines into their exact contiguous source span.

    Models sometimes omit an intervening rank-basis line while quoting a structured
    record. Restore that source context without changing the answer, accepting altered
    values, or performing fuzzy matching. Unstructured/legacy sources stay strict.
    """
    normalize = lambda text: " ".join(text.casefold().split())
    text = source["text"]
    normalized = normalize(quote)
    if normalized and normalized in normalize(text):
        return quote
    if not source.get("verified") or source.get("kind") != "cutoff":
        return None
    canonical, separator, _ = text.partition("\nSource row:")
    if not separator or not canonical.startswith("IIIT Naya Raipur published opening and closing ranks\n"):
        return None
    lines = canonical.splitlines(keepends=True)
    requested = [normalize(line) for line in quote.splitlines() if line.strip()]
    if len(requested) < 2:
        return None
    positions = []
    for line in requested:
        matches = [i for i, candidate in enumerate(lines) if normalize(candidate) == line]
        if len(matches) != 1 or (positions and matches[0] <= positions[-1]):
            return None
        positions.append(matches[0])
    return "".join(lines[positions[0]:positions[-1] + 1]).rstrip("\r\n")
