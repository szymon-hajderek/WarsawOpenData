"""Ticket price from the ZTM fare table and the Veturilo price brackets.

Pure functions. The fare rows come from GTFS (`fare_attributes.txt` + `fare_rules.txt`);
the bike brackets follow the Veturilo GBFS pricing plans.
"""
from __future__ import annotations

import math


def cheapest_fare(fares: list[dict], zones: set[str], seconds: int, route_ids: set[str]) -> float | None:
    """Cheapest fare that covers these zones, this ride time and these route ids.

    A fare with `routes` applies only to those routes (local L lines, no transfers).
    A fare with `zones` must contain every zone the ride touches.
    `duration_s` is the maximum time the ticket stays valid. `None` when no fare matches.
    """
    best = None
    for fare in fares:
        routes = fare.get("routes") or set()
        if routes and (not route_ids or not route_ids <= routes):
            continue
        if fare.get("transfers") == 0 and len(route_ids) != 1:
            continue
        fare_zones = fare.get("zones") or set()
        if fare_zones and not zones <= fare_zones:
            continue
        if not routes and not fare_zones:
            continue
        duration = fare.get("duration_s")
        if duration is not None and seconds > duration:
            continue
        price = float(fare["price"])
        if best is None or price < best:
            best = price
    return best


def veturilo_pln(minutes: float, electric: bool) -> float:
    """Price of one Veturilo rental. Brackets are the totals from the GBFS plan names (July 2026)."""
    minutes = max(0.0, minutes)
    if electric:
        if minutes <= 20:
            return 0.0
        if minutes <= 60:
            return 6.0
        if minutes <= 720:
            extra_hours = math.ceil((minutes - 60) / 60)
            return 6.0 + 14.0 * extra_hours
        return 300.0
    if minutes <= 20:
        return 0.0
    if minutes <= 60:
        return 1.0
    if minutes <= 120:
        return 4.0
    if minutes <= 180:
        return 9.0
    if minutes <= 720:
        extra_hours = math.ceil((minutes - 180) / 60)
        return 9.0 + 7.0 * extra_hours
    return 272.0
