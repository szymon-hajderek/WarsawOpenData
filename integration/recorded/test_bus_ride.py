"""Scenario 1 on a recording: users ride real buses; the backend must tell which bus each one is on.

The clock moves through the recording. Each user's phone reports a position every 10 s (the bus position
between two feed reports, plus GPS error). After each fix the app asks `/api/live/nearest-buses` with the
last 1-3 fixes, as the frontend does.

The fixes fall between feed reports (as on a real phone), so a bus of another line a few dozen metres
away on the same street sometimes ranks first. That is why top-1 is lower here than in
`algorithms/simulation/RESULTS.md`, where users stand exactly on the feed points.
"""
import random

import pytest

import results
from config import haversine_m
from sim.journey import GpsNoise, interpolate
from sim import api as sim_api

pytestmark = pytest.mark.recorded


def _moving_buses(polls, min_m=300, min_reports=8):
    tracks: dict[str, list] = {}
    for p in polls:
        for v in p["vehicles"]:
            track = tracks.setdefault(f"{v['mode']}-{v['vehicle']}", [])
            if not track or track[-1][0] != v["t"]:
                track.append((v["t"], v["lat"], v["lon"]))
    return {vid: t for vid, t in tracks.items()
            if len(t) >= min_reports and haversine_m(t[0][1], t[0][2], t[-1][1], t[-1][2]) >= min_m}


def test_detects_the_bus_the_user_rides(client, gtfs_ready, scenario):
    sc = scenario("recorded-bus-ride")
    spec = sc.spec["test"]
    rng = random.Random(spec["seed"])
    moving = _moving_buses(sc.polls)
    chosen = rng.sample(sorted(moving), min(spec["users"], len(moving)))
    users = [{"bus": vid, "track": moving[vid], "noise_m": spec["noise_m"][i % len(spec["noise_m"])],
              "points": [], "ranks": []} for i, vid in enumerate(chosen)]
    for u in users:
        u["gps"] = GpsNoise(u["noise_m"], rng)

    first = sc.polls[0]["poll"]
    last = sc.polls[-1]["poll"]
    t = first + 5
    feed_ok = True
    while t <= last:
        sim_api.step(to=t)
        feed = client.get("/api/live/vehicles", params={"type": "bus"}).json()
        feed_ok &= len(feed) > 800
        for u in users:
            if t > u["track"][-1][0]:
                continue
            lat, lon = u["gps"].apply(*interpolate(u["track"], t))
            u["points"].append({"lat": lat, "lon": lon, "time_ms": t * 1000})
            r = client.post("/api/live/nearest-buses", json={"points": u["points"][-3:]})
            assert r.status_code == 200, r.text
            ids = [c["id"] for c in r.json()["candidates"]]
            u["ranks"].append((min(len(u["points"]), 3), ids.index(u["bus"]) + 1 if u["bus"] in ids else None))
        t += spec["every_s"]

    three = [rank for u in users for n, rank in u["ranks"] if n == 3]
    one = [rank for u in users for n, rank in u["ranks"] if n == 1]
    top4 = sum(r is not None for r in three) / len(three)
    top1 = sum(r == 1 for r in three) / len(three)
    top1_one = sum(r == 1 for r in one) / len(one)

    delay = client.get("/api/live/delay", params={"vehicle": users[0]["bus"]})
    checks = [
        ("the replayed feed has the recorded buses at every step (> 800)", feed_ok),
        ("own bus in the top 4 for at least 98% of requests with 3 fixes", top4 >= 0.98),
        ("own bus first for at least 75% of requests with 3 fixes", top1 >= 0.75),
        ("/api/live/delay answers for a ridden bus", delay.status_code == 200),
    ]
    results.record("recorded-bus-ride", sc.spec["title"], "recorded", {
        "users": len(users), "GPS error (m)": "/".join(map(str, spec["noise_m"])),
        "requests with 3 fixes": len(three), "top-4 with 3 fixes (%)": 100 * top4,
        "top-1 with 3 fixes (%)": 100 * top1, "top-1 with 1 fix (%)": 100 * top1_one,
    }, checks, replay={"users": [{"bus": u["bus"], "noise_m": u["noise_m"], "points": u["points"],
                                  "ranks": u["ranks"]} for u in users]})
    for name, ok in checks:
        assert ok, name
