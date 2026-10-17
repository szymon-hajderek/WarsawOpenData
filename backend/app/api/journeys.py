"""Completed journey statistics, separate from stateless speed history."""
import re
import sqlite3
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

import journey_stats

router = APIRouter(prefix="/api", tags=["journey statistics"])


class JourneyPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str = Field(min_length=1, max_length=160)
    position: tuple[float, float]
    isCurrentLocation: bool = False

    @model_validator(mode="after")
    def valid_point(self):
        lat, lon = self.position
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("invalid journey coordinates")
        if self.isCurrentLocation:
            if self.id != "current-location":
                raise ValueError("current location requires current-location id")
        elif not re.fullmatch(r"(?:osm:(?:node|way|relation):\d+|(?:ztm|wkd|pkp|vet):[^\s:]+)", self.id):
            raise ValueError("invalid journey point id")
        return self


class JourneyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    token: UUID
    from_: JourneyPoint = Field(alias="from")
    to: JourneyPoint


class JourneyResponse(BaseModel):
    recorded: bool


@router.post("/journeys", response_model=JourneyResponse)
def record_journey(req: JourneyRequest) -> JourneyResponse:
    try:
        return JourneyResponse(recorded=journey_stats.store.record(req.token, req.from_, req.to))
    except (journey_stats.Unavailable, OSError, sqlite3.Error) as exc:
        raise HTTPException(503, "journey statistics unavailable") from exc
    except ValueError as exc:
        raise HTTPException(422, "unknown journey point id") from exc
