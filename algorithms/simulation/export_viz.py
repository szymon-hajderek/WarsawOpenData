"""Rebuild the HTML result pages of the nearest bus simulation in artifacts/bus-detection/.

Run from backend/:  uv run python ../algorithms/simulation/export_viz.py [sample.json]

- artifacts/bus-detection/bus-detection-simulation.html: replays simulate_nearest_buses.py with the same seed
  (same numbers as RESULTS.md), 5 random points per line.
- artifacts/bus-detection/bus-detection-hotspots.html: hard cases on a bus + tram recording
  (data/live/vehicle_track_sample.json): 10 most crowded places and 10 lines with the most GTFS trips that day,
  5 points u * L each; skipped when that recording is missing.
- artifacts/bus-detection/bus-detection-fraction.html: the same 15 lines, 10 points per line, each point placed at
  distance u * (polyline length) with u drawn from U(0, 1) and shown on the page.
Both pages get a runtime benchmark of rank_buses (complexity section).
"""
import json
import math
import random
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "algorithms"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hotspots  # noqa: E402
import simulate_nearest_buses as sim  # noqa: E402
from nearest_buses import rank_buses  # noqa: E402

TEMPLATE = REPO / "artifacts" / "bus-detection" / "templates" / "bus-detection-simulation.html"
OUT_RANDOM = REPO / "artifacts" / "bus-detection" / "bus-detection-simulation.html"
OUT_FRACTION = REPO / "artifacts" / "bus-detection" / "bus-detection-fraction.html"
OUT_HOTSPOTS = REPO / "artifacts" / "bus-detection" / "bus-detection-hotspots.html"
HOT_SAMPLE = REPO / "data" / "live" / "vehicle_track_sample.json"
HOT_SEED, HOT_POINTS, HOT_N = 1018, 5, 10
PLACE_CELL_M, PLACE_RADIUS_M, PLACE_SEP_M = 300, 300, 600
IN_SERVICE_M = 100  # a vehicle counts for crowding only if it moved this far in the recording (no parked depots)
FRACTION_SEED, FRACTION_POINTS = 2026, 10
BENCH_SIZES = (250, 500, 1000, 2000, 4000, 8000)


def r5(x: float) -> float:
    return round(x, 5)


def choose_targets(tracks, line_of, rng):
    """Same steps and draws as sim.main(): 15 random lines, one moving vehicle each."""
    moving = [vid for vid, tr in tracks.items() if len(tr) >= 5 and sim.length_m(tr) >= 300]
    by_line: dict[str, list[str]] = {}
    for vid in moving:
        by_line.setdefault(line_of[vid], []).append(vid)
    lines = rng.sample(sorted(by_line), min(sim.N_LINES, len(by_line)))
    return moving, [rng.choice(by_line[ln]) for ln in lines]


def run_trials(tracks, line_of, points, rng):
    """points: [(vehicle id, time, u or None)]. Returns (summary rows, trials, seconds per rank_buses call)."""
    summary, trials, secs = [], [], []
    for r in sim.RADII_M:
        for k in (1, 3):
            top1 = top4 = line4 = 0
            rmse = []
            for i, (vid, tp, u) in enumerate(points):
                hist = sim.history_at(tracks, tp)
                user = []
                for t in [tp - 10 * j for j in reversed(range(k))]:
                    lat, lon = sim.in_radius(*sim.at_time(tracks[vid], t), r, rng)
                    user.append({"lat": lat, "lon": lon, "t": t})
                t0 = time.perf_counter()
                ranked = rank_buses(user, hist, limit=len(hist))
                secs.append(time.perf_counter() - t0)
                ids = [x["id"] for x in ranked]
                rank = ids.index(vid) + 1
                top1 += rank == 1
                top4 += rank <= sim.POPUP
                line4 += line_of[vid] in {line_of[x] for x in ids[:sim.POPUP]}
                rmse.append(ranked[rank - 1]["rmse_m"])
                true = sim.at_time(tracks[vid], tp)
                trials.append({
                    "r": r, "k": k, "i": i, "line": line_of[vid], "rank": rank, "u": None if u is None else round(u, 3),
                    "rmse": round(ranked[rank - 1]["rmse_m"]), "true": [r5(true[0]), r5(true[1])],
                    "user": [[r5(x["lat"]), r5(x["lon"])] for x in user],
                    "top": [{"line": line_of[x["id"]], "rmse": round(x["rmse_m"]), "own": x["id"] == vid}
                            for x in ranked[:sim.POPUP]],
                })
            n = len(points)
            summary.append({"r": r, "k": k, "top1": round(100 * top1 / n), "top4": round(100 * top4 / n),
                            "line4": round(100 * line4 / n), "rmse": round(statistics.median(rmse))})
    return summary, trials, secs


def benchmark():
    """Median time of one rank_buses call (3 user points, 3 reports per bus) for a growing number of buses."""
    rng = random.Random(1)
    user = [{"lat": 52.23 + 0.001 * i, "lon": 21.0, "t": 10.0 * i} for i in range(3)]
    rows = []
    for v in BENCH_SIZES:
        hist = {f"b{j}": [{"lat": 52.1 + 0.25 * rng.random(), "lon": 20.85 + 0.35 * rng.random(), "t": 10.0 * i}
                          for i in range(3)] for j in range(v)}
        runs = []
        for _ in range(15):
            t0 = time.perf_counter()
            rank_buses(user, hist, limit=4)
            runs.append(time.perf_counter() - t0)
        rows.append({"v": v, "ms": round(1000 * statistics.median(runs), 2)})
    return rows


def page_data(sample, tracks, line_of, moving, targets, per, summary, trials, secs, bench, mode):
    first_poll = json.loads(sample.read_text())[0]
    reports = [len(tr) for tr in tracks.values()]
    return {
        "mode": mode, "per": per,
        # Feed times are Warsaw wall-clock times stored as local epochs, so fromtimestamp() gives them back
        # in Warsaw time on any machine (the recorder's own clock may be in another zone).
        "recorded": datetime.fromtimestamp(max(v["t"] for v in first_poll["vehicles"])).strftime("%d.%m.%Y, %H:%M"),
        "buses": len(tracks), "moving": len(moving), "max_reports": max(reports),
        "lines": [{"line": line_of[v], "vid": v, "len_m": round(sim.length_m(tracks[v])),
                   "path": [[r5(p["lat"]), r5(p["lon"])] for p in tracks[v]]} for v in targets],
        "background": [[r5(tr[-1]["lat"]), r5(tr[-1]["lon"])] for tr in tracks.values()],
        "summary": summary, "trials": trials,
        "req_ms": round(1000 * statistics.median(secs), 2), "bench": bench,
    }


def trips_per_line(date: str) -> dict[tuple[str, str], int]:
    """(mode, line) -> number of ZTM bus / tram trips on that date (GTFS, needs the backend's caches)."""
    sys.path.insert(0, str(REPO / "backend"))
    from sources import mkuran
    routes, services = mkuran.routes(), mkuran.services()
    out: dict[tuple[str, str], int] = {}
    for trip in mkuran.trips():
        route = routes.get(trip[1])
        if route and route["feed"] == "ztm" and route["mode"] in ("bus", "tram") and date in services.get(trip[2], ()):
            key = (route["mode"], route["short_name"])
            out[key] = out.get(key, 0) + 1
    return out


def nearest_stop_name(lat: float, lon: float) -> str:
    sys.path.insert(0, str(REPO / "backend"))
    from sources import mkuran
    stops = [s for s in mkuran.stops() if s["feed"] == "ztm" and s.get("boarding")]
    return min(stops, key=lambda s: hotspots.haversine_m(lat, lon, s["lat"], s["lon"]))["name"]


def group_summary(trials: list[dict], keep) -> list[dict]:
    out = []
    for r in sim.RADII_M:
        for k in (1, 3):
            rows = [t for t in trials if t["r"] == r and t["k"] == k and keep(t)]
            n = len(rows)
            out.append({"r": r, "k": k, "top1": round(100 * sum(t["rank"] == 1 for t in rows) / n),
                        "top4": round(100 * sum(t["rank"] <= sim.POPUP for t in rows) / n),
                        "line4": round(100 * sum(any(c["line"] == t["line"] for c in t["top"]) for t in rows) / n),
                        "rmse": round(statistics.median(t["rmse"] for t in rows))})
    return out


def hotspots_page(bench) -> None:
    sample = HOT_SAMPLE
    snaps = json.loads(sample.read_text())
    tracks = sim.load_tracks(sample)
    line_of = {vid: tr[-1]["line"] for vid, tr in tracks.items()}
    mode_of = {vid: tr[-1].get("mode", "bus") for vid, tr in tracks.items()}
    moving = [vid for vid, tr in tracks.items() if len(tr) >= 5 and sim.length_m(tr) >= 300]
    rng = random.Random(HOT_SEED)
    points, targets = [], []

    # 10 most crowded places: one vehicle that passed through each, 5 points u * L on the part near the place.
    in_service = {vid for vid, tr in tracks.items() if sim.length_m(tr) >= IN_SERVICE_M}
    for cell in hotspots.crowded_cells(snaps, PLACE_CELL_M, top=3 * HOT_N, min_sep_m=PLACE_SEP_M, only=in_service):
        if len([t for t in targets if t["group"] == "place"]) == HOT_N:
            break
        passing = []
        for vid in sorted(in_service):
            part = hotspots.near_part(tracks[vid], cell["lat"], cell["lon"], PLACE_RADIUS_M)
            if len(tracks[vid]) >= 3 and part and hotspots.path_length_m(part) >= 60:
                passing.append((vid, part))
        if not passing:
            continue
        vid, part = rng.choice(passing)
        targets.append({"vid": vid, "group": "place", "place": nearest_stop_name(cell["lat"], cell["lon"]),
                        "count": cell["count"], "centre": [r5(cell["lat"]), r5(cell["lon"])],
                        "part_m": round(hotspots.path_length_m(part))})
        for _ in range(HOT_POINTS):
            u = rng.random()
            points.append((vid, sim.time_at_fraction(part, u), u))

    # 10 lines with the most GTFS trips that day: one moving vehicle each, 5 points u * L on its whole track.
    date = datetime.fromtimestamp(max(v["t"] for v in snaps[0]["vehicles"])).strftime("%Y%m%d")
    freq = trips_per_line(date)
    for (mode, line), n in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0])):
        if len([t for t in targets if t["group"] == "line"]) == HOT_N:
            break
        cands = sorted(v for v in moving if line_of[v] == line and mode_of[v] == mode)
        if not cands:
            continue
        vid = rng.choice(cands)
        targets.append({"vid": vid, "group": "line", "trips": n})
        for _ in range(HOT_POINTS):
            u = rng.random()
            points.append((vid, sim.time_at_fraction(tracks[vid], u), u))

    summary, trials, secs = run_trials(tracks, line_of, points, random.Random(HOT_SEED + 1))
    n_place = HOT_POINTS * len([t for t in targets if t["group"] == "place"])
    data = page_data(sample, tracks, line_of, moving, [t["vid"] for t in targets], HOT_POINTS,
                     summary, trials, secs, bench, "hotspots")
    for entry, t in zip(data["lines"], targets):
        entry.update({k: v for k, v in t.items() if k != "vid"}, mode=mode_of[t["vid"]])
    data["groups"] = [
        {"id": "place", "name": "10 najbardziej zatłoczonych miejsc", "summary": group_summary(trials, lambda t: t["i"] < n_place)},
        {"id": "line", "name": "10 najczęstszych linii", "summary": group_summary(trials, lambda t: t["i"] >= n_place)},
    ]
    data["trams"] = sum(1 for m in mode_of.values() if m == "tram")
    write(OUT_HOTSPOTS, data, "Tłok na mieście")


def write(path: Path, data: dict, title: str):
    html = (TEMPLATE.read_text(encoding="utf-8").replace("__TITLE__", title)
            .replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
    path.write_text(html, encoding="utf-8")
    print(f"wrote {path}")
    for s in data["summary"]:
        print("  ", s)


def main():
    sample = Path(sys.argv[1]) if len(sys.argv) > 1 else sim.SAMPLE
    tracks = sim.load_tracks(sample)
    line_of = {vid: tr[-1]["line"] for vid, tr in tracks.items()}
    bench = benchmark()

    # Page 1: the RESULTS.md run (same rng sequence as sim.main()).
    rng = random.Random(sim.SEED)
    moving, targets = choose_targets(tracks, line_of, rng)
    points = [(vid, sim.random_time_on(tracks[vid], rng), None) for vid in targets for _ in range(sim.POINTS_PER_LINE)]
    summary, trials, secs = run_trials(tracks, line_of, points, rng)
    write(OUT_RANDOM, page_data(sample, tracks, line_of, moving, targets, sim.POINTS_PER_LINE,
                                summary, trials, secs, bench, "random"), "Którym autobusem jadę?")

    # Page 2: same lines, u ~ U(0, 1) drawn explicitly, point at u * length.
    _, targets = choose_targets(tracks, line_of, random.Random(sim.SEED))
    urng = random.Random(FRACTION_SEED)
    points = []
    for vid in targets:
        for _ in range(FRACTION_POINTS):
            u = urng.random()
            points.append((vid, sim.time_at_fraction(tracks[vid], u), u))
    summary, trials, secs = run_trials(tracks, line_of, points, random.Random(FRACTION_SEED + 1))
    write(OUT_FRACTION, page_data(sample, tracks, line_of, moving, targets, FRACTION_POINTS,
                                  summary, trials, secs, bench, "fraction"), "Punkt u·L na trasie")
    if HOT_SAMPLE.exists():
        hotspots_page(bench)
    print("bench:", bench)


if __name__ == "__main__":
    main()
