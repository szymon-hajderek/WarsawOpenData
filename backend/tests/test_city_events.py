"""Real journal/JSON persistence, retry recovery and validated research payloads."""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import city_events
import journey_stats
from app.api import city_events as api


def event():
    return {"event_id": str(uuid4()), "type": "search", "age_group": "25-34",
            "origin": {"position": [52.229126789, 21.012349999]}, "result_count": 0}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    store = city_events.EventStore(tmp_path)
    monkeypatch.setattr(city_events, "store", store)
    monkeypatch.setattr(journey_stats.store, "anchors", {"vet:123": ("vet:123", 52.2, 21)})
    monkeypatch.setattr(api.scenario, "current", lambda: None)
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app), store


def read_events(store):
    return [item for path in store.directory.glob("????-??-??.json")
            for bucket in json.loads(path.read_text(encoding="utf-8"))["hours"].values() for item in bucket]


def test_api_hexes_and_deduplication(setup):
    client, store = setup
    body = event()
    assert client.post("/api/city-events", json=body).json() == {"recorded": True}
    assert client.post("/api/city-events", json=body).json() == {"recorded": False}
    saved = read_events(store)
    assert len(saved) == 1 and ":" in saved[0]["origin"]["hex"]
    raw = json.dumps(saved)
    assert "52.229126789" not in raw and "position" not in raw
    assert b"52.229126789" not in (store.directory / "journal.sqlite").read_bytes()


def test_concurrent_writes_and_retries_keep_every_event(setup):
    _, store = setup
    bodies = [{"event_id": str(uuid4()), "type": "search"} for _ in range(20)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(store.record, bodies * 2))
    assert sum(results) == 20
    assert len(read_events(store)) == 20


def test_midnight_and_warsaw_timezone(setup):
    _, store = setup
    journey = str(uuid4())
    for hour in (21, 22):  # UTC -> Warsaw 23:00 and 00:00 in October
        store.record({"event_id": str(uuid4()), "journey_id": journey},
                     datetime.fromisoformat(f"2026-10-18T{hour}:00:00+00:00"))
    first = json.loads((store.directory / "2026-10-18.json").read_text())
    second = json.loads((store.directory / "2026-10-19.json").read_text())
    assert first["hours"]["23"][0]["journey_id"] == second["hours"]["00"][0]["journey_id"]


def test_failed_export_is_repaired_by_retry(setup, monkeypatch):
    client, store = setup
    body = event()
    export = store.export
    monkeypatch.setattr(store, "export", lambda *_: (_ for _ in ()).throw(OSError("disk failure")))
    assert client.post("/api/city-events", json=body).status_code == 503
    monkeypatch.setattr(store, "export", export)
    assert client.post("/api/city-events", json=body).json() == {"recorded": False}
    assert len(read_events(store)) == 1
    next(store.directory.glob("????-??-??.json")).unlink()
    store.recover()
    assert len(read_events(store)) == 1


def test_retention_removes_rows_and_exports(setup):
    _, store = setup
    store.record({"event_id": str(uuid4())}, datetime.fromisoformat("2025-10-17T10:00:00+02:00"))
    store.record({"event_id": str(uuid4())}, datetime.fromisoformat("2025-10-18T10:00:00+02:00"))
    store.record({"event_id": str(uuid4())}, datetime.fromisoformat("2026-10-18T10:00:00+02:00"))
    assert not (store.directory / "2025-10-17.json").exists()
    assert (store.directory / "2025-10-18.json").exists()
    with sqlite3.connect(store.directory / "journal.sqlite") as conn:
        assert conn.execute("SELECT count(*) FROM events").fetchone()[0] == 2


def test_relevant_station_snapshot_only(setup, monkeypatch):
    client, store = setup
    feed = {"last_updated": 1, "data": {"stations": [
        {"station_id": "123", "num_bikes_available": 0, "is_renting": True},
        {"station_id": "456", "num_bikes_available": 9}]}}
    monkeypatch.setattr(api.nextbike, "_get", lambda *_: feed)
    body = event()
    body["origin"]["station_id"] = "vet:123"
    client.post("/api/city-events", json=body)
    snapshot = read_events(store)[0]["station_status"]
    assert snapshot["available"] and snapshot["feed_age_s"] > 0
    assert [s["station_id"] for s in snapshot["stations"]] == ["123"]


def test_feed_failure_does_not_drop_event(setup, monkeypatch):
    client, store = setup
    monkeypatch.setattr(api.nextbike, "_get", lambda *_: (_ for _ in ()).throw(OSError()))
    body = event()
    body["origin"]["station_id"] = "vet:123"
    assert client.post("/api/city-events", json=body).status_code == 200
    assert read_events(store)[0]["station_status"] == {"available": False}


@pytest.mark.parametrize("extra", [{"age": 35}, {"track": []}, {"type": "journey_finished"},
                                  {"origin": {"position": [91, 21]}}, {"age_group": "35"}])
def test_invalid_or_unapproved_fields_rejected(setup, extra):
    client, store = setup
    assert client.post("/api/city-events", json=event() | extra).status_code == 422
    assert not read_events(store)


def test_simulation_not_collected(setup, monkeypatch):
    client, store = setup
    monkeypatch.setattr(api.scenario, "current", lambda: object())
    assert client.post("/api/city-events", json=event()).json() == {"recorded": False}
    assert not read_events(store)
