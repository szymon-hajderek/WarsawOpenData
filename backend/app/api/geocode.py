"""Geocoding proxy to OpenStreetMap Nominatim, limited to Warsaw.

Mirrors the frontend's `searchPlaces` (same query params and result mapping),
so the UI can call the backend instead of Nominatim directly.
"""
import httpx
from fastapi import APIRouter, HTTPException, Query

from ..config import settings
from ..models import Place

router = APIRouter(prefix="/api", tags=["geocode"])

# Bounding box of Warsaw (left, top, right, bottom).
WARSAW_VIEWBOX = "20.85,52.37,21.28,52.10"


@router.get("/geocode", response_model=list[Place])
async def geocode(q: str = Query(..., min_length=1)) -> list[Place]:
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
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Geocoding failed: {exc}") from exc

    places: list[Place] = []
    for item in items:
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
                id=f"osm-{item['place_id']}",
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
    return unique
