"""Cut a real transit polyline at ordered stops when a feed omits shape distances."""
import numpy as np


def slice_shape_by_stops(shape, stops) -> list[list[float]]:
    """Project stops forwards along [lat, lon] vertices, keeping every intervening bend."""
    if len(shape) < 2 or len(stops) < 2:
        return []
    points = np.asarray(shape, dtype=float)
    scale = np.array([1.0, np.cos(np.radians(points[:, 0].mean()))])
    xy = (points - points[0]) * scale
    edge = np.diff(xy, axis=0)
    length2 = (edge * edge).sum(axis=1)
    indices = np.arange(len(edge))
    cursor = 0.0
    projections = []
    for stop in stops:
        target = (np.asarray(stop) - points[0]) * scale
        fraction = np.divide(((target - xy[:-1]) * edge).sum(axis=1), length2,
                             out=np.zeros(len(edge)), where=length2 > 0)
        fraction = np.clip(fraction, 0, 1)
        # A repeated stop on a loop must not jump backwards to the first occurrence.
        fraction = np.maximum(fraction, np.clip(cursor - indices, 0, 1))
        distance2 = ((xy[:-1] + fraction[:, None] * edge - target) ** 2).sum(axis=1)
        distance2[indices + fraction < cursor] = np.inf
        i = int(np.argmin(distance2))
        cursor = i + float(fraction[i])
        projections.append((cursor, points[i] + fraction[i] * (points[i + 1] - points[i])))
    begin, first = projections[0]
    end, last = projections[-1]
    if end <= begin:
        return []
    path = [first, *points[int(np.floor(begin)) + 1:int(np.ceil(end))], last]
    result = []
    for point in path:
        rounded = [round(float(v), 6) for v in point]
        if not result or result[-1] != rounded:
            result.append(rounded)
    return result
