"""Geocoder object identity survives a change of Nominatim's database place_id."""
import asyncio

import httpx

from app.api import geocode
from config import TTLCache


def test_uses_osm_object_identity_and_omits_unreferenced_results(monkeypatch):
    item = {"place_id": 1, "osm_type": "node", "osm_id": 42, "lat": "52.2", "lon": "21.0",
            "display_name": "Stop", "name": "Stop"}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            return httpx.Response(200, request=httpx.Request("GET", url),
                                  json=[item, {"place_id": 9, "lat": "52.1", "lon": "21.1"}])

    monkeypatch.setattr(geocode.httpx, "AsyncClient", Client)
    monkeypatch.setattr(geocode, "_cache", TTLCache(600))
    first = asyncio.run(geocode.geocode("first query"))
    item["place_id"] = 999
    second = asyncio.run(geocode.geocode("second query"))
    assert len(first) == len(second) == 1
    assert first[0].id == second[0].id == "osm:node:42"
    assert first[0].position == (52.2, 21.0)
