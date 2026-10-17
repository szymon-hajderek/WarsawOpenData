"""Building search results use their own public entrances; no network or local data files."""
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

import main
from app import geocode_access
from app.api import geocode
from config import TTLCache

AsyncClient = httpx.AsyncClient
client = TestClient(main.app)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(geocode, "_local_index", lambda: [])
    monkeypatch.setattr(geocode, "_cache", TTLCache(600))
    monkeypatch.setattr(geocode_access, "_cache", TTLCache(86400))


def node(node_id, entrance="yes", **tags):
    return {"type": "node", "id": node_id, "lat": 52.2, "lon": 21.0 + node_id / 100000,
            "tags": {"entrance": entrance, **tags}}


@pytest.mark.parametrize("kind, object_id, category, tags, centre, entrance", [
    ("way", 23599997, "building", {}, (52.2118208, 20.9819437), (52.2118727, 20.9822002)),
    ("relation", 1319250, "tourism", {"building": "public"},
     (52.2317657, 21.0057979), (52.2319291, 21.006901)),
])
def test_search_returns_the_building_main_entrance_and_keeps_identity(
    monkeypatch, kind, object_id, category, tags, centre, entrance,
):
    """MIM UW and Palace of Culture exercise both Nominatim classifications and OSM object types."""
    item = {"osm_type": kind, "osm_id": object_id, "category": category, "extratags": tags,
            "lat": str(centre[0]), "lon": str(centre[1]), "name": "Building", "display_name": "Building, Warsaw"}
    main_door = {"type": "node", "id": 1, "lat": entrance[0], "lon": entrance[1],
                 "tags": {"entrance": "main"}}
    elements = [main_door, node(2), {"type": "way", "id": object_id if kind == "way" else 7, "nodes": [1, 2]}]
    if kind == "relation":
        elements.append({"type": "relation", "id": object_id,
                         "members": [{"type": "way", "ref": 7, "role": "outer"}]})
    osm_calls = []

    def answer(request):
        if request.url.path == "/search":
            assert request.url.params["extratags"] == "1"
            return httpx.Response(200, json=[item])
        assert request.url.path == f"/api/0.6/{kind}/{object_id}/full.json"
        osm_calls.append(request)
        return httpx.Response(200, json={"elements": elements})

    monkeypatch.setattr(geocode.httpx, "AsyncClient",
                        lambda **kwargs: AsyncClient(transport=httpx.MockTransport(answer), **kwargs))
    first = client.get("/api/geocode", params={"q": "first name"})
    second = client.get("/api/geocode", params={"q": "another name"})
    assert first.status_code == second.status_code == 200
    assert first.json()[0]["id"] == f"osm:{kind}:{object_id}"
    assert first.json()[0]["label"] == "Building"
    assert first.json()[0]["position"] == second.json()[0]["position"] == list(entrance)
    assert len(osm_calls) == 1  # an object is cached across different search texts


def test_relation_ignores_courtyard_and_unrelated_entrances():
    elements = [node(1, "main"), node(2), node(3, "main"), node(4, "main"),
                {"type": "way", "id": 10, "nodes": [2]},
                {"type": "way", "id": 11, "nodes": [3]},
                {"type": "relation", "id": 20, "members": [
                    {"type": "way", "ref": 10, "role": "outer"},
                    {"type": "way", "ref": 11, "role": "inner"}]}]
    assert geocode_access._entrance({"elements": elements}, "relation", 20, (52.2, 21)) == (52.2, 21.00002)


@pytest.mark.parametrize("tags", [
    {"entrance": "service"}, {"entrance": "emergency"}, {"entrance": "no"},
    {"access": "private"}, {"access": "no"}, {"foot": "private"}, {"foot": "no"},
])
def test_restricted_or_service_entrance_is_not_selected(tags):
    elements = [node(1, "main", **{k: v for k, v in tags.items() if k != "entrance"}), node(2),
                {"type": "way", "id": 10, "nodes": [1, 2]}]
    elements[0]["tags"].update(tags)
    assert geocode_access._entrance({"elements": elements}, "way", 10, (52.2, 21)) == (52.2, 21.00002)


@pytest.mark.parametrize("failure", ["unmapped", "unavailable", "bad-json"])
def test_missing_entrance_or_upstream_failure_preserves_the_search_point(failure):
    calls = []

    def answer(request):
        calls.append(request)
        if failure == "unavailable":
            return httpx.Response(503)
        if failure == "bad-json":
            return httpx.Response(200, text="not JSON")
        return httpx.Response(200, json={"elements": [{"type": "way", "id": 10, "nodes": []}]})

    async def run():
        item = {"osm_type": "way", "osm_id": 10, "category": "building", "lat": "52.2", "lon": "21"}
        async with AsyncClient(transport=httpx.MockTransport(answer)) as upstream:
            for _ in range(2):
                assert await geocode_access.building_position(upstream, item, {}) == (52.2, 21)

    asyncio.run(run())
    assert len(calls) == (1 if failure == "unmapped" else 2)


def test_non_building_search_does_not_download_an_osm_object():
    async def run():
        async with AsyncClient(transport=httpx.MockTransport(lambda r: pytest.fail("Unexpected OSM request"))) as upstream:
            item = {"osm_type": "relation", "osm_id": 1, "category": "boundary", "lat": "52.2", "lon": "21"}
            assert await geocode_access.building_position(upstream, item, {}) == (52.2, 21)

    asyncio.run(run())
