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


def track_mse(user_points: list[dict], bus_points: list[dict]) -> float:
    """Mean of squared distances (m^2). Each user point is paired with the bus point closest in time."""
    total = 0.0
    for u in user_points:
        b = min(bus_points, key=lambda p: abs(p["t"] - u["t"]))
        total += haversine_m(u["lat"], u["lon"], b["lat"], b["lon"]) ** 2
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
