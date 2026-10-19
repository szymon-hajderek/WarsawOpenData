"""The router's timetable file (TTB1, timetable.bin): trips as calls at StationLocations indexes.

Written by backend/preprocess_transit.py, read by algorithms/router/transit.hpp. Format: algorithms/router/README.md
("Timetable file"). Little-endian; a string is a uint32 byte length + UTF-8 bytes.
"""
import struct
from pathlib import Path

import numpy as np

MAGIC, VERSION = b"TTB1", 1


def _str(f, s: str) -> None:
    b = s.encode("utf-8")
    f.write(struct.pack("<I", len(b)))
    f.write(b)


def write(f, stations_hash: str, n_locations: int, routes: list[tuple[str, str, str]], services: list[list],
          trip_route, trip_service, trip_ids: list[str], headsigns: list[str], trip_offset, call_loc, call_arr,
          call_dep) -> None:
    """Write TTB1 into the open binary file f. routes: (route id, line, mode); services: YYYYMMDD dates each;
    trip_* one entry per trip; trip_offset (trips + 1): the calls of trip t are call_*[trip_offset[t]:trip_offset[t+1]].
    Times are seconds after midnight of the service day (may pass 24 h)."""
    f.write(MAGIC)
    f.write(struct.pack("<I", VERSION))
    _str(f, stations_hash)
    f.write(struct.pack("<I", n_locations))
    f.write(struct.pack("<I", len(routes)))
    for rid, line, mode in routes:
        _str(f, rid), _str(f, line), _str(f, mode)
    f.write(struct.pack("<I", len(services)))
    for dates in services:
        d = np.array(sorted(int(x) for x in dates), dtype="<u4")
        f.write(struct.pack("<I", len(d)))
        f.write(d.tobytes())
    f.write(struct.pack("<I", len(trip_ids)))
    for arr, dtype in ((trip_route, "<u4"), (trip_service, "<u4"), (trip_offset, "<u4")):
        f.write(np.asarray(arr, dtype=dtype).tobytes())
    for tid, head in zip(trip_ids, headsigns):
        _str(f, tid), _str(f, head)
    f.write(struct.pack("<I", len(call_loc)))
    for arr, dtype in ((call_loc, "<u4"), (call_arr, "<i4"), (call_dep, "<i4")):
        f.write(np.asarray(arr, dtype=dtype).tobytes())


def pack(trips: list[dict]) -> dict:
    """Trips as dicts {route, service, id, headsign, calls: [(loc, arr, dep)]} -> the trip / call arguments of
    write()."""
    offset = np.r_[0, np.cumsum([len(t["calls"]) for t in trips])].astype(np.int64)
    calls = [c for t in trips for c in t["calls"]]
    return {"trip_route": [t["route"] for t in trips], "trip_service": [t["service"] for t in trips],
            "trip_ids": [t["id"] for t in trips], "headsigns": [t["headsign"] for t in trips],
            "trip_offset": offset, "call_loc": [c[0] for c in calls], "call_arr": [c[1] for c in calls],
            "call_dep": [c[2] for c in calls]}


def header_hash(path: Path) -> str | None:
    """The stations hash a timetable file was written for (None: no file / not TTB1)."""
    try:
        with open(path, "rb") as f:
            if f.read(4) != MAGIC or struct.unpack("<I", f.read(4))[0] != VERSION:
                return None
            n = struct.unpack("<I", f.read(4))[0]
            return f.read(n).decode("utf-8")
    except (OSError, struct.error):
        return None
