"""`/api/sim/*`: read and move the simulation clock, switch the scenario. Mounted only in simulation mode."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import bus_detect
from sim import clock, scenario

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
