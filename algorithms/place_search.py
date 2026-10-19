"""Search a list of named places while the user is typing.

Pure functions, no I/O. The TypeScript twin is `frontend/src/utils/placeSearch.ts` (keep both in sync).

Text is compared without case and without Polish accents ("lodz" finds "Łódź"), split into words of letters and
words of digits ("DS2" = "ds 2", "Os.Ługi" = "os lugi"). Common Polish abbreviations match their full form both
ways ("pl" = "plac", "ds" = "dom studenta", "uw" = "uniwersytet warszawski"), and "nr", "ul", "ulica" in the query
are ignored. A number only matches the same number ("2" finds "nr 2" but not "21"); other query words match the
start of a word of the name.

Quality of a match (lower is better), for the name and for each alias of a place:
0 the whole name, 1 the start of the name (or the whole name with abbreviations written out), 2 every query word is a whole word of the name (any order),
3 every query word starts a word of the name (any order), 4 the query is somewhere inside the name.
Equal matches are ordered by `rank` (well-known places 0 before stops 1), then by distance from `near`, then by name.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Iterable, Mapping, Sequence

_EXTRA = str.maketrans({"ł": "l", "Ł": "l", "ø": "o", "đ": "d"})

# Short form -> its full forms (folded words). The first full form is the canonical one.
ABBREVIATIONS: dict[str, list[list[str]]] = {
    "ds": [["dom", "studenta"], ["dom", "studencki"]],
    "pl": [["plac"]],
    "al": [["aleja"], ["aleje"], ["alei"]],
    "dw": [["dworzec"]],
    "os": [["osiedle"]],
    "uw": [["uniwersytet", "warszawski"], ["uniwersytetu", "warszawskiego"]],
    "pw": [["politechnika", "warszawska"], ["politechniki", "warszawskiej"]],
}
# Query words that carry no meaning for a place name ("ul. Marszałkowska", "Dom Studenta nr 2").
STOPWORDS = {"nr", "ul", "ulica"}

_WORD = re.compile(r"[a-z]+|\d+")
# "Marszałkowska 1", "Nowy Świat 15a", "Grójecka 17/19": some letters, then a house number at the end.
_ADDRESS = re.compile(r"^.*[a-z]{2}.*[a-z.]\s+\d+[a-z]?(/\d+[a-z]?)?$")


def fold(text: str) -> str:
    """Lower case, accents removed, hyphens and runs of spaces turned into single spaces."""
    text = unicodedata.normalize("NFKD", text.translate(_EXTRA))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().replace("-", " ").split())


def words(text: str) -> list[str]:
    """Folded words of letters and of digits: "DS2 UW" -> ["ds", "2", "uw"]."""
    return _WORD.findall(fold(text))


def _canonical(ws: Sequence[str]) -> list[str]:
    out: list[str] = []
    for w in ws:
        out += ABBREVIATIONS[w][0] if w in ABBREVIATIONS else [w]
    return out


def _expanded(ws: Sequence[str]) -> frozenset[str]:
    """The words of a name plus the other forms of its abbreviations ("pl" adds "plac", "dom studenta" adds "ds")."""
    out = set(ws)
    for short, forms in ABBREVIATIONS.items():
        if short in out:
            for form in forms:
                out.update(form)
        for form in forms:
            n = len(form)
            if any(list(ws[i:i + n]) == form for i in range(len(ws) - n + 1)):
                out.add(short)
    return frozenset(out)


def _prepare_text(text: str) -> tuple[str, list[str], list[str], frozenset[str]]:
    ws = words(text)
    return fold(text), ws, _canonical(ws), _expanded(ws)


def prepare(place: Mapping) -> dict:
    """A copy of the place with its match data computed once (`search` is then a few ms for thousands of places)."""
    texts = [place["name"], *place.get("aliases", ())]
    return {**place, "_match": [_prepare_text(t) for t in texts]}


def _query(query: str) -> tuple[str, list[str], list[str]] | None:
    ws = words(query)
    kept = [w for w in ws if w not in STOPWORDS] or ws
    if not kept:
        return None
    return fold(query), kept, _canonical(kept)


def _token_hits(token: str, word: str) -> bool:
    return word == token if token.isdigit() else word.startswith(token)


def _score(q, prepared) -> int | None:
    folded_q, tokens, canon_q = q
    folded_n, ws, canon_n, expanded = prepared
    if not canon_n:
        return None
    if tokens == ws:
        return 0
    if canon_q == canon_n:
        return 1
    if len(canon_q) <= len(canon_n) and canon_q[:-1] == canon_n[:len(canon_q) - 1] and _token_hits(
        canon_q[-1], canon_n[len(canon_q) - 1]
    ):
        return 1
    if all(t in expanded for t in tokens):
        return 2
    if all(any(_token_hits(t, w) for w in expanded) for t in tokens):
        return 3
    if folded_q in folded_n and not any(t.isdigit() for t in tokens):  # "2" must not be found inside "21"
        return 4
    return None


def _best(q, place: Mapping) -> int | None:
    match = place.get("_match") or prepare(place)["_match"]
    scores = [s for s in (_score(q, m) for m in match) if s is not None]
    return min(scores) if scores else None


def match_score(query: str, name: str, aliases: Sequence[str] = ()) -> int | None:
    """0..4 (see the module doc) for the best of the name and its aliases; None = no match."""
    q = _query(query)
    if q is None or not fold(name):
        return None
    return _best(q, {"name": name, "aliases": aliases})


def looks_like_address(query: str) -> bool:
    """A street and a house number ("Marszałkowska 1"): Nominatim, not our stop list, is the source for it."""
    ws = words(query)
    return bool(_ADDRESS.match(fold(query))) and not STOPWORDS.intersection(ws) and "ds" not in ws


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
    """The best `limit` places whose `name` (or one of its `aliases`) matches `query`.

    Each place needs `name`, `lat`, `lon`; optional `aliases` and `rank`. Pass places from `prepare` for speed.
    """
    q = _query(query)
    if q is None:
        return []
    scored = []
    for place in places:
        score = _best(q, place)
        if score is None:
            continue
        distance = _metres(near, place["lat"], place["lon"]) if near else 0.0
        scored.append((score, place.get("rank", 1), round(distance), place["name"], place))
    scored.sort(key=lambda row: row[:4])
    return [row[4] for row in scored[:limit]]


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
