"""Trial report for the Veturilo station siting (sources/siting.py).

Usage (from backend/):
    uv run python siting_report.py            # report + HTML from the cached hex grid
    uv run python siting_report.py --rebuild  # recompute the hex grid first
    uv run python siting_report.py --mocks    # regenerate the mock measurements (fixed seed), then rebuild

Writes data/SITING_REPORT.md, data/siting_report.json and artifacts/veturilo-siting.html.
"""
import argparse
import json
import math

import numpy as np

from config import DATA, REPO, load_json, save_json
from sources import nextbike, siting
from station_siting import DEFAULTS, HEX_SIZE_M

N = 10
TEMPLATE = REPO / "artifacts" / "templates" / "veturilo-siting.html"
OUT = REPO / "artifacts" / "veturilo-siting.html"


def pct(a) -> dict:
    a = np.asarray(a, dtype=float)
    a = a[np.isfinite(a)]
    q = np.percentile(a, [0, 25, 50, 75, 100])
    return {"min": q[0], "p25": q[1], "median": q[2], "p75": q[3], "max": q[4], "mean": float(a.mean())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--mocks", action="store_true")
    args = ap.parse_args()
    if args.mocks:
        print("mocks:", siting.make_mocks())
    h = siting.hexes(rebuild=args.rebuild or args.mocks)
    p = dict(DEFAULTS)
    steps = siting.run(N, **p)
    options = [siting.option(h, k + 1, s, p) for k, s in enumerate(steps)]

    tc = load_json(siting.TRAFFIC)["counters"]
    sc = load_json(siting.SCOOTERS)
    stations = nextbike.stations()
    stats = {k: pct(h[k]) for k in ("t_raw", "t", "e", "s")}
    stats["d_net"] = pct(h["d_net"])
    summary = {"hexes": int(len(h["q"])), "candidates": int(h["candidate"].sum()),
               "station_hexes": int((h["stations"] > 0).sum()), "stations": len(stations),
               "no_streets": int(h["no_streets"].sum()), "beyond_max_r": int(np.isinf(h["d_net"]).sum()),
               "counters": len(tc), "hexes_with_counter": int((h["t_counters"] > 0).sum()),
               "scooter_hexes": len(sc["value"]), "hexes_with_scooter_value": int((h["e_values"] > 0).sum())}
    save_json(DATA / "siting_report.json", {"mock": True, "params": p, "hex_size_m": HEX_SIZE_M,
                                            "summary": summary, "stats": stats, "options": options})
    write_markdown(p, summary, stats, options)
    write_html(h, p, steps, options, tc, stations, summary)
    print(f"wrote data/SITING_REPORT.md, data/siting_report.json, {OUT.relative_to(REPO)}")


def write_markdown(p, summary, stats, options) -> None:
    f = lambda v, d=2: "inf" if math.isinf(v) else f"{v:.{d}f}"  # noqa: E731
    lines = [
        "# Veturilo station siting: trial report",
        "",
        "> **T (car traffic) and E (e-scooters) are MOCK data** (`data/mock/`, fixed seed). S comes from OpenStreetMap,",
        "> d_net from the OSM bike graph and the real Veturilo stations. Rebuild: `cd backend && uv run python siting_report.py`.",
        "",
        "## Cost",
        "",
        "J(p) = -α·T(p)·(1 + δ·E(p)) + β·P(d_net(p)) + γ·S(p),  P(d) = (1 - d/R)² for d < R, else 0. Lower is better.",
        "",
        f"Parameters: α = {p['alpha']}, β = {p['beta']}, γ = {p['gamma']}, δ = {p['delta']}, R = {p['r']:.0f} m, "
        f"hex radius {HEX_SIZE_M:.0f} m. Proposals are picked greedily: after each pick a station is placed there and "
        "d_net is updated (Dijkstra from the new station), so the next pick is not next door.",
        "",
        "## Data",
        "",
        f"- {summary['hexes']} hexes inside the Warsaw boundary; {summary['candidates']} candidates "
        f"({summary['station_hexes']} hexes already have one of {summary['stations']} stations, "
        f"{summary['no_streets']} have no street).",
        f"- T: {summary['counters']} mock counters in {summary['hexes_with_counter']} hexes; the rest by IDW "
        "(6 nearest, power 2); normalised to 0..1 at the 99th percentile.",
        f"- E: mock e-scooter crowding index 0..1 for {summary['scooter_hexes']} hexagons of 175 m (the format the city "
        "receives from operators), averaged per our hex; our hexes without a value by IDW.",
        "- S: length-weighted mean of the OSM street segments in the hex: 0 bike path (DDR / CPR), 0.3 quiet street or "
        "painted bike lane, 0.6 single-lane main road, 1.0 multi-lane / trunk road without a bike path.",
        f"- d_net: bike network (ridden + pushed), multi-source Dijkstra from all stations, up to {siting.MAX_R_M:.0f} m "
        f"({summary['beyond_max_r']} hexes are farther).",
        "",
        "| value | min | p25 | median | p75 | max | mean |",
        "|---|---|---|---|---|---|---|",
    ]
    names = {"t_raw": "T raw (cars / h)", "t": "T", "e": "E", "s": "S", "d_net": "d_net (m)"}
    for k, name in names.items():
        st = stats[k]
        d = 0 if k in ("t_raw", "d_net") else 2
        lines.append(f"| {name} | " + " | ".join(f(st[c], d) for c in ("min", "p25", "median", "p75", "max", "mean")) + " |")
    lines += ["", "## Top proposals", "",
              "| # | hex | lat, lon | J | T | E | d_net (m) | P | S |", "|---|---|---|---|---|---|---|---|---|"]
    for o in options:
        d = "inf" if o["dNet"] is None else f"{o['dNet']:.0f}"
        lines.append(f"| {o['rank']} | {o['hex']} | {o['lat']:.5f}, {o['lon']:.5f} | {o['j']:.3f} | {o['t']:.2f} | "
                     f"{o['e']:.2f} | {d} | {o['p']:.3f} | {o['s']:.2f} |")
    lines += ["", "d_net is the distance at the moment of the pick (after the earlier picks).",
              "Interactive map: `artifacts/veturilo-siting.html`. API: `GET /api/veturilo/siting` (`data/API.md`).", ""]
    (DATA / "SITING_REPORT.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_html(h, p, steps, options, tc, stations, summary) -> None:
    d0 = np.where(np.isinf(h["d_net"]), -1, np.round(h["d_net"])).astype(int)
    prev = h["d_net"]
    step_data = []
    for s, o in zip(steps, options):
        changed = np.nonzero(s["d_after"] < prev - 0.5)[0]
        step_data.append({**o, "i": s["pick"],
                          "changed": [[int(i), int(round(s["d_after"][i]))] for i in changed]})
        prev = s["d_after"]
    geo = load_json(siting.BOUNDARY)["geometry"]
    polys = [geo["coordinates"]] if geo["type"] == "Polygon" else geo["coordinates"]
    data = {
        "params": p, "hexSize": HEX_SIZE_M, "maxR": siting.MAX_R_M, "summary": summary,
        "boundary": [[[round(c[1], 5), round(c[0], 5)] for c in ring] for poly in polys for ring in poly],
        "hex": {"lat": np.round(h["lat"], 5).tolist(), "lon": np.round(h["lon"], 5).tolist(),
                "t": np.round(h["t"], 3).tolist(), "e": np.round(h["e"], 3).tolist(), "s": np.round(h["s"], 3).tolist(),
                "d": d0.tolist(), "cand": h["candidate"].astype(int).tolist(), "st": h["stations"].astype(int).tolist(),
                "tRaw": np.round(h["t_raw"]).astype(int).tolist()},
        "steps": step_data,
        "stations": [[round(s["lat"], 5), round(s["lon"], 5), s["name"]] for s in stations],
        "counters": [[c["lat"], c["lon"], int(np.mean(c["hourly"])), c["road"]] for c in tc],
    }
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null",
                                                        json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    OUT.write_text(html, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
