"""Rebuild the HTML page with the simulation results: artifacts/bus-detection-simulation.html.

Run from backend/:  uv run python ../algorithms/simulation/export_viz.py [sample.json]
Replays simulate_nearest_buses.py with the same seed (same numbers as RESULTS.md), keeps every trial
and inlines the data into artifacts/templates/bus-detection-simulation.html.
"""
import json
import random
import statistics
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "algorithms"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import simulate_nearest_buses as sim  # noqa: E402
from nearest_buses import rank_buses  # noqa: E402

TEMPLATE = REPO / "artifacts" / "templates" / "bus-detection-simulation.html"
OUT = REPO / "artifacts" / "bus-detection-simulation.html"


def r5(x: float) -> float:
    return round(x, 5)


def build(sample: Path) -> dict:
    # Same steps and random draws, in the same order, as sim.main().
    rng = random.Random(sim.SEED)
    tracks = sim.load_tracks(sample)
    line_of = {vid: tr[-1]["line"] for vid, tr in tracks.items()}
    moving = [vid for vid, tr in tracks.items() if len(tr) >= 5 and sim.length_m(tr) >= 300]
    by_line: dict[str, list[str]] = {}
    for vid in moving:
        by_line.setdefault(line_of[vid], []).append(vid)
    lines = rng.sample(sorted(by_line), min(sim.N_LINES, len(by_line)))
    targets = [rng.choice(by_line[ln]) for ln in lines]
    points = [(vid, sim.random_time_on(tracks[vid], rng)) for vid in targets for _ in range(sim.POINTS_PER_LINE)]

    # Feed times are Warsaw wall-clock times stored as local epochs, so fromtimestamp() gives them back
    # in Warsaw time on any machine (the recorder's own clock may be in another zone).
    first_poll = json.loads(sample.read_text())[0]
    out = {
        "recorded": datetime.fromtimestamp(max(v["t"] for v in first_poll["vehicles"])).strftime("%d.%m.%Y, %H:%M"),
        "buses": len(tracks),
        "moving": len(moving),
        "lines": [{"line": line_of[v], "vid": v, "len_m": round(sim.length_m(tracks[v])),
                   "path": [[r5(p["lat"]), r5(p["lon"])] for p in tracks[v]]} for v in targets],
        "background": [[r5(tr[-1]["lat"]), r5(tr[-1]["lon"])] for tr in tracks.values()],
        "summary": [],
        "trials": [],
    }
    for r in sim.RADII_M:
        for k in (1, 3):
            top1 = top4 = line4 = 0
            rmse = []
            for i, (vid, tp) in enumerate(points):
                hist = sim.history_at(tracks, tp)
                user = []
                for t in [tp - 10 * j for j in reversed(range(k))]:
                    lat, lon = sim.in_radius(*sim.at_time(tracks[vid], t), r, rng)
                    user.append({"lat": lat, "lon": lon, "t": t})
                ranked = rank_buses(user, hist, limit=len(hist))
                ids = [x["id"] for x in ranked]
                rank = ids.index(vid) + 1
                top1 += rank == 1
                top4 += rank <= sim.POPUP
                line4 += line_of[vid] in {line_of[x] for x in ids[:sim.POPUP]}
                rmse.append(ranked[rank - 1]["rmse_m"])
                true = sim.at_time(tracks[vid], tp)
                out["trials"].append({
                    "r": r, "k": k, "i": i, "line": line_of[vid], "rank": rank,
                    "rmse": round(ranked[rank - 1]["rmse_m"]), "true": [r5(true[0]), r5(true[1])],
                    "user": [[r5(u["lat"]), r5(u["lon"])] for u in user],
                    "top": [{"line": line_of[x["id"]], "rmse": round(x["rmse_m"]), "own": x["id"] == vid}
                            for x in ranked[:sim.POPUP]],
                })
            n = len(points)
            out["summary"].append({"r": r, "k": k, "top1": round(100 * top1 / n), "top4": round(100 * top4 / n),
                                   "line4": round(100 * line4 / n), "rmse": round(statistics.median(rmse))})
    return out


def main():
    sample = Path(sys.argv[1]) if len(sys.argv) > 1 else sim.SAMPLE
    data = build(sample)
    html = TEMPLATE.read_text(encoding="utf-8").replace(
        "/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    OUT.write_text(html, encoding="utf-8")
    for s in data["summary"]:
        print(s)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
