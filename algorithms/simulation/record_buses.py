"""Record live ZTM bus positions (City Hall API, needs PORTAL_KEY in .env) every 10 s for 2 minutes.

Run from backend/:  uv run python ../algorithms/simulation/record_buses.py
Writes data/live/bus_track_sample.json: a list of polls {"poll", "vehicles": [{id, line, brigade, lat, lon, t}]},
"t" in epoch seconds.
"""
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))
from config import LIVE_DIR, save_json  # noqa: E402
from sources.um_warszawa import fetch_vehicles, fresh  # noqa: E402

POLLS, EVERY_S = 13, 10  # 0 .. 120 s
OUT = LIVE_DIR / "bus_track_sample.json"


def epoch(local_time: str) -> float:
    return datetime.strptime(local_time, "%Y-%m-%d %H:%M:%S").timestamp()


snaps = []
for i in range(POLLS):
    t0 = time.time()
    try:
        rows = [{"id": f"bus-{v['vehicle']}", "line": v["line"], "brigade": v["brigade"],
                 "lat": v["lat"], "lon": v["lon"], "t": epoch(v["time"])}
                for v in fresh(fetch_vehicles("bus"))]
        snaps.append({"poll": t0, "vehicles": rows})
        print(f"poll {i}: {len(rows)} buses", flush=True)
    except Exception as e:  # one failed poll should not stop the recording
        print(f"poll {i} failed: {e}", flush=True)
    time.sleep(max(0.0, EVERY_S - (time.time() - t0)))

save_json(OUT, snaps)
print(f"saved {OUT}")
