"""Builds data/REPORT.md and data/report.json: sources, ID compatibility, vertex and edge counts.
Usage (from backend/): uv run python report.py
"""
import time
from collections import Counter
from datetime import datetime

import numpy as np
from scipy.spatial import cKDTree

from config import DATA, DERIVED, load_json, save_json, to_xy
from sources import mkuran, nextbike, osm, um_warszawa
from sources.registry import SOURCES

RADII = (300, 500, 1000)


def pair_counts(points) -> dict:
    lat = np.array([p[0] for p in points])
    lon = np.array([p[1] for p in points])
    x, y = to_xy(lat, lon)
    tree = cKDTree(np.c_[x, y])
    n = len(points)
    out = {"n": n, "all_pairs_unordered": n * (n - 1) // 2, "all_pairs_directed": n * (n - 1)}
    for r in RADII:
        out[f"pairs_within_{r}m"] = int(tree.count_neighbors(tree, r) - n) // 2
    return out


def compatibility(ref_date: str) -> dict:
    ztm_ids = {s["id"] for s in mkuran.stops() if s["feed"] == "ztm"}
    ztm_posts = {s["id"] for s in mkuran.vertices()
                 if s["feed"] == "ztm" and s["raw_id"].isdigit() and len(s["raw_id"]) == 6}
    variants = um_warszawa.route_variants_snapshot()
    um_posts = {um_warszawa.join_stop_id(v["nr_zespolu"], v["nr_przystanku"])
                for line in variants.values() for var in line.values() for v in var.values()}
    gtfs_lines = {r["short_name"] for r in mkuran.routes().values() if r["feed"] == "ztm"}
    vehicles = um_warszawa.vehicles_snapshot()
    stale = len(vehicles)
    if vehicles:
        newest = max(datetime.strptime(v["time"], "%Y-%m-%d %H:%M:%S") for v in vehicles)
        vehicles = um_warszawa.fresh(vehicles, 300, newest)
    stale -= len(vehicles)
    veh_lines = {v["line"] for v in vehicles}
    # brigade check: (line, brigade) of live vehicles vs (route, block_short_name) of today's GTFS trips
    svc = mkuran.services()
    today = vehicles[0]["time"][:10].replace("-", "") if vehicles else ref_date
    blocks = {(mkuran.routes()[t[1]]["short_name"], t[3]) for t in mkuran.trips()
              if t[0].startswith("ztm:") and today in svc.get(t[2], ())}
    veh_pairs = {(v["line"], v["brigade"]) for v in vehicles}
    # Veturilo: no shared ids, only distance to the nearest transit vertex
    tv = mkuran.vertices()
    tx, ty = to_xy(np.array([s["lat"] for s in tv]), np.array([s["lon"] for s in tv]))
    st = nextbike.stations()
    vx, vy = to_xy(np.array([s["lat"] for s in st]), np.array([s["lon"] for s in st]))
    d, _ = cKDTree(np.c_[tx, ty]).query(np.c_[vx, vy])
    merge = mkuran.merge_info()
    merged_stations = [k for k in merge["merged"] if mkuran.stops_by_id()[k]["location_type"] == 1
                       or k.startswith("wkd:")]
    return {
        "um_route_posts_in_gtfs": f"{len(um_posts & ztm_ids)}/{len(um_posts)}",
        "gtfs_ztm_posts_in_um_routes": f"{len(ztm_posts & um_posts)}/{len(ztm_posts)}",
        "live_lines_in_gtfs": f"{len(veh_lines & gtfs_lines)}/{len(veh_lines)}",
        "live_line_brigade_in_gtfs_blocks": f"{len(veh_pairs & blocks)}/{len(veh_pairs)} (date {today})",
        "veturilo_to_nearest_stop_m": {"median": round(float(np.median(d))), "p90": round(float(np.percentile(d, 90))),
                                       "within_300m": f"{int((d <= 300).sum())}/{len(d)}"},
        "live_stale_positions_dropped": stale,
        "rail_stations_merged_into_ztm": len(merged_stations),
        "rail_platforms_merged_into_ztm": len(merge["merged"]) - len(merged_stations),
        "near_misses": merge["unmatched_near"],
    }


def street_matrix(sample: int = 100, seed: int = 1) -> dict | None:
    """Junction counts, matrix stats and a check against osm.route() on random pairs (needs preprocess_street.py)."""
    out_dir = DERIVED / "street"
    if not (out_dir / "meta.json").exists():
        return None
    meta = load_json(out_dir / "meta.json")
    import csv
    with open(out_dir / "points.csv") as f:
        pts = list(csv.DictReader(f))
    n = len(pts)
    rng = np.random.default_rng(seed)
    out = {"points": n, "modes": {}}
    for mode in ("walk", "bike", "accessible"):
        if mode not in meta:
            continue
        mm = np.memmap(out_dir / f"{mode}.bin", dtype=np.float32, mode="r", shape=(2, n, n))
        rows = rng.choice(n, size=200, replace=False)
        dist, wait = np.asarray(mm[0, rows]), np.asarray(mm[1, rows])
        s, d, _, _, jid = osm.edges(mode)
        nw = osm.node_wait(mode)
        signal = np.isin(osm.graph()["kind"], (1, 3)) & (nw > 0)
        diffs = []
        plain = np.array([i for i, p in enumerate(pts) if int(p["entrances"]) == 0])  # osm.route() has no metro entrances
        for a, b in rng.choice(plain, size=(sample, 2)):
            if a == b:
                continue
            r = osm.route(float(pts[a]["lat"]), float(pts[a]["lon"]), float(pts[b]["lat"]), float(pts[b]["lon"]),
                          mode, limit_s=np.inf)
            diffs.append((abs(float(mm[0, a, b]) - r["length_m"]), abs(float(mm[1, a, b]) - r["wait_s"])))
        diffs = np.array(diffs)
        # sanity: path >= straight line, detour factor, walk symmetry (end points outside junctions)
        lat = np.array([float(p["lat"]) for p in pts])
        lon = np.array([float(p["lon"]) for p in pts])
        x, y = to_xy(lat, lon)
        air = np.hypot(x[rows, None] - x[None, :], y[rows, None] - y[None, :])
        far = (air > 500) & np.isfinite(dist)
        ratio = dist[far] / air[far]
        sym = None
        if mode != "bike":
            node = osm.nearest_many(lat[rows], lon[rows], mode)[0]
            ok = rows[jid[node] < 0]
            cost = mm[0][np.ix_(ok, ok)] / osm.SPEED[mode] + mm[1][np.ix_(ok, ok)]
            sym = round(float(np.nanmax(np.abs(cost - cost.T))), 2)
        out["modes"][mode] = {
            "shorter_than_straight_line": int((dist < air - 1).sum()),
            "detour_median": round(float(np.median(ratio)), 2), "detour_p99": round(float(np.percentile(ratio, 99)), 2),
            "walk_symmetry_max_diff_s": sym,
            **meta[mode],
            "signal_nodes": int(signal.sum()), "junctions": int(len(np.unique(jid[signal]))),
            "junction_interior_nodes": int(((jid >= 0) & ~signal).sum()),
            "nan_share_sampled_rows": round(float(np.isnan(dist).mean()), 4),
            "median_distance_m": round(float(np.nanmedian(dist))), "median_wait_s": round(float(np.nanmedian(wait))),
            "check_pairs": len(diffs), "check_max_distance_diff_m": round(float(diffs[:, 0].max()), 2),
            "check_max_wait_diff_s": round(float(diffs[:, 1].max()), 2),
        }
    out["threads"] = meta.get("threads")
    return out


def build() -> dict:
    t0 = time.time()
    ref = mkuran.reference_date()
    verts = mkuran.vertices()
    by_mode = Counter(m for s in verts for m in s["modes"])
    by_feed = Counter(s["feed"] for s in verts)
    groups = {s["group"] for s in verts}
    vet = nextbike.stations()
    e = {k: v for k, v in mkuran.edges(ref).items() if k != "list"}  # edges() is cached: do not change it

    transit_pts = [(s["lat"], s["lon"]) for s in verts]
    vet_pts = [(s["lat"], s["lon"]) for s in vet]
    pairs_transit = pair_counts(transit_pts)
    pairs_all = pair_counts(transit_pts + vet_pts)

    osm_counts = {m: osm.counts(m) for m in ("walk", "bike")}
    pts = transit_pts + vet_pts
    snap = osm.snap_distances(pts, "walk")
    bench = [
        osm.benchmark(pts, "walk", limit_s=None),
        osm.benchmark(pts, "walk", limit_s=900),
        osm.benchmark(pts, "bike", limit_s=None),
        osm.benchmark(pts, "bike", limit_s=1200),
    ]
    report = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "reference_date": ref,
        "vertices": {
            "transit_posts": len(verts), "transit_stop_groups": len(groups),
            "by_feed": dict(by_feed), "by_mode": dict(by_mode),
            "veturilo_stations": len(vet),
            "osm_walk": osm_counts["walk"]["vertices"], "osm_bike": osm_counts["bike"]["vertices"],
        },
        "item1_transit_edges": e,
        "item2_walk_pairs": {"transit": pairs_transit, "transit_plus_veturilo": pairs_all},
        "item3_osm": osm_counts,
        "item4_feasibility": {
            "speeds_m_s": osm.SPEED, "waits_s": osm.WAIT,
            "nodes_with_signal_timing_tags": int(osm.graph()["timing_tagged"][0]),
            "snap_to_walk_graph_m": {"median": round(float(np.median(snap)), 1),
                                     "p99": round(float(np.percentile(snap, 99)), 1),
                                     "over_200m": int((snap > 200).sum())},
            "benchmarks": bench,
        },
        "compatibility": compatibility(ref),
        "street_matrix": street_matrix(),
        "seconds_to_build": round(time.time() - t0, 1),
    }
    return report


def endpoints() -> list[tuple[str, str, str]]:
    """(method, path, first docstring line) for every /api route, read from the OpenAPI schema."""
    from main import app
    out = []
    for path, ops in app.openapi()["paths"].items():
        for method, op in ops.items():
            params = [q["name"] for q in op.get("parameters", []) if q["in"] == "query"]
            full = path + ("?" + "&".join(params) if params else "")
            doc = (op.get("description") or op.get("summary") or "").strip().split("\n")[0]
            out.append((method.upper(), full, doc))
    return out


MERMAID = """```mermaid
flowchart LR
  subgraph Sources
    MK["mkuran.pl GTFS<br/>warsaw.zip / wkd.zip / polish_trains.zip"]
    RT["mkuran GTFS-RT .pb<br/>listed only"]
    DUM["dane.um.warszawa.pl<br/>live vehicles"]
    AUM["api.um.warszawa.pl<br/>lines + times at stop, route variants"]
    NB["Nextbike GBFS<br/>nextbike_vw"]
    OSM["Geofabrik OSM<br/>mazowieckie, cut to ZTM area"]
    PLK["PKP PLK API<br/>listed, key pending"]
  end
  subgraph Files["data/"]
    FG["gtfs/*.zip"]
    FL["live/*.json snapshots"]
    FB["gbfs/veturilo_*.json"]
    FO["osm/warsaw_ztm.osm.pbf"]
  end
  subgraph Parsers["backend/sources/"]
    PM["mkuran.py"]
    PU["um_warszawa.py"]
    PN["nextbike.py"]
    PO["osm.py"]
  end
  subgraph API["FastAPI /api"]
    EG["/api/gtfs/*"]
    EL["/api/live/vehicles<br/>/api/ztm/*"]
    EV["/api/veturilo/*"]
    EO["/api/osm/*"]
  end
  MK --> FG --> PM --> EG
  DUM --> FL
  AUM --> FL
  FL --> PU --> EL
  NB --> FB --> PN --> EV
  OSM --> FO --> PO --> EO
  PM -. "stop_id 700901 = zespół 7009 + słupek 01" .- PU
  PM -. "route_short_name = Lines; block_short_name = Brigade" .- PU
  PM -. "rail stations merged: name + < 150 m" .- PM
  RT -. "trip_id (partial match)" .- PM
  PLK -. "plk_secondary_id in polish_trains stops" .- PM
  PN -. "no shared ids: nearest stop by distance" .- PM
  PO -. "no shared ids: nearest OSM node" .- PM
  PO -. "nearest OSM node" .- PN
```"""


def fmt(n) -> str:
    return f"{n:,}".replace(",", " ") if isinstance(n, int) else str(n)


def write_md(r: dict, eps) -> str:
    v, e, p, o, f, c = (r["vertices"], r["item1_transit_edges"], r["item2_walk_pairs"], r["item3_osm"],
                        r["item4_feasibility"], r["compatibility"])
    L = ["# Data report", "",
         f"Generated {r['generated']} by `backend/report.py`. Reference day for timetables: {r['reference_date']}.",
         "Numbers come from the files in `data/`. Re-run the script after a new download.", "",
         "## Where the data comes from", "", MERMAID, "",
         "Solid arrows: data flow. Dotted lines: how IDs connect between sources.", "",
         "| Source | Status | Key | Content |", "|---|---|---|---|"]
    for s in SOURCES:
        L.append(f"| {s['url'].split(' ')[0] if s['url'].startswith('http') else s['url']} | {s['status']} | "
                 f"{s.get('key') or '-'} | {s['content']} |")
    L += ["", "Sources marked *listed* are not downloaded. `GET /api/sources` gives the instructions "
          "(`how_to_use`), license and attribution for each.", "",
          "## Deduplication", "",
          "- Stops come only from GTFS. The City Hall APIs give live data and per-stop lines; they map to GTFS ids.",
          "- ZTM incl. metro and SKM: `warsaw.zip`. WKD: `wkd.zip`. Other trains: `polish_trains.zip` "
          "without SKM and only inside the ZTM area (bbox 51.91-52.51 N, 20.57-21.48 E).",
          f"- Rail stations from different feeds merge when the name is equal and the distance is < 150 m: "
          f"{c['rail_stations_merged_into_ztm']} stations ({c['rail_platforms_merged_into_ztm']} platforms) "
          "now point to the ZTM stop (`same_as`).",
          "- Train stations never merge with bus / tram / metro stops. They connect through walk edges.",
          f"- Near misses (< 150 m, different name, not merged): {len(c['near_misses'])}. "
          "See `GET /api/gtfs/merge`.", "",
          "## ID compatibility", "",
          "| Link | Result |", "|---|---|",
          f"| api.um route variants posts (`nr_zespolu`+`nr_przystanku`) found in GTFS `stop_id` | {c['um_route_posts_in_gtfs']} |",
          f"| GTFS ZTM bus/tram posts found in api.um route variants | {c['gtfs_ztm_posts_in_um_routes']} |",
          f"| Live vehicle `Lines` found in GTFS `route_short_name` (fresh positions; {c['live_stale_positions_dropped']} older than 5 min dropped) | {c['live_lines_in_gtfs']} |",
          f"| Live (`Lines`, `Brigade`) found in GTFS (`route`, `block_short_name`) on that day | {c['live_line_brigade_in_gtfs_blocks']} |",
          f"| Veturilo station to nearest transit post (no shared ids) | median {c['veturilo_to_nearest_stop_m']['median']} m, "
          f"p90 {c['veturilo_to_nearest_stop_m']['p90']} m, within 300 m: {c['veturilo_to_nearest_stop_m']['within_300m']} |",
          "| OSM nodes (no shared ids) | stops and stations snap to the nearest graph node |",
          "| mkuran GTFS-RT `trip_id` | matches `warsaw.zip` only partly (positions come from the City Hall) |",
          "| PKP PLK API station ids | `plk_secondary_id` column in `polish_trains.zip` stops |", "",
          "## Vertices", "",
          "| Part | Vertices |", "|---|---|",
          f"| Transit boarding points (posts / platforms, after merge) | {fmt(v['transit_posts'])} |",
          f"| Transit stop groups (ZTM zespół / station) | {fmt(v['transit_stop_groups'])} |"]
    for k, n in sorted(v["by_feed"].items()):
        L.append(f"| - feed `{k}` | {fmt(n)} |")
    for k, n in sorted(v["by_mode"].items()):
        L.append(f"| - served by {k} (a post can have more modes) | {fmt(n)} |")
    L += [f"| Veturilo stations | {fmt(v['veturilo_stations'])} |",
          f"| OSM walk graph nodes | {fmt(v['osm_walk'])} |",
          f"| OSM bike graph nodes | {fmt(v['osm_bike'])} |", "",
          "## Edges", "",
          "### 1. Stop -> next stop on each line", "",
          "| Count | Edges |", "|---|---|",
          f"| Unique (from, to, route) | {fmt(e['unique_from_to_route'])} |",
          f"| Unique (from, to) pairs, any line | {fmt(e['unique_from_to'])} |",
          f"| Timetable edges on {e['date']} (every trip, metro frequencies expanded) | {fmt(e['timetable_edges_on_date'])} |", "",
          "### 2. Walk edges between every pair of stops / stations", "",
          "Straight-line distance. Transit = boarding points; + Veturilo = also bike stations.", "",
          "| Pairs | Transit | Transit + Veturilo |", "|---|---|---|"]
    for key, label in [("n", "Points"), ("all_pairs_unordered", "All pairs n(n-1)/2"),
                       ("all_pairs_directed", "All directed pairs n(n-1)")] + \
                      [(f"pairs_within_{r}m", f"Pairs within {r} m") for r in RADII]:
        L.append(f"| {label} | {fmt(p['transit'][key])} | {fmt(p['transit_plus_veturilo'][key])} |")
    L += ["", "### 3. Street graph for first / last mile (OSM)", "",
          "| | Walk | Bike |", "|---|---|---|"]
    for key, label in [("vertices", "Vertices (all way nodes)"), ("edges_undirected", "Edges (undirected segments)"),
                       ("edges_directed", "Edges (directed, bike respects oneway)"),
                       ("simplified_vertices", "Vertices after merging degree-2 nodes"),
                       ("simplified_edges_undirected", "Edges after merging degree-2 nodes"),
                       ("signal_crossings", "Crossings with signals"), ("other_crossings", "Other crossings"),
                       ("road_signals", "Road traffic signals")]:
        L.append(f"| {label} | {fmt(o['walk'][key])} | {fmt(o['bike'][key])} |")
    w = f["waits_s"]
    L += ["", "### 4. Feasibility: precompute street time for every pair of stops / stations", "",
          "Cost of a street path in seconds = length / speed + expected wait at crossings and signals on the path "
          "(\"EV wait time\"). Signal nodes closer than 30 m to each other (by path) form one junction "
          "and its wait is paid once; nodes on the short path between them (e.g. a traffic island) belong to it.",
          f"Speeds: walk {f['speeds_m_s']['walk']} m/s, bike {f['speeds_m_s']['bike']} m/s.",
          "OSM has no adopted tag for signal timings (only proposals `phases=*`, `timing=*`); "
          f"{f['nodes_with_signal_timing_tags']} signal / crossing nodes in the extract carry such a tag.",
          "So the expected wait at a signal uses the HCM average delay d = (C - g)^2 / (2C) "
          "for a fixed-time signal (C = 90 s cycle; g = 20 s pedestrian green, 30 s green on the road):",
          f"walk: signal crossing {w['walk']['crossing_signals']:.1f} s, other crossing {w['walk']['crossing']:.0f} s; "
          f"bike: signal crossing {w['bike']['crossing_signals']:.1f} s, road signal {w['bike']['traffic_signals']:.1f} s.",
          "The constants live in `backend/sources/osm.py` (`WAIT`, `SPEED`).", "",
          f"Snap of stops / stations to the walk graph: median {f['snap_to_walk_graph_m']['median']} m, "
          f"p99 {f['snap_to_walk_graph_m']['p99']} m, {f['snap_to_walk_graph_m']['over_200m']} points over 200 m "
          "(no footway nearby).", "",
          "Measured: one-to-all Dijkstra (scipy, 1 core) from random sample sources, extrapolated to all points.", "",
          "| Mode | Limit | s / source | All sources, 1 core (min) | Avg points reached | Pairs to store | Dense matrix (float32) |",
          "|---|---|---|---|---|---|---|"]
    for b in f["benchmarks"]:
        lim = f"{int(b['limit_s'] / 60)} min" if b["limit_s"] else "none"
        L.append(f"| {b['mode']} | {lim} | {b['seconds_per_source']} | {round(b['all_pairs_hours_1_core'] * 60, 1)} | "
                 f"{fmt(int(b['avg_points_reached']))} | {fmt(b['pairs_to_store'])} | {fmt(b['dense_matrix_mb_float32'])} MB |")
    L += ["", "Conclusion: full precomputation is feasible offline (done in section 5). "
          "The street paths for the first / last mile from an arbitrary address still need an online Dijkstra "
          "with a limit (one call to `/api/osm/route` style code).", ""]
    sm = r.get("street_matrix")
    if sm:
        L += ["### 5. Street matrix: every pair of stops / stations", "",
              "Built by `cd backend && uv run python preprocess_street.py` into `data/derived/street/` (git-ignored): "
              "`points.csv` (index, id, kind, lat, lon, snap per mode) and `walk.bin` / `bike.bin` "
              "(float32, shape (2, N, N): `[0]` distance_m, `[1]` wait_s; row = from, col = to; NaN = no path). "
              "Each point joins the graph through up to 6 nearest nodes (at most 30 m farther than the nearest), "
              "a multi-source Dijkstra via virtual nodes; these access segments are walked (a bike is pushed, "
              "the extra time is in wait_s). Time with the default speeds = distance_m / speed + wait_s.", "",
              f"Points: {fmt(sm['points'])}. Threads (C++): {sm['threads']}.", "",
              "| Mode | Build (min) | File | Far points (> 1000 m) | Signal nodes | Junctions | Island nodes | "
              "Median distance | Median wait | Check vs `osm.route()` (max diff) |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        checks = []
        for mode, m in sm["modes"].items():
            L.append(f"| {mode} | {round(m['seconds'] / 60, 1)} | {fmt(m['file_mb'])} MB | {m['far_points']} | "
                     f"{fmt(m['signal_nodes'])} | {fmt(m['junctions'])} | {fmt(m['junction_interior_nodes'])} | "
                     f"{fmt(m['median_distance_m'])} m | {m['median_wait_s']} s | "
                     f"{m['check_pairs']} pairs: {m['check_max_distance_diff_m']} m, {m['check_max_wait_diff_s']} s |")
            checks.append(f"- {mode}: paths shorter than the straight line: {m['shorter_than_straight_line']}; "
                          f"detour factor (pairs > 500 m apart) median {m['detour_median']}, p99 {m['detour_p99']}"
                          + (f"; A -> B vs B -> A time, max diff {m['walk_symmetry_max_diff_s']} s"
                             if m["walk_symmetry_max_diff_s"] is not None else "") + ".")
        L += ["", "Checks on 200 random rows (all columns):", ""] + checks
        L += ["", "Known limit: an L-shaped walk across two legs of the same junction pays its wait only once "
              "(an underestimate). Waits are averages (no signal timing data, no green wave).", ""]
    L += ["## Endpoints", "",
          "Run: `cd backend && uv run uvicorn main:app --reload`, docs at http://localhost:8000/docs.", "",
          "| Method | Path | What it does |", "|---|---|---|"]
    for m, path, doc in eps:
        L.append(f"| {m} | `{path}` | {doc} |")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    rep = build()
    eps = endpoints()
    rep["endpoints"] = [{"method": m, "path": p, "doc": d} for m, p, d in eps]
    save_json(DATA / "report.json", rep)
    (DATA / "REPORT.md").write_text(write_md(rep, eps))
    print("wrote data/REPORT.md and data/report.json in", rep["seconds_to_build"], "s")
