"""GTFS shape_dist_traveled for Warsaw is in kilometers. Some other feeds use meters."""


def shape_meters(value) -> int:
    """Meters along a shape. ``None`` and junk become -1.

    A number up to 200 is kilometers (a Warsaw trip is shorter than that).
    A larger number is already meters.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return -1
    if number < 0:
        return -1
    if number <= 200:
        return int(round(number * 1000))
    return int(round(number))
