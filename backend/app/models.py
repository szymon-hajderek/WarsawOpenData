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
