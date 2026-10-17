"""Integration tests: synthetic trips on real data, against the whole backend in simulation mode.

Run from backend/: `uv run pytest ../integration` (all), `-m recorded` or `-m gtfs`.
One app for the whole session (the GTFS and OSM caches load once, about 1-2 minutes).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "backend", ROOT / "algorithms", ROOT / "integration"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import results  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "recorded: replays a recording of the live City Hall feed")
    config.addinivalue_line("markers", "gtfs: vehicles made from the GTFS timetable (deterministic)")


def pytest_sessionfinish(session, exitstatus):
    results.write()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    import main
    from sim import api as sim_api

    if not any(getattr(r, "path", "").startswith("/api/sim") for r in main.app.routes):
        main.app.include_router(sim_api.router)
    yield TestClient(main.app)


@pytest.fixture(scope="session")
def gtfs_ready():
    from sources import mkuran

    mkuran.warm()


@pytest.fixture(scope="session")
def osm_ready():
    from sources import osm

    osm.warm()


@pytest.fixture
def scenario(client):
    """`scenario("name")` loads integration/scenarios/name.json; simulation mode ends after the test."""
    from sim import api as sim_api
    from sim import scenario as sim_scenario

    def load(name: str):
        return sim_api.activate(name)

    yield load
    sim_scenario.unload()
