"""Simulate users riding recorded buses and check if rank_buses (algorithms/nearest_buses.py) finds their bus.

Run from backend/:  uv run python ../algorithms/simulation/simulate_nearest_buses.py [sample.json]
Default sample: data/live/bus_track_sample.json (record it with record_buses.py).

For each of N_LINES random lines (one moving vehicle each) the recorded positions form a polyline.
POINTS_PER_LINE random points are drawn on it (uniform by length). The simulated user stands at that point
(1 point) or rode the bus for the last 20 s (3 points, 10 s apart). Every user point is moved to a uniform
random spot inside a circle of radius R (GPS error). The backend only knows the last 3 reports per vehicle
that are not newer than the user's time, like backend/bus_detect.py.
"""
import json
import math
import random
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "algorithms"))
from nearest_buses import haversine_m, rank_buses  # noqa: E402

N_LINES, POINTS_PER_LINE, SEED = 15, 5, 42
RADII_M = (10, 25, 50, 100)
POPUP = 4  # candidates shown in the popup
SAMPLE = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "data" / "live" / "bus_track_sample.json"


def load_tracks(path: Path) -> dict[str, list[dict]]:
    """vehicle id -> reports sorted by time (repeated reports of the cached feed removed)."""
    tracks: dict[str, dict[float, dict]] = {}
    for snap in json.loads(path.read_text()):
        for v in snap["vehicles"]:
            tracks.setdefault(v["id"], {})[v["t"]] = v
    return {vid: [pts[t] for t in sorted(pts)] for vid, pts in tracks.items()}


def length_m(tr):
    return sum(haversine_m(a["lat"], a["lon"], b["lat"], b["lon"]) for a, b in zip(tr, tr[1:]))


def at_time(tr, t):
    """Position on the polyline at time t (linear between reports, clamped to the ends)."""
    if t <= tr[0]["t"]:
        return tr[0]["lat"], tr[0]["lon"]
    for a, b in zip(tr, tr[1:]):
        if a["t"] <= t <= b["t"]:
            k = (t - a["t"]) / (b["t"] - a["t"])
            return a["lat"] + k * (b["lat"] - a["lat"]), a["lon"] + k * (b["lon"] - a["lon"])
    return tr[-1]["lat"], tr[-1]["lon"]


def random_time_on(tr, rng):
    """Time of a random point on the polyline (uniform by length)."""
    return time_at_fraction(tr, rng.random())


def time_at_fraction(tr, u):
    """Time of the point at distance u * (polyline length) from the start, u in [0, 1]."""
    seg = [haversine_m(a["lat"], a["lon"], b["lat"], b["lon"]) for a, b in zip(tr, tr[1:])]
    d = u * sum(seg)
    for (a, b), L in zip(zip(tr, tr[1:]), seg):
        if d <= L:
            return a["t"] + (d / L if L else 0) * (b["t"] - a["t"])
        d -= L
    return tr[-1]["t"]


def in_radius(lat, lon, r_m, rng):
    """Uniform random point inside a circle of radius r_m."""
    d, a = r_m * math.sqrt(rng.random()), rng.uniform(0, 2 * math.pi)
    return (lat + d * math.cos(a) / 111_320,
            lon + d * math.sin(a) / (111_320 * math.cos(math.radians(lat))))


def history_at(tracks, t):
    out = {}
    for vid, tr in tracks.items():
        seen = [p for p in tr if p["t"] <= t][-3:]
        if seen:
            out[vid] = [{"lat": p["lat"], "lon": p["lon"], "t": p["t"]} for p in seen]
    return out


def main():
    rng = random.Random(SEED)
    tracks = load_tracks(SAMPLE)
    line_of = {vid: tr[-1]["line"] for vid, tr in tracks.items()}
    moving = [vid for vid, tr in tracks.items() if len(tr) >= 5 and length_m(tr) >= 300]
    by_line: dict[str, list[str]] = {}
    for vid in moving:
        by_line.setdefault(line_of[vid], []).append(vid)
    lines = rng.sample(sorted(by_line), min(N_LINES, len(by_line)))
    targets = [rng.choice(by_line[ln]) for ln in lines]
    # Same random points for every radius, so radii are comparable.
    points = [(vid, random_time_on(tracks[vid], rng)) for vid in targets for _ in range(POINTS_PER_LINE)]
    print(f"sample: {SAMPLE.name}, buses: {len(tracks)}, moving: {len(moving)}, "
          f"lines: {', '.join(lines)}, trials per row: {len(points)}\n")

    print("| radius | points | top-1 | in popup (top-4) | right line in top-4 | median RMSE to own bus |")
    print("|---|---|---|---|---|---|")
    for r in RADII_M:
        for k in (1, 3):
            top1 = top4 = line4 = 0
            rmse = []
            for vid, tp in points:
                hist = history_at(tracks, tp)
                user = []
                for t in [tp - 10 * i for i in reversed(range(k))]:
                    lat, lon = in_radius(*at_time(tracks[vid], t), r, rng)
                    user.append({"lat": lat, "lon": lon, "t": t})
                ranked = rank_buses(user, hist, limit=len(hist))
                ids = [x["id"] for x in ranked]
                rank = ids.index(vid) + 1
                top1 += rank == 1
                top4 += rank <= POPUP
                line4 += line_of[vid] in {line_of[i] for i in ids[:POPUP]}
                rmse.append(ranked[rank - 1]["rmse_m"])
            n = len(points)
            print(f"| {r} m | {k} | {100 * top1 / n:.0f}% | {100 * top4 / n:.0f}% | {100 * line4 / n:.0f}% "
                  f"| {statistics.median(rmse):.0f} m |")


if __name__ == "__main__":
    main()
