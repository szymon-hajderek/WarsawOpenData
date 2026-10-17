"""Search a list of named places while the user is typing.

Pure functions, no I/O. Text is compared without case and without Polish accents, so "lodz" finds "Łódź"
and "marszalk" finds "Marszałkowska". A name matches when the query is, in this order of quality:
the whole name (0), the start of the name (1), the starts of words of the name, in any order (2), or
somewhere inside it (3). Equal matches are ordered by distance from `near` (when given), then by name.
"""
from __future__ import annotations

import math
import unicodedata
from typing import Iterable, Mapping, Sequence

_EXTRA = str.maketrans({"ł": "l", "Ł": "l", "ø": "o", "đ": "d"})


def fold(text: str) -> str:
    """Lower case, accents removed, hyphens and runs of spaces turned into single spaces."""
    text = unicodedata.normalize("NFKD", text.translate(_EXTRA))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().replace("-", " ").split())


def match_score(query: str, name: str) -> int | None:
    """0 exact, 1 name starts with the query, 2 every query word starts a word of the name, 3 contains; None = no match."""
    q, n = fold(query), fold(name)
    if not q or not n:
        return None
    if q == n:
        return 0
    if n.startswith(q):
        return 1
    words = n.split()
    tokens = q.split()
    if all(any(w.startswith(t) for w in words) for t in tokens):
        return 2
    if q in n:
        return 3
    return None


def _metres(a: tuple[float, float], lat: float, lon: float) -> float:
    dy = (lat - a[0]) * 111_320
    dx = (lon - a[1]) * 111_320 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def search(
    query: str,
    places: Iterable[Mapping],
    limit: int = 5,
    near: tuple[float, float] | None = None,
) -> list[Mapping]:
    """The best `limit` places whose `name` matches `query` (each place needs `name`, `lat`, `lon`)."""
    scored = []
    for place in places:
        score = match_score(query, place["name"])
        if score is None:
            continue
        distance = _metres(near, place["lat"], place["lon"]) if near else 0.0
        scored.append((score, round(distance), place["name"], place))
    scored.sort(key=lambda row: row[:3])
    return [row[3] for row in scored[:limit]]


def group_by_name(rows: Sequence[Mapping]) -> list[dict]:
    """One place per distinct (folded) name: the centre of the rows that share it. Rows need `name`, `lat`, `lon`."""
    groups: dict[str, list[Mapping]] = {}
    for row in rows:
        groups.setdefault(fold(row["name"]), []).append(row)
    out = []
    for members in groups.values():
        first = members[0]
        out.append({
            **first,
            "lat": sum(m["lat"] for m in members) / len(members),
            "lon": sum(m["lon"] for m in members) / len(members),
        })
    return out
