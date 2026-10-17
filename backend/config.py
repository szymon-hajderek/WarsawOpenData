"""Shared paths, area, keys and small helpers for all data sources."""
import json
import logging
import math
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
GTFS_DIR = DATA / "gtfs"
GBFS_DIR = DATA / "gbfs"
OSM_DIR = DATA / "osm"
LIVE_DIR = DATA / "live"
# Parsed caches (numpy arrays etc.). Rebuilt from raw files, git-ignored.
DERIVED = DATA / "derived"

load_dotenv(REPO / ".env")
PORTAL_KEY = os.getenv("PORTAL_KEY", "")
WAW_API_KEY = os.getenv("WAW_API_KEY", "")
PLK_KEY = os.getenv("PLK_KEY", "")

log = logging.getLogger(__name__)


class UpstreamError(RuntimeError):
    """An external API answered with something we cannot use. main.py turns it into 502."""


class MissingKey(RuntimeError):
    """A key from .env is empty. main.py turns it into 503."""


def require_key(name: str, value: str) -> str:
    if not value:
        raise MissingKey(f"{name} is not set (see ACCESS.md)")
    return value

# ZTM zone 1+2 area: the extent of all ZTM stops plus a small margin.
# Computed once from warsaw.zip (see mkuran.ztm_bbox) and kept here as a constant.
BBOX = (51.91, 20.57, 52.51, 21.48)  # (min_lat, min_lon, max_lat, max_lon)


def in_bbox(lat: float, lon: float, bbox=BBOX) -> bool:
    return bbox[0] <= lat <= bbox[2] and bbox[1] <= lon <= bbox[3]


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def to_xy(lat, lon):
    """Local equirectangular projection in metres around Warsaw (good enough for distances < 50 km).
    Works on floats and numpy arrays."""
    import numpy as np

    lat0 = 52.23
    x = np.radians(lon) * 6371000.0 * math.cos(math.radians(lat0))
    y = np.radians(lat) * 6371000.0
    return x, y


@contextmanager
def atomic_write(path: Path, mode: str = "wb", **kwargs):
    """Write to `<path>.part`, then rename. A crash never leaves a half-written `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    try:
        with open(tmp, mode, **kwargs) as f:
            yield f
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def save_json(path: Path, obj) -> None:
    with atomic_write(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=1))


def save_npz(path: Path, **arrays) -> None:
    import numpy as np

    with atomic_write(path) as f:
        np.savez_compressed(f, **arrays)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TTLCache:
    """Small thread-safe in-memory cache for live proxy endpoints. Keeps at most `maxsize` entries."""

    def __init__(self, ttl: float = 30.0, maxsize: int = 256):
        self.ttl = ttl
        self.maxsize = maxsize
        self._data: dict = {}
        self._lock = threading.Lock()

    def peek(self, key):
        """The cached value, or None when the key is missing or too old. Always None in simulation mode,
        where the clock jumps and live answers must follow it."""
        from sim import clock

        if clock.simulated():
            return None
        with self._lock:
            hit = self._data.get(key)
            if hit and time.monotonic() - hit[0] < self.ttl:
                return hit[1]
        return None

    def put(self, key, value) -> None:
        with self._lock:
            now = time.monotonic()
            if len(self._data) >= self.maxsize:
                self._data = {k: v for k, v in self._data.items() if now - v[0] < self.ttl}
                while len(self._data) >= self.maxsize:  # still full: drop the oldest
                    self._data.pop(next(iter(self._data)))
            self._data[key] = (now, value)

    def get(self, key, fetch):
        value = self.peek(key)
        if value is None:
            value = fetch()  # outside the lock: a slow upstream call must not block other keys
            self.put(key, value)
        return value
