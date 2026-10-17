"""Opt-in daily object-to-object counters. Never persist a raw GPS track or user ID."""
import logging
import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import REPO

sys.path.insert(0, str(REPO / "algorithms"))
from journey_points import nearest_anchor  # noqa: E402

log = logging.getLogger(__name__)


class Unavailable(RuntimeError):
    pass


class JourneyStore:
    def __init__(self, path: Path):
        self.path = path
        self.anchors = None

    def prepare(self, anchors):
        """Called during startup, never from a request."""
        self.anchors = None
        if not anchors:
            raise Unavailable()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS places (
                    id TEXT PRIMARY KEY, lat REAL NOT NULL, lon REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS journeys (
                    day TEXT NOT NULL, from_id TEXT NOT NULL, to_id TEXT NOT NULL,
                    count INTEGER NOT NULL CHECK (count > 0),
                    PRIMARY KEY (day, from_id, to_id),
                    FOREIGN KEY (from_id) REFERENCES places(id),
                    FOREIGN KEY (to_id) REFERENCES places(id)
                );
                CREATE TABLE IF NOT EXISTS receipts (token TEXT PRIMARY KEY);
            """)
        self.anchors = {a[0]: a for a in anchors}

    def resolve(self, point):
        if point.isCurrentLocation:
            return nearest_anchor(point.position, self.anchors.values())
        if point.id.startswith("osm:"):
            return point.id, *point.position
        if point.id not in self.anchors:
            raise ValueError("unknown journey point id")
        return self.anchors[point.id]

    def record(self, token, origin, destination):
        if self.anchors is None:
            raise Unavailable()
        with closing(sqlite3.connect(self.path, timeout=5)) as conn, conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("BEGIN IMMEDIATE")
            inserted = conn.execute("INSERT OR IGNORE INTO receipts VALUES (?)", (str(token),))
            if not inserted.rowcount:
                return False
            start, end = self.resolve(origin), self.resolve(destination)
            for point in (start, end):
                conn.execute("""INSERT INTO places VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET lat=excluded.lat, lon=excluded.lon""", point)
            day = datetime.now(ZoneInfo("Europe/Warsaw")).date().isoformat()
            conn.execute("""INSERT INTO journeys VALUES (?, ?, ?, 1)
                ON CONFLICT(day, from_id, to_id) DO UPDATE SET count=count+1""", (day, start[0], end[0]))
        return True


store = JourneyStore(Path(os.getenv("JOURNEY_STATS_DB") or REPO / "db" / "journey_stats.sqlite"))


def initialize():
    """Read local catalogs once; a missing source may fall back to the other catalog."""
    from sources import mkuran, nextbike

    anchors = []
    try:
        anchors.extend((s["id"], s["lat"], s["lon"]) for s in mkuran.stops_by_id().values()
                       if s.get("location_type", 0) == 0 and not s.get("same_as") and s.get("served", True))
    except (OSError, ValueError, KeyError):
        log.warning("journey transit anchors unavailable")
    try:
        anchors.extend((s["id"], s["lat"], s["lon"]) for s in nextbike.stations(live=False))
    except (OSError, ValueError, KeyError):
        log.warning("journey Veturilo anchors unavailable")
    try:
        store.prepare(anchors)
    except (OSError, sqlite3.Error, Unavailable):
        log.warning("journey statistics initialization unavailable")
