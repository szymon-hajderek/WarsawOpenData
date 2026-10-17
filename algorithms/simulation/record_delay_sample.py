"""Record live bus + tram positions and the live delay answers of our server, for the delay simulation.

Needs the local server running (cd backend && uv run uvicorn main:app). Every 3 s it reads
/api/live/vehicles?type=bus and ?type=tram and keeps every new feed point of every vehicle; every 30 s it asks
/api/live/delay for the vehicles of LINES (what the live server said at that moment).

Run from backend/:  uv run python ../algorithms/simulation/record_delay_sample.py [minutes] [base url]
Writes data/live/delay_sample.json.gz:
  {"date": "YYYY-MM-DD", "started", "minutes", "lines",
   "polls": [[t, mode, ok]],                       # every poll, ok = 0 when it failed
   "vehicles": {"bus-1234": {"mode", "runs": [{"line", "brigade", "points": [[t, lat, lon]]}]}},
   "live": [{"t", "answer": <GET /api/live/delay answer>}]}
t = seconds since local midnight of "date" (Warsaw time, as in the feed), so the file does not depend on the
time zone of the computer that reads it.
"""
import gzip
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "live" / "delay_sample.json.gz"
LINES = ["175", "180", "523", "189", "17", "33"]  # buses and trams, centre and outskirts
POLL_S, LIVE_S = 3, 30
MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 30
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"

started = None
day = None
polls, live = [], []
vehicles: dict[str, dict] = {}


def sec(local_time: str) -> int:
    global day
    clock = datetime.strptime(local_time, "%Y-%m-%d %H:%M:%S")
    if day is None:
        day = clock.date()
    return int((clock - datetime.combine(day, datetime.min.time())).total_seconds())


def now_sec() -> int:
    """Our clock as feed-time seconds: last feed point seen (the computer may run in another time zone)."""
    return max((r["points"][-1][0] for v in vehicles.values() for r in v["runs"][-1:]), default=0)


client = httpx.Client(timeout=30)
end = time.time() + MINUTES * 60
next_live = time.time() + LIVE_S
while time.time() < end:
    t0 = time.time()
    for mode in ("bus", "tram"):
        try:
            r = client.get(f"{BASE}/api/live/vehicles", params={"type": mode})
            r.raise_for_status()
            rows = r.json()
        except Exception as e:  # a failed poll is part of the data: the simulation sees it as a break
            polls.append([now_sec(), mode, 0])
            print(f"{mode} poll failed: {e}", flush=True)
            continue
        for v in rows:
            t = sec(v["time"])
            veh = vehicles.setdefault(f"{mode}-{v['vehicle']}", {"mode": mode, "runs": []})
            runs = veh["runs"]
            if not runs or runs[-1]["line"] != v["line"] or runs[-1]["brigade"] != v["brigade"]:
                runs.append({"line": v["line"], "brigade": v["brigade"], "points": []})
            pts = runs[-1]["points"]
            if not pts or t > pts[-1][0]:
                pts.append([t, round(v["lat"], 6), round(v["lon"], 6)])
        polls.append([now_sec(), mode, 1])
        started = started or datetime.now().isoformat(timespec="seconds")
    if time.time() >= next_live:
        next_live += LIVE_S
        t = now_sec()
        asked = 0
        for vid, veh in vehicles.items():
            if veh["runs"][-1]["line"] not in LINES or t - veh["runs"][-1]["points"][-1][0] > 60:
                continue
            try:
                r = client.get(f"{BASE}/api/live/delay", params={"vehicle": vid})
                if r.status_code == 200:
                    live.append({"t": t, "answer": r.json()})
                    asked += 1
            except Exception as e:
                print(f"delay {vid} failed: {e}", flush=True)
        n = sum(len(r["points"]) for v in vehicles.values() for r in v["runs"])
        print(f"{datetime.now():%H:%M:%S} {len(vehicles)} vehicles, {n} points, {asked} live answers", flush=True)
    time.sleep(max(0.0, POLL_S - (time.time() - t0)))

OUT.parent.mkdir(parents=True, exist_ok=True)
with gzip.open(OUT, "wt", encoding="utf-8") as f:
    json.dump({"date": day.isoformat(), "started": started, "minutes": MINUTES, "lines": LINES,
               "polls": polls, "vehicles": vehicles, "live": live}, f, separators=(",", ":"))
print(f"saved {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
