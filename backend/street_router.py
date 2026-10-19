"""Client of the C++ street router (algorithms/router/): point-to-point paths for walk, bike, accessible and stroller,
and transit trips planned by RAPTOR (plan()).

The backend starts the router at startup (start(), from main.py) and stops it at shutdown. Set ROUTER_URL to use
a router that runs elsewhere; then nothing is started. API and file formats: algorithms/router/README.md.
"""
import logging
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from config import DERIVED, REPO

URL = os.getenv("ROUTER_URL", "").rstrip("/")
PORT = int(os.getenv("ROUTER_PORT", "8090"))
BINARY = REPO / "algorithms" / "router" / "build" / "street_router"
GRAPHS = DERIVED / "street"
LOG = GRAPHS / "router.log"
log = logging.getLogger("uvicorn.error")

_proc: subprocess.Popen | None = None
_http = httpx.Client(timeout=30)


class RouterUnavailable(RuntimeError):
    """The router does not answer (not started, crashed, wrong ROUTER_URL)."""


class RouteError(ValueError):
    """The router answered with an error: 400 bad request, 404 no path, 422 point too far from the graph."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def base_url() -> str:
    return URL or f"http://127.0.0.1:{PORT}"


def _place(p):
    return p if isinstance(p, str) else [p[0], p[1]]


def _post(path: str, body: dict) -> dict:
    try:
        r = _http.post(f"{base_url()}{path}", json=body)
    except httpx.TransportError as e:
        raise RouterUnavailable(f"street router not reachable at {base_url()}: {e}") from e
    data = r.json()
    if r.status_code == 501:
        raise NotImplementedError(f"street router does not support: {', '.join(data['unimplemented'])}")
    if r.status_code != 200:
        raise RouteError(r.status_code, data.get("error", r.text))
    return data


def route(a, b, mode: str = "walk", **options) -> dict:
    """Path from a to b ((lat, lon) each, or a location id of stations.json).  Extra options are relayed as they
    are; the router answers 501 (NotImplementedError here) for the ones it does not support yet. The answer is
    returned unchanged: `legs` (always), and in the older format also top-level totals. Read the legs
    (app/routing/real_engine.legs_from_router)."""
    body = {"from": _place(a), "to": _place(b), "mode": mode, **options}
    return _post("/route", body)


def access(point, mode: str = "walk", direction: str = "from", limit_s: float = 900, **options) -> list[dict]:
    """Every station reachable from `point` within limit_s (direction "from"), or from which `point` is reachable
    ("to"). `point` = (lat, lon) or a location id. Returns [{id, seconds, walk_m, bike_m, wait_s}], nearest first."""
    body = {"point": list(point) if not isinstance(point, str) else point, "mode": mode, "direction": direction,
            "limit_s": limit_s, **options}
    return _post("/access", body)["stations"]


SERVICE_DAY_CUTOFF_H = 4  # before 04:00 a trip is planned on the previous GTFS service day (times past 24:00)


def service_time(when: datetime) -> tuple[str, int]:
    """A moment -> (service day YYYYMMDD, seconds after its midnight), Europe/Warsaw."""
    local = when.astimezone(ZoneInfo("Europe/Warsaw")) if when.tzinfo else when
    day = local.date() - timedelta(days=1) if local.hour < SERVICE_DAY_CUTOFF_H else local.date()
    seconds = int((local.replace(tzinfo=None) - datetime(day.year, day.month, day.day)).total_seconds())
    return day.strftime("%Y%m%d"), seconds


def plan(a, b, mode: str = "walk", when: datetime | None = None, **options) -> list[dict]:
    """Transit trips from a to b ((lat, lon) or a location id) leaving at `when` (naive = Warsaw local time; default
    now), planned by RAPTOR in the router. Options are relayed (speeds, max_legs, access_s, egress_s, footpath_s,
    veturilo_s, veturilo_pickup_s, veturilo_return_s, exclude_modes, min_bikes; date / time instead of `when`). Returns the options:
    [{seconds, dep_s, arr_s, transfers, walk_m, bike_m, wait_s, legs}], times in seconds after midnight of the
    service day. Format: algorithms/router/README.md ("POST /plan")."""
    if "date" not in options:
        options["date"], options["time"] = service_time(when or datetime.now(ZoneInfo("Europe/Warsaw")))
    return _post("/plan", {"from": _place(a), "to": _place(b), "mode": mode, **options})["options"]


STATE_EVERY_S = 30  # as the Veturilo status cache (sources/nextbike.py)
_state_thread: threading.Thread | None = None


def push_state() -> dict:
    """Send the live bikes per Veturilo dock to the router (POST /state; `min_bikes` of /plan reads it). A dock that
    does not rent counts as 0 bikes. Returns {"veturilo": {"docks", "unknown"}}."""
    from sources import nextbike

    bikes = {f"vet:{s['station_id']}": 0 if s["renting"] in (False, 0) else s["bikes"] for s in nextbike.status()}
    return _post("/state", {"veturilo": bikes})


def _state_loop() -> None:
    while True:
        try:
            push_state()
        except Exception as e:  # the feed or the router is down: try again next time
            log.warning("street router: Veturilo state not sent: %s", e)
        time.sleep(STATE_EVERY_S)


def _start_state_loop() -> None:
    global _state_thread
    if _state_thread is None:
        _state_thread = threading.Thread(target=_state_loop, daemon=True, name="router-state")
        _state_thread.start()


def health() -> dict:
    try:
        return _http.get(f"{base_url()}/health", timeout=5).json()
    except httpx.TransportError as e:
        raise RouterUnavailable(f"street router not reachable at {base_url()}: {e}") from e


def healthy() -> bool:
    try:
        return _http.get(f"{base_url()}/health", timeout=2).status_code == 200
    except httpx.TransportError:
        return False


def start(timeout_s: float = 120) -> None:
    """Write the graph files and the timetable if they are missing or stale, start `street_router serve` and wait
    until it answers."""
    global _proc
    if URL:
        log.info("street router: using %s", URL)
        _start_state_loop()
        return
    import preprocess_street  # imported here: it loads GTFS and OSM
    import preprocess_transit
    import stations

    if stations.stale():
        log.info("street router: building stations.json (the StationLocations overlay)")
        stations.build()
    if preprocess_street.graphs_stale():
        log.info("street router: writing graph files")
        preprocess_street.write_graphs()
    if preprocess_transit.stale():
        log.info("street router: writing the RAPTOR timetable")
        log.info("street router: timetable %s", preprocess_transit.build())
    if not BINARY.exists():
        raise RouterUnavailable(f"{BINARY} not built, see algorithms/router/README.md")
    if healthy():
        log.warning("street router: something already answers on port %s; using it", PORT)
        _start_state_loop()
        return
    _proc = subprocess.Popen([str(BINARY), "serve", str(GRAPHS), "--port", str(PORT)], stdout=open(LOG, "ab"),
                             stderr=subprocess.STDOUT)
    t0 = time.time()
    while not healthy():
        if _proc.poll() is not None or time.time() - t0 > timeout_s:
            raise RouterUnavailable(f"street router did not start, see {LOG}")
        time.sleep(0.5)
    log.info("street router: serving on %s (%.0f s)", base_url(), time.time() - t0)
    _start_state_loop()


def stop() -> None:
    global _proc
    if _proc and _proc.poll() is None:
        _proc.terminate()
        _proc.wait(timeout=10)
    _proc = None
