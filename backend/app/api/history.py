"""Speed history: turns a GPS track into per-mode trip records and records into average speeds.

Stateless on purpose (privacy): nothing is stored or logged here. The device sends a track once, gets
back records without coordinates and keeps only those. See `algorithms/speed_history.py`.
"""
import sys
from datetime import datetime, timezone

from fastapi import APIRouter

from config import REPO

sys.path.insert(0, str(REPO / "algorithms"))
from speed_history import split_track, summarize  # noqa: E402

from ..models import SpeedSummary, SummaryRequest, TripRecord, TripRecordsRequest, TripRecordsResponse

router = APIRouter(prefix="/api/history", tags=["speed history"])


@router.post("/records", response_model=TripRecordsResponse)
def trip_records(req: TripRecordsRequest) -> TripRecordsResponse:
    """Records (walking / cycling / wheelchair) of one ridden route. Empty when the track is too short or does not fit the route."""
    at = req.at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    records = split_track(
        [p.model_dump() for p in req.track],
        [leg.model_dump() for leg in req.legs],
        walk_as=req.walkAs,
        at=at,
    )
    return TripRecordsResponse(records=[TripRecord(**r) for r in records])


@router.post("/summary", response_model=SpeedSummary)
def speed_summary(req: SummaryRequest) -> SpeedSummary:
    """Average speed per mode from the records (the latest `window` of each mode)."""
    summary = summarize([r.model_dump() for r in req.records], min_trips=req.minTrips, window=req.window)
    return SpeedSummary(**summary)
