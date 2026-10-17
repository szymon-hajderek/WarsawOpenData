"""Stub routing engine.

Ported 1:1 from the frontend mock (`frontend/src/api/routes.ts`) so the full
app works end-to-end before the C++ engine exists. Costs and speeds are rough
estimates. Replace this with `CppRouteEngine` once the real engine is ready;
nothing else in the backend or frontend needs to change.
"""
from datetime import datetime, timedelta
from typing import Any, Optional, TypedDict

from ..models import Place, Profile, RouteLeg, RouteOption, TransportMode
from .engine import RouteEngine
from .geo import build_path, format_time, haversine, round_half_up, slice_path


class _TemplateLeg(TypedDict):
    mode: TransportMode
    share: float  # share of the total distance (shares of one template sum to 1)


class _Template(TypedDict):
    id: str
    title: str
    legs: list[_TemplateLeg]
    bend: float
    minDistanceM: float
    maxDistanceM: Optional[float]


TEMPLATES: list[_Template] = [
    {
        "id": "bike",
        "title": "Veturilo",
        "legs": [
            {"mode": "walk", "share": 0.04},
            {"mode": "bike", "share": 0.92},
            {"mode": "walk", "share": 0.04},
        ],
        "bend": 0.06,
        "minDistanceM": 1200,
        "maxDistanceM": 15000,
    },
    {
        "id": "metro-bike",
        "title": "Metro + Veturilo",
        "legs": [
            {"mode": "walk", "share": 0.05},
            {"mode": "metro", "share": 0.6},
            {"mode": "bike", "share": 0.3},
            {"mode": "walk", "share": 0.05},
        ],
        "bend": 0.03,
        "minDistanceM": 3000,
        "maxDistanceM": None,
    },
    {
        "id": "bike-bus",
        "title": "Veturilo + autobus",
        "legs": [
            {"mode": "bike", "share": 0.25},
            {"mode": "bus", "share": 0.7},
            {"mode": "walk", "share": 0.05},
        ],
        "bend": 0.09,
        "minDistanceM": 2500,
        "maxDistanceM": None,
    },
    {
        "id": "tram",
        "title": "Tramwaj",
        "legs": [
            {"mode": "walk", "share": 0.06},
            {"mode": "tram", "share": 0.88},
            {"mode": "walk", "share": 0.06},
        ],
        "bend": -0.07,
        "minDistanceM": 1500,
        "maxDistanceM": None,
    },
    {
        "id": "metro",
        "title": "Metro",
        "legs": [
            {"mode": "walk", "share": 0.06},
            {"mode": "metro", "share": 0.88},
            {"mode": "walk", "share": 0.06},
        ],
        "bend": 0.02,
        "minDistanceM": 2500,
        "maxDistanceM": None,
    },
    {
        "id": "rail-bike",
        "title": "SKM + Veturilo",
        "legs": [
            {"mode": "walk", "share": 0.04},
            {"mode": "rail", "share": 0.72},
            {"mode": "bike", "share": 0.2},
            {"mode": "walk", "share": 0.04},
        ],
        "bend": -0.04,
        "minDistanceM": 6000,
        "maxDistanceM": None,
    },
    {
        "id": "walk",
        "title": "Pieszo",
        "legs": [{"mode": "walk", "share": 1}],
        "bend": 0.03,
        "minDistanceM": 0,
        "maxDistanceM": 3500,
    },
]

# Speeds in km/h. Public transport speeds include stops.
WALK_BIKE_SPEED: dict[Profile, dict[str, float]] = {
    "standard": {"walk": 4.8, "bike": 15},
    "slow": {"walk": 3.4, "bike": 11},
    "accessible": {"walk": 3.6, "bike": 0},  # no Veturilo for a wheelchair / stroller
}
PT_SPEED: dict[str, float] = {"bus": 17, "tram": 19, "metro": 32, "rail": 38}
PT_WAIT_MIN = 4
BIKE_UNLOCK_MIN = 1
DETOUR_FACTOR = 1.25  # straight line -> real street network

KCAL_PER_KM = {"walk": 55, "bike": 32}
TICKET_PLN = 4.4  # estimate: 20-minute ticket
VETURILO_FREE_MIN = 20

LINES: dict[str, list[str]] = {
    "bus": ["175", "186", "523"],
    "tram": ["17", "18", "25", "33"],
    "metro": ["M1", "M2"],
    "rail": ["S1", "S2", "S3"],
}
STOP_NAME: dict[TransportMode, str] = {
    "walk": "",
    "bike": "Stacja Veturilo",
    "bus": "Przystanek autobusowy",
    "tram": "Przystanek tramwajowy",
    "metro": "Stacja metra",
    "rail": "Stacja SKM",
}


def _node_name(a: TransportMode, b: TransportMode) -> str:
    """Name of the point where one leg meets the next (the non-walking mode wins)."""
    return STOP_NAME[a if a != "walk" else b]


def _build_option(
    template: _Template,
    frm: Place,
    to: Place,
    profile: Profile,
    distance_m: float,
    seed: int,
    departure: datetime,
) -> RouteOption:
    speeds = WALK_BIKE_SPEED[profile]
    master = build_path(frm.position, to.position, template["bend"], seed % 7)
    total_m = distance_m * DETOUR_FACTOR

    cursor = 0.0
    pt_boarded = False
    template_legs = template["legs"]
    legs: list[RouteLeg] = []
    for i, tl in enumerate(template_legs):
        start = cursor
        cursor += tl["share"]
        dist_m = total_m * tl["share"]
        lines = LINES.get(tl["mode"])
        line = lines[(seed + i) % len(lines)] if lines else None

        if tl["mode"] == "walk":
            minutes = (dist_m / 1000 / speeds["walk"]) * 60
        elif tl["mode"] == "bike":
            minutes = (dist_m / 1000 / speeds["bike"]) * 60 + BIKE_UNLOCK_MIN
        else:
            minutes = (dist_m / 1000 / PT_SPEED.get(tl["mode"], 20)) * 60 + (
                2 if pt_boarded else PT_WAIT_MIN
            )
            pt_boarded = True

        prev = template_legs[i - 1] if i > 0 else None
        nxt = template_legs[i + 1] if i < len(template_legs) - 1 else None
        legs.append(
            RouteLeg(
                mode=tl["mode"],
                from_=_node_name(prev["mode"], tl["mode"]) if prev else frm.label,
                to=_node_name(tl["mode"], nxt["mode"]) if nxt else to.label,
                line=line,
                durationMin=max(1, round_half_up(minutes)),
                distanceM=dist_m,
                path=slice_path(master, start, min(1.0, cursor)),
            )
        )

    duration_min = sum(leg.durationMin for leg in legs)
    bike_min = sum(leg.durationMin for leg in legs if leg.mode == "bike")
    uses_pt = any(leg.mode in PT_SPEED for leg in legs)
    calories = round_half_up(
        sum(
            (leg.distanceM / 1000) * KCAL_PER_KM["walk"]
            if leg.mode == "walk"
            else (leg.distanceM / 1000) * KCAL_PER_KM["bike"]
            if leg.mode == "bike"
            else 0
            for leg in legs
        )
    )
    non_walk = sum(1 for leg in legs if leg.mode != "walk")
    arrival = departure + timedelta(minutes=duration_min)

    return RouteOption(
        id=template["id"],
        title=template["title"],
        legs=legs,
        departure=format_time(departure),
        arrival=format_time(arrival),
        durationMin=duration_min,
        distanceM=total_m,
        calories=calories,
        transfers=max(0, non_walk - 1),
        costPln=(TICKET_PLN if uses_pt else 0) + (1 if bike_min > VETURILO_FREE_MIN else 0),
        tags=[],
    )


class StubRouteEngine(RouteEngine):
    """Local mock engine (no C++, no database)."""

    def update_state(self, update: dict[str, Any]) -> None:
        # The stub has no live state to update.
        return None

    def query_routes(self, frm: Place, to: Place, profile: Profile, when: str | None = None) -> list[RouteOption]:
        distance_m = haversine(frm.position, to.position)
        seed = abs(round_half_up((frm.position[0] + to.position[1]) * 1000))
        departure = datetime.now() + timedelta(minutes=2)

        options: list[RouteOption] = [
            _build_option(t, frm, to, profile, distance_m, seed, departure)
            for t in TEMPLATES
            if distance_m >= t["minDistanceM"]
            and (t["maxDistanceM"] is None or distance_m <= t["maxDistanceM"])
            and not (profile == "accessible" and any(leg["mode"] == "bike" for leg in t["legs"]))
        ]

        options.sort(key=lambda o: o.durationMin)
        if not options:
            return options

        options[0].tags.append("Najszybsza")
        min_cost = min(o.costPln for o in options)
        cheapest = [o for o in options if o.costPln == min_cost]
        if len(cheapest) == 1 and len(options) > 1:
            cheapest[0].tags.append("Najtańsza")
        most_active = max(options, key=lambda o: o.calories)
        if most_active.calories > 0 and len(options) > 1 and len(most_active.tags) < 2:
            most_active.tags.append("Najaktywniejsza")
        return options
