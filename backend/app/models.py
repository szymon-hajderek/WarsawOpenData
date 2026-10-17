"""Pydantic models mirroring the frontend contract in `frontend/src/types.ts`.

Field names match the JSON the frontend expects (camelCase). Where a field name
clashes with a Python keyword (`from`) we use an alias so the JSON key stays right.
FastAPI serializes responses by alias, so the output matches the TypeScript types.
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# [lat, lng] pair, same as the frontend `LatLng`.
LatLng = tuple[float, float]

# Most intermediate stops on one trip.
MAX_VIA = 5

TransportMode = Literal["walk", "bike", "bus", "tram", "metro", "rail"]
Profile = Literal["standard", "slow", "accessible"]


class Place(BaseModel):
    id: str
    label: str
    sublabel: Optional[str] = None
    position: LatLng
    isCurrentLocation: Optional[bool] = None


class RouteLeg(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: TransportMode
    from_: str = Field(alias="from")
    to: str
    line: Optional[str] = None
    durationMin: int
    distanceM: float
    path: list[LatLng]
    # 1-based number of the intermediate stop this leg ends at (multi-stop trips), else None.
    stop: Optional[int] = None


class RouteOption(BaseModel):
    id: str
    title: str
    legs: list[RouteLeg]
    departure: str
    arrival: str
    durationMin: int
    distanceM: float
    calories: int
    transfers: int
    costPln: float
    tags: list[str]
    # Start, the intermediate stops in the order they are visited, destination (multi-stop trips only).
    waypoints: list[Place] = Field(default_factory=list)


class RouteRequest(BaseModel):
    """Body of `POST /api/routes` — the backend seam for the frontend's
    `fetchRouteOptions(from, to, profile)`.
    """

    model_config = ConfigDict(populate_by_name=True)

    from_: Place = Field(alias="from")
    to: Place
    profile: Profile = "standard"
    # Intermediate stops (at most MAX_VIA). `order` says whether to keep them as given or reorder
    # them for the shortest trip (start and destination stay fixed).
    via: list[Place] = Field(default_factory=list, max_length=MAX_VIA)
    order: Literal["given", "optimal"] = "given"


# ---- speed history (stateless: nothing is stored, tracks are not kept) --------------------------

SpeedMode = Literal["walking", "cycling", "wheelchair"]


class TrackPoint(BaseModel):
    lat: float
    lon: float
    t: float  # seconds (any epoch; only differences matter)


class PlannedLeg(BaseModel):
    mode: TransportMode
    distanceM: float = Field(ge=0)


class TripRecordsRequest(BaseModel):
    """Body of `POST /api/history/records`: a GPS track and the legs of the route that was ridden."""

    track: list[TrackPoint] = Field(max_length=20000)
    legs: list[PlannedLeg] = Field(max_length=30)
    # walking legs count as walking or as wheelchair
    walkAs: Literal["walking", "wheelchair"] = "walking"
    # ISO date-time of the trip; empty = now (UTC)
    at: str = Field("", max_length=40)


class TripRecord(BaseModel):
    """What the device keeps of a trip: no coordinates, only distance, moving time and speed."""

    mode: SpeedMode
    distanceM: float
    durationS: float
    kmh: float
    at: str = Field(max_length=40)


class TripRecordsResponse(BaseModel):
    records: list[TripRecord]


class SummaryRequest(BaseModel):
    """Body of `POST /api/history/summary`."""

    records: list[TripRecord] = Field(max_length=500)
    minTrips: int = Field(5, ge=1, le=50)
    window: int = Field(20, ge=1, le=200)


class ModeSummary(BaseModel):
    trips: int
    distanceKm: float
    avgKmh: Optional[float] = None
    medianKmh: Optional[float] = None
    # enough trips to use the average as the speed setting
    enough: bool


class SpeedSummary(BaseModel):
    walking: ModeSummary
    cycling: ModeSummary
    wheelchair: ModeSummary
