"""Synthetic user: GPS noise, movement along a polyline and a whole trip along a planned route.

The user walks and cycles along the leg geometry at the profile speed. On a bus or tram leg the user
waits at the stop for a synthetic vehicle of that line that goes to the leg's last stop, rides with it
and gets off near that stop. Metro and rail have no live feed, so those legs follow the plan in time.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from config import haversine_m
from sim import clock, synth

M_PER_DEG = 111195.0


def offset(lat: float, lon: float, east_m: float, north_m: float) -> tuple[float, float]:
    return lat + north_m / M_PER_DEG, lon + east_m / (M_PER_DEG * math.cos(math.radians(lat)))


class GpsNoise:
    """GPS error that drifts slowly, like a real receiver: AR(1) offset with standard deviation `sigma_m`
    per axis. A new random point every fix would invent a lot of distance on a slow walk."""

    def __init__(self, sigma_m: float, rng: random.Random, rho: float = 0.9):
        self.sigma, self.rng, self.rho = sigma_m, rng, rho
        self.e = rng.gauss(0, sigma_m)
        self.n = rng.gauss(0, sigma_m)

    def apply(self, lat: float, lon: float) -> tuple[float, float]:
        k = self.sigma * math.sqrt(1 - self.rho ** 2)
        self.e = self.rho * self.e + self.rng.gauss(0, k)
        self.n = self.rho * self.n + self.rng.gauss(0, k)
        return offset(lat, lon, self.e, self.n)


def along(path: list, metres: float) -> tuple[float, float]:
    """The point `metres` along a [[lat, lon], ...] polyline (clamped to its ends)."""
    if metres <= 0 or len(path) < 2:
        return tuple(path[0])
    done = 0.0
    for a, b in zip(path, path[1:]):
        seg = haversine_m(a[0], a[1], b[0], b[1])
        if done + seg >= metres and seg > 0:
            f = (metres - done) / seg
            return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
        done += seg
    return tuple(path[-1])


def length(path: list) -> float:
    return sum(haversine_m(a[0], a[1], b[0], b[1]) for a, b in zip(path, path[1:]))


def interpolate(track: list[tuple[float, float, float]], t: float) -> tuple[float, float]:
    """Position at time `t` on a [(t, lat, lon), ...] track, linear between points."""
    if t <= track[0][0]:
        return track[0][1], track[0][2]
    for a, b in zip(track, track[1:]):
        if t <= b[0]:
            f = 0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
            return a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f
    return track[-1][1], track[-1][2]


# ---------------------------------------------------------------- whole trip (gtfs scenarios)

BOARD_RADIUS_M = 80  # a vehicle this close to the waiting user is "at the stop"
ALIGHT_RADIUS_M = 80
MAX_WAIT_S = 30 * 60


@dataclass
class Fix:
    t: float
    lat: float  # what the phone reports (with GPS error)
    lon: float
    true_lat: float
    true_lon: float
    leg: int
    vehicle: str | None = None  # vehicle id as in bus detection ("bus-S131-2") while riding


@dataclass
class Trip:
    fixes: list[Fix] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    ok: bool = True
    reason: str = ""

    @property
    def end(self) -> float:
        return self.fixes[-1].t


class Walker:
    """Moves the clock in steps of `step_s` and records a fix every step. `on_step` runs after each step."""

    def __init__(self, noise: GpsNoise, step_s: float, on_step=None):
        self.noise, self.step_s, self.on_step = noise, step_s, on_step
        self.trip = Trip()

    def fix(self, lat, lon, leg, vehicle=None):
        noisy = self.noise.apply(lat, lon)
        self.trip.fixes.append(Fix(clock.now(), noisy[0], noisy[1], lat, lon, leg, vehicle))
        if self.on_step:
            self.on_step(self.trip)

    def tick(self):
        clock.advance(self.step_s)

    def move(self, path, speed_mps, leg):
        total = length(path)
        done = 0.0
        while done < total:
            self.tick()
            done = min(total, done + speed_mps * self.step_s)
            self.fix(*along(path, done), leg)

    def follow_plan(self, path, minutes, leg):
        """A leg without a live feed (metro, rail): move along the path in the planned time."""
        self.move(path, max(0.5, length(path) / max(60.0, minutes * 60)), leg)

    def ride(self, path, line, mode, leg, delays) -> bool:
        """Wait for a vehicle of `line` that reaches the end of `path`, ride with it, get off there."""
        here, goal = path[0], path[-1]
        waited = 0.0
        vehicle = None
        while vehicle is None:
            for v in synth.vehicles(clock.now(), delays):
                if v["line"] != line or v["mode"] != mode:
                    continue
                if haversine_m(v["lat"], v["lon"], here[0], here[1]) > BOARD_RADIUS_M:
                    continue
                later = [s for s in synth.trip_stops(v["trip"]) if s["dist"] > v["dist"]]
                if any(haversine_m(s["lat"], s["lon"], goal[0], goal[1]) < 150 for s in later):
                    vehicle = v
                    break
            if vehicle is None:
                if waited >= MAX_WAIT_S:
                    self.trip.ok, self.trip.reason = False, f"no {line} came in {MAX_WAIT_S // 60} min"
                    return False
                self.tick()
                waited += self.step_s
                self.fix(here[0], here[1], leg)
        vid = f"{mode}-{vehicle['vehicle']}"
        self.trip.events.append({"t": clock.now(), "event": "board", "line": line, "vehicle": vid,
                                 "waited_s": waited})
        best = math.inf
        while True:
            self.tick()
            v = next((x for x in synth.vehicles(clock.now(), delays)
                      if x["vehicle"] == vehicle["vehicle"] and x["trip"] == vehicle["trip"]), None)
            if v is None:  # the trip ended: get off where the vehicle was last seen
                break
            self.fix(v["lat"], v["lon"], leg, vid)
            gap = haversine_m(v["lat"], v["lon"], goal[0], goal[1])
            if gap < ALIGHT_RADIUS_M or gap > best + 300:  # at the stop, or it went past it
                break
            best = min(best, gap)
        self.trip.events.append({"t": clock.now(), "event": "alight", "line": line, "vehicle": vid})
        return True


def follow(option: dict, speeds: dict, noise: GpsNoise, step_s: float = 5, on_step=None,
           delays=None) -> Trip:
    """Travel along a RouteOption (JSON form) from the clock's current time."""
    walker = Walker(noise, step_s, on_step)
    start = option["legs"][0]["path"][0]
    walker.fix(start[0], start[1], 0)
    for i, leg in enumerate(option["legs"]):
        path = leg["path"]
        if walker.trip.fixes:  # start each leg where the user is (a vehicle can stop a bit off the path)
            last = walker.trip.fixes[-1]
            path = [[last.true_lat, last.true_lon], *path]
        if leg["mode"] in ("walk", "bike", "veturilo"):
            walker.move(path, speeds["walk" if leg["mode"] == "walk" else "bike"], i)
        elif leg["mode"] in ("bus", "tram"):
            if not walker.ride(leg["path"], leg["line"], leg["mode"], i, delays or {}):
                break
        else:
            walker.follow_plan(path, leg["durationMin"], i)
    return walker.trip


# ---------------------------------------------------------------- a planned trip with bus detection

DETECT_EVERY_S = 10  # the app sends a fix to bus detection every 10 s (last 3 fixes)


def planned_epoch(start_epoch: float, hhmm: str) -> float:
    """Epoch of an `HH:MM` on the day of `start_epoch` (Warsaw time), the next day when it is earlier."""
    day = clock.warsaw_time(start_epoch)
    hour, minute = map(int, hhmm.split(":"))
    at = clock.warsaw_epoch(day.replace(hour=hour, minute=minute, second=0, microsecond=0))
    return at + 86400 if at < start_epoch - 3600 else at


def travel(client, option: dict, profile: str, rng: random.Random, sigma_m: float = 15,
           delays=None, step_s: float = 5) -> dict:
    """Follow `option` from now. Bus detection reads the feed every 10 s; while riding, the app asks
    `/api/live/nearest-buses` with the last 3 detection fixes. Returns the trip and the detection ranks."""
    import bus_detect
    from app.routing.real_engine import PROFILE_SPEED

    sent: list[dict] = []
    ranks: list[int | None] = []
    state = {"next": clock.now()}

    def on_step(trip: Trip):
        if clock.now() < state["next"]:
            return
        state["next"] += DETECT_EVERY_S
        bus_detect.poll_once()
        f = trip.fixes[-1]
        sent.append({"lat": f.lat, "lon": f.lon, "time_ms": f.t * 1000})
        if f.vehicle and len(sent) >= 3:
            r = client.post("/api/live/nearest-buses", json={"points": sent[-3:]})
            ids = [c["id"] for c in r.json()["candidates"]] if r.status_code == 200 else []
            ranks.append(ids.index(f.vehicle) + 1 if f.vehicle in ids else None)

    from sim import scenario

    if delays is None and scenario.current():
        delays = scenario.current().delays
    start = clock.now()
    trip = follow(option, PROFILE_SPEED[profile], GpsNoise(sigma_m, rng), step_s, on_step, delays)
    return {"trip": trip, "ranks": ranks, "start": start}


def replay_of(option: dict, run: dict, every: int = 2) -> dict:
    """What the replay page needs: the plan, the fixes (every `every`-th) and the events."""
    trip = run["trip"]
    return {"plan": [{"mode": leg["mode"], "line": leg.get("line"), "path": leg["path"]} for leg in option["legs"]],
            "fixes": [[round(f.t, 1), round(f.lat, 6), round(f.lon, 6), round(f.true_lat, 6), round(f.true_lon, 6),
                       f.leg, f.vehicle] for f in trip.fixes[::every]],
            "events": trip.events, "ranks": run["ranks"]}
