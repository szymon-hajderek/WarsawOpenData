"""Route list without duplicates (`real_engine._finish`): `pytest tests` from `backend/` (no data files)."""
from app.models import RouteLeg, RouteOption
from app.routing.real_engine import _finish
from route_delays import trip_ids_from_option


def ride(trip: str, line="M1", frm="a", to="b") -> RouteLeg:
    return RouteLeg.model_validate({"mode": "metro", "from": frm, "to": to, "line": line, "durationMin": 10,
                                    "distanceM": 5000.0, "path": [(0, 0), (0, 1)], "fromId": frm, "toId": to,
                                    "tripId": trip})


def opt(trip: str, dep: str, arr: str, minutes: int) -> RouteOption:
    return RouteOption(id=f"pt-{trip}", title="M1", legs=[ride(trip)], departure=dep, arrival=arr,
                       durationMin=minutes, distanceM=5000.0, transfers=0, tags=[])


def test_same_rides_same_arrival_keep_the_latest_departure():
    out = _finish([opt("ztm:t1", "17:31", "18:06", 35), opt("ztm:t1", "17:35", "18:06", 31)])
    assert [(o.departure, o.durationMin) for o in out] == [("17:35", 31)]


def test_frequency_runs_stay_apart_with_unique_ids():
    out = _finish([opt("ztm:M1:NdM:KAB", "06:00", "06:20", 20), opt("ztm:M1:NdM:KAB", "06:08", "06:28", 20)])
    assert [o.id for o in out] == ["pt-ztm:M1:NdM:KAB", "pt-ztm:M1:NdM:KAB@0608"]
    assert trip_ids_from_option(out[1].id) == ["ztm:M1:NdM:KAB"]
