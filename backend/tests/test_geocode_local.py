"""Place search: our own stops and Veturilo stations come first and survive a Nominatim failure. No network."""
import httpx
import pytest
from fastapi.testclient import TestClient

import main
from app.api import geocode

client = TestClient(main.app)  # no `with`: the lifespan does not run

INDEX = [
    {"id": "stop-1", "name": "Marszałkowska", "lat": 52.2297, "lon": 21.0122, "kind": "Przystanek"},
    {"id": "stop-2", "name": "Metro Politechnika", "lat": 52.2185, "lon": 21.0158, "kind": "Przystanek"},
    {"id": "veturilo-9", "name": "Politechnika Warszawska", "lat": 52.2203, "lon": 21.0118, "kind": "Stacja Veturilo"},
]


class Down:
    """A stand-in for httpx.AsyncClient that cannot reach Nominatim."""

    calls = 0

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, *a, **k):
        Down.calls += 1
        raise httpx.ConnectError("down")


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    geocode._cache._data.clear()
    monkeypatch.setattr(geocode, "_local_index", lambda: INDEX)
    monkeypatch.setattr(geocode.httpx, "AsyncClient", Down)
    Down.calls = 0
    yield


def ask(q, **params):
    return client.get("/api/geocode", params={"q": q, **params})


def test_a_short_text_is_answered_locally_without_nominatim():
    r = ask("po")
    assert r.status_code == 200
    assert [p["label"] for p in r.json()] == ["Politechnika Warszawska", "Metro Politechnika"]
    assert Down.calls == 0


def test_the_start_of_a_word_is_enough():
    assert ask("marszalk").json()[0]["id"] == "stop-1"
    assert ask("marszalk").json()[0]["sublabel"] == "Przystanek"


def test_local_stops_survive_a_nominatim_failure():
    r = ask("politechn")
    assert r.status_code == 200 and len(r.json()) == 2
    assert Down.calls == 1


def test_nominatim_failure_without_local_matches_is_still_a_502():
    assert ask("zzzzzz").status_code == 502


def test_near_orders_equal_matches_by_distance(monkeypatch):
    index = [
        {"id": "far", "name": "Wilanowska", "lat": 52.17, "lon": 21.03, "kind": "Przystanek"},
        {"id": "close", "name": "Wilanowska", "lat": 52.23, "lon": 21.0, "kind": "Przystanek"},
    ]
    monkeypatch.setattr(geocode, "_local_index", lambda: index)
    assert ask("wilan", lat=52.231, lon=21.0).json()[0]["id"] == "close"
    assert ask("wilan", lat=52.17, lon=21.03).json()[0]["id"] == "far"


def test_a_bad_position_is_rejected():
    assert ask("po", lat=200, lon=21).status_code == 422
