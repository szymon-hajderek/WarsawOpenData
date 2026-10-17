"""Where to put a new Veturilo station: hex grid + the J_synergy cost (pure functions).

    J(p) = -alpha * T(p) * (1 + delta * E(p)) + beta * P(d_net(p)) + gamma * S(p)
    P(d) = (1 - d / R)^2 for d < R, else 0

T = car traffic 0..1, E = e-scooter trip density 0..1, S = infrastructure safety 0 (bike path) .. 1
(multi-lane road without one), d_net = network distance (m) to the nearest station. Lower J is better.

Coordinates are local metres (config.to_xy). Hexes are pointy-top, axial coordinates (q, r),
`size` = circumradius (centre to corner).
"""
from __future__ import annotations

import math
from typing import Callable

import numpy as np
from scipy.spatial import cKDTree

HEX_SIZE_M = 175.0
DEFAULTS = {"alpha": 1.0, "beta": 1.0, "gamma": 0.5, "delta": 0.5, "r": 1000.0}

SQRT3 = math.sqrt(3.0)


def hex_center(q, r, size: float = HEX_SIZE_M):
    """Centre (x, y) of axial hex (q, r)."""
    q, r = np.asarray(q, dtype=float), np.asarray(r, dtype=float)
    return size * SQRT3 * (q + r / 2), size * 1.5 * r


def hex_of(x, y, size: float = HEX_SIZE_M):
    """Axial (q, r) of the hex that contains each point (cube rounding)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    fq = (SQRT3 / 3 * x - y / 3) / size
    fr = (2 / 3 * y) / size
    fs = -fq - fr
    q, r, s = np.round(fq), np.round(fr), np.round(fs)
    dq, dr, ds = np.abs(q - fq), np.abs(r - fr), np.abs(s - fs)
    fix_q = (dq > dr) & (dq > ds)
    fix_r = ~fix_q & (dr > ds)
    q = np.where(fix_q, -r - s, q)
    r = np.where(fix_r, -q - s, r)
    return q.astype(np.int64), r.astype(np.int64)


def hex_grid(xmin: float, ymin: float, xmax: float, ymax: float, size: float = HEX_SIZE_M):
    """All hexes whose centre lies in the box: (q, r, x, y) arrays."""
    r_lo, r_hi = math.floor(ymin / (1.5 * size)), math.ceil(ymax / (1.5 * size))
    qs, rs = [], []
    for r in range(r_lo, r_hi + 1):
        q_lo = math.floor(xmin / (SQRT3 * size) - r / 2)
        q_hi = math.ceil(xmax / (SQRT3 * size) - r / 2)
        qs.extend(range(q_lo, q_hi + 1))
        rs.extend([r] * (q_hi - q_lo + 1))
    q, r = np.array(qs, dtype=np.int64), np.array(rs, dtype=np.int64)
    x, y = hex_center(q, r, size)
    keep = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
    return q[keep], r[keep], x[keep], y[keep]


def points_in_rings(x, y, rings: list[np.ndarray]) -> np.ndarray:
    """Even-odd rule over all rings (outer rings and holes of a (multi)polygon). Each ring: (k, 2) array."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    inside = np.zeros(x.shape, dtype=bool)
    for ring in rings:
        ax, ay = ring[:, 0], ring[:, 1]
        bx, by = np.roll(ax, -1), np.roll(ay, -1)
        for x1, y1, x2, y2 in zip(ax, ay, bx, by):
            if y1 == y2:
                continue
            crosses = (y1 > y) != (y2 > y)
            xc = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            inside ^= crosses & (x < xc)
    return inside


def penalty(d, r: float):
    """P(d) = (1 - d/R)^2 for d < R, else 0. d = inf gives 0."""
    d = np.asarray(d, dtype=float)
    return np.where(d < r, (1 - np.minimum(d, r) / r) ** 2, 0.0)


def cost(t, e, s, d_net, alpha: float, beta: float, gamma: float, delta: float, r: float):
    """J_synergy for arrays of hexes."""
    return -alpha * np.asarray(t) * (1 + delta * np.asarray(e)) + beta * penalty(d_net, r) + gamma * np.asarray(s)


def mean_per_hex(index, values, n: int):
    """Mean of `values` per hex index (-1 = outside every hex): (mean with NaN where empty, count)."""
    index, values = np.asarray(index), np.asarray(values, dtype=float)
    ok = index >= 0
    count = np.bincount(index[ok], minlength=n)
    total = np.bincount(index[ok], weights=values[ok], minlength=n)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0, total / np.maximum(count, 1), np.nan), count


def weighted_mean_per_hex(index, values, weights, n: int):
    """Weighted mean per hex (S: weights = segment length); NaN where a hex has no weight."""
    index, values, weights = np.asarray(index), np.asarray(values, dtype=float), np.asarray(weights, dtype=float)
    ok = index >= 0
    w = np.bincount(index[ok], weights=weights[ok], minlength=n)
    total = np.bincount(index[ok], weights=(values * weights)[ok], minlength=n)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(w > 0, total / np.where(w > 0, w, 1), np.nan)


def idw_fill(x, y, values, k: int = 6, power: float = 2.0):
    """Fill NaN entries by inverse distance weighting from the k nearest known entries."""
    values = np.asarray(values, dtype=float).copy()
    known = ~np.isnan(values)
    if known.all() or not known.any():
        return values
    pts = np.c_[x, y]
    tree = cKDTree(pts[known])
    kk = min(k, int(known.sum()))
    dist, idx = tree.query(pts[~known], k=kk)
    dist, idx = dist.reshape(len(dist), kk), idx.reshape(len(idx), kk)
    w = 1.0 / np.maximum(dist, 1.0) ** power
    values[~known] = (w * values[known][idx]).sum(axis=1) / w.sum(axis=1)
    return values


def normalize(values, pct: float = 99.0):
    """Scale to 0..1: 0 = min, 1 = the pct-th percentile (larger values clipped)."""
    values = np.asarray(values, dtype=float)
    lo, hi = np.nanmin(values), np.nanpercentile(values, pct)
    if hi <= lo:
        return np.zeros_like(values)
    return np.clip((values - lo) / (hi - lo), 0.0, 1.0)


def greedy(t, e, s, d_net, candidate, n: int, distances_from: Callable[[int], np.ndarray], params: dict):
    """Pick n hexes one by one. After each pick a station is placed there: d_net = min(d_net, distances_from(pick)),
    so the next pick is not next door. Returns a list of steps {pick, j (at pick time), d_net (after the pick)}."""
    p = {**DEFAULTS, **params}
    d = np.asarray(d_net, dtype=float).copy()
    cand = np.asarray(candidate, dtype=bool).copy()
    steps = []
    for _ in range(n):
        if not cand.any():
            break
        j = cost(t, e, s, d, p["alpha"], p["beta"], p["gamma"], p["delta"], p["r"])
        pick = int(np.argmin(np.where(cand, j, np.inf)))
        j_pick = float(j[pick])
        d_before = float(d[pick])
        d = np.minimum(d, distances_from(pick))
        d[pick] = 0.0
        cand[pick] = False
        steps.append({"pick": pick, "j": j_pick, "d_net": d_before, "d_after": d.copy()})
    return steps
