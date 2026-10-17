"""Shared paths, area, keys and small helpers for all data sources."""
import json
import math
import os
import time
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


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TTLCache:
    """Tiny in-memory cache for live proxy endpoints."""

    def __init__(self, ttl: float = 30.0):
        self.ttl = ttl
        self._data: dict = {}

    def get(self, key, fetch):
        hit = self._data.get(key)
        if hit and time.time() - hit[0] < self.ttl:
            return hit[1]
        value = fetch()
        self._data[key] = (time.time(), value)
        return value
