"""One clock for the whole backend: real time, or the simulated time a scenario set.

All live code (vehicle feed, bus detection, route engine) reads the time here, so a test can move it.
Times are epoch seconds. Warsaw wall time is a naive datetime in Europe/Warsaw.
"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")
_sim: float | None = None


def now() -> float:
    return time.time() if _sim is None else _sim


def simulated() -> bool:
    return _sim is not None


def set_time(epoch: float) -> None:
    global _sim
    _sim = float(epoch)


def advance(seconds: float) -> None:
    set_time(now() + seconds)


def stop() -> None:
    """Back to real time."""
    global _sim
    _sim = None


def warsaw_time(epoch: float) -> datetime:
    """Naive Warsaw wall time of an epoch, independent of the server's time zone."""
    return datetime.fromtimestamp(epoch, WARSAW).replace(tzinfo=None)


def warsaw_now() -> datetime:
    return warsaw_time(now())


def warsaw_epoch(wall: datetime) -> float:
    """Epoch of a naive Warsaw wall time (as in the feeds and GTFS), independent of the server's time zone."""
    return wall.replace(tzinfo=WARSAW).timestamp()
