"""Check the C++ street matrix on 100 stop-level pairs (README.md, "Checks").

Run from backend/: uv run python ../algorithms/router/preprocess/check_pairs.py
For each pair and mode: the C++ result from the GTFS positions, the same from the OSM platform nodes
(`ref` = ZTM stop id), and osm.route() (Python). Writes data/derived/street/check_pairs.csv.
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
        subprocess.run([str(CPP), f"{tmp}/graph.bin", f"{tmp}/out.bin"], check=True, capture_output=True)
        return np.fromfile(f"{tmp}/out.bin", dtype="<f4").reshape(2, len(points), len(points))


def main() -> None:
    plat = osm_platforms()
    posts = [v | {"osm": plat[v["raw_id"]]} for v in mkuran.vertices()
             if v["feed"] == "ztm" and v["raw_id"] in plat]
    pairs = pick_pairs(posts)
    # 4 points per pair: GTFS a, GTFS b, OSM a, OSM b
    points = [q for a, b in pairs for q in (a, b, a["osm"], b["osm"])]
    rows = [{"from": f"{a['name']} {a['code']}", "to": f"{b['name']} {b['code']}",
             "air_m": round(float(np.hypot(*np.subtract(to_xy(a["lat"], a["lon"]), to_xy(b["lat"], b["lon"])))))}
            for a, b in pairs]
    for mode in ("walk", "bike"):
        mat = cpp_matrix(points, mode)
        for i, ((a, b), row) in enumerate(zip(pairs, rows)):
            r = osm.route(a["lat"], a["lon"], b["lat"], b["lon"], mode, limit_s=np.inf)
            g, o = (4 * i, 4 * i + 1), (4 * i + 2, 4 * i + 3)
            row |= {f"{mode}_m": round(float(mat[0][g])), f"{mode}_wait_s": round(float(mat[1][g]), 1),
                    f"{mode}_min": round((float(mat[0][g]) / osm.SPEED[mode] + float(mat[1][g])) / 60, 1),
                    f"{mode}_osm_m": round(float(mat[0][o])), f"{mode}_osm_wait_s": round(float(mat[1][o]), 1),
                    f"{mode}_route_diff_m": abs(float(mat[0][g]) - r["length_m"]),
                    f"{mode}_route_diff_s": abs(float(mat[1][g]) - r["wait_s"])}
    with open(OUT / "check_pairs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    col = lambda k: np.array([r[k] for r in rows], dtype=float)  # noqa: E731
    print(f"posts matched to OSM platforms: {len(posts)}; pairs: {len(rows)}")
    for mode in ("walk", "bike"):
        d = np.abs(col(f"{mode}_m") - col(f"{mode}_osm_m"))
        print(f"{mode}: C++ vs osm.route() max diff {col(f'{mode}_route_diff_m').max():.2f} m, "
              f"{col(f'{mode}_route_diff_s').max():.2f} s | GTFS vs OSM position: median {np.median(d):.0f} m, "
              f"p90 {np.percentile(d, 90):.0f} m, max {d.max():.0f} m")
    for r in rows[:6]:
        print(f"  {r['from']} -> {r['to']} ({r['air_m']} m): walk {r['walk_m']} m + {r['walk_wait_s']} s = "
              f"{r['walk_min']} min, bike {r['bike_m']} m + {r['bike_wait_s']} s = {r['bike_min']} min")


if __name__ == "__main__":
    main()
