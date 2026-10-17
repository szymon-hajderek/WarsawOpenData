"""`/api/sim/*`: read and move the simulation clock, switch the scenario. Mounted only in simulation mode."""
import json
import random
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import bus_detect
from sim import clock, journey, scenario

router = APIRouter(prefix="/api/sim", tags=["simulation"])


def activate(name: str, poll: bool = True) -> scenario.Scenario:
    """Load a scenario, forget the vehicles of the previous one, read the feed once at the start time.

    `poll=False` at server start: the first read needs the GTFS cache, which loads in the background.
    """
    loaded = scenario.load(name)
    bus_detect.reset()
    if poll:
        bus_detect.poll_once()
    return loaded


def step(seconds: float | None = None, to: float | None = None) -> None:
    """Move the clock (by `seconds` or to the epoch `to`), then let bus detection read the feed."""
    if to is not None:
        clock.set_time(to)
    if seconds:
        clock.advance(seconds)
    bus_detect.poll_once()


def state() -> dict:
    loaded = scenario.current()
    now = clock.now()
    return {**loaded.describe(), "t": now, "time": clock.warsaw_time(now).isoformat(timespec="seconds"),
            "elapsed_s": round(now - loaded.start, 1)}


class ClockRequest(BaseModel):
    t: float | None = Field(None, description="set the clock to this epoch (s)")
    step_s: float | None = Field(None, ge=0, le=3600, description="then move it forward by this many seconds")


class ScenarioRequest(BaseModel):
    name: str = Field(..., pattern=r"^[a-z0-9-]{1,60}$")


@router.get("/state")
def api_state():
    """Clock time and the loaded scenario."""
    return state()


@router.post("/clock")
def api_clock(req: ClockRequest):
    """Set and / or move the simulation clock. Bus detection reads the feed at the new time."""
    step(req.step_s, req.t)
    return state()


@router.get("/scenario")
def api_scenario():
    """The loaded scenario file (trip, start time, delays, alerts, Veturilo changes)."""
    return scenario.current().spec


@router.post("/scenario")
def api_load(req: ScenarioRequest):
    """Load another scenario from integration/scenarios/ and set the clock to its start."""
    try:
        activate(req.name)
    except FileNotFoundError:
        raise HTTPException(404, "unknown scenario") from None
    return state()


def scenarios() -> list[dict]:
    """Every scenario file with its title and trip (the demo lists them)."""
    out = []
    for path in sorted(scenario.SCENARIOS.glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        out.append({"name": path.stem, "title": spec.get("title", path.stem), "source": spec["source"],
                    "trip": spec.get("trip")})
    return out


@router.get("/scenarios")
def api_scenarios():
    """The scenarios in integration/scenarios/. `trip` is null for a scenario without a planned trip."""
    return scenarios()


class RideRequest(BaseModel):
    option: dict = Field(..., description="a RouteOption as returned by POST /api/routes")
    profile: str = Field("standard", pattern=r"^[a-z]{1,20}$")
    noiseM: float = Field(15, ge=0, le=100, description="GPS error, standard deviation per axis (m)")
    seed: int = 1


_RIDE_LOCK = threading.Lock()  # the simulation clock is global: one ride at a time


def _nearest(points: list[dict]) -> list[dict]:
    """What the app gets from POST /api/live/nearest-buses, without the HTTP call."""
    req = bus_detect.NearestRequest(points=[bus_detect.UserPoint(**p) for p in points])
    return bus_detect.api_nearest_buses(req)["candidates"]


def ride(option: dict, profile: str, noise_m: float, seed: int) -> dict:
    """Travel `option` with a synthetic user from the planned departure, then put the clock back."""
    from app.routing.real_engine import PROFILE_SPEED

    if profile not in PROFILE_SPEED:
        raise ValueError(f"unknown profile: {profile}")
    loaded = scenario.current()
    with _RIDE_LOCK:
        try:
            asked = clock.now()
            step(to=max(asked, journey.planned_epoch(asked, option["departure"])))  # leave at the planned time
            run = journey.travel(None, option, profile, random.Random(seed), sigma_m=noise_m, nearest=_nearest)
        finally:
            activate(loaded.name)  # the next ride starts from the same state
    trip = run["trip"]
    return {
        "ok": trip.ok, "reason": trip.reason, "start": run["start"], "end": trip.end,
        "plan": [{"mode": leg["mode"], "line": leg.get("line"), "path": leg["path"]} for leg in option["legs"]],
        "fixes": [{"t": round(f.t, 1), "lat": round(f.lat, 6), "lon": round(f.lon, 6),
                   "trueLat": round(f.true_lat, 6), "trueLon": round(f.true_lon, 6), "leg": f.leg,
                   "vehicle": f.vehicle} for f in trip.fixes],
        "events": [{"t": round(e["t"], 1), "event": e["event"], "line": e["line"], "vehicle": e["vehicle"],
                    **({"waitedS": e["waited_s"]} if "waited_s" in e else {})} for e in trip.events],
        "detections": run["detections"],
    }


@router.post("/ride")
def api_ride(req: RideRequest):
    """Simulate a user travelling a route option and return the whole timeline (the demo plays it back).

    Takes 30-60 s for a long trip. The clock goes back to the scenario start afterwards."""
    if scenario.current() is None:
        raise HTTPException(409, "no scenario loaded")
    try:
        return ride(req.option, req.profile, req.noiseM, req.seed)
    except (KeyError, ValueError, IndexError) as e:
        raise HTTPException(422, f"bad option: {e}") from None
