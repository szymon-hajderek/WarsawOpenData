"""Rough boxes for the Warsaw districts the preferences screen can exclude.

A stop inside a box, or inside a user point's radius, is treated as blocked.
Boxes overlap at the borders on purpose: this is a filter, not a cadastre.
"""
from __future__ import annotations

# (min_lat, max_lat, min_lon, max_lon)
BOXES: dict[str, tuple[float, float, float, float]] = {
    "Bemowo": (52.220, 52.270, 20.870, 20.940),
    "Białołęka": (52.300, 52.400, 20.950, 21.100),
    "Bielany": (52.260, 52.310, 20.900, 20.980),
    "Mokotów": (52.165, 52.215, 20.970, 21.080),
    "Ochota": (52.190, 52.225, 20.950, 21.000),
    "Praga-Południe": (52.210, 52.255, 21.040, 21.120),
    "Praga-Północ": (52.250, 52.285, 21.010, 21.060),
    "Rembertów": (52.250, 52.290, 21.120, 21.200),
    "Śródmieście": (52.215, 52.250, 20.990, 21.045),
    "Targówek": (52.270, 52.320, 21.000, 21.100),
    "Ursus": (52.180, 52.210, 20.860, 20.920),
    "Ursynów": (52.120, 52.165, 20.980, 21.080),
    "Wawer": (52.150, 52.230, 21.100, 21.250),
    "Wesoła": (52.200, 52.250, 21.180, 21.280),
    "Wilanów": (52.140, 52.180, 21.050, 21.130),
    "Włochy": (52.180, 52.220, 20.900, 20.970),
    "Wola": (52.215, 52.255, 20.920, 20.990),
    "Żoliborz": (52.255, 52.285, 20.960, 21.010),
}


def in_district(lat: float, lon: float, name: str) -> bool:
    box = BOXES.get(name)
    if box is None:
        return False
    return box[0] <= lat <= box[1] and box[2] <= lon <= box[3]


def blocked(lat: float, lon: float, districts: list[str], points: list[tuple[float, float, float]],
            distance) -> bool:
    """True when the point sits in an excluded district or inside an excluded circle.

    `points` are `(lat, lon, radius_m)`. `distance(a, b)` is metres between two lat/lon pairs.
    """
    if any(in_district(lat, lon, name) for name in districts):
        return True
    for plat, plon, radius in points:
        if distance((lat, lon), (plat, plon)) <= radius:
            return True
    return False
