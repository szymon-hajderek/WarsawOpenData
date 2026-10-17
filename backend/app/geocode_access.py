"""Resolve building search results to mapped public entrances, rather than points inside walls."""
import logging
import math

import httpx

from config import TTLCache

log = logging.getLogger(__name__)
_cache = TTLCache(ttl=86400, maxsize=512)
OSM_API = "https://www.openstreetmap.org/api/0.6"


def _entrance(data: dict, kind: str, object_id: int, centre: tuple[float, float]):
    """Choose an entrance belonging to this building's outer boundary, main before ordinary."""
    elements = data.get("elements", [])
    root = next((e for e in elements if e.get("type") == kind and e.get("id") == object_id), None)
    if root is None:
        return None
    if kind == "way":
        boundary = set(root.get("nodes", []))
    else:
        outer = {m["ref"] for m in root.get("members", [])
                 if m.get("type") == "way" and m.get("role", "") in ("", "outer")}
        boundary = {n for e in elements if e.get("type") == "way" and e["id"] in outer
                    for n in e.get("nodes", [])}
    candidates = []
    for node in elements:
        if node.get("type") != "node" or node["id"] not in boundary:
            continue
        tags = node.get("tags", {})
        if tags.get("entrance") not in ("main", "yes"):
            continue
        if tags.get("access") in ("no", "private") or tags.get("foot") in ("no", "private"):
            continue
        candidates.append(node)
    if not candidates:
        return None
    lon_scale = math.cos(math.radians(centre[0]))

    def rank(node):
        distance = (node["lat"] - centre[0]) ** 2 + ((node["lon"] - centre[1]) * lon_scale) ** 2
        return node["tags"]["entrance"] != "main", distance, node["id"]

    chosen = min(candidates, key=rank)
    return float(chosen["lat"]), float(chosen["lon"])


async def building_position(client: httpx.AsyncClient, item: dict, headers: dict) -> tuple[float, float]:
    position = float(item["lat"]), float(item["lon"])
    kind = item.get("osm_type")
    tags = item.get("extratags") or {}
    building = item.get("category", item.get("class")) == "building" or tags.get("building", "no") != "no"
    if kind not in ("way", "relation") or not item.get("osm_id") or not building:
        return position
    object_id = int(item["osm_id"])
    key = (kind, object_id)
    cached = _cache.peek(key)
    if cached is not None:
        return cached or position
    try:
        response = await client.get(f"{OSM_API}/{kind}/{object_id}/full.json", headers=headers, timeout=3)
        response.raise_for_status()
        entrance = _entrance(response.json(), kind, object_id, position)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
        log.warning("building entrance lookup failed (%s)", type(exc).__name__)
        return position
    _cache.put(key, entrance or ())
    return entrance or position
