"""Geometry helpers, ported from `frontend/src/utils/geo.ts` and `format.ts`.

Used by the stub engine to produce plausible route geometry until the real
C++ routing service provides it.
"""
import math
from datetime import datetime

from ..models import LatLng

EARTH_RADIUS_M = 6371000


def _to_rad(deg: float) -> float:
    return deg * math.pi / 180


def haversine(a: LatLng, b: LatLng) -> float:
    d_lat = _to_rad(b[0] - a[0])
    d_lng = _to_rad(b[1] - a[1])
    h = (
        math.sin(d_lat / 2) ** 2
        + math.cos(_to_rad(a[0])) * math.cos(_to_rad(b[0])) * math.sin(d_lng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _lerp(a: LatLng, b: LatLng, t: float) -> LatLng:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def build_path(a: LatLng, b: LatLng, bend: float, phase: float, points: int = 48) -> list[LatLng]:
    """Street-like curve between two points (placeholder geometry)."""
    d_lat = b[0] - a[0]
    d_lng = b[1] - a[1]
    k = math.cos(_to_rad(a[0]))
    path: list[LatLng] = []
    for i in range(points + 1):
        t = i / points
        amp = bend * math.sin(math.pi * t) * (1 + 0.4 * math.sin(4 * math.pi * t + phase))
        base = _lerp(a, b, t)
        path.append((base[0] + amp * d_lng * k, base[1] - (amp * d_lat) / k))
    return path


def slice_path(path: list[LatLng], frm: float, to: float) -> list[LatLng]:
    """Part of a path between two fractions (0..1) of its total length."""
    cum = [0.0]
    for i in range(1, len(path)):
        cum.append(cum[i - 1] + haversine(path[i - 1], path[i]))
    total = cum[-1]

    def at(d: float) -> LatLng:
        i = 1
        while i < len(cum) - 1 and cum[i] < d:
            i += 1
        seg = (cum[i] - cum[i - 1]) or 1
        return _lerp(path[i - 1], path[i], (d - cum[i - 1]) / seg)

    d0 = frm * total
    d1 = to * total
    out: list[LatLng] = [at(d0)]
    for i in range(len(path)):
        if d0 < cum[i] < d1:
            out.append(path[i])
    out.append(at(d1))
    return out


def round_half_up(value: float) -> int:
    """Match JavaScript's `Math.round` for non-negative values (ties go up)."""
    return math.floor(value + 0.5)


def format_time(dt: datetime) -> str:
    """HH:MM, like the frontend's `formatTime` (pl-PL, 24h)."""
    return dt.strftime("%H:%M")
