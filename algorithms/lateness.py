"""How late a live vehicle is, compared with the timetable along its trip."""


def lateness_s(calls: list[dict], point: tuple[float, float], now_sec: int, distance, cap_s: int = 1200) -> int:
    """Seconds the vehicle is behind schedule.

    The scheduled stop is the last call that should already have been left.
    If the vehicle is still closer to an earlier stop, it has not got there yet.
    A vehicle at or ahead of the scheduled stop counts as on time.
    """
    scheduled = None
    for index, call in enumerate(calls):
        if call["dep"] <= now_sec:
            scheduled = index
    if scheduled is None:
        return 0
    nearest = min(range(len(calls)), key=lambda i: distance(point, (calls[i]["lat"], calls[i]["lon"])))
    if nearest >= scheduled:
        return 0
    late = now_sec - int(calls[nearest]["dep"])
    return int(max(0, min(late, cap_s)))
