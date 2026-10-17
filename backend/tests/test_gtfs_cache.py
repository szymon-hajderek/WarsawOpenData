"""GTFS cache migrations must not infer distance units from another feed's maximum."""
import numpy as np
import pytest

import config
from sources import mkuran


def write_cache(path, *, version=None, distances=(0, 21, 1126)):
    config.save_json(path / "gtfs_stops.json", [{"zone": "1"}])
    config.save_json(path / "gtfs_trips.json", [["ztm:metro", "ztm:M1"], ["pkp:train", "pkp:R1"]])
    arrays = {"trip": np.array([0, 0, 1])}
    if distances is not None:
        arrays["shape_dist"] = np.array(distances)
    if version is not None:
        arrays["cache_version"] = np.array(version)
    config.save_npz(path / "gtfs_stop_times.npz", **arrays)


def test_unversioned_mixed_feed_cache_is_rebuilt(tmp_path, monkeypatch):
    monkeypatch.setattr(mkuran, "DERIVED", tmp_path)
    # Truncated metro kilometres are hidden by another feed's value above the old 500 m threshold.
    write_cache(tmp_path)
    builds = []
    monkeypatch.setattr(mkuran, "_build", lambda: builds.append(True))

    mkuran._ensure_built()

    assert builds == [True]


@pytest.mark.parametrize("version", [0, 999])
def test_incompatible_cache_version_is_rebuilt(tmp_path, monkeypatch, version):
    monkeypatch.setattr(mkuran, "DERIVED", tmp_path)
    write_cache(tmp_path, version=version)
    builds = []
    monkeypatch.setattr(mkuran, "_build", lambda: builds.append(True))

    mkuran._ensure_built()

    assert builds == [True]


def test_current_cache_is_reused_even_for_short_distances(tmp_path, monkeypatch):
    monkeypatch.setattr(mkuran, "DERIVED", tmp_path)
    write_cache(tmp_path, version=mkuran.CACHE_VERSION, distances=(0, 21, 42))
    builds = []
    monkeypatch.setattr(mkuran, "_build", lambda: builds.append(True))

    mkuran._ensure_built()
    mkuran._ensure_built()

    assert builds == []


def test_current_cache_without_shape_distances_is_rebuilt(tmp_path, monkeypatch):
    monkeypatch.setattr(mkuran, "DERIVED", tmp_path)
    write_cache(tmp_path, version=mkuran.CACHE_VERSION, distances=None)
    builds = []
    monkeypatch.setattr(mkuran, "_build", lambda: builds.append(True))

    mkuran._ensure_built()

    assert builds == [True]


def test_cache_version_is_not_a_stop_time_array(tmp_path, monkeypatch):
    monkeypatch.setattr(mkuran, "DERIVED", tmp_path)
    write_cache(tmp_path, version=mkuran.CACHE_VERSION)

    arrays = mkuran.stop_times.__wrapped__()

    assert set(arrays) == {"trip", "shape_dist"}
    assert arrays["shape_dist"].tolist() == [0, 21, 1126]


def test_build_stamps_cache_and_preserves_fractional_kilometres(tmp_path, monkeypatch):
    monkeypatch.setattr(mkuran, "DERIVED", tmp_path)
    monkeypatch.setattr(mkuran, "FEEDS", {"ztm": ("unused.zip", "unused")})
    monkeypatch.setattr(mkuran, "routes", lambda: {"ztm:M1": {"type": 1}})
    stops = [
        {"id": f"ztm:{sid}", "feed": "ztm", "raw_id": sid, "name": sid, "code": "",
         "lat": 52.2, "lon": 21.0, "location_type": 0, "parent": None, "wheelchair": "1", "zone": "1"}
        for sid in ("a", "b")
    ]
    monkeypatch.setattr(mkuran, "_raw_stops", lambda feed: stops)
    tables = {
        "trips.txt": [{"trip_id": "metro", "route_id": "M1", "service_id": "day", "shape_id": "m1"}],
        "stop_times.txt": [
            {"trip_id": "metro", "stop_id": "a", "stop_sequence": "0", "arrival_time": "10:00:00",
             "departure_time": "10:00:00", "shape_dist_traveled": "0"},
            {"trip_id": "metro", "stop_id": "b", "stop_sequence": "1", "arrival_time": "10:02:00",
             "departure_time": "10:02:00", "shape_dist_traveled": "0.829644"},
        ],
    }
    monkeypatch.setattr(mkuran, "_rows", lambda feed, table: iter(tables.get(table, [])))

    mkuran._build()

    with np.load(tmp_path / "gtfs_stop_times.npz") as cache:
        assert int(cache["cache_version"]) == mkuran.CACHE_VERSION
        assert cache["shape_dist"].tolist() == [0, 830]
