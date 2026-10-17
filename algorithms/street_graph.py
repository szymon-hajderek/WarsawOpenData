"""The street graph handed to the C++ program, and its file format (SMG2).

Format and meaning: algorithms/router/preprocess/README.md ("Graph file").
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class StreetGraph:
    """A directed graph: street nodes first, then a virtual out node and in node for each point."""

    # one entry per edge
    src: np.ndarray
    dst: np.ndarray
    cost: np.ndarray    # s: length / speed + wait, what Dijkstra minimises
    length: np.ndarray  # m
    wait: np.ndarray    # s
    flags: np.ndarray   # street_model.FLAG_*
    # one entry per node
    lon: np.ndarray
    lat: np.ndarray
    # one entry per point
    out_node: np.ndarray
    in_node: np.ndarray
    active: np.ndarray  # the point is on the graph; otherwise its row and column are NaN

    @property
    def nodes(self) -> int:
        return len(self.lon)

    def save(self, path: Path) -> None:
        order = np.argsort(self.src, kind="stable")
        offset = np.r_[0, np.cumsum(np.bincount(self.src, minlength=self.nodes))]
        with open(path, "wb") as f:
            f.write(b"SMG2")
            np.array([self.nodes, len(self.src), len(self.out_node)], dtype="<u4").tofile(f)
            for arr, dtype in ((offset, "<u4"), (self.dst[order], "<u4"), (self.cost[order], "<f8"),
                               (self.length[order], "<f4"), (self.wait[order], "<f4"), (self.flags[order], "u1"),
                               (self.out_node, "<u4"), (self.in_node, "<u4"), (self.active, "u1"),
                               (self.lon, "<f4"), (self.lat, "<f4")):
                np.asarray(arr).astype(dtype).tofile(f)
