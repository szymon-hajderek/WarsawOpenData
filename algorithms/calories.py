"""Net calories of a walked or cycled route, from the same tables the app uses.

Public-transport legs count as rest. An electric wheelchair burns nothing on a
walk. Flat ground: slope, load, bike type and wind are not in the model.
"""
from __future__ import annotations

WALK_MET = ((2.7, 2.3), (3.2, 2.8), (4.0, 3.0), (4.8, 3.5), (5.6, 4.3), (6.4, 5.0), (7.2, 7.0), (8.0, 8.3))
BIKE_MET = ((8.0, 3.5), (12.0, 4.0), (16.0, 5.5), (19.0, 6.8), (22.0, 8.0), (25.0, 10.0), (30.0, 12.0))
WHEELCHAIR_MET = ((2.0, 1.8), (3.6, 2.8), (5.0, 3.8), (6.5, 5.0))

DEFAULTS = {"weightKg": 70.0, "heightCm": 170.0, "age": 35.0}


def _met(table, kmh: float) -> float:
    if kmh <= table[0][0]:
        return table[0][1]
    for (x1, y1), (x0, y0) in zip(table[1:], table):
        if kmh <= x1:
            return y0 + (y1 - y0) * (kmh - x0) / (x1 - x0)
    return table[-1][1]


def resting_kcal_per_day(body: dict | None) -> float:
    """Mifflin-St Jeor. An unknown sex uses the mean of the two formulas."""
    body = body or {}
    weight = float(body.get("weightKg") or DEFAULTS["weightKg"])
    height = float(body.get("heightCm") or DEFAULTS["heightCm"])
    age = float(body.get("age") or DEFAULTS["age"])
    base = 10 * weight + 6.25 * height - 5 * age
    sex = body.get("sex")
    return base + (5 if sex == "male" else -161 if sex == "female" else -78)


def net_kcal(legs: list, walk_kmh: float, bike_kmh: float, body: dict | None = None,
             wheelchair: str = "none") -> int:
    """Net kcal above resting. `legs` need `mode` and `distanceM`."""
    weight = float((body or {}).get("weightKg") or DEFAULTS["weightKg"])
    rest_per_hour = resting_kcal_per_day(body) / 24
    total = 0.0
    for leg in legs:
        mode = leg.mode if hasattr(leg, "mode") else leg["mode"]
        distance = leg.distanceM if hasattr(leg, "distanceM") else leg["distanceM"]
        if mode == "walk" and wheelchair == "electric":
            continue
        if mode == "walk":
            kmh = walk_kmh
            table = WHEELCHAIR_MET if wheelchair == "manual" else WALK_MET
        elif mode == "bike":
            kmh = bike_kmh or 13.0
            table = BIKE_MET
        else:
            continue
        if kmh <= 0:
            continue
        hours = (distance / 1000) / kmh
        total += max(0.0, _met(table, kmh) * weight - rest_per_hour) * hours
    return int(round(total))
