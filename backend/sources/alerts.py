"""Live ZTM alerts from the mkuran GTFS-Realtime JSON mirror. Failure leaves the set empty."""
import httpx

from config import TTLCache

URL = "https://mkuran.pl/gtfs/warsaw/alerts.json"
_cache = TTLCache(60)


def alerted_lines() -> set[str]:
    """Line short names mentioned in the current alerts (diversions, closures)."""
    try:
        body = _cache.get("alerts", lambda: httpx.get(URL, timeout=8).json())
    except Exception:
        return set()
    lines = set()
    for alert in body.get("alerts") or []:
        lines.update(str(line) for line in alert.get("routes") or [])
    return lines
