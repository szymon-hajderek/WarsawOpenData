"""Which bus is the user on? Rank buses by the MSE between the user's track and each bus track.

Pure functions, no I/O. A point is a dict {"lat", "lon", "t"} with "t" in epoch seconds.
"""
import math

EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


EXTRAPOLATE_MAX_S = 30.0  # how far past its last feed point a vehicle is moved along its last movement


def position_at(bus_points: list[dict], t: float) -> tuple[float, float]:
    """Where the vehicle was at time `t`: interpolated between its points (oldest first); after the last one moved on
    along the last movement for at most EXTRAPOLATE_MAX_S (the feed lags the phone by ~10-20 s); before the first one
    its first point."""
    first, last = bus_points[0], bus_points[-1]
    if t <= first["t"] or len(bus_points) == 1:
        p = first if t <= first["t"] else last
        return p["lat"], p["lon"]
    for a, b in zip(bus_points, bus_points[1:]):
        if a["t"] <= t <= b["t"]:
            f = (t - a["t"]) / ((b["t"] - a["t"]) or 1.0)
            return a["lat"] + f * (b["lat"] - a["lat"]), a["lon"] + f * (b["lon"] - a["lon"])
    a, b = bus_points[-2], last
    dt = (b["t"] - a["t"]) or 1.0
    ahead = min(t - b["t"], EXTRAPOLATE_MAX_S)
    return b["lat"] + (b["lat"] - a["lat"]) / dt * ahead, b["lon"] + (b["lon"] - a["lon"]) / dt * ahead


def track_mse(user_points: list[dict], bus_points: list[dict]) -> float:
    """Mean of squared distances (m^2) between each user point and the vehicle's position at that point's time."""
    total = 0.0
    for u in user_points:
        lat, lon = position_at(bus_points, u["t"])
        total += haversine_m(u["lat"], u["lon"], lat, lon) ** 2
    return total / len(user_points)


def rank_buses(user_points: list[dict], bus_history: dict[str, list[dict]], limit: int = 4) -> list[dict]:
    """The `limit` vehicles with the lowest MSE, best first: [{"id", "mse_m2", "rmse_m"}].

    `bus_history` maps a vehicle id to its last positions. Vehicles without positions are skipped.
    """
    if not user_points:
        return []
    scored = [(track_mse(user_points, pts), vid) for vid, pts in bus_history.items() if pts]
    scored.sort()
    return [{"id": vid, "mse_m2": mse, "rmse_m": math.sqrt(mse)} for mse, vid in scored[:limit]]
