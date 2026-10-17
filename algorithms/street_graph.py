"""The street graph handed to the C++ router, and its file format (SMG4).

Format and meaning: algorithms/router/README.md ("Graph file").
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class StreetGraph:
    """A directed graph: street nodes first, then a virtual out node and in node for each fixed point.
    The router computes an edge's cost as walk / walk speed + bike / bike speed + wait."""

    # the mode's default speeds (m/s) and how a coordinate joins the graph
    walk_speed: float
    bike_speed: float
    access_k: int          # up to this many nearest usable nodes ...
    access_extra_m: float  # ... at most this much farther than the nearest one
    max_snap_m: float      # no route when the nearest usable node is farther
    # one entry per edge
    src: np.ndarray
    dst: np.ndarray
    walk: np.ndarray    # m walked (also a pushed bike, access segments, metro stairs)
    bike: np.ndarray    # m ridden
    wait: np.ndarray    # s that do not scale with speed (signals, crossings, elevators)
    flags: np.ndarray   # street_model.FLAG_*
    # one entry per node
    lon: np.ndarray
    lat: np.ndarray
    usable: np.ndarray      # a coordinate may join the graph here (the mode's main component)
    entry_wait: np.ndarray  # s paid when the graph is entered at this node (street_model.entry_wait)
    # one entry per fixed point (stops, Veturilo stations; used by the matrix run)
    out_node: np.ndarray
    in_node: np.ndarray
    active: np.ndarray  # the point is on the graph; otherwise its row and column are NaN

    @property
    def nodes(self) -> int:
        return len(self.lon)

    def cost(self) -> np.ndarray:
        """Edge cost (s) with the default speeds."""
        return self.walk / self.walk_speed + self.bike / self.bike_speed + self.wait

    def save(self, path: Path) -> None:
        order = np.argsort(self.src, kind="stable")
        offset = np.r_[0, np.cumsum(np.bincount(self.src, minlength=self.nodes))]
        with open(path, "wb") as f:
            f.write(b"SMG4")
            np.array([self.nodes, len(self.src), len(self.out_node), self.access_k], dtype="<u4").tofile(f)
            np.array([self.walk_speed, self.bike_speed, self.access_extra_m, self.max_snap_m], dtype="<f4").tofile(f)
            for arr, dtype in ((offset, "<u4"), (self.dst[order], "<u4"), (self.walk[order], "<f4"),
                               (self.bike[order], "<f4"), (self.wait[order], "<f4"), (self.flags[order], "u1"),
                               (self.out_node, "<u4"), (self.in_node, "<u4"), (self.active, "u1"),
                               (self.lon, "<f8"), (self.lat, "<f8"), (self.usable, "u1"),
                               (self.entry_wait, "<f4")):
                np.asarray(arr).astype(dtype).tofile(f)
