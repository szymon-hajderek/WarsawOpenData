"""Speed history endpoints: `pytest tests` from `backend/` (a small app with just this router)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import history

app = FastAPI()
app.include_router(history.router)
client = TestClient(app)

M_PER_DEG_LAT = 111_195.0


def walk_track(metres=1000, kmh=5.0, step_s=5.0):
    speed = kmh / 3.6
    points, lat, t, walked = [{"lat": 52.0, "lon": 21.0, "t": 0.0}], 52.0, 0.0, 0.0
    while walked < metres:
        d = min(speed * step_s, metres - walked)
        walked += d
        lat += d / M_PER_DEG_LAT
        t += d / speed
        points.append({"lat": lat, "lon": 21.0, "t": t})
    return points


def test_records_from_a_track():
    body = {"track": walk_track(), "legs": [{"mode": "walk", "distanceM": 1000}], "at": "2026-10-17T10:00:00+00:00"}
    r = client.post("/api/history/records", json=body)
    assert r.status_code == 200
    rec = r.json()["records"][0]
    assert rec["mode"] == "walking" and abs(rec["kmh"] - 5.0) < 0.2
    assert rec["at"] == "2026-10-17T10:00:00+00:00"
    assert set(rec) == {"mode", "distanceM", "durationS", "kmh", "at"}  # no coordinates come back


def test_wheelchair_and_default_date():
    body = {"track": walk_track(kmh=3.6), "legs": [{"mode": "walk", "distanceM": 1000}], "walkAs": "wheelchair"}
    rec = client.post("/api/history/records", json=body).json()["records"][0]
    assert rec["mode"] == "wheelchair" and rec["at"]


def test_a_track_that_does_not_fit_gives_no_records():
    body = {"track": walk_track(metres=300), "legs": [{"mode": "walk", "distanceM": 3000}]}
    assert client.post("/api/history/records", json=body).json() == {"records": []}


def test_oversized_input_is_rejected():
    body = {"track": [{"lat": 0, "lon": 0, "t": i} for i in range(20001)], "legs": []}
    assert client.post("/api/history/records", json=body).status_code == 422


def test_summary_of_records():
    records = [
        {"mode": "walking", "distanceM": 1000, "durationS": 720, "kmh": 5.0, "at": f"2026-10-0{i}"} for i in range(1, 6)
    ]
    s = client.post("/api/history/summary", json={"records": records}).json()
    assert s["walking"]["trips"] == 5 and s["walking"]["enough"] is True
    assert abs(s["walking"]["avgKmh"] - 5.0) < 0.1
    assert s["cycling"]["trips"] == 0 and s["cycling"]["avgKmh"] is None


def test_summary_min_trips_can_be_changed():
    records = [{"mode": "cycling", "distanceM": 3000, "durationS": 720, "kmh": 15.0, "at": "2026-10-01"}]
    s = client.post("/api/history/summary", json={"records": records, "minTrips": 1}).json()
    assert s["cycling"]["enough"] is True
