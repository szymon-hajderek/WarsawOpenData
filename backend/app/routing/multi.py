"""Trips with intermediate stops, built on top of any `RouteEngine`.

The engine answers "from A to B". A trip A -> S1 -> S2 -> B is asked as one query per segment; the
n-th best option of every segment is chained into the n-th option of the trip. The stops are kept in
the given order or reordered for the shortest trip (start and destination stay fixed).

Simplifications (also written in `changes/feature-multi-stop-trips.md`): every segment is planned
as if it started now, there is no time spent at a stop, and the order is chosen by straight-line distance.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import Optional

from config import REPO, haversine_m

sys.path.insert(0, str(REPO / "algorithms"))
from stop_order import best_order  # noqa: E402

from ..models import Place, Profile, RouteLeg, RouteOption
from .engine import RouteEngine

# How many ranked options of the trip are returned.
MAX_OPTIONS = 3


def _distance(a: Place, b: Place) -> float:
    return haversine_m(a.position[0], a.position[1], b.position[0], b.position[1])


def _add_minutes(hhmm: str, minutes: int) -> str:
    t = datetime.strptime(hhmm, "%H:%M") + timedelta(minutes=minutes)
    return t.strftime("%H:%M")


def _title(segments: list[RouteOption]) -> str:
    titles: list[str] = []
    for seg in segments:
        if seg.title not in titles:
            titles.append(seg.title)
    return " → ".join(titles[:3]) + ("…" if len(titles) > 3 else "")


def combine(index: int, segments: list[RouteOption], waypoints: list[Place]) -> RouteOption:
    """One trip option from one option per segment (in trip order)."""
    legs: list[RouteLeg] = []
    for k, seg in enumerate(segments):
        seg_legs = [leg.model_copy(deep=True) for leg in seg.legs]
        if k < len(segments) - 1 and seg_legs:
            seg_legs[-1].stop = k + 1  # this leg ends at the (k+1)-th intermediate stop
        legs.extend(seg_legs)

    duration = sum(seg.durationMin for seg in segments)
    departure = segments[0].departure
    return RouteOption(
        id=f"multi-{index}",
        title=_title(segments),
        legs=legs,
        departure=departure,
        arrival=_add_minutes(departure, duration),
        durationMin=duration,
        distanceM=sum(seg.distanceM for seg in segments),
        calories=sum(seg.calories for seg in segments),
        transfers=sum(seg.transfers for seg in segments),
        costPln=round(sum(seg.costPln for seg in segments), 2),
        tags=[],
        waypoints=waypoints,
    )


def _tag(options: list[RouteOption]) -> None:
    if not options:
        return
    options[0].tags.append("Najszybsza")  # options are sorted by duration
    if len(options) > 1:
        min_cost = min(o.costPln for o in options)
        cheapest = [o for o in options if o.costPln == min_cost]
        if len(cheapest) == 1:
            cheapest[0].tags.append("Najtańsza")
        most_active = max(options, key=lambda o: o.calories)
        if most_active.calories > 0 and len(most_active.tags) < 2:
            most_active.tags.append("Najaktywniejsza")


def query_multi(
    engine: RouteEngine,
    frm: Place,
    to: Place,
    via: list[Place],
    order: str,
    profile: Profile,
    max_options: int = MAX_OPTIONS,
) -> list[RouteOption]:
    """Options for a trip `frm -> via... -> to`. Empty when some segment has no connection."""
    stops = best_order(frm, via, to, _distance) if order == "optimal" else list(via)
    points = [frm, *stops, to]

    per_segment: list[list[RouteOption]] = []
    for a, b in zip(points, points[1:]):
        options = sorted(engine.query_routes(a, b, profile), key=lambda o: o.durationMin)
        if not options:
            return []
        per_segment.append(options)

    count = min(max_options, max(len(options) for options in per_segment))
    result: list[RouteOption] = []
    seen: set[tuple[str, ...]] = set()
    for i in range(count):
        # the i-th best option of each segment (the last one when a segment has fewer)
        chosen = [options[min(i, len(options) - 1)] for options in per_segment]
        key = tuple(o.id for o in chosen)
        if key in seen:
            continue
        seen.add(key)
        result.append(combine(len(result), chosen, points))

    result.sort(key=lambda o: o.durationMin)
    _tag(result)
    return result
