"""Rebuild the HTML result pages of the nearest bus simulation in artifacts/.

Run from backend/:  uv run python ../algorithms/simulation/export_viz.py [sample.json]

- artifacts/bus-detection-simulation.html: replays simulate_nearest_buses.py with the same seed
  (same numbers as RESULTS.md), 5 random points per line.
- artifacts/bus-detection-fraction.html: the same 15 lines, 10 points per line, each point placed at
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
import simulate_nearest_buses as sim  # noqa: E402
from nearest_buses import rank_buses  # noqa: E402

TEMPLATE = REPO / "artifacts" / "templates" / "bus-detection-simulation.html"
OUT_RANDOM = REPO / "artifacts" / "bus-detection-simulation.html"
OUT_FRACTION = REPO / "artifacts" / "bus-detection-fraction.html"
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
    print("bench:", bench)


if __name__ == "__main__":
    main()
