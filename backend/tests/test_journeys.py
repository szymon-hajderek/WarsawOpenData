"""Real SQLite persistence and API behavior, with small in-memory anchor catalogs."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import journey_stats
from app.api import journeys

ANCHORS = [("ztm:700901", 52.229123456, 21.012345678), ("vet:203610", 52.25602, 21.046219)]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    store = journey_stats.JourneyStore(tmp_path / "journeys.sqlite")
    store.prepare(ANCHORS)
    monkeypatch.setattr(journey_stats, "store", store)
    app = FastAPI()
    app.include_router(journeys.router)
    return TestClient(app), store


def body():
    return {"token": str(uuid4()),
            "from": {"id": "current-location", "position": [52.229126789, 21.012349999], "isCurrentLocation": True},
            "to": {"id": "vet:203610", "position": [0, 0]}}


def rows(store, table):
    with sqlite3.connect(store.path) as conn:
        return conn.execute(f"SELECT * FROM {table}").fetchall()


def test_exact_catalog_points_replace_gps_and_untrusted_station_coordinates(setup):
    client, store = setup
    payload = body()
    assert client.post("/api/journeys", json=payload).json() == {"recorded": True}
    assert sorted(rows(store, "places")) == sorted(ANCHORS)
    counts = rows(store, "journeys")
    assert counts[0][1:] == ("ztm:700901", "vet:203610", 1)
    assert rows(store, "receipts") == [(payload["token"],)]
    with sqlite3.connect(store.path) as conn:
        assert {r[1] for r in conn.execute("PRAGMA table_info(places)")} == {"id", "lat", "lon"}
        assert {r[1] for r in conn.execute("PRAGMA table_info(journeys)")} == {"day", "from_id", "to_id", "count"}
    raw = store.path.read_bytes()
    assert b"current-location" not in raw and b"52.229126789" not in raw


def test_retry_is_idempotent_and_separate_journeys_increment_counter(setup):
    client, store = setup
    payload = body()
    assert client.post("/api/journeys", json=payload).json()["recorded"]
    assert client.post("/api/journeys", json=payload).json() == {"recorded": False}
    payload["token"] = str(uuid4())
    assert client.post("/api/journeys", json=payload).json()["recorded"]
    assert rows(store, "journeys")[0][-1] == 2


def test_concurrent_retries_commit_only_once(setup):
    _, store = setup
    req = journeys.JourneyRequest.model_validate(body())
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.record(req.token, req.from_, req.to), range(16)))
    assert sum(results) == 1
    assert rows(store, "journeys")[0][-1] == 1


def test_osm_object_coordinates_are_not_quantized(setup):
    client, store = setup
    payload = body()
    payload["from"] = {"id": "osm:node:123", "position": [52.234567891, 21.123456789]}
    assert client.post("/api/journeys", json=payload).status_code == 200
    assert ("osm:node:123", 52.234567891, 21.123456789) in rows(store, "places")


@pytest.mark.parametrize("change", [
    lambda p: p.update(userId="private"),
    lambda p: p["from"].update(label="Private address"),
    lambda p: p.update(track=[]),
    lambda p: p["from"].update(position=[91, 21]),
    lambda p: p["from"].update(position=[52, float("inf")]),
    lambda p: p["from"].update(id="current-location", isCurrentLocation=False),
    lambda p: p["to"].update(id="vet:missing"),
    lambda p: p.update(token="not-a-uuid"),
])
def test_rejects_invalid_or_identifying_fields_and_rolls_back(setup, change):
    client, store = setup
    payload = body()
    change(payload)
    # httpx JSON correctly refuses infinity; exercise that validation through the model instead.
    if payload["from"]["position"][1] == float("inf"):
        with pytest.raises(ValueError):
            journeys.JourneyRequest.model_validate(payload)
    else:
        assert client.post("/api/journeys", json=payload).status_code == 422
    assert not rows(store, "places") and not rows(store, "receipts")


def test_unavailable_storage_returns_sanitized_error(setup, monkeypatch):
    client, store = setup
    def fail(*args):
        raise sqlite3.OperationalError("private path and coordinates")
    monkeypatch.setattr(store, "record", fail)
    response = client.post("/api/journeys", json=body())
    assert response.status_code == 503
    assert response.json() == {"detail": "journey statistics unavailable"}


def test_uninitialized_catalog_never_builds_inside_a_request(setup, monkeypatch):
    client, store = setup
    store.anchors = None
    monkeypatch.setattr(journey_stats, "initialize", lambda: pytest.fail("request-time initialization"))
    assert client.post("/api/journeys", json=body()).status_code == 503


def test_store_survives_restart_without_recounting_a_receipt(setup):
    client, store = setup
    payload = body()
    assert client.post("/api/journeys", json=payload).json()["recorded"]
    restarted = journey_stats.JourneyStore(store.path)
    restarted.prepare(ANCHORS)
    req = journeys.JourneyRequest.model_validate(payload)
    assert not restarted.record(req.token, req.from_, req.to)
    assert rows(restarted, "journeys")[0][-1] == 1
