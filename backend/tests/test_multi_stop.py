"""Trips with intermediate stops: `pytest tests` from `backend/` (needs no timetable data)."""
import pytest
from pydantic import ValidationError

from app.models import Place, RouteLeg, RouteOption, RouteRequest
from app.routing.engine import RouteEngine
from app.routing.multi import combine, query_multi


def place(name: str, lat: float, lon: float) -> Place:
    return Place(id=name, label=name, position=(lat, lon))


def option(oid: str, duration: int, *, cost=0.0, calories=0, title="Test", transfers=0, leg_to="") -> RouteOption:
    leg = RouteLeg.model_validate(
        {"mode": "walk", "from": "x", "to": leg_to, "durationMin": duration, "distanceM": duration * 80.0, "path": [(0, 0), (0, 1)]}
    )
    return RouteOption(
        id=oid, title=title, legs=[leg], departure="10:00", arrival="10:00", durationMin=duration,
        distanceM=duration * 80.0, calories=calories, transfers=transfers, costPln=cost, tags=[],
    )


class FakeEngine(RouteEngine):
    """Returns the canned options for a (from, to) pair, or one default option."""

    def __init__(self, table=None):
        self.table = table or {}
        self.calls: list[tuple[str, str]] = []

    def query_routes(self, frm, to, profile):
        self.calls.append((frm.id, to.id))
        return self.table.get((frm.id, to.id), [option(f"{frm.id}{to.id}", 10, leg_to=to.label)])

    def update_state(self, update):
        return None


A, S1, S2, B = place("A", 0, 0), place("S1", 0, 1), place("S2", 0, 2), place("B", 0, 3)


def test_given_order_is_kept_and_totals_are_summed():
    engine = FakeEngine()
    result = query_multi(engine, A, B, [S2, S1], "given", "standard")
    assert engine.calls == [("A", "S2"), ("S2", "S1"), ("S1", "B")]
    trip = result[0]
    assert [p.id for p in trip.waypoints] == ["A", "S2", "S1", "B"]
    assert trip.durationMin == 30
    assert trip.arrival == "10:30"
    assert trip.distanceM == pytest.approx(2400)
    assert len(trip.legs) == 3


def test_legs_that_end_at_a_stop_are_numbered():
    trip = query_multi(FakeEngine(), A, B, [S1, S2], "given", "standard")[0]
    assert [leg.stop for leg in trip.legs] == [1, 2, None]


def test_optimal_order_reorders_the_stops():
    # S2 lies before S1 on the way from A to B
    engine = FakeEngine()
    trip = query_multi(engine, A, B, [S2, S1], "optimal", "standard")[0]
    assert [p.id for p in trip.waypoints] == ["A", "S1", "S2", "B"]
    assert engine.calls == [("A", "S1"), ("S1", "S2"), ("S2", "B")]


def test_start_and_destination_never_move():
    trip = query_multi(FakeEngine(), A, B, [S2, S1], "optimal", "standard")[0]
    assert trip.waypoints[0].id == "A" and trip.waypoints[-1].id == "B"


def test_nth_best_options_are_chained_and_the_count_is_limited():
    table = {
        ("A", "S1"): [option("a1", 5), option("a2", 8), option("a3", 11), option("a4", 14)],
        ("S1", "B"): [option("b1", 6), option("b2", 9)],
    }
    result = query_multi(FakeEngine(table), A, B, [S1], "given", "standard")
    assert [o.durationMin for o in result] == [11, 17, 20]  # 5+6, 8+9, 11+9 (the last option is reused)
    assert len(result) <= 3


def test_a_segment_without_connections_gives_no_trip():
    table = {("S1", "B"): []}
    assert query_multi(FakeEngine(table), A, B, [S1], "given", "standard") == []


def test_tags_fastest_cheapest_and_most_active():
    table = {
        ("A", "S1"): [option("a1", 5, cost=4.4, calories=0), option("a2", 9, cost=0, calories=300)],
        ("S1", "B"): [option("b1", 5, cost=4.4, calories=0), option("b2", 9, cost=0, calories=300)],
    }
    result = query_multi(FakeEngine(table), A, B, [S1], "given", "standard")
    assert result[0].tags == ["Najszybsza"]
    assert "Najtańsza" in result[1].tags


def test_combine_titles_are_unique_and_short():
    segs = [option("1", 5, title="Metro"), option("2", 5, title="Metro"), option("3", 5, title="Tramwaj")]
    assert combine(0, segs, [A, S1, S2, B]).title == "Metro → Tramwaj"


def test_request_accepts_up_to_five_stops_and_rejects_more():
    stops = [place(f"S{i}", 0, i) for i in range(5)]
    req = RouteRequest.model_validate({"from": A, "to": B, "via": stops})
    assert req.order == "given" and len(req.via) == 5
    with pytest.raises(ValidationError):
        RouteRequest.model_validate({"from": A, "to": B, "via": [*stops, S2]})


def test_request_without_stops_is_unchanged():
    req = RouteRequest.model_validate({"from": A, "to": B})
    assert req.via == [] and req.order == "given"
