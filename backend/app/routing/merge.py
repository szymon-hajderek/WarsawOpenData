"""Joins neighbouring street legs of the same kind into one.

The router splits a trip at every station it passes: a ride that ends at one post of a stop and the walk to the
next post of the same stop (a short transfer) come as two legs, and the street walk to the destination as a third.
For the person on the street that is one walk. `merge_street_legs` joins such neighbours without changing anything
else: the same points in the same order, the same distances and minutes (the sums of the parts) and the same
elevators, steps and segments.
"""
from __future__ import annotations

from ..models import RouteLeg

# Only these join. Rented bikes (`veturilo`) stay apart: a second rental is a different ride, not the same one.
MERGEABLE = ("walk", "bike")


def _can_join(a: RouteLeg, b: RouteLeg) -> bool:
    # A leg that ends at an intermediate stop of the trip is a boundary the person sees.
    return a.mode == b.mode and a.mode in MERGEABLE and a.stop is None


def _plus(a, b):
    return None if a is None and b is None else [*(a or []), *(b or [])]


def _join(a: RouteLeg, b: RouteLeg) -> RouteLeg:
    # The two paths meet at one point: it is kept once. If they do not meet exactly, both points stay (nothing is moved).
    path = [*a.path, *(b.path[1:] if a.path and b.path and tuple(a.path[-1]) == tuple(b.path[0]) else b.path)]
    merged = a.model_copy(
        update={
            "to": b.to,
            "durationMin": a.durationMin + b.durationMin,
            "distanceM": round(a.distanceM + b.distanceM, 1),
            "path": path,
            "end": b.end,
            "toId": b.toId,
            "stop": b.stop,
            "approximatePath": a.approximatePath or b.approximatePath,
            "segments": [*a.segments, *b.segments],
            "elevators": _plus(a.elevators, b.elevators),
            "steps": _plus(a.steps, b.steps),
        },
        deep=True,
    )
    # Totals of the option (walked / ridden metres, waits) are read from these.
    if a._street_distances is not None or b._street_distances is not None:
        aw, ab = a._street_distances or (0.0, 0.0)
        bw, bb = b._street_distances or (0.0, 0.0)
        merged._street_distances = (aw + bw, ab + bb)
    merged._street_wait = a._street_wait + b._street_wait
    return merged


def merge_street_legs(legs: list[RouteLeg]) -> list[RouteLeg]:
    """`legs` with every run of neighbouring walk legs (and of neighbouring own-bike legs) joined into one leg."""
    out: list[RouteLeg] = []
    for leg in legs:
        if out and _can_join(out[-1], leg):
            out[-1] = _join(out[-1], leg)
        else:
            out.append(leg)
    return out
