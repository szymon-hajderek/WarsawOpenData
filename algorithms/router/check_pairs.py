"""Check the C++ street router on 100 stop-level pairs (README.md, "Checks").

Run from backend/: uv run python ../algorithms/router/check_pairs.py
For each pair and mode it compares:
- the matrix value (`street_router matrix`, the points' virtual nodes built in Python);
- the server's route between the same coordinates (C++ joins the coordinates itself), and by the stop ids
  (the overlay position, which may be the OSM post instead of the GTFS point);
- the matrix value from the OSM platform node of the same post (`ref` = ZTM stop id).
Writes data/derived/street/check_pairs.csv. Starts the router if none answers.
"""
import csv
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import osmium

sys.path.insert(0, ".")
from config import DERIVED, in_bbox, to_xy  # noqa: E402
import street_router  # noqa: E402
from preprocess_street import CPP  # noqa: E402
from sources import mkuran, osm  # noqa: E402

OUT = DERIVED / "street"
EXAMPLE = ("ztm:435102", "ztm:701303")  # Grójecka 02 -> Centrum 03


def osm_platforms() -> dict:
    """ZTM stop id -> OSM platform node (cached)."""
    cache = OUT / "osm_platforms.json"
    if not cache.exists():
        out = {}
        for o in osmium.FileProcessor(str(osm.PBF), osmium.osm.NODE):
            ref = o.tags.get("ref")
            if ref and o.tags.get("public_transport") == "platform" and in_bbox(o.location.lat, o.location.lon):
                out[ref] = {"lat": o.location.lat, "lon": o.location.lon, "name": o.tags.get("name")}
        cache.write_text(json.dumps(out, ensure_ascii=False))
    return json.loads(cache.read_text())


def pick_pairs(posts: list[dict], seed: int = 11) -> list[tuple[dict, dict]]:
    rng = np.random.default_rng(seed)
    by_id = {p["id"]: p for p in posts}
    pairs = [(by_id[EXAMPLE[0]], by_id[EXAMPLE[1]])]
    groups = defaultdict(list)
    for p in posts:
        groups[p["group"]].append(p)
    multi = [g for g in groups.values() if len(g) > 1]
    for k in rng.choice(len(multi), 20, replace=False):  # posts of the same stop
        a, b = rng.choice(len(multi[k]), 2, replace=False)
        pairs.append((multi[k][a], multi[k][b]))
    xy = np.array([to_xy(p["lat"], p["lon"]) for p in posts])
    while len(pairs) < 100:  # random pairs 0.2-5 km apart
        a, b = rng.integers(len(posts), size=2)
        if 200 < np.hypot(*(xy[a] - xy[b])) < 5000:
            pairs.append((posts[a], posts[b]))
    return pairs


def cpp_matrix(points: list[dict], mode: str) -> np.ndarray:
    with tempfile.TemporaryDirectory() as tmp:
        osm.points_graph([p["lat"] for p in points], [p["lon"] for p in points], mode).save(Path(tmp) / "graph.bin")
        subprocess.run([str(CPP), "matrix", f"{tmp}/graph.bin", f"{tmp}/out.bin"], check=True, capture_output=True)
        return np.fromfile(f"{tmp}/out.bin", dtype="<f4").reshape(3, len(points), len(points))  # walk, bike, wait


def main() -> None:
    plat = osm_platforms()
    posts = [v | {"osm": plat[v["raw_id"]]} for v in mkuran.vertices()
             if v["feed"] == "ztm" and v["raw_id"] in plat]
    pairs = pick_pairs(posts)
    street_router.start()
    # 4 points per pair: GTFS a, GTFS b, OSM a, OSM b
    points = [q for a, b in pairs for q in (a, b, a["osm"], b["osm"])]
    rows = [{"from": f"{a['name']} {a['code']}", "to": f"{b['name']} {b['code']}",
             "air_m": round(float(np.hypot(*np.subtract(to_xy(a["lat"], a["lon"]), to_xy(b["lat"], b["lon"])))))}
            for a, b in pairs]
    for mode in ("walk", "bike"):
        walk, bike, wait = cpp_matrix(points, mode)
        dist = walk + bike
        for i, ((a, b), row) in enumerate(zip(pairs, rows)):
            r = street_router.route((a["lat"], a["lon"]), (b["lat"], b["lon"]), mode)
            try:
                rid = street_router.route(a["id"], b["id"], mode)
                row[f"{mode}_by_id_m"] = round(rid["length_m"])
            except street_router.RouteError:
                row[f"{mode}_by_id_m"] = None
            g, o = (4 * i, 4 * i + 1), (4 * i + 2, 4 * i + 3)
            row |= {f"{mode}_m": round(float(dist[g])), f"{mode}_wait_s": round(float(wait[g]), 1),
                    f"{mode}_min": round(float(osm.seconds(mode, walk[g], bike[g], wait[g])) / 60, 1),
                    f"{mode}_osm_m": round(float(dist[o])), f"{mode}_osm_wait_s": round(float(wait[o]), 1),
                    f"{mode}_route_diff_m": abs(float(dist[g]) - r["length_m"]),
                    f"{mode}_route_diff_s": abs(float(wait[g]) - r["wait_s"])}
    with open(OUT / "check_pairs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    col = lambda k: np.array([r[k] for r in rows], dtype=float)  # noqa: E731
    print(f"posts matched to OSM platforms: {len(posts)}; pairs: {len(rows)}")
    for mode in ("walk", "bike"):
        d = np.abs(col(f"{mode}_m") - col(f"{mode}_osm_m"))
        by_id = np.array([r[f"{mode}_by_id_m"] for r in rows if r[f"{mode}_by_id_m"] is not None], dtype=float)
        print(f"{mode}: routes by id answered for {len(by_id)}/{len(rows)} pairs")
        print(f"{mode}: server route vs matrix max diff {col(f'{mode}_route_diff_m').max():.2f} m, "
              f"{col(f'{mode}_route_diff_s').max():.2f} s | GTFS vs OSM position: median {np.median(d):.0f} m, "
              f"p90 {np.percentile(d, 90):.0f} m, max {d.max():.0f} m")
    for r in rows[:6]:
        print(f"  {r['from']} -> {r['to']} ({r['air_m']} m): walk {r['walk_m']} m + {r['walk_wait_s']} s = "
              f"{r['walk_min']} min, bike {r['bike_m']} m + {r['bike_wait_s']} s = {r['bike_min']} min")


if __name__ == "__main__":
    try:
        main()
    finally:
        street_router.stop()
