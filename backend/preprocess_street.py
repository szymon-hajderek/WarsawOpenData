"""Street matrix: walk / bike / accessible paths between every pair of points (stops + Veturilo stations).

Usage (from backend/): uv run python preprocess_street.py [walk|bike|accessible] [--threads N] [--graph-only]
Docs (deliverable, formats, model): algorithms/router/README.md.

Python builds the graph (osm.points_graph), the C++ router (street_router matrix) runs the all-pairs Dijkstra.
The same graph files serve point-to-point routes (street_router serve, started by the backend).
Output in data/derived/street/ (git-ignored):
- points.csv: index,id,kind,lat,lon,snap_walk_m,snap_bike_m,entrances
- graph_<mode>.bin: the graph with the points, input of the C++ program (also for --route)
- <mode>.bin: float32, row-major, shape (2, N, N): [0] = distance_m, [1] = wait_s; row = from, column = to
- meta.json: build time and size per mode (read by report.py)
"""
import argparse
import csv
import os
import subprocess
import time
from collections import defaultdict

from config import DERIVED, GTFS_DIR, REPO, load_json, save_json
from sources import mkuran, nextbike, osm

OUT = DERIVED / "street"
CPP = REPO / "algorithms" / "router" / "build" / "street_router"


def points() -> list[dict]:
    """Stops + Veturilo. A metro platform gets the entrances of its station (GTFS location_type 2)."""
    entrances = defaultdict(list)
    for s in mkuran.stops():
        if s["location_type"] == 2 and s["parent"]:
            entrances[s["parent"]].append((s["lat"], s["lon"]))
    stops = [{"id": s["id"], "kind": "stop", "lat": s["lat"], "lon": s["lon"],
              "entrances": entrances.get(s["parent"], []) if "metro" in s["modes"] else []}
             for s in mkuran.vertices()]
    vet = [{"id": s["id"], "kind": "veturilo", "lat": s["lat"], "lon": s["lon"], "entrances": []}
           for s in nextbike.stations()]
    return stops + vet


def write_points(pts: list[dict]) -> None:
    lat, lon = [p["lat"] for p in pts], [p["lon"] for p in pts]
    snaps = {m: osm.nearest_many(lat, lon, m)[1] for m in ("walk", "bike")}
    with open(OUT / "points.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "id", "kind", "lat", "lon", "snap_walk_m", "snap_bike_m", "entrances"])
        for i, p in enumerate(pts):
            w.writerow([i, p["id"], p["kind"], p["lat"], p["lon"], round(float(snaps["walk"][i]), 1),
                        round(float(snaps["bike"][i]), 1), len(p["entrances"])])


def graphs_stale() -> bool:
    """A graph file is missing, or older than the OSM graph cache or a GTFS zip (it depends on both)."""
    sources = [DERIVED / "osm_graph.npz", osm.PBF, *GTFS_DIR.glob("*.zip")]
    newest = max((f.stat().st_mtime for f in sources if f.exists()), default=0)
    files = [OUT / f"graph_{m}.bin" for m in osm.SPEED]
    return not all(f.exists() for f in files) or min(f.stat().st_mtime for f in files) < newest


def write_graphs(modes=None) -> None:
    """points.csv + graph_<mode>.bin for every mode (enough for the router's serve and route)."""
    OUT.mkdir(parents=True, exist_ok=True)
    pts = points()
    write_points(pts)
    for mode in modes or osm.SPEED:
        build(mode, pts, 0, graph_only=True)


def build(mode: str, pts: list[dict], threads: int, graph_only: bool) -> dict:
    t0 = time.time()
    g = osm.points_graph([p["lat"] for p in pts], [p["lon"] for p in pts], mode, [p["entrances"] for p in pts])
    graph_file, out = OUT / f"graph_{mode}.bin", OUT / f"{mode}.bin"
    g.save(graph_file)
    print(f"{mode}: {len(pts)} points, {g.nodes} nodes, {len(g.src)} edges")
    if graph_only:
        return {"mode": mode, "graph": graph_file.name, "seconds": round(time.time() - t0)}
    subprocess.run([str(CPP), "matrix", str(graph_file), str(out), "--threads", str(threads)], check=True)
    return {"mode": mode, "points": len(pts), "far_points": int((~g.active).sum()),
            "seconds": round(time.time() - t0), "file_mb": round(out.stat().st_size / 1e6)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("modes", nargs="*", help="walk, bike, accessible (default all)")
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--graph-only", action="store_true",
                    help="only write points.csv + graph_<mode>.bin (enough for street_matrix --route)")
    args = ap.parse_args()
    args.modes = args.modes or list(osm.SPEED)
    if set(args.modes) - set(osm.SPEED):
        ap.error("modes must be walk, bike or accessible")
    if not args.graph_only and not CPP.exists():
        ap.error(f"{CPP} not built, see algorithms/router/README.md")
    OUT.mkdir(parents=True, exist_ok=True)
    pts = points()
    write_points(pts)
    meta = {mode: build(mode, pts, args.threads, args.graph_only) for mode in args.modes}
    for m in meta.values():
        print(m)
    if not args.graph_only:
        old = load_json(OUT / "meta.json") if (OUT / "meta.json").exists() else {}
        save_json(OUT / "meta.json", {**old, **meta, "threads": args.threads})


if __name__ == "__main__":
    main()
