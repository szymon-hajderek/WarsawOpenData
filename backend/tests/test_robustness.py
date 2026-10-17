"""Locks, atomic cache files, bounded cache, input checks and error codes. No network, no real data files."""
import json
import threading
import time

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

import bus_detect
import config
import main
from app.api import geocode
from sources import mkuran, osm, um_warszawa

client = TestClient(main.app)  # no `with`: the lifespan (poller, warm-up) does not run


# ---------------------------------------------------------------- config

def test_ttl_cache_expires(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(config.time, "monotonic", lambda: now[0])
    cache = config.TTLCache(ttl=10)
    calls = []
    assert cache.get("k", lambda: calls.append(1) or "a") == "a"
    assert cache.get("k", lambda: calls.append(1) or "b") == "a"  # still fresh
    now[0] += 11
    assert cache.get("k", lambda: calls.append(1) or "b") == "b"  # expired, fetched again
    assert len(calls) == 2


def test_ttl_cache_is_bounded():
    cache = config.TTLCache(ttl=1000, maxsize=3)
    for i in range(10):
        cache.put(i, i)
    assert len(cache._data) <= 3
    assert cache.peek(9) == 9  # the newest stays
    assert cache.peek(0) is None  # the oldest is gone


def test_atomic_write_keeps_the_old_file_on_failure(tmp_path):
    path = tmp_path / "x.json"
    config.save_json(path, {"a": 1})
    with pytest.raises(RuntimeError), config.atomic_write(path, "w") as f:
        f.write("half")
        raise RuntimeError("crash")
    assert json.loads(path.read_text()) == {"a": 1}
    assert list(tmp_path.iterdir()) == [path]  # no .part left


def test_require_key():
    with pytest.raises(config.MissingKey):
        config.require_key("X_KEY", "")
    assert config.require_key("X_KEY", "abc") == "abc"


# ---------------------------------------------------------------- pure helpers

def test_split_stop_id():
    assert um_warszawa.split_stop_id("ztm:700901") == ("7009", "01")
    for bad in ("wkd:brzoz", "ztm:7009", "ztm:abcdef", "700901x"):
        with pytest.raises(ValueError):
            um_warszawa.split_stop_id(bad)


def test_fresh_drops_old_positions():
    from datetime import datetime
    now = datetime(2026, 10, 17, 12, 0, 0)
    rows = [{"time": "2026-10-17 11:58:00"}, {"time": "2026-10-17 11:50:00"}, {"time": "2020-01-01 00:00:00"}]
    assert um_warszawa.fresh(rows, 300, now) == rows[:1]


def test_gtfs_small_helpers():
    assert mkuran._sec("25:10:05") == 25 * 3600 + 10 * 60 + 5
    assert mkuran._norm_name("  Warszawa-Śródmieście  ") == "warszawa śródmieście"
    assert mkuran.parse_bbox("1,2,3,4") == (1.0, 2.0, 3.0, 4.0)
    for bad in ("1,2", "a,b,c,d", "5,2,3,4"):
        with pytest.raises(Exception) as exc:
            mkuran.parse_bbox(bad)
        assert exc.value.status_code == 422


def test_osm_way_filters():
    assert osm.walk_ok({"highway": "footway"})
    assert not osm.walk_ok({"highway": "motorway"})
    assert not osm.walk_ok({"highway": "residential", "foot": "no"})
    assert not osm.walk_ok({"highway": "service", "access": "private"})
    assert osm.walk_ok({"highway": "service", "access": "private", "foot": "yes"})
    assert osm.bike_ok({"highway": "cycleway"})
    assert not osm.bike_ok({"highway": "steps"})
    assert not osm.bike_ok({"highway": "footway"})
    assert osm.bike_oneway({"oneway": "yes"}) == 1
    assert osm.bike_oneway({"oneway": "-1"}) == -1
    assert osm.bike_oneway({"oneway": "yes", "oneway:bicycle": "no"}) == 0
    assert osm.bike_oneway({"highway": "residential"}) == 0


# ---------------------------------------------------------------- locks on the lazy builds

def test_osm_graph_is_built_once_and_never_half_visible(tmp_path, monkeypatch):
    config.save_npz(tmp_path / "osm_graph.npz", lat=np.array([52.2, 52.21]), lon=np.array([21.0, 21.01]))
    monkeypatch.setattr(osm, "DERIVED", tmp_path)
    monkeypatch.setattr(osm, "_G", {})
    seen, errors = [], []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        try:
            g = osm.graph()
            seen.append(g["tree"] is not None and len(g["lat"]) == 2)
        except Exception as exc:  # a thread that saw a half-filled dict used to raise KeyError
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    assert seen == [True] * 8


def test_gtfs_cache_build_runs_once(tmp_path, monkeypatch):
    monkeypatch.setattr(mkuran, "DERIVED", tmp_path)
    builds = []

    def fake_build():
        builds.append(1)
        time.sleep(0.2)  # the real build takes 25 s: other threads must wait, not start a second build
        config.save_json(tmp_path / "gtfs_stops.json", [{"zone": ""}])
        config.save_json(tmp_path / "gtfs_trips.json", [])
        config.save_npz(tmp_path / "gtfs_stop_times.npz", shape_dist=np.array([1200]))

    monkeypatch.setattr(mkuran, "_build", fake_build)
    threads = [threading.Thread(target=mkuran._ensure_built) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(builds) == 1


def test_old_kilometer_shape_cache_is_rebuilt(tmp_path, monkeypatch):
    """Caches from before shape distances were stored as meters max out around 20."""
    monkeypatch.setattr(mkuran, "DERIVED", tmp_path)
    config.save_json(tmp_path / "gtfs_stops.json", [{"zone": "1"}])
    config.save_json(tmp_path / "gtfs_trips.json", [])
    config.save_npz(tmp_path / "gtfs_stop_times.npz", shape_dist=np.array([12]))
    called = []
    monkeypatch.setattr(mkuran, "_build", lambda: called.append(1))
    mkuran._ensure_built()
    assert called == [1]


def test_gtfs_cache_without_the_marker_file_is_rebuilt(tmp_path, monkeypatch):
    """A crash after the JSON files but before the .npz must not leave a cache that looks complete."""
    monkeypatch.setattr(mkuran, "DERIVED", tmp_path)
    config.save_json(tmp_path / "gtfs_stops.json", [{"zone": ""}])
    config.save_json(tmp_path / "gtfs_trips.json", [])
    called = []
    monkeypatch.setattr(mkuran, "_build", lambda: called.append(1))
    mkuran._ensure_built()
    assert called == [1]


# ---------------------------------------------------------------- input checks -> 4xx

@pytest.mark.parametrize("url", [
    "/api/gtfs/stops?bbox=1,2",
    "/api/gtfs/stops?bbox=a,b,c,d",
    "/api/gtfs/edges?limit=-1",
    "/api/gtfs/edges?limit=999999",
    "/api/gtfs/edges?offset=-5",
    "/api/gtfs/stops/ztm:700901/departures?time=abc",
    "/api/gtfs/stops/ztm:700901/departures?date=tomorrow",
    "/api/gtfs/stops/ztm:700901/departures?limit=0",
    "/api/osm/nearest?lat=999&lon=21",
    "/api/osm/route?from_lat=52&from_lon=21&to_lat=52&to_lon=400",
    "/api/live/vehicles?type=bus&max_age_s=0",
])
def test_bad_parameters_give_422(url):
    assert client.get(url).status_code == 422


def test_bad_values_give_400():
    assert client.get("/api/live/vehicles?type=boat").status_code == 400
    assert client.get("/api/ztm/stops/abc/lines").status_code == 400
    assert client.get("/api/ztm/stops/ztm:7009/lines/131/times").status_code == 400
    assert client.get("/api/osm/nearest?lat=52&lon=21&mode=car").status_code == 400


def test_junk_stop_ids_do_not_fill_the_cache(monkeypatch):
    cache = config.TTLCache(30)
    monkeypatch.setattr(um_warszawa, "_cache", cache)
    for i in range(20):
        client.get(f"/api/ztm/stops/junk{i}/lines")
    assert cache._data == {}


# ---------------------------------------------------------------- error codes

def test_upstream_failure_gives_502_without_the_key(monkeypatch):
    def boom(kind):
        raise httpx.ConnectError("failed for https://api.um.warszawa.pl/x?apikey=SECRET123")

    monkeypatch.setattr(um_warszawa, "fetch_vehicles", boom)
    monkeypatch.setattr(um_warszawa, "_veh_cache", config.TTLCache(3))
    r = client.get("/api/live/vehicles?type=bus")
    assert r.status_code == 502
    assert "SECRET123" not in r.text


def test_missing_key_gives_503(monkeypatch):
    monkeypatch.setattr(um_warszawa, "PORTAL_KEY", "")
    monkeypatch.setattr(um_warszawa, "_veh_cache", config.TTLCache(3))
    r = client.get("/api/live/vehicles?type=tram")
    assert r.status_code == 503
    assert "PORTAL_KEY" in r.json()["detail"]


def test_missing_data_file_gives_404(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA", tmp_path)
    r = client.get("/api/stats")
    assert r.status_code == 404
    assert "report.json" in r.json()["detail"]


def test_endpoints_wait_while_caches_load():
    main.READY.clear()
    try:
        assert client.get("/api/gtfs/merge").status_code == 503
        assert client.get("/api/osm/graph/summary").status_code == 503
        assert client.get("/api/sources").status_code == 200  # no cache needed
    finally:
        main.READY.set()


# ---------------------------------------------------------------- bus_detect, geocode

def test_bus_detect_forgets_vehicles_that_left_the_feed(monkeypatch):
    now = time.time()
    monkeypatch.setattr(bus_detect, "_history", {"bus-1": [{"lat": 0, "lon": 0, "t": now - 10}],
                                                 "bus-2": [{"lat": 0, "lon": 0, "t": now - 4000}]})
    monkeypatch.setattr(bus_detect, "_info", {"bus-1": {"line": "1"}, "bus-2": {"line": "2"}})
    bus_detect._forget_stale()
    assert list(bus_detect._history) == ["bus-1"]
    assert list(bus_detect._info) == ["bus-1"]


def test_geocode_answers_from_the_cache():
    from app.models import Place
    geocode._cache.put("rondo daszyńskiego", [Place(id="osm-1", label="Rondo", position=(52.2, 21.0))])
    r = client.get("/api/geocode", params={"q": "Rondo   Daszyńskiego"})  # same key after normalising
    assert r.status_code == 200
    assert r.json()[0]["id"] == "osm-1"
    assert client.get("/api/geocode", params={"q": "x" * 201}).status_code == 422
