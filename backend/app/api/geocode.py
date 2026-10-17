"""Geocoding proxy to OpenStreetMap Nominatim, limited to Warsaw.

Mirrors the frontend's `searchPlaces` (same query params and result mapping),
so the UI can call the backend instead of Nominatim directly.
"""
import logging

import httpx
from fastapi import APIRouter, HTTPException, Query

from config import TTLCache

from ..config import settings
from ..models import Place

router = APIRouter(prefix="/api", tags=["geocode"])
log = logging.getLogger(__name__)

# Nominatim allows about 1 request per second. Users call us, we call Nominatim, and repeated
# searches (typing, retries) are answered from this cache.
_cache = TTLCache(ttl=600, maxsize=512)

# Bounding box of Warsaw (left, top, right, bottom).
WARSAW_VIEWBOX = "20.85,52.37,21.28,52.10"


@router.get("/geocode", response_model=list[Place])
async def geocode(q: str = Query(..., min_length=1, max_length=200)) -> list[Place]:
    cache_key = " ".join(q.lower().split())
    cached = _cache.peek(cache_key)
    if cached is not None:
        return cached
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
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(settings.nominatim_url, params=params, headers=headers)
            res.raise_for_status()
            items = res.json()
    except (httpx.HTTPError, ValueError) as exc:  # ValueError: the answer was not JSON
        log.warning("geocoding failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Geocoding service failed") from exc

    places: list[Place] = []
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
        sublabel = ", ".join(
            x for x in [street if (item.get("name") and street) else None, area] if x
        )
        places.append(
            Place(
                id=f"osm:{item['osm_type']}:{item['osm_id']}",
                label=label,
                sublabel=sublabel or None,
                position=(float(item["lat"]), float(item["lon"])),
            )
        )

    # Nominatim often returns the same place several times (node + way + relation).
    seen: set[str] = set()
    unique: list[Place] = []
    for place in places:
        key = f"{place.label}|{place.sublabel or ''}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(place)
    _cache.put(cache_key, unique)
    return unique
