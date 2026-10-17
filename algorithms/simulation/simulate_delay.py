"""How exact is the delay estimate (algorithms/bus_delay.py)? Replay a recording and compare with the full track.

Run from backend/:  uv run python ../algorithms/simulation/simulate_delay.py [--radius 30] [--drop 0.1] [--noise 10]
                    [--sample data/live/delay_sample.json.gz] [--all-lines]

Reference ("prawda"): for every stop a vehicle crosses, the moment its full recorded track crosses the stop's
distance along the trip shape (linear between two feed points at most MAX_GAP_S apart). Reference delay = that -
scheduled departure.

Simulated server: the same feed points arrive one by one, as on the live server: buffer with midpoints, no midpoint
after a lost poll (a real failed poll from the recording, or a dropped one with probability `drop`), GPS noise of
up to `noise_m` metres. After each point `estimate` runs; the first available estimate for stop K-1 is what the user
would see at stop K. It is compared with the reference delay of the same vehicle, trip and stop.

`evaluate(...)` is the function to call from other scripts. `evaluate_many(...)` scores many radii in one replay
(trip match and K-1 do not depend on R, only "is the closest buffered point within R"); search_delay_radius.py uses it.
"""
import argparse
import gzip
import json
import random
import statistics
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "algorithms"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bus_delay import MAX_GAP_S, WINDOW_S, add_point, estimate, match_trip  # noqa: E402
from nearest_buses import haversine_m  # noqa: E402
from simulate_nearest_buses import in_radius  # noqa: E402
from sources import mkuran  # noqa: E402

SAMPLE = REPO / "data" / "live" / "delay_sample.json.gz"
BUFFER_MARGIN_S, BUFFER_DEFAULT_S = 60, 600  # as in backend/bus_detect.py


def load(path: Path = SAMPLE) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        sample = json.load(f)
    sample["midnight"] = datetime.fromisoformat(sample["date"]).timestamp()  # naive local, like mkuran
    return sample


@lru_cache(maxsize=None)
def _trips(line: str, brigade: str, minute: int) -> tuple:
    """Candidate trips of a brigade around a time (cached per 10 minutes)."""
    return tuple(mkuran.brigade_trips(line, brigade, datetime.fromtimestamp(minute * 600), WINDOW_S + 600))


@lru_cache(maxsize=None)
def _keep_s(line: str, brigade: str, minute: int) -> float:
    seg = mkuran.max_segment_for(line, brigade, datetime.fromtimestamp(minute * 60))
    return BUFFER_DEFAULT_S if seg is None else seg + BUFFER_MARGIN_S


def _runs(sample: dict, lines: set | None):
    """(vehicle id, mode, line, brigade, points with epoch t) of every recorded run."""
    base = sample["midnight"]
    for vid, veh in sample["vehicles"].items():
        for run in veh["runs"]:
            if lines is not None and run["line"] not in lines:
                continue
            pts = [{"lat": lat, "lon": lon, "t": base + t} for t, lat, lon in run["points"]]
            if len(pts) >= 3:
                yield vid, veh["mode"], run["line"], run["brigade"], pts


def _trips_for(line, brigade, t):
    return list(_trips(line, brigade, int(t // 600)))


def reference(line: str, brigade: str, pts: list[dict]) -> dict:
    """(trip id, stop id) -> {"t", "delay_s", "stop", "trip"} from the full track."""
    out, prev, last = {}, None, None
    for p in pts:
        hit = match_trip(_trips_for(line, brigade, p["t"]), p["lat"], p["lon"], p["t"], prev)
        if hit is None:
            prev = last = None
            continue
        trip, along = hit
        prev = {"trip_id": trip["trip_id"], "dist": along}
        if last and last[0]["trip_id"] == trip["trip_id"] and 0 < p["t"] - last[2] <= MAX_GAP_S and along > last[1]:
            for s in trip["stops"]:
                if last[1] < s["dist"] <= along:
                    t = last[2] + (s["dist"] - last[1]) / (along - last[1]) * (p["t"] - last[2])
                    out[(trip["trip_id"], s["id"])] = {"t": t, "delay_s": round(t - s["sched"]), "stop": s,
                                                       "trip": trip}
        last = (trip, along, p["t"])
    return out


def _failed_polls(sample: dict) -> dict[str, list[float]]:
    base = sample["midnight"]
    out = {"bus": [], "tram": []}
    for t, mode, ok in sample["polls"]:
        if not ok:
            out[mode].append(base + t)
    return out


def simulate(line, brigade, mode, pts, drop, noise_m, rng, failed) -> dict:
    """(trip id, stop id) -> [(distance of the closest buffered point to the stop m, delay at that point s)], one item
    per feed point while the stop was K-1. For a radius R the server shows the first item with distance <= R."""
    out, buf, prev, broken, last_t = {}, [], None, False, None
    for p in pts:
        if drop and rng.random() < drop:
            broken = True  # this poll was lost: the point never arrives
            continue
        if last_t is not None and any(last_t < f < p["t"] for f in failed[mode]):
            broken = True
        point = dict(p)
        if noise_m:
            point["lat"], point["lon"] = in_radius(p["lat"], p["lon"], noise_m, rng)
        add_point(buf, point, broken, _keep_s(line, brigade, int(p["t"] // 60)))
        broken, last_t = False, p["t"]
        r = estimate(buf, _trips_for(line, brigade, p["t"]), float("inf"), prev)
        if r["trip"] is not None:
            prev = {"trip_id": r["trip"]["trip_id"], "dist": r["dist"]}
        if r["prev_index"] is None:
            continue
        stop = r["trip"]["stops"][r["prev_index"]]
        closest = next(b for b in buf if b["t"] == r["passed_at"])
        d = haversine_m(closest["lat"], closest["lon"], stop["lat"], stop["lon"])
        out.setdefault((r["trip"]["trip_id"], stop["id"]), []).append((d, r["delay_s"]))
    return out


def _shown(observations, radius_m):
    """The delay the server shows for a stop with radius R: the first observation within R, else None."""
    return next((delay for d, delay in observations if d <= radius_m), None)


def _q(values, p):
    v = sorted(values)
    return v[min(len(v) - 1, int(p / 100 * len(v)))] if v else None


ACCURATE_S = 30  # an estimate within this many seconds of the reference counts as accurate


def _metrics(pairs, skipped, radius_m, drop, noise_m) -> dict:
    ok = [p for p in pairs if p["est"] is not None]
    err = [p["est"] - p["ref"] for p in ok]
    accurate = sum(abs(e) <= ACCURATE_S for e in err)
    return {"radius_m": radius_m, "drop": drop, "noise_m": noise_m, "pairs_n": len(pairs), "skipped_n": skipped,
            "available_n": len(ok), "available": len(ok) / len(pairs) if pairs else 0.0,
            "err_median": statistics.median(err) if err else None,
            "abs_err_median": statistics.median(abs(e) for e in err) if err else None,
            "abs_err_p90": _q([abs(e) for e in err], 90),
            "within_30s": accurate / len(err) if err else 0.0,
            # score of a radius: share of ALL passes shown with an accurate delay (availability and accuracy together)
            "score": accurate / len(pairs) if pairs else 0.0}


def evaluate_many(sample: dict, radii, drop: float = 0.0, noise_m: float = 0.0, seed: int = 42,
                  lines: set | None = None, keep_pairs: bool = False) -> list[dict]:
    """Metrics for every radius in `radii`, from one replay. A pair = (vehicle, trip, stop) the reference saw crossed.

    available = share of pairs with an estimate; error = estimate - reference (s); score = share of pairs with an
    estimate within ACCURATE_S of the reference.
    """
    rng = random.Random(seed)
    lines = set(sample["lines"]) if lines is None else lines
    failed = _failed_polls(sample)
    rows, skipped = [], 0
    for vid, mode, line, brigade, pts in _runs(sample, lines or None):
        ref = reference(line, brigade, pts)
        obs = simulate(line, brigade, mode, pts, drop, noise_m, rng, failed)
        for key, rv in ref.items():
            if key not in obs:  # the estimator never had this stop as K-1 (e.g. passed two stops between points)
                skipped += 1
                continue
            s = rv["stop"]
            rows.append(({"vehicle": vid, "mode": mode, "line": line, "trip": key[0], "stop": s["id"],
                          "name": s["name"], "lat": s["lat"], "lon": s["lon"], "sched": s["sched"],
                          "ref": rv["delay_s"]}, obs[key]))
    out = []
    for r in radii:
        pairs = [{**p, "est": _shown(o, r)} for p, o in rows]
        m = _metrics(pairs, skipped, r, drop, noise_m)
        if keep_pairs:
            m["pairs"] = pairs
        out.append(m)
    return out


def evaluate(sample: dict, radius_m: float = 30, drop: float = 0.0, noise_m: float = 0.0, seed: int = 42,
             lines: set | None = None, keep_pairs: bool = False) -> dict:
    """Metrics of one radius (see evaluate_many)."""
    return evaluate_many(sample, [radius_m], drop, noise_m, seed, lines, keep_pairs)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=Path, default=SAMPLE)
    ap.add_argument("--radius", type=float, default=30)
    ap.add_argument("--drop", type=float, default=0.0)
    ap.add_argument("--noise", type=float, default=0.0)
    ap.add_argument("--all-lines", action="store_true", help="every recorded line, not only the sample's LINES")
    a = ap.parse_args()
    sample = load(a.sample)
    m = evaluate(sample, a.radius, a.drop, a.noise, lines=set() if a.all_lines else None)
    print(json.dumps(m, indent=1))


if __name__ == "__main__":
    main()
