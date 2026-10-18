"""Place search for the start / destination fields: well-known places, our own stops and Veturilo stations first,
then OpenStreetMap Nominatim (limited to Warsaw) for addresses and other places.

Two parts with very different speeds:
- local (`source=local`): an in-memory index, a few ms. Matches words in any order, abbreviations ("ds 2 uw",
  "pl. zbawiciela") and works when Nominatim is down (`algorithms/place_search.py`).
- Nominatim (`source=nominatim`): 0.3-2 s over the internet and limited to about 1 request per second. Answers are
  cached for an hour, a call waits for at most 1.5 s, calls are spaced 1 s apart (a request that would wait longer
  is skipped), and after a 429 Nominatim is not called for 30 s.
The frontend asks for both separately and shows local hits at once. `source=all` (default) returns both merged.
"""
import asyncio
import json
import logging
import sys
import time
from functools import lru_cache
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, HTTPException, Query

from config import REPO, TTLCache

from ..config import settings
from ..models import Place

sys.path.insert(0, str(REPO / "algorithms"))
import place_search  # noqa: E402

router = APIRouter(prefix="/api", tags=["geocode"])
log = logging.getLogger(__name__)

# Nominatim results per normalised query (not per position: Nominatim does not use it).
_cache = TTLCache(ttl=3600, maxsize=1024)

# Bounding box of Warsaw (left, top, right, bottom).
WARSAW_VIEWBOX = "20.85,52.37,21.28,52.10"
LANDMARKS = REPO / "data" / "places" / "landmarks.json"

LOCAL_LIMIT = 5
MIN_NOMINATIM_CHARS = 3  # shorter texts are answered locally only
NOMINATIM_TIMEOUT_S = 1.5
NOMINATIM_SPACING_S = 1.0  # Nominatim usage policy: at most 1 request per second
NOMINATIM_MAX_WAIT_S = 1.0  # a request that would wait longer for its turn skips Nominatim
NOMINATIM_COOLDOWN_S = 30.0  # after a 429 (too many requests)

_next_slot = 0.0  # monotonic time of the next allowed Nominatim call
_cooldown_until = 0.0
_clients: dict[int, httpx.AsyncClient] = {}  # one keep-alive client per event loop (saves the TLS handshake)


def _landmarks() -> list[dict]:
    try:
        rows = json.loads(LANDMARKS.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("well-known places unavailable for place search: %s", exc)
        return []
    return [
        {"id": "place-" + "-".join(place_search.words(r["name"])), "name": r["name"], "aliases": r.get("aliases", []),
         "lat": r["lat"], "lon": r["lon"], "kind": r.get("kind") or "Miejsce", "rank": 0}
        for r in rows
    ]


@lru_cache
def _local_index() -> list[dict]:
    """Well-known places, stops (one entry per stop name, at the centre of its posts) and Veturilo stations,
    prepared for matching. Parts whose data is missing are left out."""
    index: list[dict] = _landmarks()
    try:
        from sources import mkuran

        posts = [
            {"id": f"stop-{s['id']}", "name": s["name"], "lat": s["lat"], "lon": s["lon"], "kind": "Przystanek"}
            for s in mkuran.vertices()
        ]
        index += place_search.group_by_name(posts)
    except Exception as exc:  # GTFS not downloaded or unreadable: the search still works without it
        log.warning("stop names unavailable for place search: %s", exc)
    try:
        from sources import nextbike

        index += [
            {"id": f"veturilo-{s['station_id']}", "name": s["name"], "lat": s["lat"], "lon": s["lon"],
             "kind": "Stacja Veturilo"}
            for s in nextbike.stations()
            if s.get("name")
        ]
    except Exception as exc:
        log.warning("Veturilo stations unavailable for place search: %s", exc)
    return [place_search.prepare(p) for p in index]


def _local(q: str, near: tuple[float, float] | None) -> list[Place]:
    found = place_search.search(q, _local_index(), limit=LOCAL_LIMIT, near=near)
    return [
        Place(id=p["id"], label=p["name"], sublabel=p["kind"], position=(p["lat"], p["lon"])) for p in found
    ]


def _client() -> httpx.AsyncClient:
    loop = id(asyncio.get_running_loop())
    if loop not in _clients:
        _clients.clear()  # clients of a finished loop (tests) cannot be reused
        _clients[loop] = httpx.AsyncClient(timeout=NOMINATIM_TIMEOUT_S)
    return _clients[loop]


async def _wait_for_turn() -> bool:
    """Keeps calls 1 s apart. False when Nominatim is cooling down after a 429 or the turn is too far away."""
    global _next_slot
    now = time.monotonic()
    if now < _cooldown_until:
        return False
    slot = max(now, _next_slot)
    if slot - now > NOMINATIM_MAX_WAIT_S:
        return False
    _next_slot = slot + NOMINATIM_SPACING_S  # no await between the check and this line: no race in asyncio
    if slot > now:
        await asyncio.sleep(slot - now)
    return True


def _to_places(items: list[dict]) -> list[Place]:
    places: list[Place] = []
    seen: set[str] = set()
    for item in items:
        if item.get("osm_type") not in ("node", "way", "relation") or not item.get("osm_id"):
            continue
        address = item.get("address") or {}
        street = " ".join(x for x in [address.get("road"), address.get("house_number")] if x)
        label = item.get("name") or street or item["display_name"].split(",")[0]
        area = (
            address.get("suburb")
            or address.get("neighbourhood")
            or address.get("city_district")
            or address.get("city")
            or address.get("town")
        )
        sublabel = ", ".join(x for x in [street if (item.get("name") and street) else None, area] if x)
        # Nominatim often returns the same place several times (node + way + relation).
        key = f"{label}|{sublabel}"
        if key in seen:
            continue
        seen.add(key)
        places.append(
            Place(
                id=f"osm:{item['osm_type']}:{item['osm_id']}",
                label=label,
                sublabel=sublabel or None,
                position=(float(item["lat"]), float(item["lon"])),
            )
        )
    return places


async def _nominatim(q: str) -> list[Place] | None:
    """Nominatim places for the text (cached), or None when Nominatim failed or was skipped."""
    global _cooldown_until
    key = " ".join(q.lower().split())
    cached = _cache.peek(key)
    if cached is not None:
        return cached
    if not await _wait_for_turn():
        log.info("Nominatim skipped (rate limit)")
        return None
    params = {
        "format": "jsonv2",
        "q": q,
        "limit": "6",
        "addressdetails": "1",
        "viewbox": WARSAW_VIEWBOX,
        "bounded": "1",
        "countrycodes": "pl",
        "accept-language": "pl",
    }
    headers = {"User-Agent": settings.nominatim_user_agent}
    try:
        res = await _client().get(settings.nominatim_url, params=params, headers=headers)
        if res.status_code == 429:
            _cooldown_until = time.monotonic() + NOMINATIM_COOLDOWN_S
        res.raise_for_status()
        places = _to_places(res.json())
    except (httpx.HTTPError, ValueError) as exc:  # ValueError: the answer was not JSON
        log.warning("geocoding failed (%s)", type(exc).__name__)
        return None
    _cache.put(key, places)
    return places


def merge(q: str, local: list[Place], remote: list[Place]) -> list[Place]:
    """Local places first, then Nominatim's (a place already listed is not repeated). For a street address
    ("Marszałkowska 1") Nominatim's come first: it is the source for addresses."""
    seen = {place_search.fold(p.label) for p in local}
    extra = [p for p in remote if place_search.fold(p.label) not in seen]
    return extra + local if place_search.looks_like_address(q) else local + extra


@router.get("/geocode", response_model=list[Place])
async def geocode(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    source: Annotated[Literal["all", "local", "nominatim"], Query()] = "all",
) -> list[Place]:
    near = (lat, lon) if lat is not None and lon is not None else None
    local = _local(q, near) if source != "nominatim" else []
    if source == "local" or len(q.strip()) < MIN_NOMINATIM_CHARS:
        return local
    remote = await _nominatim(q)
    if remote is None:
        if local:  # our own places are still a useful answer
            return local
        raise HTTPException(status_code=502, detail="Geocoding service failed")
    return merge(q, local, remote)
