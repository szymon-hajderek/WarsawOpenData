"""Ticket price from the ZTM fare table and the Veturilo price brackets.

Pure functions. The fare rows come from GTFS (`fare_attributes.txt` + `fare_rules.txt`);
the bike brackets follow the Veturilo GBFS pricing plans.
"""
from __future__ import annotations

import math


def open_fare(fares: list[dict], seconds: int) -> float | None:
    """Cheapest feed-wide fare (no zone and no route limit) that covers `seconds`.

    An empty `duration_s` means the ticket does not expire. Used for WKD, whose
    GTFS fare file has a price and a transfer duration but no zones.
    """
    best = None
    for fare in fares:
        if fare.get("routes") or fare.get("zones"):
            continue
        duration = fare.get("duration_s")
        if duration is not None and seconds > duration:
            continue
        price = float(fare["price"])
        if best is None or price < best:
            best = price
    return best


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


def veturilo_from_brackets(minutes: float, brackets: list[dict]) -> float:
    """Price from a GBFS ``per_min_pricing`` list.

    A step with ``interval`` 0 adds ``rate`` once when the rental passes ``start``
    (the standard plan's steps add up to the totals in the plan name, including 272 zł
    after 12 h). A step with a positive ``interval`` adds ``rate`` for every interval
    that the rental spends after ``start``.
    """
    minutes = max(0.0, minutes)
    price = 0.0
    for step in sorted(brackets, key=lambda item: item["start"]):
        start = float(step["start"])
        if minutes <= start:
            break
        interval = int(step.get("interval") or 0)
        rate = float(step["rate"])
        if interval:
            end = step.get("end")
            span_end = minutes if end is None else min(minutes, float(end))
            if span_end > start:
                price += math.ceil((span_end - start) / interval) * rate
        else:
            price += rate
    return price


def brackets_for(plans: list[dict], electric: bool) -> list[dict] | None:
    """The standard plan (20 min free, then 1 zł) or the e-bike plan (14 zł/h after 1 h)."""
    if electric:
        for plan in plans:
            for step in plan.get("per_min_pricing") or []:
                if step.get("interval") and float(step.get("rate") or 0) >= 10:
                    return plan["per_min_pricing"]
        return None
    for plan in plans:
        steps = plan.get("per_min_pricing") or []
        if any(step.get("start") == 20 and step.get("rate") == 1 for step in steps):
            return steps
    return None


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
