"""Order of the intermediate stops of a trip.

Pure function, no I/O: `best_order` reorders the stops between a fixed start and a fixed
destination so that the whole path is as short as possible. It tries every permutation, so it
is exact; the limit keeps it fast (7 stops = 5040 permutations).
"""
from itertools import permutations
from typing import Callable, Sequence, TypeVar

T = TypeVar("T")

MAX_STOPS = 7


def path_length(points: Sequence[T], dist: Callable[[T, T], float]) -> float:
    """Total length of the path through `points` in the given order."""
    return sum(dist(a, b) for a, b in zip(points, points[1:]))


def best_order(start: T, stops: Sequence[T], end: T, dist: Callable[[T, T], float]) -> list[T]:
    """The stops in the order that gives the shortest path `start -> stops -> end`.

    Start and end stay where they are. Ties keep the given order (the identity permutation is tried
    first and only a strictly shorter path replaces it).
    """
    if len(stops) > MAX_STOPS:
        raise ValueError(f"at most {MAX_STOPS} intermediate stops are supported")
    if len(stops) < 2:
        return list(stops)

    best = list(stops)
    best_len = path_length([start, *best, end], dist)
    for perm in permutations(stops):
        length = path_length([start, *perm, end], dist)
        if length < best_len - 1e-9:
            best, best_len = list(perm), length
    return best
