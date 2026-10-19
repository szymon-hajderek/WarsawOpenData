"""Hard cases for the nearest vehicle simulation: crowded places and the parts of tracks near them.

Pure functions, no I/O. A report is a dict {"lat", "lon", "t", ...}; a track is a vehicle's reports sorted by time.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nearest_buses import haversine_m  # noqa: E402

LAT0 = 52.23  # local projection around Warsaw
M_PER_DEG = 111_320.0


def to_xy(lat: float, lon: float) -> tuple[float, float]:
    return lon * M_PER_DEG * math.cos(math.radians(LAT0)), lat * M_PER_DEG


def from_xy(x: float, y: float) -> tuple[float, float]:
    return y / M_PER_DEG, x / (M_PER_DEG * math.cos(math.radians(LAT0)))


def crowded_cells(snaps: list[dict], cell_m: float = 300, top: int = 10, min_sep_m: float = 600,
                  only: set | None = None) -> list[dict]:
    """The `top` square cells with the most vehicles at the same moment (one poll), best first.

    Score of a cell = the largest number of distinct vehicles inside it in any single poll.
    Picked cells are at least `min_sep_m` apart (centre to centre). `only`: count just these vehicle ids
    (e.g. vehicles that moved, so a depot full of parked buses does not count). Returns [{"lat", "lon", "count"}].
    """
    best: dict[tuple[int, int], int] = {}
    for snap in snaps:
        cells: dict[tuple[int, int], set] = {}
        for v in snap["vehicles"]:
            if only is not None and v["id"] not in only:
                continue
            x, y = to_xy(v["lat"], v["lon"])
            cells.setdefault((math.floor(x / cell_m), math.floor(y / cell_m)), set()).add(v["id"])
        for key, ids in cells.items():
            best[key] = max(best.get(key, 0), len(ids))
    picked: list[dict] = []
    for (cx, cy), count in sorted(best.items(), key=lambda kv: (-kv[1], kv[0])):
        lat, lon = from_xy((cx + 0.5) * cell_m, (cy + 0.5) * cell_m)
        if all(haversine_m(lat, lon, p["lat"], p["lon"]) >= min_sep_m for p in picked):
            picked.append({"lat": lat, "lon": lon, "count": count})
        if len(picked) == top:
            break
    return picked


def near_part(track: list[dict], lat: float, lon: float, radius_m: float) -> list[dict]:
    """The longest run of consecutive reports within `radius_m` of (lat, lon); [] if no run has 2 reports."""
    best: list[dict] = []
    run: list[dict] = []
    for p in track:
        if haversine_m(p["lat"], p["lon"], lat, lon) <= radius_m:
            run.append(p)
            if len(run) > len(best):
                best = list(run)
        else:
            run = []
    return best if len(best) >= 2 else []


def path_length_m(track: list[dict]) -> float:
    return sum(haversine_m(a["lat"], a["lon"], b["lat"], b["lon"]) for a, b in zip(track, track[1:]))
