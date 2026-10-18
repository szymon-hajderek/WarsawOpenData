"""Recover real GTFS paths without changing route selection or geocoding."""
import numpy as np
import pytest

import config
from sources import mkuran


def cache(path, *, version=None, distances=(0, 21, 1126)):
    config.save_json(path / "gtfs_stops.json", [{"zone": "1", "platform": None, "boarding": True}])
    config.save_json(path / "gtfs_trips.json", [])
    arrays = {}
    if distances is not None:
        arrays["shape_dist"] = np.array(distances)
    if version is not None:
        arrays["cache_version"] = np.int32(version)
    config.save_npz(path / "gtfs_stop_times.npz", **arrays)


@pytest.mark.parametrize("version", [None, 1, 999])
def test_legacy_cache_rebuilds_even_when_another_feed_hides_truncated_units(tmp_path, monkeypatch, version):
    monkeypatch.setattr(mkuran, "DERIVED", tmp_path)
    cache(tmp_path, version=version)
    builds = []
    monkeypatch.setattr(mkuran, "_build", lambda: builds.append(True))
    mkuran._ensure_built()
    assert builds == [True]


def test_current_cache_is_reused_even_for_short_routes(tmp_path, monkeypatch):
    monkeypatch.setattr(mkuran, "DERIVED", tmp_path)
    cache(tmp_path, version=mkuran.CACHE_VERSION, distances=(0, 21, 42))
    monkeypatch.setattr(mkuran, "_build", lambda: pytest.fail("Current cache should be reused"))
    mkuran._ensure_built()
    mkuran._ensure_built()
    arrays = mkuran.stop_times.__wrapped__()
    assert set(arrays) == {"shape_dist"}


def test_current_cache_without_distances_is_rebuilt(tmp_path, monkeypatch):
    monkeypatch.setattr(mkuran, "DERIVED", tmp_path)
    cache(tmp_path, version=mkuran.CACHE_VERSION, distances=None)
    builds = []
    monkeypatch.setattr(mkuran, "_build", lambda: builds.append(True))
    mkuran._ensure_built()
    assert builds == [True]


@pytest.mark.parametrize("route_type", [0, 1, 2, 3])
def test_real_builder_keeps_distance_precision_and_new_platform_fields(tmp_path, monkeypatch, route_type):
    monkeypatch.setattr(mkuran, "DERIVED", tmp_path)
    monkeypatch.setattr(mkuran, "FEEDS", {"ztm": ("unused.zip", "unused")})
    monkeypatch.setattr(mkuran, "routes", lambda: {"ztm:line": {"type": route_type}})
    stops = [
        {"id": f"ztm:{sid}", "feed": "ztm", "raw_id": sid, "name": sid, "code": "",
         "lat": 52.2, "lon": 21.0, "location_type": 0, "parent": None, "wheelchair": "1", "zone": "1"}
        for sid in ("a", "b")
    ]
    monkeypatch.setattr(mkuran, "_raw_stops", lambda _: stops)
    tables = {
        "trips.txt": [{"trip_id": "trip", "route_id": "line", "service_id": "day", "shape_id": "shape"}],
        "stop_times.txt": [
            {"trip_id": "trip", "stop_id": "a", "stop_sequence": "0", "arrival_time": "10:00:00",
             "departure_time": "10:00:00", "shape_dist_traveled": "0"},
            {"trip_id": "trip", "stop_id": "b", "stop_sequence": "1", "arrival_time": "10:02:00",
             "departure_time": "10:02:00", "shape_dist_traveled": "0.829644"},
        ],
    }
    monkeypatch.setattr(mkuran, "_rows", lambda feed, table: iter(tables.get(table, [])))
    mkuran._build()
    with np.load(tmp_path / "gtfs_stop_times.npz") as stored:
        assert int(stored["cache_version"]) == mkuran.CACHE_VERSION
        assert stored["shape_dist"].tolist() == [0, 830]
    assert all(s["boarding"] and s["platform"] is None for s in config.load_json(tmp_path / "gtfs_stops.json"))


def test_shapes_follow_sequence_when_feed_distances_are_missing(monkeypatch):
    monkeypatch.setattr(mkuran, "FEEDS", {"wkd": ("unused.zip", "unused")})
    # Shuffled input rows, with no usable distances, still define an unambiguous track order.
    rows = [{"shape_id": "1", "shape_pt_sequence": str(i), "shape_pt_lat": str(52.2 + i / 1000),
             "shape_pt_lon": "21", "shape_dist_traveled": ""} for i in (2, 0, 1)]
    monkeypatch.setattr(mkuran, "_rows", lambda *a: iter(rows))
    shapes = mkuran._shapes.__wrapped__()
    assert shapes["wkd:1"][1].tolist() == pytest.approx([52.2, 52.201, 52.202])
