"""Street matrix: walk / bike / accessible / stroller paths between every pair of points (stops + Veturilo stations).

Usage (from backend/): uv run python preprocess_street.py [walk|bike|accessible|stroller] [--threads N] [--graph-only]
Docs (deliverable, formats, model): algorithms/router/README.md.

Python builds the graph (osm.points_graph), the C++ router (street_router matrix) runs the all-pairs Dijkstra.
The same graph files serve point-to-point routes (street_router serve, started by the backend).
Output in data/derived/street/ (git-ignored):
- points.csv: index,id,kind,source,lat,lon,snap_walk_m,snap_bike_m,entrances (the overlay, stations.json)
- graph_<mode>.bin: the graph with the points, input of the C++ program (also for --route)
- <mode>.bin: float32, row-major, shape (2, N, N): [0] = distance_m, [1] = wait_s; row = from, column = to
- meta.json: build time and size per mode, the overlay hash and graph sizes the matrices belong to (/health)
"""
import argparse
import csv
import os
import subprocess
import time

import stations
from config import DERIVED, GTFS_DIR, REPO, load_json, save_json
from sources import osm

OUT = DERIVED / "street"
CPP = REPO / "algorithms" / "router" / "build" / "street_router"


def points() -> list[dict]:
    """The StationLocations overlay (stations.json): one point per location, at its OSM or GTFS position; a metro
    platform joins the graph through its entrances."""
    return [{"id": l["id"], "kind": l["kind"], "source": l["source"], "lat": l["position"]["lat"],
             "lon": l["position"]["lon"], "entrances": [(e["lat"], e["lon"]) for e in l["entrances"]],
             "transfers": [(t["to"], t["walk_m"]) for t in l["transfers"]]}
            for l in stations.locations()]


def transfers(pts: list[dict]) -> list[tuple[int, int, float]]:
    """In-station transfers as (point index, point index, walk_m)."""
    index = {p["id"]: i for i, p in enumerate(pts)}
    return [(i, index[to], m) for i, p in enumerate(pts) for to, m in p["transfers"] if to in index]


def write_points(pts: list[dict]) -> None:
    lat, lon = [p["lat"] for p in pts], [p["lon"] for p in pts]
    snaps = {m: osm.nearest_many(lat, lon, m)[1] for m in ("walk", "bike")}
    with open(OUT / "points.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "id", "kind", "source", "lat", "lon", "snap_walk_m", "snap_bike_m", "entrances"])
        for i, p in enumerate(pts):
            w.writerow([i, p["id"], p["kind"], p["source"], p["lat"], p["lon"], round(float(snaps["walk"][i]), 1),
                        round(float(snaps["bike"][i]), 1), len(p["entrances"])])


def graphs_stale() -> bool:
    """A graph file is missing, or older than the OSM graph cache, the overlay or a GTFS zip."""
    sources = [DERIVED / "osm_graph.npz", osm.PBF, stations.FILE, *GTFS_DIR.glob("*.zip")]
    newest = max((f.stat().st_mtime for f in sources if f.exists()), default=0)
    files = [OUT / f"graph_{m}.bin" for m in osm.SPEED]
    return not all(f.exists() for f in files) or min(f.stat().st_mtime for f in files) < newest


def expected_meta() -> dict:
    """What meta.json must say for the matrices to belong to the current overlay and graph files."""
    return {"stations_hash": stations.load()["hash"],
            "graphs": {m: {"bytes": (OUT / f"graph_{m}.bin").stat().st_size} for m in osm.SPEED
                       if (OUT / f"graph_{m}.bin").exists()}}


def matrices_stale() -> bool:
    """meta.json is missing or was written for another overlay / other graph files (what /health reports too)."""
    if not (OUT / "meta.json").exists() or not all((OUT / f"{m}.bin").exists() for m in osm.SPEED):
        return True
    meta = load_json(OUT / "meta.json")
    want = expected_meta()
    return meta.get("stations_hash") != want["stations_hash"] or meta.get("graphs") != want["graphs"]


def write_graphs(modes=None) -> None:
    """points.csv + graph_<mode>.bin for every mode (enough for the router's serve and route)."""
    OUT.mkdir(parents=True, exist_ok=True)
    pts = points()
    write_points(pts)
    for mode in modes or osm.SPEED:
        build(mode, pts, 0, graph_only=True)


def build(mode: str, pts: list[dict], threads: int, graph_only: bool) -> dict:
    t0 = time.time()
    g = osm.points_graph([p["lat"] for p in pts], [p["lon"] for p in pts], mode, [p["entrances"] for p in pts],
                         transfers(pts))
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
    ap.add_argument("modes", nargs="*", help="walk, bike, accessible, stroller (default all)")
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--graph-only", action="store_true",
                    help="only write points.csv + graph_<mode>.bin (enough for street_matrix --route)")
    args = ap.parse_args()
    args.modes = args.modes or list(osm.SPEED)
    if set(args.modes) - set(osm.SPEED):
        ap.error("modes must be walk, bike, accessible or stroller")
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
        save_json(OUT / "meta.json", {**old, **meta, **expected_meta(), "threads": args.threads,
                                      "built": time.strftime("%Y-%m-%dT%H:%M:%S")})


if __name__ == "__main__":
    main()
