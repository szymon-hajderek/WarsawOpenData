"""Build the HTML report of the delay simulation: artifacts/delays/delay-statistics.html.

Run from backend/:  uv run python ../algorithms/simulation/export_delay_viz.py [--radius 30] [--sample ...]

Runs simulate_delay.evaluate for the base setting and the variants (lost polls, GPS noise), compares the live
server's answers from the recording with the reference, and inlines everything into the template
artifacts/delays/templates/delay-statistics.html (slot /*__DATA__*/null).
"""
import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search_delay_radius as srch  # noqa: E402
import simulate_delay as sd  # noqa: E402

REPO = sd.REPO
TEMPLATE = REPO / "artifacts" / "delays" / "templates" / "delay-statistics.html"
OUT = REPO / "artifacts" / "delays" / "delay-statistics.html"
VARIANTS = [("drop", 0.1), ("drop", 0.3), ("noise", 10), ("noise", 20)]
WARMUP_S = 300  # live answers in the first 5 minutes: the server buffer was still filling


def clock(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%H:%M:%S")


def med(v):
    return statistics.median(v) if v else None


def summary(m: dict) -> dict:
    return {k: m[k] for k in ("radius_m", "drop", "noise_m", "pairs_n", "skipped_n", "available_n", "available",
                              "err_median", "abs_err_median", "abs_err_p90", "within_30s", "score")}


def shape_points(shape, n=160):
    _, lat, lon = shape
    step = max(1, len(lat) // n)
    pts = [[round(float(lat[i]), 5), round(float(lon[i]), 5)] for i in range(0, len(lat), step)]
    pts.append([round(float(lat[-1]), 5), round(float(lon[-1]), 5)])
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=Path, default=sd.SAMPLE)
    ap.add_argument("--radius", type=float, default=30)
    a = ap.parse_args()
    sample = sd.load(a.sample)
    lines = sample["lines"]

    print("base run ...", flush=True)
    base = sd.evaluate(sample, a.radius, keep_pairs=True)
    variants = [summary(base)]
    for kind, value in VARIANTS:
        print(f"variant {kind}={value} ...", flush=True)
        kw = {"drop": value} if kind == "drop" else {"noise_m": value}
        variants.append(summary(sd.evaluate(sample, a.radius, **kw)))
    pairs = base["pairs"]

    print("radius search ...", flush=True)
    found = srch.search(sample)
    pick = lambda m: {k: m[k] for k in ("radius_m", "score", "available", "abs_err_median", "abs_err_p90")}
    search = {"coarse": [pick(m) for m in found["coarse"]], "fine": [pick(m) for m in found["fine"]],
              "pair": found["pair"], "best": pick(found["best"]), "accurate_s": sd.ACCURATE_S}

    # reference per (vehicle, trip, stop) + one shape per line and direction, for the live check and the maps
    refs, shapes, vehicles_per_line = {}, defaultdict(dict), defaultdict(set)
    for vid, mode, line, brigade, pts in sd._runs(sample, set(lines)):
        vehicles_per_line[line].add(vid)
        for (trip_id, stop_id), rv in sd.reference(line, brigade, pts).items():
            refs[(vid, trip_id, stop_id)] = rv
            head = rv["trip"]["headsign"]
            if head not in shapes[line]:
                shapes[line][head] = shape_points(rv["trip"]["shape"])

    # what the live server answered during the recording
    first_t = min(t for t, _, _ in sample["polls"]) + sample["midnight"]
    # one row per (vehicle, trip, stop K-1): the server is asked every 30 s, the first available answer counts
    by_key = {}
    for row in sample["live"]:
        ans = row["answer"]
        if sample["midnight"] + row["t"] - first_t < WARMUP_S or not ans.get("prevStop"):
            continue
        key = (ans["vehicleId"], ans["tripId"], ans["prevStop"]["id"])
        rv = refs.get(key)
        if rv is None:
            continue
        if key not in by_key or (ans["available"] and not by_key[key]["available"]):
            by_key[key] = {"line": ans["line"], "available": ans["available"], "est": ans["delaySec"],
                           "ref": rv["delay_s"]}
    live_rows = list(by_key.values())
    live_ok = [r for r in live_rows if r["available"]]
    live_err = [r["est"] - r["ref"] for r in live_ok]
    live = {"answers": len(live_rows), "available": len(live_ok) / len(live_rows) if live_rows else 0,
            "abs_err_median": med([abs(e) for e in live_err]), "abs_err_p90": sd._q([abs(e) for e in live_err], 90),
            "within_30s": sum(abs(e) <= 30 for e in live_err) / len(live_err) if live_err else 0,
            "points": [[r["ref"], r["est"]] for r in live_ok][:600]}

    # per line and per stop (base run)
    by_line = defaultdict(list)
    by_stop = defaultdict(list)
    for p in pairs:
        by_line[p["line"]].append(p)
        by_stop[(p["line"], p["name"])].append(p)
    per_line = []
    for line in lines:
        ps = by_line.get(line, [])
        ok = [p for p in ps if p["est"] is not None]
        stops = defaultdict(lambda: [0, 0, None, None])
        for p in ps:
            s = stops[p["stop"]]
            s[0] += 1
            s[1] += p["est"] is not None
            s[2], s[3] = p["lat"], p["lon"]
        per_line.append({
            "line": line, "mode": ps[0]["mode"] if ps else ("tram" if len(line) <= 2 else "bus"),
            "vehicles": len(vehicles_per_line.get(line, ())), "pairs": len(ps), "available": len(ok) / len(ps) if ps else 0,
            "abs_err_median": med([abs(p["est"] - p["ref"]) for p in ok]),
            "ref_delay_median": med([p["ref"] for p in ps]),
            "shapes": list(shapes.get(line, {}).values())[:2],
            "stops": [[round(v[2], 5), round(v[3], 5), v[0], v[1]] for v in stops.values()]})
    per_stop = []
    for (line, name), ps in sorted(by_stop.items(), key=lambda kv: -len(kv[1]))[:18]:
        ok = [p for p in ps if p["est"] is not None]
        per_stop.append({"line": line, "name": name, "passes": len(ps), "available": len(ok) / len(ps),
                         "abs_err_median": med([abs(p["est"] - p["ref"]) for p in ok]),
                         "ref_delay_median": med([p["ref"] for p in ps])})

    # one vehicle, stop by stop
    best = max(by_line.values(), key=len, default=[])
    story = []
    if best:
        vid = max({p["vehicle"] for p in best}, key=lambda v: sum(p["vehicle"] == v for p in best))
        story = [{"name": p["name"], "sched": clock(p["sched"]), "ref": p["ref"], "est": p["est"]}
                 for p in sorted((p for p in best if p["vehicle"] == vid), key=lambda p: p["sched"])][:14]
        story = {"vehicle": vid, "line": best[0]["line"], "rows": story}

    ok = [p for p in pairs if p["est"] is not None]
    times = [t for v in sample["vehicles"].values() for r in v["runs"] for t, _, _ in r["points"]]
    data = {
        "meta": {"date": sample["date"], "from": clock(sample["midnight"] + min(times)),
                 "to": clock(sample["midnight"] + max(times)), "minutes": sample["minutes"], "lines": lines,
                 "vehicles_all": len(sample["vehicles"]), "points_all": len(times),
                 "polls": len(sample["polls"]), "failed_polls": sum(1 for p in sample["polls"] if not p[2]),
                 "radius_m": a.radius, "warmup_s": WARMUP_S},
        "variants": variants, "search": search,
        "errors": [p["est"] - p["ref"] for p in ok],
        "scatter": [[p["ref"], p["est"], p["line"]] for p in ok][:1500],
        "per_line": per_line, "per_stop": per_stop, "live": live, "story": story,
    }
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    OUT.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps(variants, indent=1))
    print("best R:", search["best"], "pair:", search["pair"])
    print("live:", {k: v for k, v in live.items() if k != "points"})
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
