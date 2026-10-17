"""Picks the route engine from `ROUTE_ENGINE` (default `real`).

The integration tests in `integration/` run against whatever engine this returns. When a new
pathfinding engine (the C++ `CppRouteEngine`) is added, register it here and run the whole integration
suite with `ROUTE_ENGINE=<name>` before it replaces `real` (see `integration/README.md`).
"""
import os

from .engine import RouteEngine


def make_engine(name: str | None = None) -> RouteEngine:
    name = (name or os.getenv("ROUTE_ENGINE") or "real").strip().lower()
    if name == "real":
        from .real_engine import RealRouteEngine
        return RealRouteEngine()
    if name == "stub":
        from .stub_engine import StubRouteEngine
        return StubRouteEngine()
    raise ValueError(f"unknown ROUTE_ENGINE {name!r} (known: real, stub)")
