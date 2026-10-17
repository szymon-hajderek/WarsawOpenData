"""Trip-update delays and, when the key is set, PKP PLK delays.

A failed feed or an empty key returns an empty map. Route search still answers
from the timetable.
"""
from __future__ import annotations

import logging

import httpx

from config import PLK_KEY, TTLCache
from sim import scenario

log = logging.getLogger("uvicorn.error")

_CACHE = TTLCache(ttl=30, maxsize=4)
TRAIN_UPDATES = (
    "https://mkuran.pl/gtfs/polish_trains/updates.pb",
    "https://mkuran.pl/gtfs/wkd.pb",
)
PLK_URL = "https://pdp-api.plk-sa.pl/api/v1/operations?carriersInclude=KM,SKM&withPlanned=true"


def delays_by_trip() -> dict[str, int]:
    """GTFS-RT trip id -> delay in seconds. Both the raw id and the feed-prefixed id are stored.
    Empty in simulation mode (train delays are not simulated)."""
    if scenario.current():
        return {}
    try:
        return _CACHE.get("gtfs-rt", _trip_updates) or {}
    except Exception as exc:
        log.warning("trip updates skipped: %s", exc)
        return {}


def delays_by_station() -> dict[str, int]:
    """PLK station id -> delay in seconds. Empty when `PLK_KEY` is not set."""
    if not PLK_KEY or scenario.current():
        return {}
    try:
        return _CACHE.get("plk", _plk) or {}
    except Exception as exc:
        log.warning("PLK feed skipped: %s", exc)
        return {}


def _trip_updates() -> dict[str, int]:
    from google.transit import gtfs_realtime_pb2

    out: dict[str, int] = {}
    with httpx.Client(timeout=2.5) as client:
        for url in TRAIN_UPDATES:
            try:
                res = client.get(url)
                res.raise_for_status()
            except httpx.HTTPError as exc:
                log.warning("trip update feed failed: %s", exc)
                continue
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(res.content)
            for entity in feed.entity:
                if not entity.HasField("trip_update"):
                    continue
                update = entity.trip_update
                delay = int(update.delay or 0)
                if not delay and update.stop_time_update:
                    first = update.stop_time_update[0]
                    delay = int(first.departure.delay or first.arrival.delay or 0)
                trip = update.trip.trip_id
                if trip and delay > 0:
                    out[trip] = max(out.get(trip, 0), delay)
                    out[trip.split(":")[-1]] = max(out.get(trip.split(":")[-1], 0), delay)
    return out


def _plk() -> dict[str, int]:
    res = httpx.get(PLK_URL, headers={"X-API-Key": PLK_KEY}, timeout=2.5)
    res.raise_for_status()
    out: dict[str, int] = {}
    _collect(res.json(), out)
    return out


def _collect(node, out: dict[str, int]) -> None:
    """Read delayMinutes (minutes) or delay (seconds) next to a station id."""
    if isinstance(node, dict):
        station = node.get("stationId") or node.get("plkId") or node.get("posterunekId")
        if isinstance(station, str) and station:
            if isinstance(node.get("delayMinutes"), (int, float)):
                seconds = int(node["delayMinutes"] * 60)
            elif isinstance(node.get("delay"), (int, float)):
                seconds = int(node["delay"])
            else:
                seconds = 0
            if seconds > 0:
                out[station] = max(out.get(station, 0), seconds)
        for value in node.values():
            _collect(value, out)
    elif isinstance(node, list):
        for item in node:
            _collect(item, out)
