"""Private SQLite event journal and recoverable daily JSON files for city research."""
import calendar
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import REPO, atomic_write

WARSAW = ZoneInfo("Europe/Warsaw")


class EventStore:
    def __init__(self, directory):
        self.directory = Path(directory)

    def connect(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        conn = sqlite3.connect(self.directory / "journal.sqlite", timeout=15)
        conn.execute("PRAGMA secure_delete=ON")
        conn.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, day TEXT, hour TEXT, body TEXT)")
        conn.execute("CREATE INDEX IF NOT EXISTS events_day ON events(day)")
        return conn

    def maintain(self, conn, now):
        year = now.year - 1
        cutoff = now.date().replace(year=year, day=min(now.day, calendar.monthrange(year, now.month)[1])).isoformat()
        conn.execute("DELETE FROM events WHERE day < ?", (cutoff,))
        for path in self.directory.glob("????-??-??.json"):
            if path.stem < cutoff:
                path.unlink()

    def export(self, conn, day):
        hours = {f"{hour:02}": [] for hour in range(24)}
        for hour, body in conn.execute("SELECT hour, body FROM events WHERE day=? ORDER BY rowid", (day,)):
            hours[hour].append(json.loads(body))
        with atomic_write(self.directory / f"{day}.json", "w", encoding="utf-8") as stream:
            json.dump({"schema_version": 1, "day": day, "timezone": "Europe/Warsaw", "hours": hours},
                      stream, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())

    def recover(self):
        with closing(self.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            self.maintain(conn, datetime.now(WARSAW))
            for (day,) in conn.execute("SELECT DISTINCT day FROM events").fetchall():
                self.export(conn, day)

    def record(self, event, now=None):
        now = (now or datetime.now(WARSAW)).astimezone(WARSAW)
        day, hour = now.date().isoformat(), now.strftime("%H")
        # The journal commits before export: failed exports are repaired by retries/startup.
        with closing(self.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            self.maintain(conn, now)
            inserted = conn.execute("INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?)",
                                    (event["event_id"], day, hour, json.dumps(event, allow_nan=False))).rowcount
        with closing(self.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            saved = conn.execute("SELECT day FROM events WHERE id=?", (event["event_id"],)).fetchone()
            if saved:
                self.export(conn, saved[0])
        return bool(inserted)


store = EventStore(os.getenv("CITY_EVENTS_DIR") or REPO / "db" / "city-events")
