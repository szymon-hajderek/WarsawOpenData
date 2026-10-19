"""Run from backend/: uv run pytest ../algorithms"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hotspots import crowded_cells, near_part, path_length_m  # noqa: E402

V = lambda vid, lat, lon, t=0: {"id": vid, "lat": lat, "lon": lon, "t": t}


def test_crowded_cells_counts_one_poll_and_keeps_distance():
    # 3 vehicles together in the first poll, 2 in another place; the second poll repeats one vehicle 3 times.
    snaps = [
        {"vehicles": [V("a", 52.2301, 21.0001), V("b", 52.2302, 21.0002), V("c", 52.2303, 21.0003),
                      V("d", 52.2501, 21.0501), V("e", 52.2502, 21.0502)]},
        {"vehicles": [V("a", 52.2501, 21.0501), V("a", 52.2502, 21.0502), V("a", 52.2503, 21.0503)]},
    ]
    cells = crowded_cells(snaps, top=5)
    assert [c["count"] for c in cells] == [3, 2]


def test_crowded_cells_only_counts_given_vehicles():
    snaps = [{"vehicles": [V("a", 52.2301, 21.0001), V("b", 52.2302, 21.0002), V("c", 52.2501, 21.0501)]}]
    assert [c["count"] for c in crowded_cells(snaps, only={"a", "c"})] == [1, 1]


def test_crowded_cells_drops_neighbours_closer_than_min_sep():
    snaps = [{"vehicles": [V("a", 52.2301, 21.0001), V("b", 52.2302, 21.0002),
                           V("c", 52.2331, 21.0001)]}]  # c: next cell, ~330 m north
    assert len(crowded_cells(snaps, min_sep_m=600)) == 1
    assert len(crowded_cells(snaps, min_sep_m=100)) == 2


def test_near_part_takes_longest_run_inside_radius():
    track = [V("x", 52.2300, 21.0, 0), V("x", 52.2310, 21.0, 10), V("x", 52.2400, 21.0, 20),
             V("x", 52.2301, 21.0, 30), V("x", 52.2302, 21.0, 40), V("x", 52.2303, 21.0, 50)]
    part = near_part(track, 52.2300, 21.0, 200)
    assert [p["t"] for p in part] == [30, 40, 50]
    assert near_part(track[:3], 52.2400, 21.0, 50) == []
    assert round(path_length_m(part)) == 22
