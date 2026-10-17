"""Nearest public journey anchor, without retaining the user's GPS coordinates."""
import math


def nearest_anchor(position, anchors):
    """Return (id, lat, lon); equal distances use the lexicographically first ID."""
    if not anchors:
        raise ValueError("no journey anchors")
    lat, lon = map(math.radians, position)

    def rank(anchor):
        other_lat, other_lon = map(math.radians, anchor[1:])
        # Haversine's monotonic part is sufficient to compare geographic distances.
        distance = (math.sin((other_lat - lat) / 2) ** 2
                    + math.cos(lat) * math.cos(other_lat) * math.sin((other_lon - lon) / 2) ** 2)
        return distance, anchor[0]

    return min(anchors, key=rank)
