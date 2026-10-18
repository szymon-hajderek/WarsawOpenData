"""RAPTOR in the C++ router (POST /plan) against a brute-force search. Run from backend/: uv run pytest ../algorithms

A toy city: the 5 x 5 street grid of test_street_model (walk and bike graphs), 6 posts and 2 Veturilo docks on its
nodes, matrices built from the router's own /route answers (so the planner and the leg traces agree), and random
small timetables (shared stops, loops, overtaking trips, other service days, trips after midnight).
"""
import dataclasses
import itertools
import json
import random
import subprocess
import time
import urllib.error
import urllib.request

import numpy as np
import pytest

import timetable_file
from test_street_model import BIKE, CPP, free_port, grid_city, post, street_graph

pytestmark = pytest.mark.skipif(not CPP.exists(), reason="C++ street_router not built")

DATE, YESTERDAY, OTHER = 20261021, 20261020, 20261023
POSTS = [0, 4, 12, 20, 24, 8]  # grid nodes of the six posts
DOCKS = [2, 22]                # grid nodes of the two Veturilo docks
IDS = [f"ztm:p{i}" for i in range(len(POSTS))] + [f"vet:{i}" for i in range(len(DOCKS))]
N = len(IDS)
PICKUP, RETURN = 30.0, 15.0
INF = float("inf")
WALK = 0.25  # the toy graphs' default walking speed (m/s): slow, so that rides and transfers matter in a small grid


def save_graphs(street):
    lat, lon, src, dst, ln, wait, flags, entry = grid_city()
    usable = np.ones(len(lat), bool)
    none = np.zeros(0, int)
    for name, walk, bike in (("walk", ln, np.zeros(len(src))), ("bike", np.zeros(len(src)), ln)):
        g = street_graph(src, dst, walk, bike, wait, none, none, len(lat), flags=flags, lon=lon, lat=lat,
                         usable=usable, entry=entry)
        dataclasses.replace(g, walk_speed=WALK).save(street / f"graph_{name}.bin")


def save_overlay(path, hash_="toy"):
    lat, lon, *_ = grid_city()
    nodes = POSTS + DOCKS
    locs = [{"id": id_, "kind": "veturilo" if id_.startswith("vet:") else "bus_post",
             "position": {"lat": float(lat[n]), "lon": float(lon[n])}, "entrances": [], "transfers": []}
            for id_, n in zip(IDS, nodes)]
    doc = {"hash": hash_, "constants": {"metro_access_m": 150.0, "elevator_s": 60.0, "no_steps": ["bike"]},
           "locations": locs}
    path.write_text(json.dumps(doc))


def serve(street):
    port = free_port()
    proc = subprocess.Popen([str(CPP), "serve", str(street), "--port", str(port), "--threads", "2"],
                            stderr=subprocess.DEVNULL)
    for _ in range(200):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as r:
                return proc, port, json.loads(r.read())
        except urllib.error.URLError:
            time.sleep(0.05)
    proc.kill()
    raise RuntimeError("server did not start")


@pytest.fixture(scope="module")
def city(tmp_path_factory):
    """Graphs, overlay, points.csv, meta.json and the walk / bike matrices (from /route by id)."""
    root = tmp_path_factory.mktemp("city")
    street = root / "street"
    street.mkdir()
    save_graphs(street)
    save_overlay(root / "stations.json")
    proc, port, health = serve(street)
    mats = {}
    try:
        assert health["plan"]["walk"] == "no timetable.bin"
        for mode in ("walk", "bike"):
            m = np.zeros((3, N, N), dtype="<f4")
            for i, j in itertools.permutations(range(N), 2):
                status, got = post(port, {"from": IDS[i], "to": IDS[j], "mode": mode})
                assert status == 200
                leg = got["legs"][0]
                m[:, i, j] = leg["walk_m"], leg["bike_m"], leg["wait_s"]
            m.tofile(street / f"{mode}.bin")
            mats[mode] = m.astype(float)
    finally:
        proc.terminate()
        proc.wait()
    lat, lon, *_ = grid_city()
    rows = ["index,id,kind,source,lat,lon,snap_walk_m,snap_bike_m,entrances"]
    rows += [f"{i},{id_},x,gtfs,0,0,0,0,0" for i, id_ in enumerate(IDS)]
    (street / "points.csv").write_text("\n".join(rows) + "\n")
    (street / "meta.json").write_text(json.dumps({"stations_hash": "toy", "walk": {"points": 1}}))
    return street, mats


def write_timetable(street, trips, hash_="toy"):
    """trips: dicts {route, service (0 = DATE, 1 = YESTERDAY, 2 = OTHER), calls [(loc, arr, dep)]}."""
    for k, t in enumerate(trips):
        t.setdefault("id", f"trip{k}")
        t.setdefault("headsign", f"to {t['calls'][-1][0]}")
    routes = [(f"ztm:r{r}", str(100 + r), "bus") for r in range(max(t["route"] for t in trips) + 1)]
    with open(street / "timetable.bin", "wb") as f:
        timetable_file.write(f, hash_, N, routes, [[str(DATE)], [str(YESTERDAY)], [str(OTHER)]],
                             **timetable_file.pack(trips))


def plan(port, **body):
    return post(port, {"mode": "walk", "date": str(DATE), **body}, path="/plan")


# ---------------------------------------------------------------- brute force


def secs(m, i, j, walk=WALK, bike=BIKE):
    return m[0, i, j] / walk + m[1, i, j] / bike + m[2, i, j]


def brute_force(trips, mats, o, d, t0, veturilo=True, footpath_s=INF, max_legs=8, speeds=(WALK, BIKE)):
    """Pareto set [(counted legs, arrival)] by rounds over every trip and boarding stop, without any RAPTOR trick:
    best[k][p] = earliest arrival with <= k legs; a round rides every trip from every stop reached in the previous
    round (or rents a bike at a reached dock), then walks once from the stops it improved."""
    walk = mats["walk"]
    runs = [[(loc, a + shift, dp + shift) for loc, a, dp in t["calls"]]
            for t in trips for shift in ([0] if t["service"] == 0 else [-86400] if t["service"] == 1 else [])]
    best = [t0 + (0 if p == o else secs(walk, o, p, *speeds)) for p in range(N)]
    out, target = [], t0 + secs(walk, o, d, *speeds)
    out.append((0, target))
    for k in range(1, max_legs + 1):
        ride = [INF] * N
        for calls in runs:
            for i, (p, _, dep) in enumerate(calls):
                if best[p] <= dep:
                    for q, arr, _ in calls[i + 1:]:
                        ride[q] = min(ride[q], arr)
        if veturilo:
            for u, v in itertools.permutations(range(len(POSTS), N), 2):
                ride[v] = min(ride[v], best[u] + PICKUP + secs(mats["bike"], u, v, speeds[0], BIKE) + RETURN)
        new = [min(best[p], ride[p]) for p in range(N)]
        for p in range(N):
            if ride[p] < best[p]:
                for q in range(N):
                    if q != p and secs(walk, p, q, *speeds) <= footpath_s:
                        new[q] = min(new[q], ride[p] + secs(walk, p, q, *speeds))
        best = new
        arrival = min(best[p] + (0 if p == d else secs(walk, p, d, *speeds)) for p in range(N))
        if arrival < target - 1.0:  # the router keeps an option only when >= 1 s earlier
            target = arrival
            out.append((k, arrival))
    return out


def counted(option):
    return sum(leg["mode"] not in ("walk", "bike") for leg in option["legs"])


def random_trips(rng, t0):
    trips = []
    for r in range(rng.randint(3, 6)):
        stops = rng.sample(range(len(POSTS)), rng.randint(2, 5))
        if rng.random() < 0.3 and len(stops) > 2:
            stops.append(stops[0])  # a loop: the first stop again at the end
        for _ in range(rng.randint(2, 8)):
            service = rng.choice([0, 0, 0, 1, 2])
            t = t0 + rng.randint(-200, 900) + (86400 if service == 1 else 0)
            calls = []
            for loc in stops:
                dwell = rng.choice([0, 0, 20])
                calls.append((loc, t, t + dwell))
                t += dwell + rng.randint(10, 150)  # different speeds: trips overtake each other
            trips.append({"route": r, "service": service, "calls": calls})
    return trips


def check_answer(got, t0):
    """Leg chain, times and totals of every option."""
    prev = None
    for o in got["options"]:
        assert o["dep_s"] >= t0 - 0.11
        assert o["seconds"] == pytest.approx(o["arr_s"] - o["dep_s"], abs=0.11)
        assert o["seconds"] == pytest.approx(sum(l["seconds"] for l in o["legs"]), abs=0.3)
        assert o["wait_s"] == pytest.approx(sum(l["wait_s"] for l in o["legs"]), abs=0.3)
        assert o["transfers"] == max(0, counted(o) - 1)
        for a, b in zip(o["legs"], o["legs"][1:]):
            assert a["to"] == b["from"]
        if prev is not None:
            assert counted(o) > prev[0] and o["arr_s"] < prev[1]
        prev = counted(o), o["arr_s"]


def same(got, want):
    have = [(counted(x), x["arr_s"]) for x in got["options"]]
    assert [k for k, _ in have] == [k for k, _ in want], (have, want)
    assert np.allclose([a for _, a in have], [a for _, a in want], atol=0.3), (have, want)


@pytest.mark.parametrize("seed", range(100))
def test_plan_matches_brute_force(city, seed):
    street, mats = city
    rng = random.Random(seed)
    t0 = rng.choice([8 * 3600, 600])  # morning, or just after midnight (yesterday's late trips)
    trips = random_trips(rng, t0)
    write_timetable(street, trips)
    proc, port, health = serve(street)
    try:
        assert health["plan"] == {"walk": "ok", "bike": "ok"}
        for _ in range(6):
            o, d = rng.sample(range(N), 2)
            status, got = plan(port, **{"from": IDS[o], "to": IDS[d], "time": t0})
            assert status == 200, got
            check_answer(got, t0)
            want = brute_force(trips, mats, o, d, t0)
            same(got, want)
    finally:
        proc.terminate()
        proc.wait()


def test_limits_speeds_and_bike_mode_match_brute_force(city):
    street, mats = city
    rng = random.Random(99)
    trips = random_trips(rng, 8 * 3600)
    write_timetable(street, trips)
    proc, port, _ = serve(street)
    try:
        for o, d in itertools.permutations(range(len(POSTS)), 2):
            for extra, kwargs in (({"footpath_s": 100}, {"footpath_s": 100}), ({"max_legs": 1}, {"max_legs": 1}),
                                  ({"speeds": {"walk": 2.0, "bike": BIKE}}, {"speeds": (2.0, BIKE)})):
                status, got = plan(port, **{"from": IDS[o], "to": IDS[d], "time": 8 * 3600, **extra})
                assert status == 200
                want = brute_force(trips, mats, o, d, 8 * 3600, **kwargs)
                same(got, want)
            # bike mode: own bike, no Veturilo, footpaths ridden from the bike matrix
            status, got = plan(port, **{"from": IDS[o], "to": IDS[d], "time": 8 * 3600, "mode": "bike"})
            assert status == 200 and all(l["mode"] != "veturilo" for x in got["options"] for l in x["legs"])
            want = brute_force(trips, {"walk": mats["bike"], "bike": mats["bike"]}, o, d, 8 * 3600, veturilo=False)
            same(got, want)
    finally:
        proc.terminate()
        proc.wait()


@pytest.fixture
def served(city):
    """A server on a timetable given by the test: served(trips) -> port."""
    street, _ = city
    procs = []

    def start(trips, hash_="toy"):
        write_timetable(street, trips, hash_)
        proc, port, health = serve(street)
        procs.append(proc)
        return port, health

    yield start
    for p in procs:
        p.terminate()
        p.wait()


def test_overtaking_trip_is_found(served):
    # trip 0 leaves first but arrives last; trip 1 overtakes it: a single pattern would only ever board trip 0
    port, _ = served([{"route": 0, "service": 0, "calls": [(0, 1000, 1000), (1, 1200, 1200), (4, 1400, 1400)]},
                      {"route": 0, "service": 0, "calls": [(0, 1010, 1010), (1, 1050, 1050), (4, 1100, 1100)]}])
    status, got = plan(port, **{"from": IDS[0], "to": IDS[4], "time": 900, "veturilo_s": 0})
    ride = [l for l in got["options"][-1]["legs"] if l["mode"] == "bus"]
    assert status == 200 and ride[0]["trip_id"] == "trip1" and ride[0]["arr_s"] == 1100


def test_after_midnight_uses_yesterdays_trip_and_the_service_day(served):
    trips = [{"route": 0, "service": 1, "calls": [(0, 86400 + 700, 86400 + 700), (4, 86400 + 760, 86400 + 760)]},
             {"route": 0, "service": 2, "calls": [(0, 650, 650), (4, 680, 680)]}]  # another day only
    port, _ = served(trips)
    status, got = plan(port, **{"from": IDS[0], "to": IDS[4], "time": 600, "veturilo_s": 0})
    o = got["options"][-1]
    ride = [l for l in o["legs"] if l["mode"] == "bus"][0]
    assert status == 200 and ride["trip_id"] == "trip0" and (ride["dep_s"], ride["arr_s"]) == (700, 760)
    assert ride["stops"] == [{"id": IDS[0], "arr_s": 700, "dep_s": 700}, {"id": IDS[4], "arr_s": 760, "dep_s": 760}]
    assert ride["wait_s"] == 0 and o["dep_s"] == 700  # leaves just in time
    status, got = plan(port, **{"from": IDS[0], "to": IDS[4], "time": 600, "date": str(OTHER), "veturilo_s": 0})
    rides = [l for l in got["options"][-1]["legs"] if l["mode"] == "bus"]
    assert status == 200 and rides[0]["trip_id"] == "trip1" and got["options"][-1]["arr_s"] == 680


def test_transit_leg_fields_and_wait_at_a_transfer(served, city):
    # p0 -> p1 by bus, walk p1 -> p5, bus p5 -> p4. Walking straight to p5 misses that bus; the first bus catches it.
    _, mats = city
    walk15 = secs(mats["walk"], 1, 5)
    dep = int(np.ceil(1020 + walk15 + 5))
    assert 900 + secs(mats["walk"], 0, 5) > dep
    trips = [{"route": 0, "service": 0, "calls": [(0, 1000, 1000), (1, 1020, 1020)]},
             {"route": 1, "service": 0, "calls": [(5, dep - 10, dep), (4, dep + 20, dep + 20)]}]
    port, _ = served(trips)
    status, got = plan(port, **{"from": IDS[0], "to": IDS[4], "time": 900, "veturilo_s": 0})
    check_answer(got, 900)
    o = got["options"][-1]
    assert status == 200 and [l["mode"] for l in o["legs"]] == ["bus", "walk", "bus"]
    first, foot, second = o["legs"]
    assert first == {"mode": "bus", "line": "100", "route_id": "ztm:r0", "trip_id": "trip0", "headsign": "to 1",
                     "from": IDS[0], "to": IDS[1], "dep_s": 1000, "arr_s": 1020, "seconds": 20.0, "wait_s": 0.0,
                     "stops": [{"id": IDS[0], "arr_s": 1000, "dep_s": 1000}, {"id": IDS[1], "arr_s": 1020, "dep_s": 1020}]}
    assert foot["from"] == IDS[1] and foot["to"] == IDS[5] and "from_snap_m" not in foot
    assert foot["seconds"] == pytest.approx(walk15, abs=0.11) and foot["path"] and foot["segments"]
    assert second["wait_s"] == pytest.approx(dep - 1020 - walk15, abs=0.2)  # standing at the stop, not walking
    assert second["seconds"] == pytest.approx(second["wait_s"] + 20, abs=0.2) and second["dep_s"] == dep
    assert o["dep_s"] == 1000 and o["arr_s"] == dep + 20 and o["transfers"] == 1


def test_coordinate_ends_are_null_with_snap(served):
    lat, lon, *_ = grid_city()
    port, _ = served([{"route": 0, "service": 0, "calls": [(0, 1000, 1000), (4, 1050, 1050)]}])
    a, b = [float(lat[0]) + 0.0001, float(lon[0])], [float(lat[24]), float(lon[24]) - 0.0001]
    status, got = plan(port, **{"from": a, "to": b, "time": 600, "veturilo_s": 0})
    assert status == 200
    check_answer(got, 600)
    street_only, transit = got["options"]
    assert street_only["legs"][0]["from"] is None and street_only["legs"][0]["to"] is None
    first, ride, last = transit["legs"]
    assert first["from"] is None and first["to"] == IDS[0] and first["from_snap_m"] > 0 and "to_snap_m" not in first
    assert ride["mode"] == "bus" and last["from"] == IDS[4] and last["to"] is None and "to_snap_m" in last


def test_veturilo_is_a_counted_leg_only_on_foot(served, city):
    _, mats = city
    port, _ = served([{"route": 0, "service": 0, "calls": [(0, 99000, 99000), (1, 99100, 99100)]}])
    d0, d1 = len(POSTS), len(POSTS) + 1
    status, got = plan(port, **{"from": IDS[d0], "to": IDS[d1], "time": 1000})
    bike = got["options"][-1]
    assert status == 200 and counted(bike) == 1 and bike["transfers"] == 0
    leg = bike["legs"][0]
    assert leg["mode"] == "veturilo" and (leg["from"], leg["to"]) == (IDS[d0], IDS[d1])
    assert (leg["pickup_s"], leg["return_s"]) == (PICKUP, RETURN)
    assert leg["seconds"] == pytest.approx(PICKUP + secs(mats["bike"], d0, d1) + RETURN, abs=0.11)
    assert leg["wait_s"] == pytest.approx(PICKUP + RETURN + mats["bike"][2, d0, d1], abs=0.11)
    status, got = plan(port, **{"from": IDS[d0], "to": IDS[d1], "time": 1000, "veturilo_pickup_s": 100,
                                "veturilo_return_s": 0})
    assert got["options"][-1]["legs"][0]["seconds"] == pytest.approx(100 + secs(mats["bike"], d0, d1), abs=0.11)
    for extra in ({"veturilo_s": 0}, {"mode": "bike"}):
        status, got = plan(port, **{"from": IDS[d0], "to": IDS[d1], "time": 1000, **extra})
        assert status == 200 and all(l["mode"] != "veturilo" for o in got["options"] for l in o["legs"])


def test_errors(served, city):
    street, _ = city
    port, health = served([{"route": 0, "service": 0, "calls": [(0, 1000, 1000), (1, 1100, 1100)]}])
    ok = {"from": IDS[0], "to": IDS[1], "time": 600}
    assert health["timetable"]["status"] == "ok" and health["timetable"]["trips"] == 1
    assert plan(port, **ok, **{"date": "2026-10-21"})[0] == 400
    assert plan(port, **ok, **{"date": "20261341"})[0] == 400
    assert plan(port, **{**ok, "time": "08:30"})[0] == 400
    assert plan(port, **ok, max_legs=-1)[0] == 400
    assert plan(port, **ok, footpath_s=-5)[0] == 400
    assert plan(port, **ok, preferences={}) == (501, {"error": "not implemented", "unimplemented": ["preferences"]})
    assert plan(port, **{**ok, "to": "ztm:nope"})[0] == 404
    status, got = plan(port, **ok, max_legs=0)
    assert status == 200 and [counted(o) for o in got["options"]] == [0]
    # a timetable for another overlay, or a matrix of the wrong size / for another overlay: refused, not guessed
    port, health = served([{"route": 0, "service": 0, "calls": [(0, 1000, 1000), (1, 1100, 1100)]}], hash_="old")
    assert health["timetable"]["status"] == "stale" and plan(port, **ok)[0] == 503
    meta = (street / "meta.json").read_text()
    try:
        (street / "meta.json").write_text(json.dumps({"stations_hash": "old"}))
        port, health = served([{"route": 0, "service": 0, "calls": [(0, 1000, 1000), (1, 1100, 1100)]}])
        assert "stations_hash" in health["plan"]["walk"] and plan(port, **ok)[0] == 503
    finally:
        (street / "meta.json").write_text(meta)
    bike = (street / "bike.bin").read_bytes()
    try:
        (street / "bike.bin").write_bytes(bike[:-4])
        port, health = served([{"route": 0, "service": 0, "calls": [(0, 1000, 1000), (1, 1100, 1100)]}])
        assert "bytes" in health["plan"]["bike"] and health["plan"]["walk"] == "ok"
        status, got = plan(port, **ok)  # walk still plans, without Veturilo
        assert status == 200 and plan(port, **ok, mode="bike")[0] == 503
    finally:
        (street / "bike.bin").write_bytes(bike)
