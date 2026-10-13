"""Find configured canary strings in an outbound payload (FR-23, FR-24)."""

from __future__ import annotations

import re


def find_canaries(text: str, canaries: list[str]) -> list[dict]:
    """Return non-overlapping hits as {"text", "start", "end"}, sorted by position.

    Matching is case-insensitive. Where hits overlap, the earliest wins, then the longest.
    """
    terms = sorted({c for c in canaries if c.strip()}, key=len, reverse=True)
    if not terms:
        return []
    pattern = re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE)
    return [{"text": m.group(0), "start": m.start(), "end": m.end()} for m in pattern.finditer(text)]
