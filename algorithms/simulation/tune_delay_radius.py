"""Pick the radius R for the delay estimate (algorithms/bus_delay.py) on live data.

Polls live ZTM buses and trams (City Hall API, needs PORTAL_KEY in .env) every 3 s for a few minutes and keeps
the same buffer as the server (midpoints, breaks after failed polls, per-trip length). Every 60 s, for every
vehicle and every R, it runs `estimate` and counts how often the delay is available and what it is.

Run from backend/:  uv run python ../algorithms/simulation/tune_delay_radius.py [minutes]
Prints a Markdown table; results of a run are in algorithms/simulation/DELAY_RESULTS.md.
"""
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "algorithms"))
from bus_delay import WINDOW_S, add_point, estimate  # noqa: E402
from sources import mkuran  # noqa: E402
from sources.um_warszawa import fetch_vehicles, fresh  # noqa: E402

RADII = [20, 30, 50, 75, 100]
POLL_S, EVAL_S = 3, 60
MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 6


def local(t: str) -> datetime:
    return datetime.strptime(t, "%Y-%m-%d %H:%M:%S")


buffers: dict[str, list] = {}
info: dict[str, dict] = {}
broken: set[str] = set()
prev: dict[tuple, dict] = {}  # (vehicle, R) -> last projection
reasons = {r: Counter() for r in RADII}
delays = defaultdict(list)
evals = 0

print("loading GTFS ...", flush=True)
mkuran.warm()
end = time.time() + MINUTES * 60
next_eval = time.time() + EVAL_S
polls = failed = 0
while time.time() < end:
    t0 = time.time()
    for mode in ("bus", "tram"):
        try:
            rows = fresh(fetch_vehicles(mode))
        except Exception as e:  # a failed poll is a break in the data, like on the server
            failed += 1
            broken.update(v for v, i in info.items() if i["mode"] == mode)
            print(f"{mode} poll failed: {e}", flush=True)
            continue
        polls += 1
        for v in rows:
            vid = f"{mode}-{v['vehicle']}"
            info[vid] = {"line": v["line"], "brigade": v["brigade"], "mode": mode}
            buf = buffers.setdefault(vid, [])
            point = {"lat": v["lat"], "lon": v["lon"], "t": local(v["time"]).timestamp()}
            if buf and point["t"] <= buf[-1]["t"]:
                continue
            seg = mkuran.max_segment_for(v["line"], v["brigade"], local(v["time"]))
            add_point(buf, point, vid in broken, 600 if seg is None else seg + 60)
            broken.discard(vid)
    if time.time() >= next_eval:
        next_eval += EVAL_S
        evals += 1
        for vid, buf in buffers.items():
            if not buf or time.time() - buf[-1]["t"] > 120:
                continue
            trips = mkuran.brigade_trips(info[vid]["line"], info[vid]["brigade"],
                                         datetime.fromtimestamp(buf[-1]["t"]), WINDOW_S)
            for r in RADII:
                res = estimate(buf, trips, r, prev.get((vid, r)))
                if res["trip"] is not None:
                    prev[(vid, r)] = {"trip_id": res["trip"]["trip_id"], "dist": res["dist"]}
                reasons[r][res["reason"] or "available"] += 1
                if res["available"]:
                    delays[r].append(res["delay_s"])
        print(f"eval {evals}: {len(buffers)} vehicles, R=30 m available {reasons[30]['available']}", flush=True)
    time.sleep(max(0.0, POLL_S - (time.time() - t0)))


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(p / 100 * len(values)))] if values else None


print(f"\n{datetime.now():%Y-%m-%d %H:%M}, {MINUTES:g} min, {polls} polls ok, {failed} failed, {evals} evaluations\n")
print("| R (m) | samples | available | of samples with K-1 found | no trip | outside trip | no pass in R "
      "| median delay (s) | p10 / p90 (s) |")
print("|---|---|---|---|---|---|---|---|---|")
for r in RADII:
    c = reasons[r]
    total = sum(c.values())
    with_k1 = c["available"] + c["no_pass_in_radius"]
    share = lambda n, d: f"{100 * n / d:.0f}%" if d else "-"
    d = delays[r]
    print(f"| {r} | {total} | {share(c['available'], total)} | {share(c['available'], with_k1)} | {c['no_trip']} "
          f"| {c['outside_trip']} | {c['no_pass_in_radius']} | {statistics.median(d) if d else '-'} "
          f"| {pct(d, 10)} / {pct(d, 90)} |")
