"""Validated opt-in events; never persist request coordinates or arbitrary payloads."""
import sys
import sqlite3
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

import city_events
from config import REPO, to_xy
from sources import nextbike
from sim import scenario

sys.path.insert(0, str(REPO / "algorithms"))
from station_siting import hex_of  # noqa: E402

router = APIRouter(prefix="/api", tags=["city research data"])
Mode = Literal["walk", "bike", "veturilo", "bus", "tram", "metro", "rail"]


def initialize():
    import logging
    try:
        city_events.store.recover()
    except (OSError, ValueError, sqlite3.Error):
        logging.getLogger(__name__).warning("city event storage unavailable")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Point(StrictModel):
    position: tuple[float, float]
    station_id: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def coordinates(self):
        lat, lon = self.position
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("invalid coordinates")
        return self


class Leg(StrictModel):
    mode: Mode
    origin: Point | None = None
    destination: Point | None = None
    duration_min: float = Field(ge=0, le=100000)
    distance_m: float = Field(ge=0, le=10000000)
    wait_s: float | None = Field(default=None, ge=0, le=1000000)
    option_index: int | None = Field(default=None, ge=0, le=10000)


class Event(StrictModel):
    event_id: UUID
    journey_id: UUID | None = None
    plan_id: UUID | None = None
    type: Literal["search", "route_selected", "journey_started", "journey_finished", "journey_interrupted"]
    age_group: Literal["<18", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"] | None = None
    origin: Point | None = None
    destination: Point | None = None
    via: list[Point] = Field(default_factory=list, max_length=5)
    legs: list[Leg] = Field(default_factory=list, max_length=100)
    result_count: int | None = Field(default=None, ge=0, le=10000)
    travel: Literal["transit", "walk", "bike"] | None = None
    departure_hour: int | None = Field(default=None, ge=0, le=23)
    elapsed_s: float | None = Field(default=None, ge=0, le=10000000)
    outcome: Literal["results", "no_results", "offline", "rejected"] | None = None
    excluded_modes: list[Mode] = Field(default_factory=list, max_length=7)
    duration_min: float | None = Field(default=None, ge=0, le=100000)
    distance_m: float | None = Field(default=None, ge=0, le=10000000)
    transfers: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def journey(self):
        if self.type != "search" and self.journey_id is None:
            raise ValueError("journey_id required")
        return self


def normalize(req):
    # Reuse the already initialized local catalog; no GTFS build in the request.
    import journey_stats
    anchors = journey_stats.store.anchors or {}
    station_ids = set()

    def point(p):
        q, r = hex_of(*to_xy(*p.position))
        result = {"hex": f"{int(q)}:{int(r)}"}
        if p.station_id in anchors:
            result["station_id"] = p.station_id
            if p.station_id.startswith("vet:"):
                station_ids.add(p.station_id[4:])
        return result

    event = req.model_dump(mode="json", exclude_none=True, exclude={"origin", "destination", "via", "legs"})
    event["schema_version"] = 1
    event["source"] = "app_action"
    event["age_group"] = req.age_group
    for key in ("origin", "destination"):
        if getattr(req, key):
            event[key] = point(getattr(req, key))
    event["via"] = [point(p) for p in req.via]
    event["legs"] = []
    for index, leg in enumerate(req.legs):
        item = leg.model_dump(exclude={"origin", "destination"}, exclude_none=True)
        item.update(leg_id=f"{req.plan_id or req.event_id}:{index + 1}", sequence=index + 1, source="planned")
        for key in ("origin", "destination"):
            if getattr(leg, key):
                item[key] = point(getattr(leg, key))
        event["legs"].append(item)
    if station_ids:
        try:
            feed = nextbike._get("station_status", True)
            timestamp = feed.get("last_updated")
            event["station_status"] = {"available": True, "feed_updated_at": timestamp,
                "feed_age_s": max(0, int(datetime.now(city_events.WARSAW).timestamp()) - timestamp) if isinstance(timestamp, (int, float)) else None,
                "stations": [{key: s.get(key) for key in ("station_id", "num_bikes_available", "num_docks_available", "is_renting", "is_returning", "last_reported")}
                             for s in feed["data"]["stations"] if s["station_id"] in station_ids]}
        except Exception:
            event["station_status"] = {"available": False}
    return event


@router.post("/city-events")
def record_event(req: Event):
    if scenario.current():
        return {"recorded": False}
    try:
        return {"recorded": city_events.store.record(normalize(req))}
    except (OSError, ValueError, sqlite3.Error) as exc:
        raise HTTPException(503, "city event storage unavailable") from exc
