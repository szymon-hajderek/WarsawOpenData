"""Write the names of our stops and Veturilo stations for the frontend's offline place search.

Usage (from backend/, needs the GTFS and Veturilo data, see `download.py`):
    uv run python export_places.py

Output: frontend/src/data/places.json, a list of [name, lat, lon, kind] (kind 0 = stop, 1 = Veturilo station),
one entry per distinct stop name (at the centre of its posts). The frontend searches it when the backend is
not reachable (`frontend/src/utils/placeSearch.ts`). Run it again when the timetable or the stations change.
"""
import json
import sys

from config import REPO

sys.path.insert(0, str(REPO / "algorithms"))
import place_search  # noqa: E402
from sources import mkuran, nextbike  # noqa: E402

OUT = REPO / "frontend" / "src" / "data" / "places.json"


def main() -> None:
    stops = place_search.group_by_name(
        [{"name": s["name"], "lat": s["lat"], "lon": s["lon"]} for s in mkuran.vertices() if s.get("name")]
    )
    stations = [s for s in nextbike.stations() if s.get("name")]
    rows = [[p["name"], round(p["lat"], 5), round(p["lon"], 5), 0] for p in stops]
    rows += [[s["name"], round(s["lat"], 5), round(s["lon"], 5), 1] for s in stations]
    rows.sort(key=lambda r: (place_search.fold(r[0]), r[3]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(rows)} places ({len(stops)} stops, {len(stations)} stations) -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
