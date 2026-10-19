"""Pydantic models mirroring the frontend contract in `frontend/src/types.ts`.

Field names match the JSON the frontend expects (camelCase). Where a field name
clashes with a Python keyword (`from`) we use an alias so the JSON key stays right.
FastAPI serializes responses by alias, so the output matches the TypeScript types.
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

# [lat, lng] pair, same as the frontend `LatLng`.
LatLng = tuple[float, float]
# [lon, lat] pair (GPS / GeoJSON order) for the start and end of a leg.
LonLat = tuple[float, float]

# Most intermediate stops on one trip.
MAX_VIA = 5

# `bike` = the rider's own bike, `veturilo` = a rented Veturilo bike.
TransportMode = Literal["walk", "bike", "veturilo", "bus", "tram", "metro", "rail"]
Profile = Literal["standard", "slow", "accessible", "stroller"]
# Modes a search can exclude (`RouteRequest.excludeModes`).
ExcludableMode = Literal["bus", "tram", "metro", "rail", "veturilo"]


class Place(BaseModel):
    id: str
    label: str
    sublabel: Optional[str] = None
    position: LatLng
    isCurrentLocation: Optional[bool] = None


class RouteSegment(BaseModel):
    kind: Literal["ride", "push", "walk", "steps", "elevator", "metro_access"]
    path: list[LatLng]
    lengthM: float


class RouteLeg(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: TransportMode
    from_: str = Field(alias="from")
    to: str
    line: Optional[str] = None
    durationMin: int
    distanceM: float
    path: list[LatLng]
    # Where the leg starts and ends, `[lon, lat]`. Filled from `path` when not given.
    start: Optional[LonLat] = None
    end: Optional[LonLat] = None
    fromId: Optional[str] = None
    toId: Optional[str] = None
    segments: list[RouteSegment] = Field(default_factory=list)
    # Router totals remain exact even when optional drawing segments are absent.
    _street_distances: Optional[tuple[float, float]] = PrivateAttr(default=None)
    # 1-based number of the intermediate stop this leg ends at (multi-stop trips), else None.
    stop: Optional[int] = None
    # True when GTFS has no shape for the trip and `path` only joins the stops in order.
    approximatePath: bool = False
    # Street legs: where the path boards an elevator / starts a flight of steps, `[lat, lon]`.
    elevators: Optional[list[LatLng]] = None
    steps: Optional[list[LatLng]] = None
    # Transit legs: seconds standing at the boarding stop (`fromId`) before departure, and the GTFS trip id.
    waitS: Optional[float] = None
    tripId: Optional[str] = None
    # Street legs: expected waits (signals, crossings, elevators), part of `RouteOption.waitS`.
    _street_wait: float = PrivateAttr(default=0.0)

    @model_validator(mode="after")
    def _fill_ends(self) -> "RouteLeg":
        if self.path:
            if self.start is None:
                self.start = (self.path[0][1], self.path[0][0])
            if self.end is None:
                self.end = (self.path[-1][1], self.path[-1][0])
        return self


class RouteOption(BaseModel):
    id: str
    title: str
    legs: list[RouteLeg]
    departure: str
    arrival: str
    durationMin: int
    distanceM: float
    # Metres walked (including a pushed bike) and ridden (own bike + Veturilo).
    walkDistance: float = 0
    bikeDistance: float = 0
    transfers: int
    tags: list[str]
    # Total standing: transit `waitS` at boarding stops plus street waits (signals, crossings, elevators).
    waitS: float = 0

    @model_validator(mode="after")
    def _fill_distances(self) -> "RouteOption":
        walked = ridden = 0.0
        for leg in self.legs:
            if leg._street_distances is not None:
                walk_m, bike_m = leg._street_distances
            elif leg.segments:
                bike_m = sum(s.lengthM for s in leg.segments if s.kind == "ride")
                walk_m = sum(s.lengthM for s in leg.segments if s.kind != "ride")
            else:
                walk_m = leg.distanceM if leg.mode == "walk" else 0
                bike_m = leg.distanceM if leg.mode in ("bike", "veturilo") else 0
            walked += walk_m
            ridden += bike_m
        if "walkDistance" not in self.model_fields_set:
            self.walkDistance = round(walked, 1)
        if "bikeDistance" not in self.model_fields_set:
            self.bikeDistance = round(ridden, 1)
        if "waitS" not in self.model_fields_set:
            self.waitS = round(sum((leg.waitS or 0) + leg._street_wait for leg in self.legs), 1)
        return self
    # Start, the intermediate stops in the order they are visited, destination (multi-stop trips only).
    waypoints: list[Place] = Field(default_factory=list)


class ExcludedPoint(BaseModel):
    position: LatLng
    radiusM: float = Field(default=300, ge=50, le=5000)


class Onboard(BaseModel):
    vehicleId: str = Field(min_length=1, max_length=40)  # as in POST /api/live/nearest-buses, e.g. "bus-5914"


class RouteBody(BaseModel):
    """Optional body data for the calorie estimate. Missing fields use a typical adult."""

    weightKg: Optional[float] = Field(None, ge=30, le=250)
    heightCm: Optional[float] = Field(None, ge=120, le=230)
    age: Optional[int] = Field(None, ge=10, le=100)
    sex: Optional[Literal["female", "male"]] = None
    wheelchair: Literal["none", "manual", "electric"] = "none"


class RouteRequest(BaseModel):
    """Body of `POST /api/routes` — the backend seam for the frontend's
    `fetchRouteOptions(from, to, profile)`.
    """

    model_config = ConfigDict(populate_by_name=True)

    from_: Place = Field(alias="from")
    to: Place
    profile: Profile = "standard"
    travel: Literal["transit", "walk", "accessible", "stroller", "bike"] = "transit"
    # How a transit trip reaches, leaves and changes between stops: on foot (default) or by the user's own bike,
    # carried on transit (no Veturilo then). Not combinable with a wheelchair / stroller (422).
    access: Literal["walk", "bike"] = "walk"
    # Warsaw local departure. "HH:MM" or an ISO datetime. Empty = now.
    when: Optional[str] = None
    # Intermediate stops (at most MAX_VIA). `order` says whether to keep them as given or reorder
    # them for the shortest trip (start and destination stay fixed).
    via: list[Place] = Field(default_factory=list, max_length=MAX_VIA)
    order: Literal["given", "optimal"] = "given"
    # Pace and access. Empty speeds keep the profile table. `bikeKmh` 0 means no Veturilo.
    walkKmh: Optional[float] = Field(None, ge=1, le=10)
    bikeKmh: Optional[float] = Field(None, ge=0, le=45)
    stepFree: bool = False
    # Rent a Veturilo bike only at docks with at least this many bikes now (live state). None / 0 = every dock.
    minBikes: Optional[int] = Field(None, ge=0, le=50)
    # None = up to two transfers. 0 = direct rides only.
    maxTransfers: Optional[int] = Field(None, ge=0, le=2)
    excludedDistricts: list[str] = Field(default_factory=list, max_length=18)
    excludedPoints: list[ExcludedPoint] = Field(default_factory=list, max_length=20)
    body: Optional[RouteBody] = None
    # Modes the search must not use (a GTFS trolleybus counts as bus; veturilo = no rented bike, own bike stays).
    excludeModes: list[ExcludableMode] = Field(default_factory=list, max_length=5)
    # Plan from the vehicle the user is in (timetable only): its next stops are the origins; `from` is ignored.
    onboard: Optional[Onboard] = None

    @model_validator(mode="after")
    def _bike_access_alone(self) -> "RouteRequest":
        if self.access == "bike" and (
            self.profile in ("accessible", "stroller") or self.travel in ("accessible", "stroller")
            or self.stepFree or (self.body is not None and self.body.wheelchair != "none")
        ):
            raise ValueError("access 'bike' cannot be combined with a wheelchair or stroller")
        return self


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
