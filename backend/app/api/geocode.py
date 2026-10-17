"""Place search for the start / destination fields: our own stops and Veturilo stations first, then
OpenStreetMap Nominatim (limited to Warsaw) for addresses and other places.

The local part answers from memory from 2 characters on and matches the start of words ("marszalk"),
which Nominatim does not. It also keeps working when Nominatim is down.
"""
import asyncio
import logging
import sys
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Query

from config import REPO, TTLCache

from ..config import settings
from ..geocode_access import building_position
from ..models import Place

sys.path.insert(0, str(REPO / "algorithms"))
import place_search  # noqa: E402

router = APIRouter(prefix="/api", tags=["geocode"])
log = logging.getLogger(__name__)

# Nominatim allows about 1 request per second. Users call us, we call Nominatim, and repeated
# searches (typing, retries) are answered from this cache.
_cache = TTLCache(ttl=600, maxsize=512)

# Bounding box of Warsaw (left, top, right, bottom).
WARSAW_VIEWBOX = "20.85,52.37,21.28,52.10"

LOCAL_LIMIT = 4
MIN_NOMINATIM_CHARS = 3  # Nominatim is slow and rate limited; shorter texts are answered locally only


@lru_cache
def _local_index() -> list[dict]:
    """Stops (one entry per stop name, at the centre of its posts) and Veturilo stations. Empty when the data is missing."""
    index: list[dict] = []
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
    return index


def _local(q: str, near: tuple[float, float] | None) -> list[Place]:
    found = place_search.search(q, _local_index(), limit=LOCAL_LIMIT, near=near)
    return [
        Place(id=p["id"], label=p["name"], sublabel=p["kind"], position=(p["lat"], p["lon"])) for p in found
    ]


@router.get("/geocode", response_model=list[Place])
async def geocode(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
) -> list[Place]:
    near = (lat, lon) if lat is not None and lon is not None else None
    cache_key = " ".join(q.lower().split())
    if near:  # local ties are ordered by distance, so the answer depends on roughly where the user is
        cache_key += f"|{round(near[0], 2)},{round(near[1], 2)}"
    cached = _cache.peek(cache_key)
    if cached is not None:
        return cached
    local = _local(q, near)
    if len(q.strip()) < MIN_NOMINATIM_CHARS:
        _cache.put(cache_key, local)
        return local
    params = {
        "format": "jsonv2",
        "q": q,
        "limit": "6",
        "addressdetails": "1",
        "extratags": "1",  # building metadata is also needed for attractions such as the Palace of Culture
        "viewbox": WARSAW_VIEWBOX,
        "bounded": "1",
        "countrycodes": "pl",
        "accept-language": "pl",
    }
    headers = {"User-Agent": settings.nominatim_user_agent}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(settings.nominatim_url, params=params, headers=headers)
            res.raise_for_status()
            items = [item for item in res.json()
                     if item.get("osm_type") in ("node", "way", "relation") and item.get("osm_id")]
            positions = await asyncio.gather(*(building_position(client, item, headers) for item in items))
    except (httpx.HTTPError, ValueError) as exc:  # ValueError: the answer was not JSON
        log.warning("geocoding failed (%s)", type(exc).__name__)
        if local:  # our own stops and stations are still a useful answer
            return local
        raise HTTPException(status_code=502, detail="Geocoding service failed") from exc

    places: list[Place] = []
    for item, position in zip(items, positions):
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
        sublabel = ", ".join(
            x for x in [street if (item.get("name") and street) else None, area] if x
        )
        places.append(
            Place(
                id=f"osm:{item['osm_type']}:{item['osm_id']}",
                label=label,
                sublabel=sublabel or None,
                position=position,
            )
        )

    # Nominatim often returns the same place several times (node + way + relation); a stop we already
    # listed is not repeated either.
    seen: set[str] = {place_search.fold(p.label) for p in local}
    unique: list[Place] = list(local)
    for place in places:
        key = f"{place.label}|{place.sublabel or ''}"
        if key in seen or place_search.fold(place.label) in seen:
            continue
        seen.add(key)
        unique.append(place)
    _cache.put(cache_key, unique)
    return unique
