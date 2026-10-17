"""The loaded simulation scenario: what the live feeds return at the current clock time.

A scenario is a JSON file in `integration/scenarios/` (format in `integration/README.md`). Two sources:
- `recorded`: vehicle positions replayed from a recording of the City Hall feed;
- `gtfs`: vehicle positions made from the timetable (`sim/synth.py`), with optional delays.
In both, Veturilo status is the saved GBFS file plus per-station changes over time, and alerts are a list
of lines over time. Nothing here calls an external API.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path

from config import GBFS_DIR, REPO, load_json
from sim import clock, synth

SCENARIOS = REPO / "integration" / "scenarios"
PUBLIC = ("line", "brigade", "lat", "lon", "time", "vehicle", "mode", "route_id")
REPLAY_GAP_S = 30  # after the last recorded poll + this, the recorded feed is empty

_current: Scenario | None = None


def _recording(path: Path) -> list[dict]:
    """Polls of a recording with true epochs and the feed's Warsaw wall time per vehicle.

    `record_buses.py` stores vehicle times as the wall time read in the recorder's own time zone. The poll
    time is a true epoch, so the whole-hour difference between the two gives that zone back.
    """
    polls = sorted(load_json(path), key=lambda p: p["poll"])
    out = []
    for p in polls:
        if not p["vehicles"]:
            continue
        shift = round((max(v["t"] for v in p["vehicles"]) - p["poll"]) / 3600) * 3600
        rows = []
        for v in p["vehicles"]:
            mode, _, number = v["id"].partition("-")
            rows.append({"line": v["line"], "brigade": v["brigade"], "lat": v["lat"], "lon": v["lon"],
                         "time": clock.warsaw_time(v["t"] - shift).strftime("%Y-%m-%d %H:%M:%S"),
                         "vehicle": number, "mode": mode, "route_id": f"ztm:{v['line']}", "t": v["t"] - shift})
        out.append({"poll": p["poll"], "vehicles": rows})
    return out


class Scenario:
    def __init__(self, spec: dict, name: str):
        self.spec = spec
        self.name = name
        self.source = spec["source"]
        if self.source not in ("recorded", "gtfs"):
            raise ValueError("source must be recorded or gtfs")
        self.polls = _recording(REPO / spec["recording"]) if self.source == "recorded" else []
        if "start" in spec:
            self.start = clock.warsaw_epoch(datetime.fromisoformat(spec["start"]))
        elif self.polls:
            self.start = self.polls[0]["poll"]
        else:
            raise ValueError("a gtfs scenario needs a start time")
        self.delays: dict[tuple[str, str | None], float] = {}
        self.alerts: list[tuple[float, set[str]]] = []
        self.stations: list[tuple[float, str, int, int | None]] = []
        for d in spec.get("delays", []):
            self.set_delay(d["line"], d.get("brigade"), d["delay_s"])
        for a in spec.get("alerts", []):
            self.add_alert(a["lines"], self.start + a.get("from_s", 0))
        for s in spec.get("veturilo", []):
            self.set_station(s["station_id"], s["bikes"], s.get("docks"), self.start + s.get("from_s", 0))

    # ------------------------------------------------------------ changes during a test

    def set_delay(self, line: str, brigade: str | None, seconds: float) -> None:
        self.delays[(str(line), None if brigade is None else str(brigade))] = float(seconds)

    def add_alert(self, lines, at: float | None = None) -> None:
        self.alerts.append((clock.now() if at is None else at, {str(x) for x in lines}))

    def set_station(self, station_id: str, bikes: int, docks: int | None = None, at: float | None = None) -> None:
        self.stations.append((clock.now() if at is None else at, str(station_id), int(bikes), docks))

    # ------------------------------------------------------------ feeds

    def vehicles(self, kind: str, full: bool = False) -> list[dict]:
        """The vehicle feed at the clock time, in the form of `um_warszawa.fetch_vehicles`."""
        now = clock.now()
        if self.source == "gtfs":
            rows = [v for v in synth.vehicles(now, self.delays) if v["mode"] == kind]
        else:
            seen = [p for p in self.polls if p["poll"] <= now]
            if not seen or now - seen[-1]["poll"] > REPLAY_GAP_S:
                return []
            rows = [v for v in seen[-1]["vehicles"] if v["mode"] == kind]
        return rows if full else [{k: v[k] for k in PUBLIC} for v in rows]

    def alerted_lines(self) -> set[str]:
        now = clock.now()
        return set().union(*(lines for at, lines in self.alerts if at <= now))

    def gbfs(self, name: str) -> dict:
        """A saved GBFS file; `station_status` with the station changes that started by now."""
        data = load_json(GBFS_DIR / f"veturilo_{name}.json")
        if name != "station_status":
            return data
        now = clock.now()
        latest: dict[str, tuple[int, int | None]] = {}
        for at, station_id, bikes, docks in sorted(self.stations, key=lambda s: s[0]):
            if at <= now:
                latest[station_id] = (bikes, docks)
        if not latest:
            return data
        classic = next((t["vehicle_type_id"] for t in self.gbfs("vehicle_types")["data"]["vehicle_types"]
                        if t.get("propulsion_type") != "electric_assist"), None)
        data = copy.deepcopy(data)
        for row in data["data"]["stations"]:
            if row["station_id"] in latest:
                bikes, docks = latest[row["station_id"]]
                row["num_bikes_available"] = bikes
                row["vehicle_types_available"] = [{"vehicle_type_id": classic, "count": bikes}] if bikes else []
                if docks is not None:
                    row["num_docks_available"] = docks
        return data

    def describe(self) -> dict:
        return {"scenario": self.name, "source": self.source, "start": self.start,
                "title": self.spec.get("title", self.name)}


def find(name: str) -> Path:
    """`name` of a file in integration/scenarios/ (without .json), or a path."""
    path = SCENARIOS / f"{name}.json"
    if path.exists():
        return path
    path = Path(name)
    if path.suffix == ".json" and path.exists():
        return path
    raise FileNotFoundError(f"unknown scenario: {name}")


def load(name: str) -> Scenario:
    """Turn simulation mode on with this scenario and set the clock to its start."""
    global _current
    path = find(name)
    _current = Scenario(json.loads(path.read_text(encoding="utf-8")), path.stem)
    clock.set_time(_current.start)
    return _current


def unload() -> None:
    global _current
    _current = None
    clock.stop()


def current() -> Scenario | None:
    return _current
