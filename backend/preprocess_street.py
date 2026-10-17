"""Walk / bike street paths between every pair of points (GTFS boarding points + Veturilo stations).

Usage (from backend/): uv run python preprocess_street.py [walk|bike|accessible] [--threads N] [--engine cpp|python]
                       [--graph-only]
Docs (deliverable, formats, model): algorithms/router/preprocess/README.md.

Shortest expected-time path on the OSM graph, then per pair: distance_m and wait_s (signal / crossing
waits, a signal junction is paid once). Each point joins the graph through its few nearest nodes
(osm.access, a multi-source Dijkstra via virtual nodes); on a bike these access segments are pushed,
and the extra time is in wait_s. Time with the default speeds = distance_m / speed + wait_s.

Output in data/derived/street/ (git-ignored):
- graph_<mode>.bin: the graph with the points, input of the C++ program
- meta.json: build time and size per mode (read by report.py)
- points.csv: index,id,kind,lat,lon,snap_walk_m,snap_bike_m,entrances
- walk.bin, bike.bin, accessible.bin: float32, row-major, shape (2, N, N): [0] = distance_m, [1] = wait_s.
  Row = from, column = to (index from points.csv). NaN = no path (point > MAX_SNAP_M from the graph).
"""
import argparse
import csv
import multiprocessing as mp
import os
import subprocess
import sys
import time
from collections import defaultdict

import numpy as np

from config import DERIVED, REPO, load_json, save_json
from sources import mkuran, nextbike, osm

sys.path.insert(0, str(REPO / "algorithms"))
from street_matrix import EPS, EdgeLookup, matrix_rows, save_graph  # noqa: E402
from scipy.sparse import csr_matrix  # noqa: E402

OUT = DERIVED / "street"
CPP = REPO / "algorithms" / "router" / "preprocess" / "build" / "street_matrix"
CHUNK = 16  # sources per task

_JOB = {}  # set in the parent before fork, read by the workers


def points() -> list[dict]:
    """Stops + Veturilo. A metro platform gets the entrances of its station (GTFS location_type 2)."""
    entrances = defaultdict(list)
    for s in mkuran.stops():
        if s["location_type"] == 2 and s["parent"]:
            entrances[s["parent"]].append((s["lat"], s["lon"]))
    stops = [{"id": s["id"], "kind": "stop", "lat": s["lat"], "lon": s["lon"],
              "entrances": entrances.get(s["parent"], []) if "metro" in s["modes"] else []}
             for s in mkuran.vertices()]
    vet = [{"id": s["id"], "kind": "veturilo", "lat": s["lat"], "lon": s["lon"]} for s in nextbike.stations()]
    return stops + vet


def snap(pts: list[dict], mode: str):
    return osm.nearest_many([p["lat"] for p in pts], [p["lon"] for p in pts], mode)


def write_points(pts: list[dict]) -> None:
    snaps = {m: snap(pts, m)[1] for m in ("walk", "bike")}
    with open(OUT / "points.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "id", "kind", "lat", "lon", "snap_walk_m", "snap_bike_m", "entrances"])
        for i, p in enumerate(pts):
            w.writerow([i, p["id"], p["kind"], p["lat"], p["lon"],
                        round(float(snaps["walk"][i]), 1), round(float(snaps["bike"][i]), 1), len(p.get("entrances", []))])


def _rows(rows: np.ndarray) -> int:
    j = _JOB
    zero = np.zeros(len(j["ok"]))
    dist, wait = matrix_rows(j["cost_g"], j["lookup"], j["out"][rows], j["in"][j["ok"]], zero[:len(rows)], zero)
    mm = np.memmap(j["path"], dtype=np.float32, mode="r+", shape=(2, j["n"], j["n"]))
    mm[0, rows[:, None], j["ok"][None, :]] = dist
    mm[1, rows[:, None], j["ok"][None, :]] = wait
    mm.flush()
    return len(rows)


def _python(path, n, ok, m, src, dst, cost, length, wait, out_ids, in_ids, workers: int) -> None:
    """Reference engine (scipy), much slower than the C++ program."""
    mm = np.memmap(path, dtype=np.float32, mode="w+", shape=(2, n, n))
    mm[:] = np.nan
    mm.flush()
    del mm
    _JOB.update(cost_g=csr_matrix((cost + EPS, (src, dst)), shape=(m, m)),
                lookup=EdgeLookup(src, dst, length, wait, cost, m), out=out_ids, **{"in": in_ids},
                ok=ok, path=path, n=n)
    chunks = [ok[i:i + CHUNK] for i in range(0, len(ok), CHUNK)]
    done, t0 = 0, time.time()
    with mp.get_context("fork").Pool(workers) as pool:
        for k in pool.imap_unordered(_rows, chunks):
            done += k
            print(f"\r{done}/{len(ok)} sources, {time.time() - t0:.0f} s", end="", flush=True)
    print()
    mm = np.memmap(path, dtype=np.float32, mode="r+", shape=(2, n, n))
    mm[:, ok, ok] = 0.0  # a point to itself
    mm.flush()


def build(mode: str, pts: list[dict], engine: str, threads: int, graph_only: bool = False) -> dict:
    t0 = time.time()
    n = len(pts)
    _, dist_snap = snap(pts, mode)
    ok = np.nonzero(dist_snap <= osm.MAX_SNAP_M)[0]
    lat, lon = [p["lat"] for p in pts], [p["lon"] for p in pts]
    m, src, dst, cost, length, wait, out_ids, in_ids, flags = osm.points_graph(
        lat, lon, mode, [p.get("entrances", []) for p in pts])
    path = OUT / f"{mode}.bin"
    print(f"{mode}: {n} points, {m} nodes, {len(src)} edges, engine {engine}")
    if engine == "cpp":
        save_graph(OUT / f"graph_{mode}.bin", m, src, dst, cost, length, wait, out_ids, in_ids,
                   dist_snap <= osm.MAX_SNAP_M, *osm.points_lonlat(lat, lon), flags)
        if graph_only:
            return {"mode": mode, "graph": f"graph_{mode}.bin", "seconds": round(time.time() - t0)}
        subprocess.run([str(CPP), str(OUT / f"graph_{mode}.bin"), str(path), "--threads", str(threads)], check=True)
    else:
        _python(path, n, ok, m, src, dst, cost, length, wait, out_ids, in_ids, threads)
    return {"mode": mode, "engine": engine, "points": n, "far_points": int(n - len(ok)),
            "seconds": round(time.time() - t0), "file_mb": round(path.stat().st_size / 1e6)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("modes", nargs="*", help="walk, bike, accessible (default all)")
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--engine", choices=["cpp", "python"], default="cpp")
    ap.add_argument("--graph-only", action="store_true",
                    help="only write points.csv + graph_<mode>.bin (for street_matrix --route)")
    args = ap.parse_args()
    args.modes = args.modes or list(osm.SPEED)
    if set(args.modes) - set(osm.SPEED):
        ap.error("modes must be walk, bike or accessible")
    if args.engine == "cpp" and not CPP.exists():
        ap.error(f"{CPP} not built, see algorithms/router/preprocess/README.md")
    OUT.mkdir(parents=True, exist_ok=True)
    pts = points()
    write_points(pts)
    meta = {}
    for mode in args.modes:
        meta[mode] = build(mode, pts, args.engine, args.threads, args.graph_only)
        print(meta[mode])
    if args.graph_only:
        return
    old = load_json(OUT / "meta.json") if (OUT / "meta.json").exists() else {}
    save_json(OUT / "meta.json", {**old, **meta, "threads": args.threads})


if __name__ == "__main__":
    main()
